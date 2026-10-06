import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("setup_swap", Path(__file__).resolve().parents[1] / "tools/setup_swap.py")
swap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(swap)


class SwapTests(unittest.TestCase):
    def test_size_uses_current_ram_and_rounds_up(self):
        self.assertEqual(swap.ram_size("MemTotal: 32776800 kB\n"), 32 * swap.GIB)
        self.assertEqual(swap.ram_size("MemTotal: 8000000 kB\n"), 8 * swap.GIB)
        with self.assertRaises(RuntimeError):
            swap.ram_size("MemTotal: 0 kB\n")

    def test_fstab_preserves_other_mounts_and_is_repeatable(self):
        original = "# system mounts\nUUID=root / btrfs defaults 0 0\n/dev/zram0 none swap pri=100 0 0\n"
        updated = swap.fstab_update(original)
        self.assertTrue(updated.startswith(original))
        self.assertEqual(updated, swap.fstab_update(updated))
        self.assertEqual(updated.count("/swap/swapfile none swap"), 1)

    def test_conflicting_entries_are_rejected(self):
        for text in ["/swap/swapfile / ext4 defaults 0 0\n",
                     "/swap/swapfile none swap pri=100 0 0\n",
                     "/swap/swapfile none swap defaults 0 0\n",
                     "/swap/swapfile none swap noauto 0 0\n",
                     "/swap/swapfile none swap defaults 0 0\n" * 2]:
            with self.subTest(text=text), self.assertRaises(RuntimeError):
                swap.fstab_update(text)


if __name__ == "__main__":
    unittest.main()
