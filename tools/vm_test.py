#!/usr/bin/env python3
"""Local, disposable Omarchy VM runner. Never executes bootstrap on the host."""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import re
from pathlib import Path
import secrets
import shlex
import shutil
import socket
import subprocess
import sys
import time

REPO = Path(__file__).resolve().parents[1]
USER = "omarchy"


def run(args, **kwargs):
    return subprocess.run([str(x) for x in args], check=True, **kwargs)


def file_list(repo):
    data = run(["git", "-C", repo, "ls-files", "-z", "--cached", "--others",
                "--exclude-standard"], stdout=subprocess.PIPE).stdout
    return b"\0".join(name for name in data.split(b"\0") if name and
                       (repo / os.fsdecode(name)).exists()) + b"\0"


def verify_iso(path):
    sidecar = Path(str(path) + ".sha256")
    if not sidecar.is_file():
        raise RuntimeError(f"Missing checksum: {sidecar}")
    expected = sidecar.read_text().split()[0].lower()
    if len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
        raise RuntimeError("Invalid SHA256 sidecar")
    with path.open("rb") as stream:
        actual = hashlib.file_digest(stream, "sha256").hexdigest()
    if actual != expected:
        raise RuntimeError("ISO checksum mismatch")
    return actual


def install_config():
    mib, gib = 1024**2, 1024**3
    def partition(start, size, filesystem, **extra):
        return dict(btrfs=[], dev_path=None, flags=[], fs_type=filesystem,
                    mount_options=[], mountpoint=None, obj_id=secrets.token_hex(16),
                    size=dict(sector_size=dict(unit="B", value=512), unit="B", value=size),
                    start=dict(sector_size=dict(unit="B", value=512), unit="B", value=start),
                    status="create", type="primary", **extra)
    esp = partition(mib, 2*gib, "fat32")
    esp.update(flags=["boot", "esp"], mountpoint="/boot")
    root = partition(2*gib+mib, 60*gib-2*gib-2*mib, "btrfs")
    root.update(mount_options=["compress=zstd"], btrfs=[
        dict(mountpoint=p, name=n) for p, n in
        [("/", "@"), ("/home", "@home"), ("/var/log", "@log"),
         ("/var/cache/pacman/pkg", "@pkg")]])
    return {
        "app_config": None, "archinstall-language": "English", "auth_config": {},
        "audio_config": {"audio": "pipewire"},
        "bootloader_config": {"bootloader": "Limine", "uki": False, "removable": False},
        "custom_commands": [],
        "omarchy_install": {"mode": "full_disk", "defer_provisioning": False,
                            "target_mount": "/mnt", "boot": {
                                "esp_mount": "/boot", "esp_path": "/EFI/limine",
                                "efi_binary": "limine_x64.efi", "enable_fallback": True},
                            "storage": {"kernel": "linux-omarchy"}},
        "disk_config": {"config_type": "default_layout", "device_modifications": [
            {"device": "/dev/vda", "partitions": [esp, root], "wipe": True}]},
        "hostname": "distroconf-test", "kernels": ["linux-omarchy"],
        "network_config": {"type": "iso"}, "ntp": True, "parallel_downloads": 8,
        "script": None, "services": [], "swap": True, "timezone": "America/Toronto",
        "locale_config": {"kb_layout": "us", "sys_enc": "UTF-8", "sys_lang": "en_US.UTF-8"},
        "mirror_config": {"custom_repositories": [], "custom_servers": [
            {"url": u} for u in ["https://mirror.omarchy.org/$repo/os/$arch",
                                 "https://geo.mirror.pkgbuild.com/$repo/os/$arch"]],
                          "mirror_regions": {}, "optional_repositories": []},
        "packages": ["base-devel", "git", "omarchy-keyring", "omarchy-settings", "omarchy"],
        "profile_config": {"gfx_driver": None, "greeter": None, "profile": {}},
        "version": "3.0.9"}


