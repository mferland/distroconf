import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from types import SimpleNamespace
import os

spec = importlib.util.spec_from_file_location("vm_test", Path(__file__).resolve().parents[1] / "tools/vm_test.py")
vm_test = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vm_test)


class RunnerTests(unittest.TestCase):
    def test_iso_integrity_rejects_corruption(self):
        with tempfile.TemporaryDirectory() as directory:
            iso = Path(directory) / "omarchy-4.0.4.iso"
            iso.write_bytes(b"fixture")
            Path(str(iso) + ".sha256").write_text(hashlib.sha256(b"fixture").hexdigest() + "  fixture.iso\n")
            self.assertEqual(vm_test.verify_iso(iso), hashlib.sha256(b"fixture").hexdigest())
            iso.write_bytes(b"corrupt")
            with self.assertRaisesRegex(RuntimeError, "mismatch"):
                vm_test.verify_iso(iso)

    def test_transfer_includes_edits_new_files_but_not_ignored_or_deleted(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "init", "-q", repo], check=True)
            (repo / ".gitignore").write_text("private/\n")
            (repo / "tracked file").write_text("original")
            (repo / "deleted").write_text("old")
            subprocess.run(["git", "-C", repo, "add", "."], check=True)
            (repo / "tracked file").write_text("uncommitted edit")
            (repo / "deleted").unlink()
            (repo / "new file").write_text("new")
            (repo / "private").mkdir()
            (repo / "private/key").write_text("secret")
            files = vm_test.file_list(repo).split(b"\0")
            self.assertIn(b"tracked file", files)
            self.assertIn(b"new file", files)
            self.assertNotIn(b"deleted", files)
            self.assertNotIn(b"private/key", files)
            self.assertFalse(any(b".git/" in f for f in files))

    def test_disk_layout_only_targets_virtual_disk(self):
        config = vm_test.install_config()
        device, = config["disk_config"]["device_modifications"]
        self.assertEqual(device["device"], "/dev/vda")
        esp, root = device["partitions"]
        self.assertEqual(esp["start"]["value"] + esp["size"]["value"], root["start"]["value"])
        self.assertLess(root["start"]["value"] + root["size"]["value"], 60 * 1024**3)

    def test_pid_reuse_does_not_count_as_our_vm(self):
        vm = object.__new__(vm_test.VM)
        vm.meta = dict(pid=42, disk="/tmp/owned/disk.qcow2")
        with patch.object(Path, "read_bytes", return_value=b"unrelated\0process\0"):
            self.assertFalse(vm.running())
        command = b'qemu-system-x86_64\0-blockdev\0{"filename":"/tmp/owned/disk.qcow2"}\0'
        with patch.object(Path, "read_bytes", return_value=command):
            self.assertTrue(vm.running())

    def test_fresh_disk_and_firmware_do_not_modify_baseline(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            subprocess.run(["qemu-img", "create", "-q", "-f", "qcow2", state / "base.qcow2", "128M"], check=True)
            (state / "base-vars.fd").write_bytes(b"immutable firmware")
            original = (state / "base.qcow2").read_bytes()
            vm = object.__new__(vm_test.VM)
            vm.state = state
            with patch.object(vm, "stop"), patch.object(vm, "launch") as launch, patch.object(vm, "wait_ssh"):
                vm.fresh()
            disk, firmware, _ = launch.call_args.args
            info = json.loads(subprocess.check_output(["qemu-img", "info", "--output=json", disk]))
            self.assertEqual(info["full-backing-filename"], str(state / "base.qcow2"))
            firmware.write_bytes(b"guest changed firmware")
            self.assertEqual((state / "base-vars.fd").read_bytes(), b"immutable firmware")
            self.assertEqual((state / "base.qcow2").read_bytes(), original)

    def test_clean_test_runs_twice_then_checks_a_new_boot(self):
        with tempfile.TemporaryDirectory() as directory:
            vm = object.__new__(vm_test.VM)
            vm.state = Path(directory)
            (vm.state / "base.qcow2").touch()
            vm.artifacts = vm.state
            vm.meta = None
            with patch.object(vm, "fresh") as fresh, patch.object(vm, "sync"), \
                 patch.object(vm, "guest") as guest, patch.object(vm, "collect"), \
                 patch.object(vm, "wait_ssh"), patch.object(vm, "ssh", side_effect=[
                     SimpleNamespace(stdout="old-boot"), SimpleNamespace(stdout=""),
                     SimpleNamespace(stdout="new-boot")]):
                vm.execute_test(True)
            fresh.assert_called_once()
            self.assertEqual([c.args[0] for c in guest.call_args_list],
                             ["prepare", "bootstrap", "check", "snapshot", "bootstrap",
                              "compare", "check", "check"])

    def test_desktop_environment_recovers_wayland_socket(self):
        guest_spec = importlib.util.spec_from_file_location("vm_guest", vm_test.REPO / "tools/vm_guest.py")
        guest = importlib.util.module_from_spec(guest_spec)
        guest_spec.loader.exec_module(guest)
        proc = MagicMock()
        proc.name = "123"
        proc.stat.return_value.st_uid = os.getuid()
        proc.joinpath.return_value.read_text.return_value = "Hyprland"
        proc.joinpath.return_value.read_bytes.return_value = b"XDG_RUNTIME_DIR=/run/user/1000\0"
        instances = json.dumps([dict(pid=123, instance="guest-instance", wl_socket="wayland-1")])
        with patch.dict(os.environ, {}, clear=True), patch.object(Path, "glob", return_value=[proc]), \
             patch.object(guest.subprocess, "check_output", return_value=instances), \
             patch.object(guest.subprocess, "run"):
            guest.desktop()
            self.assertEqual(os.environ["WAYLAND_DISPLAY"], "wayland-1")
            self.assertEqual(os.environ["HYPRLAND_INSTANCE_SIGNATURE"], "guest-instance")
            self.assertEqual(os.environ["DBUS_SESSION_BUS_ADDRESS"], "unix:path=/run/user/1000/bus")

    def test_shutdown_timeout_never_forces_kill(self):
        vm = object.__new__(vm_test.VM)
        with patch.object(vm, "running", return_value=True), patch.object(vm, "ssh"), \
             patch.object(vm, "qmp") as qmp, patch.object(vm_test.time, "monotonic", side_effect=[0, 100]), \
             self.assertRaisesRegex(RuntimeError, "cleanly"):
            vm.stop()
        qmp.assert_called_once_with("system_powerdown")


if __name__ == "__main__":
    unittest.main()
