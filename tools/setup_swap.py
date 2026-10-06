#!/usr/bin/env python3
"""Add RAM-sized disk swap using Omarchy's Btrfs layout. Preview by default."""
import argparse
import fcntl
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import time

SWAP_DIR = Path("/swap")
SWAP_FILE = SWAP_DIR / "swapfile"
FSTAB = Path("/etc/fstab")
GIB = 1024**3


def command(*args):
    return subprocess.check_output([str(a) for a in args], text=True).strip()


def ram_bytes(text):
    for line in text.splitlines():
        fields = line.split()
        if fields and fields[0] == "MemTotal:" and len(fields) == 3 and fields[2] == "kB":
            size = int(fields[1]) * 1024
            if size > 0:
                return size
    raise RuntimeError("Cannot determine RAM from /proc/meminfo")


def ram_size(text):
    size = ram_bytes(text)
    return ((size + GIB - 1) // GIB) * GIB


def fstab_update(text):
    entries = [line.split("#", 1)[0].split() for line in text.splitlines()]
    matches = [row for row in entries if row and row[0] == str(SWAP_FILE)]
    if matches:
        if len(matches) != 1 or len(matches[0]) < 4 or matches[0][2] != "swap":
            raise RuntimeError("Conflicting /swap/swapfile entry in /etc/fstab")
        options = matches[0][3].split(",")
        if "pri=0" not in options or any(o in options for o in ["noauto", "nofail"]) or any(
                o.startswith("pri=") and o != "pri=0" for o in options):
            raise RuntimeError("Existing swap entry has different activation/priority options; review it first")
        return text
    return text.rstrip("\n") + f"\n\n# RAM-sized disk swap (zram remains preferred)\n{SWAP_FILE} none swap defaults,pri=0 0 0\n"


def persist(text):
    original = FSTAB.read_text()
    if text == original:
        return
    backup = FSTAB.with_name(f"fstab.distroconf-{time.time_ns()}.bak")
    shutil.copy2(FSTAB, backup)
    metadata = FSTAB.stat()
    fd, name = tempfile.mkstemp(prefix=".fstab.distroconf-", dir=FSTAB.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
            os.fchmod(stream.fileno(), stat.S_IMODE(metadata.st_mode))
            os.fchown(stream.fileno(), metadata.st_uid, metadata.st_gid)
        os.replace(name, FSTAB)
    finally:
        Path(name).unlink(missing_ok=True)
    print(f"Updated {FSTAB}; backup: {backup}")


def setup(apply):
    memory = Path("/proc/meminfo").read_text()
    size = ram_size(memory)
    for tool in ["btrfs", "findmnt", "swapon", "swaplabel", "chattr", "systemctl"]:
        if not shutil.which(tool):
            raise RuntimeError(f"Missing dependency: {tool}")
    if command("findmnt", "-n", "-o", "FSTYPE", "-T", "/") != "btrfs":
        raise RuntimeError("This setup requires Omarchy's Btrfs root filesystem")
    if any(p.is_symlink() for p in [SWAP_DIR, SWAP_FILE, FSTAB]):
        raise RuntimeError("Refusing symlinked swap paths or fstab")
    text = fstab_update(FSTAB.read_text())  # Validate before making changes.
    existing = SWAP_FILE.exists()
    if existing and (not SWAP_FILE.is_file() or SWAP_FILE.stat().st_size < ram_bytes(memory)):
        raise RuntimeError("Existing swapfile is invalid or smaller than RAM; no automatic resize is performed")
    if SWAP_DIR.exists():
        command("btrfs", "subvolume", "show", SWAP_DIR)
    if existing:
        command("swaplabel", SWAP_FILE)
        command("btrfs", "inspect-internal", "map-swapfile", SWAP_FILE)
    print(f"RAM-sized disk swap: {size // GIB} GiB at {SWAP_FILE}, priority 0")
    if not existing and shutil.disk_usage(SWAP_DIR if SWAP_DIR.exists() else Path("/")).free < size + GIB:
        raise RuntimeError("Insufficient free space: swap size plus 1 GiB reserve is required")
    if not apply:
        print("Preview only. Run sudo ./setup-swap.sh --apply to create, activate, and persist swap.")
        return
    if not SWAP_DIR.exists():
        command("btrfs", "subvolume", "create", SWAP_DIR)
        command("chattr", "+C", SWAP_DIR)
    if not existing:
        command("btrfs", "filesystem", "mkswapfile", "--size", str(size), SWAP_FILE)
    SWAP_FILE.chmod(0o600)
    command("btrfs", "inspect-internal", "map-swapfile", SWAP_FILE)
    active = command("swapon", "--show=NAME,PRIO", "--noheadings", "--raw")
    rows = [r.split() for r in active.splitlines()]
    match = next((r for r in rows if r and r[0] == str(SWAP_FILE)), None)
    if match and match[1] != "0":
        raise RuntimeError("Swapfile is active at another priority; no swapoff is performed")
    if not match:
        command("swapon", "--priority", "0", SWAP_FILE)
    persist(text)
    command("systemctl", "daemon-reload")
    print(command("swapon", "--show"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="create and activate swap; requires sudo")
    args = parser.parse_args()
    try:
        if args.apply:
            if os.geteuid() != 0:
                raise RuntimeError("Run --apply with sudo")
            with open("/run/distroconf-swap.lock", "w") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                setup(True)
        else:
            setup(False)
    except (RuntimeError, ValueError, OSError, subprocess.SubprocessError) as error:
        print(f"setup-swap: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
