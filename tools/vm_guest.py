#!/usr/bin/env python3
"""Guest-only checks and bootstrap execution with the active desktop environment."""
import hashlib
import fcntl
import signal
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HOME = Path.home()
REPO = HOME / "dev/distroconf"
STATE = HOME / "distroconf-test"


def guard():
    if not (Path("/etc/hostname").read_text().strip() == "distroconf-test" and
            HOME.name == "omarchy" and Path("/etc/sudoers.d/distroconf-test").exists()):
        raise RuntimeError("This runner only operates inside the dedicated test guest")


def desktop():
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        for proc in Path("/proc").glob("[0-9]*"):
            try:
                if proc.stat().st_uid != os.getuid():
                    continue
                if proc.joinpath("comm").read_text().strip().lower() != "hyprland":
                    continue
                environment = dict(item.split(b"=", 1) for item in
                                   proc.joinpath("environ").read_bytes().split(b"\0") if b"=" in item)
                os.environ.update({os.fsdecode(k): os.fsdecode(v) for k, v in environment.items()})
                # The instance signature may be set after compositor process launch.
                runtime = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
                instances = subprocess.check_output(["hyprctl", "instances", "-j"], text=True)
                for instance in json.loads(instances):
                    if instance["pid"] == int(proc.name):
                        os.environ["HYPRLAND_INSTANCE_SIGNATURE"] = instance["instance"]
                        os.environ["WAYLAND_DISPLAY"] = instance["wl_socket"]
                        break
                os.environ["XDG_RUNTIME_DIR"] = str(runtime)
                os.environ["DBUS_SESSION_BUS_ADDRESS"] = f"unix:path={runtime}/bus"
                os.environ["XDG_SESSION_TYPE"] = "wayland"
                subprocess.run(["hyprctl", "version"], check=True, stdout=subprocess.DEVNULL)
                return
            except (OSError, ValueError, KeyError, subprocess.SubprocessError):
                continue
        time.sleep(3)
    raise RuntimeError("No usable Hyprland session appeared within 180 seconds")


def managed_paths():
    pairs = [(REPO / "dotfiles" / p.relative_to(REPO / "dotfiles"),
              HOME / p.relative_to(REPO / "dotfiles"))
             for p in (REPO / "dotfiles").rglob("*") if p.is_file()]
    pairs += [(REPO / "init.el", HOME / ".emacs.d/init.el"),
              (REPO / "ssh.config", HOME / ".ssh/config")]
    pairs.append((REPO / "edit", HOME / "bin/edit"))
    return pairs