class VM:
    def __init__(self, args):
        self.args = args
        self.state = args.state_dir.expanduser().resolve()
        if self.state.is_relative_to(REPO):
            raise RuntimeError("VM state must live outside the repository")
        self.state.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.lock = (self.state / "lock").open("w")
        if args.command != "status":
            try:
                fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError("Another vm-test command is running") from None
        self.meta_path = self.state / "active.json"
        self.meta = json.loads(self.meta_path.read_text()) if self.meta_path.exists() else None
        self.key = self.state / "id_ed25519"
        baseline = self.state / "baseline.json"
        saved_port = json.loads(baseline.read_text()).get("port", args.port) if baseline.exists() else args.port
        self.port = self.meta["port"] if self.meta else saved_port
        self.artifacts = None

    def running(self):
        if not self.meta:
            return False
        # Check QEMU's command line as well as PID, avoiding PID-reuse accidents.
        try:
            cmd = Path(f"/proc/{self.meta['pid']}/cmdline").read_bytes().split(b"\0")
            return Path(os.fsdecode(cmd[0])).name == "qemu-system-x86_64" and any(os.fsencode(self.meta["disk"]) in c for c in cmd)
        except (OSError, KeyError):
            return False

    def prerequisites(self):
        for name in ["qemu-system-x86_64", "qemu-img", "ssh", "ssh-keygen", "rsync", "git", "openssl"]:
            if not shutil.which(name):
                raise RuntimeError(f"Missing dependency: {name}")
        if not os.access("/dev/kvm", os.R_OK | os.W_OK):
            raise RuntimeError("/dev/kvm is unavailable; enable AMD-V/VT-x and check KVM permissions")
        for path in [self.args.ovmf_code, self.args.ovmf_vars]:
            if not path.is_file():
                raise RuntimeError(f"Missing UEFI firmware: {path}")
        if shutil.disk_usage(self.state).free < 15 * 1024**3:
            raise RuntimeError("At least 15 GiB free storage is required")

    def ssh_args(self):
        return ["ssh", "-F", "/dev/null", "-i", self.key, "-p", str(self.meta["port"]),
                "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes", "-o", "ForwardAgent=no",
                "-o", "StrictHostKeyChecking=no" if self.meta.get("installing") else "StrictHostKeyChecking=accept-new", "-o",
                "UserKnownHostsFile=/dev/null" if self.meta.get("installing") else f"UserKnownHostsFile={self.state / 'known_hosts'}", "-o", "ConnectTimeout=5",
                "-o", "ServerAliveInterval=10", "-o", "ServerAliveCountMax=3",
                f"{USER}@127.0.0.1"]

    def ssh(self, command, **kwargs):
        return run(self.ssh_args() + [command], **kwargs)

    def qmp(self, command, arguments=None):
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(5)
            client.connect(self.meta["qmp"])
            stream = client.makefile("rwb")
            stream.readline()
            for request in [{"execute": "qmp_capabilities"},
                            {"execute": command, "arguments": arguments or {}}]:
                stream.write(json.dumps(request).encode() + b"\n")
                stream.flush()
                while True:
                    response = json.loads(stream.readline())
                    if "error" in response:
                        raise RuntimeError(str(response["error"]))
                    if "return" in response:
                        break
            return response["return"]

    def wait_ssh(self, timeout=600):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if not self.running():
                raise RuntimeError("QEMU exited; inspect qemu.log")
            try:
                self.ssh("true", stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
                return
            except (subprocess.SubprocessError, OSError):
                time.sleep(3)
        raise RuntimeError("Timed out waiting for guest SSH; check the console and ISO installer compatibility")

    def stop(self):
        if not self.running():
            return
        with contextlib.suppress(Exception):
            self.ssh("sudo -n systemctl poweroff", timeout=15)
        with contextlib.suppress(Exception):
            self.qmp("system_powerdown")
        end = time.monotonic() + 90
        while self.running() and time.monotonic() < end:
            time.sleep(1)
        if self.running():
            raise RuntimeError("Guest did not shut down cleanly; leaving it intact")
        socket_path = Path(self.meta["qmp"])
        with contextlib.suppress(OSError):
            socket_path.unlink(missing_ok=True)
            socket_path.parent.rmdir()

    def launch(self, disk, firmware, directory, iso=None, seed=None):
        self.prerequisites()
        if self.running():
            raise RuntimeError("VM already running")
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", self.port))
        # Short private socket path, independent of long state-directory names.
        socket_dir = Path(__import__("tempfile").mkdtemp(prefix="distroconf-qmp-"))
        qmp = socket_dir / "qmp"
        args = ["qemu-system-x86_64", "-name", "distroconf-test", "-machine", "q35,accel=kvm",
                "-cpu", "host", "-smp", "4", "-m", "8192",
                "-drive", f"if=pflash,format=raw,readonly=on,file={self.args.ovmf_code}",
                "-drive", f"if=pflash,format=raw,file={firmware}",
                "-blockdev", json.dumps({"driver": "qcow2", "node-name": "disk",
                    "file": {"driver": "file", "filename": str(disk)}}),
                "-device", "virtio-blk-pci,drive=disk,bootindex=1",
                "-device", "virtio-vga-gl", "-display", "gtk,gl=on",
                "-device", "qemu-xhci", "-device", "usb-tablet",
                "-netdev", f"user,id=net,hostfwd=tcp:127.0.0.1:{self.port}-:22",
                "-device", "virtio-net-pci,netdev=net", "-qmp", f"unix:{qmp},server=on,wait=off",
                "-serial", f"file:{directory / 'serial.log'}"]
        for name, path in [("installer", iso), ("seed", seed)]:
            if path:
                args += ["-blockdev", json.dumps({"driver": "raw", "node-name": name,
                    "read-only": True, "file": {"driver": "file", "filename": str(path)}}),
                    "-device", f"ide-cd,drive={name},bootindex=2" if name == "installer" else f"usb-storage,drive={name}"]
        log = (directory / "qemu.log").open("ab")
        process = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                   start_new_session=True)
        self.meta = dict(pid=process.pid, disk=str(disk), firmware=str(firmware),
                         directory=str(directory), qmp=str(qmp), port=self.port,
                         installing=bool(iso))
        pending = self.meta_path.with_suffix(".pending")
        pending.write_text(json.dumps(self.meta, indent=2))
        pending.replace(self.meta_path)
        time.sleep(2)
        if not self.running():
            raise RuntimeError(f"QEMU failed to start: {directory / 'qemu.log'}")

    def init(self, iso):
        if (self.state / "base.qcow2").exists():
            raise RuntimeError("Baseline already exists; use a new --state-dir to rebuild")
        self.prerequisites()
        if not iso:
            raise RuntimeError("First run requires init --iso PATH (or test --iso PATH)")
        iso = iso.resolve()
        if not iso.is_file():
            raise RuntimeError(f"ISO not found: {iso}")
        checksum = verify_iso(iso)
        # This unattended layout targets stable Omarchy 4.x, not old/dev ISO formats.
        if not re.fullmatch(r"omarchy-4\.\d+(?:\.\d+)?\.iso", iso.name):
            raise RuntimeError("Supported installer: official stable omarchy-4.x ISO")
        if not shutil.which("genisoimage"):
            raise RuntimeError("Missing dependency: genisoimage (cdrtools)")
        directory = self.new_artifacts("install")
        seed_dir = directory / "cidata"
        seed_dir.mkdir()
        if not self.key.exists():
            run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", self.key])
        password = secrets.token_urlsafe(24)
        (self.state / "guest-password").write_text(password)
        hashed = run(["openssl", "passwd", "-6", "-stdin"], input=password,
                     text=True, stdout=subprocess.PIPE).stdout.strip()
        credentials = {"root_enc_password": hashed, "users": [{"enc_password": hashed,
                        "groups": [], "sudo": True, "username": USER}]}
        (seed_dir / "user_credentials.json").write_text(json.dumps(credentials))
        (seed_dir / "user_configuration.json").write_text(json.dumps(install_config()))
        for name, text in {"user_full_name.txt": "Distroconf Test", "user_email_address.txt":
                           "test@example.invalid", "user_encrypt_installation.txt": "false"}.items():
            (seed_dir / name).write_text(text + "\n")
        shutil.copyfile(str(self.key) + ".pub", seed_dir / "authorized_keys")
        seed = directory / "cidata.iso"
        run(["genisoimage", "-quiet", "-output", seed, "-volid", "cidata", "-joliet", "-rock", seed_dir])
        disk, firmware = directory / "install.qcow2", directory / "vars.fd"
        run(["qemu-img", "create", "-f", "qcow2", disk, "60G"])
        shutil.copyfile(self.args.ovmf_vars, firmware)
        self.launch(disk, firmware, directory, iso, seed)
        print("Installing unattended; first boot can take up to 40 minutes.", flush=True)
        self.wait_ssh(2400)
        provision = """set -e
install -d /etc/sudoers.d /etc/sddm.conf.d
printf 'Defaults:omarchy verifypw=never\\nomarchy ALL=(ALL) NOPASSWD: ALL\\n' >/etc/sudoers.d/distroconf-test
chmod 440 /etc/sudoers.d/distroconf-test
visudo -cf /etc/sudoers.d/distroconf-test
printf '[Autologin]\\nUser=omarchy\\nSession=hyprland.desktop\\nRelogin=true\\n' >/etc/sddm.conf.d/zz-distroconf-test.conf
"""
        self.ssh("sudo -S -p '' bash -c " + shlex.quote(provision),
                 input=password + "\n", text=True, timeout=3600)
        self.ssh("sudo -n systemctl restart sddm", timeout=60)
        self.wait_ssh()
        self.ssh("cat > ~/vm-baseline-prepare.py", input=(REPO / "tools/vm_guest.py").read_bytes())
        with (directory / "prepare.log").open("wb") as log:
            self.ssh("python3 ~/vm-baseline-prepare.py prepare", stdout=log,
                     stderr=subprocess.STDOUT, timeout=3600)
        version = self.ssh("cat /etc/os-release; omarchy version", stdout=subprocess.PIPE,
                           text=True, timeout=30).stdout
        (self.state / "baseline.json").write_text(json.dumps(
            dict(iso=str(iso), sha256=checksum, version=version, port=self.port), indent=2))
        (self.state / "known_hosts").unlink(missing_ok=True)
        self.stop()
        shutil.move(disk, self.state / "base.qcow2")
        shutil.copyfile(firmware, self.state / "base-vars.fd")
        (self.state / "base.qcow2").chmod(0o400)
        (self.state / "base-vars.fd").chmod(0o400)
        self.meta = None
        self.meta_path.unlink()
        print("Baseline ready.")

    def new_artifacts(self, label):
        directory = self.state / "runs" / (time.strftime("%Y%m%d-%H%M%S") + "-" + label + "-" + secrets.token_hex(3))
        directory.mkdir(parents=True)
        self.artifacts = directory
        return directory

    def fresh(self):
        self.stop()
        directory = self.new_artifacts("test")
        disk, firmware = directory / "run.qcow2", directory / "vars.fd"
        run(["qemu-img", "create", "-f", "qcow2", "-F", "qcow2", "-b",
             self.state / "base.qcow2", disk])
        shutil.copyfile(self.state / "base-vars.fd", firmware)
        self.launch(disk, firmware, directory)
        self.wait_ssh()

    def sync(self):
        self.ssh("mkdir -p ~/dev/distroconf ~/distroconf-test")
        # No shell expansion of repository names; NUL-delimited list supports spaces.
        ssh_command = shlex.join(str(x) for x in self.ssh_args()[:-1])
        manifest = file_list(REPO)
        run(["rsync", "-rlpt", "--from0", "--files-from=-", "--delete", "-e", ssh_command,
             str(REPO) + "/", f"{USER}@127.0.0.1:dev/distroconf/"], input=manifest)
        # Delete stale guest source files using the exact transferred manifest.
        self.ssh("cat > ~/distroconf-test/files", input=manifest)
        self.ssh("python3 ~/dev/distroconf/tools/vm_guest.py prune", timeout=30)

    def guest(self, operation):
        print(f"Running guest {operation}; logs: {self.artifacts}", flush=True)
        path = self.artifacts / f"{time.time_ns()}-{operation}.log"
        try:
            with path.open("wb") as log:
                self.ssh("python3 ~/dev/distroconf/tools/vm_guest.py " + operation,
                         stdout=log, stderr=subprocess.STDOUT, timeout=3600)
        except subprocess.SubprocessError as error:
            print("\n".join(path.read_text(errors="replace").splitlines()[-20:]), file=sys.stderr)
            raise RuntimeError(f"Guest {operation} failed; full log: {path}") from error

    def execute_test(self, clean):
        if not (self.state / "base.qcow2").exists():
            self.init(self.args.iso)
        if clean or not self.meta:
            self.fresh()
        else:
            if self.meta.get("installing"):
                raise RuntimeError("Incomplete installation; use a new state directory")
            self.artifacts = self.new_artifacts("apply")
            if not self.running():
                self.launch(Path(self.meta["disk"]), Path(self.meta["firmware"]),
                            Path(self.meta["directory"]))
            self.wait_ssh()
        self.sync()
        self.guest("prepare")
        self.guest("bootstrap")
        self.guest("check")
        if clean:
            self.guest("snapshot")
            self.guest("bootstrap")
            self.guest("compare")
            self.guest("check")
            old_boot = self.ssh("cat /proc/sys/kernel/random/boot_id", text=True,
                                stdout=subprocess.PIPE).stdout.strip()
            with contextlib.suppress(subprocess.CalledProcessError):
                self.ssh("sudo -n systemctl reboot", timeout=30)
            deadline = time.monotonic() + 600
            while time.monotonic() < deadline:
                try:
                    new_boot = self.ssh("cat /proc/sys/kernel/random/boot_id", text=True,
                                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=15).stdout.strip()
                    if new_boot != old_boot:
                        break
                except subprocess.SubprocessError:
                    pass
                time.sleep(3)
            else:
                raise RuntimeError("Guest reboot timed out")
            self.wait_ssh()
            self.guest("check")
        self.collect()
        print(f"PASS. VM left running. Logs: {self.artifacts}")

    def collect(self):
        if not self.meta or not self.artifacts:
            return
        with contextlib.suppress(Exception):
            self.ssh("python3 ~/dev/distroconf/tools/vm_guest.py screenshot",
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=200)
            with (self.artifacts / "console.png").open("wb") as screenshot:
                self.ssh("cat ~/distroconf-test/console.png", stdout=screenshot, timeout=30)
        with contextlib.suppress(Exception):
            self.qmp("screendump", {"filename": str(self.artifacts / "console.ppm")})
        with contextlib.suppress(Exception):
            with (self.artifacts / "diagnostics.log").open("wb") as log:
                self.ssh("systemctl --user --failed; journalctl --user -b -n 200 --no-pager; "
                         "cat /etc/os-release; cat ~/distroconf-test/bootstrap*.log", stdout=log,
                         stderr=subprocess.STDOUT, timeout=30)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["init", "test", "apply", "start", "stop", "status", "ssh"])
    parser.add_argument("--iso", type=Path)
    parser.add_argument("--state-dir", type=Path, default=Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "distroconf/vm")
    parser.add_argument("--port", type=int, default=2322)
    parser.add_argument("--ovmf-code", type=Path, default=Path("/usr/share/edk2/x64/OVMF_CODE.4m.fd"))
    parser.add_argument("--ovmf-vars", type=Path, default=Path("/usr/share/edk2/x64/OVMF_VARS.4m.fd"))
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("--port must be between 1024 and 65535")
    os.umask(0o077)
    vm = None
    try:
        vm = VM(args)
        if args.command == "init":
            vm.init(args.iso)
        elif args.command in ("test", "apply"):
            vm.execute_test(args.command == "test")
        elif args.command == "status":
            print(json.dumps(dict(running=vm.running(), baseline=(vm.state / "base.qcow2").exists(), active=vm.meta), indent=2))
        elif args.command == "stop":
            vm.stop()
        elif args.command == "start":
            if not vm.meta:
                if not (vm.state / "base.qcow2").exists():
                    raise RuntimeError("Run init --iso PATH first")
                vm.fresh()
            elif not vm.running():
                if vm.meta.get("installing"):
                    raise RuntimeError("Incomplete install; use a new --state-dir")
                vm.launch(Path(vm.meta["disk"]), Path(vm.meta["firmware"]), Path(vm.meta["directory"]))
        elif args.command == "ssh":
            if not vm.running():
                raise RuntimeError("VM is not running")
            ssh_args = vm.ssh_args()
            run(ssh_args[:-1] + ["-t", ssh_args[-1], "bash -l"])
    except (RuntimeError, OSError, subprocess.SubprocessError, KeyboardInterrupt) as error:
        if vm:
            vm.collect()
        print(f"vm-test: {error}", file=sys.stderr)
        if vm and vm.artifacts:
            print(f"Artifacts: {vm.artifacts}; VM preserved for inspection.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