def fingerprints():
    result = {}
    for source, target in managed_paths():
        result[str(target.relative_to(HOME))] = {
            "link": os.readlink(target) if target.is_symlink() else None,
            "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}
    service = HOME / ".config/systemd/user/emacs.service"
    result["emacs.service"] = hashlib.sha256(service.read_bytes()).hexdigest()
    return result


def manifest(path):
    return [line.split("#", 1)[0].strip() for line in path.read_text().splitlines()
            if line.split("#", 1)[0].strip()]


def checks():
    failures = []
    def check(name, condition):
        print(f"{'PASS' if condition else 'FAIL'}: {name}", flush=True)
        if not condition:
            failures.append(name)
    for source, target in managed_paths():
        if source == REPO / "ssh.config":
            check("SSH config installed privately", target.is_file() and not target.is_symlink()
                  and target.read_bytes() == source.read_bytes()
                  and target.stat().st_mode & 0o777 == 0o600)
        else:
            check(f"link {target}", target.is_symlink() and target.resolve() == source.resolve())
    for target in (HOME / "bin").iterdir():
        if target.is_symlink() and target.resolve().is_relative_to(REPO):
            check(f"repository launcher {target} resolves", target.exists())
    service = HOME / ".config/systemd/user/emacs.service"
    check("Emacs unit installed as regular file", service.is_file() and not service.is_symlink()
          and service.read_bytes() == (REPO / "emacs.service").read_bytes())
    for unit in ["emacs.service", "ssh-agent.socket"]:
        for verb in ["is-enabled", "is-active"]:
            check(f"{unit} {verb}", subprocess.run(["systemctl", "--user", verb, "--quiet", unit]).returncode == 0)
    check("SSH agent socket", Path(os.environ["XDG_RUNTIME_DIR"], "ssh-agent.socket").is_socket())
    errors = subprocess.check_output(["hyprctl", "configerrors"], text=True).strip()
    check("Hyprland configuration", not errors)
    if errors:
        print(errors)
    check("Omarchy shell process", subprocess.run(["pgrep", "-u", str(os.getuid()), "-f", "quickshell"], stdout=subprocess.DEVNULL).returncode == 0)
    for package in manifest(REPO / "packages/arch.txt"):
        check(f"official package {package}", subprocess.run(["pacman", "-Q", package], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0)
    for package in manifest(REPO / "packages/aur.txt"):
        installed = subprocess.run(["pacman", "-Q", package], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
        print(f"{'PASS' if installed else 'WARN'}: optional AUR package {package}")
    for line in (REPO / "plugins/omarchy.tsv").read_text().splitlines():
        if not line or line.startswith("#"):
            continue
        name, _, commit = line.split("\t")
        directory = HOME / ".config/omarchy/plugins" / name
        actual = subprocess.run(["git", "-C", directory, "rev-parse", "HEAD"], text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        check(f"plugin {name} commit", actual.returncode == 0 and actual.stdout.strip() == commit)
        check(f"plugin {name} validation", subprocess.run(["omarchy", "plugin", "validate", directory]).returncode == 0)
    if failures:
        raise RuntimeError(f"{len(failures)} acceptance checks failed")


def main():
    guard()
    STATE.mkdir(exist_ok=True)
    operation = sys.argv[1]
    operation_lock = (STATE / "operation.lock").open("w")
    if operation != "screenshot":
        try:
            fcntl.flock(operation_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another guest test operation is still running") from None
    if operation == "prune":
        allowed = {os.fsdecode(p) for p in (STATE / "files").read_bytes().split(b"\0") if p}
        for path in REPO.rglob("*"):
            if (path.is_file() or path.is_symlink()) and str(path.relative_to(REPO)) not in allowed:
                path.unlink()
        return
    if operation == "prepare":
        # sudo -v otherwise requires a password even with a NOPASSWD command rule.
        policy = "Defaults:omarchy verifypw=never\nomarchy ALL=(ALL) NOPASSWD: ALL\n"
        subprocess.run(["sudo", "-n", "tee", "/etc/sudoers.d/distroconf-test"],
                       input=policy, text=True, stdout=subprocess.DEVNULL, check=True)
        subprocess.run(["sudo", "-n", "chmod", "440", "/etc/sudoers.d/distroconf-test"], check=True)
        subprocess.run(["sudo", "-n", "visudo", "-cf", "/etc/sudoers.d/distroconf-test"], check=True)
        marker = HOME / ".local/state/distroconf-vm-prepared"
        if not marker.exists():
            desktop()
            subprocess.run(["omarchy", "update", "-y"], check=True, timeout=3300)
            subprocess.run(["omarchy", "pkg", "add", "python", "rsync"], check=True, timeout=300)
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.touch()
        return
    desktop()
    if operation == "screenshot":
        subprocess.run(["grim", STATE / "console.png"], check=True, timeout=15)
    elif operation == "bootstrap":
        before = []
        for _, target in managed_paths():
            if target.exists() and not (target.is_symlink() and target.resolve().is_relative_to(REPO)):
                before.append((str(target.relative_to(HOME)), hashlib.sha256(target.read_bytes()).hexdigest()))
        log_path = STATE / ("bootstrap-" + str(time.time_ns()) + ".log")
        process = subprocess.Popen(
            ["bash", "-c", 'set -o pipefail; bash "$1" 2>&1 | tee "$2"',
             "--", str(REPO / "bootstrap.sh"), str(log_path)], cwd=REPO,
            stderr=subprocess.STDOUT, start_new_session=True)
        try:
            status = process.wait(timeout=3300)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            raise RuntimeError("Bootstrap timed out; its process group was stopped") from None
        if status:
            raise RuntimeError(f"Bootstrap exited {status}")
        backups = HOME / ".local/state/distroconf/backups"
        for relative, digest in before:
            if not any(candidate.is_file() and hashlib.sha256(candidate.read_bytes()).hexdigest() == digest
                       for candidate in backups.glob("*/" + relative)):
                raise RuntimeError(f"Missing backup for {relative}")
    elif operation == "check":
        checks()
    elif operation == "snapshot":
        (STATE / "managed.json").write_text(json.dumps(fingerprints(), sort_keys=True))
    elif operation == "compare":
        if json.loads((STATE / "managed.json").read_text()) != fingerprints():
            raise RuntimeError("Second bootstrap changed managed configuration")
        print("PASS: managed configuration stable on rerun")
    else:
        raise RuntimeError(f"Unknown operation: {operation}")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, subprocess.SubprocessError) as error:
        print(f"vm-guest: {error}", file=sys.stderr)
        sys.exit(1)
