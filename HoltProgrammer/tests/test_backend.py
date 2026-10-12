import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import BOOT, BOOT_SIZE, OPTIONS, Programmer, ProgrammingError, boot_options, run_tool, validate_options


def option_bytes(user=0xF7):
    return bytes([0xA5, 0x5A, user, user ^ 0xFF, 0x12, 0xED, 0x34, 0xCB, 0xFF, 0] * 1 + [0xFF, 0] * 3)


class FakeBoard:
    def __init__(self):
        self.options = option_bytes()
        self.boot = b"\x55" * BOOT_SIZE
        self.calls = []
        self.chip_id = "00620620"
        self.probes = 1
        self.corrupt = False
        self.short = False
        self.flash_failure = False
        self.change_options = False
        self.fresh_failure = False

    def run(self, executable, args, log):
        args = list(map(str, args))
        self.calls.append((str(executable), args))
        if str(executable) == "options":
            expected = Path(args[1]).read_bytes()
            assert expected == self.options
            if self.fresh_failure:
                raise ProgrammingError("Provisioning failed")
            self.options = boot_options(expected)
            Path(args[3]).write_bytes(self.options)
            return "PASS"
        command = args[0]
        if command == "list":
            return "\n".join("WCH-LinkE (RV mode)" for _ in range(self.probes))
        if command == "dump":
            address, size = int(args[1], 0), int(args[2])
            source = self.options if address == OPTIONS else self.boot
            data = source[:size].ljust((size + 3) & ~3, b"\xff")
            if self.short:
                data = data[:-1]
            Path(args[4]).write_bytes(data)
        if command == "flash":
            if self.flash_failure:
                raise ProgrammingError("Flash failed")
            self.boot = Path(args[-1]).read_bytes().ljust(BOOT_SIZE, b"\xff")
            if self.corrupt:
                self.boot = b"\x00" + self.boot[1:]
            if self.change_options:
                self.options = option_bytes(0xD7)
        return f"Attached chip: CH32V00X [CH32V006F8U6] (ChipID: 0x{self.chip_id})"


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.firmware = self.root / "my bootloader.bin"
        self.data = b"\x12\x34\x56\x78" + b"test" * 13 + b"!"
        self.firmware.write_bytes(self.data)
        self.board = FakeBoard()
        self.programmer = Programmer(log=lambda text: None, backup_root=self.root / "backups",
                                     runner=self.board.run, wlink="wlink", options_tool="options")

    def assert_no_flash(self):
        self.assertFalse(any("flash" in args for _, args in self.board.calls))

    def test_existing_board_backups_and_verified_report(self):
        original = self.board.boot
        folder = self.programmer.program(self.firmware)
        self.assertEqual((folder / "BOOT-original.bin").read_bytes(), original)
        self.assertEqual((folder / "options-original.bin").read_bytes(), option_bytes())
        self.assertEqual((folder / "BOOT-programmed.bin").read_bytes(), self.data)
        self.assertEqual(json.loads((folder / "report.json").read_text())["result"], "verified")
        self.assertFalse(any(exe == "options" for exe, _ in self.board.calls))
        flash = next(args for _, args in self.board.calls if "flash" in args)
        self.assertIn("0x1fff0000", flash)
        self.assertIn("--no-run", flash)
        self.assertNotIn("--erase", flash)

    def test_working_cli_arguments_and_default_detach_for_every_operation(self):
        folder = self.programmer.program(self.firmware)
        calls = [args for executable, args in self.board.calls if executable == "wlink"]
        flash = next(args for args in calls if args[0] == "flash")
        self.assertEqual(flash, ["flash", "--address", "0x1fff0000", "--no-run",
                                 str(folder / "BOOT-programmed.bin")])
        for args in calls:
            self.assertNotIn("--no-detach", args)
            self.assertNotIn("--chip", args)
        # The last operation is a normal dump that detaches on successful exit.
        self.assertEqual(calls[-1], ["dump", "0x1ffff800", "16", "--out",
                                    str(folder / "options-readback.bin")])
        self.assertEqual(json.loads((folder / "report.json").read_text())["detach_mode"], "wlink-default")

    def test_connection_check_does_not_leave_no_detach_requested(self):
        self.programmer.check()
        self.assert_no_flash()
        for _, args in self.board.calls:
            self.assertNotIn("--no-detach", args)

    def test_fresh_board_changes_only_boot_bit_and_complement(self):
        original = self.board.options = option_bytes(0xD7)
        folder = self.programmer.program(self.firmware)
        self.assertEqual(self.board.options, boot_options(original))
        self.assertEqual(self.board.options[:2] + self.board.options[4:], original[:2] + original[4:])
        self.assertTrue(json.loads((folder / "report.json").read_text())["fresh_configuration"])

    def test_wrong_chip_or_ambiguous_programmer_cannot_flash(self):
        self.board.chip_id = "00300500"
        with self.assertRaises(ProgrammingError): self.programmer.program(self.firmware)
        self.assert_no_flash()
        self.board.chip_id = "00620620"
        self.board.probes = 2
        with self.assertRaises(ProgrammingError): self.programmer.program(self.firmware)
        self.assert_no_flash()

    def test_corrupt_readback_is_failure_with_retained_backup(self):
        self.board.corrupt = True
        with self.assertRaisesRegex(ProgrammingError, "readback"):
            self.programmer.program(self.firmware)
        report = json.loads((self.programmer.session / "report.json").read_text())
        self.assertEqual(report["result"], "failed")
        self.assertTrue((self.programmer.session / "BOOT-original.bin").exists())

    def test_flash_failure_does_not_continue_to_provision(self):
        self.board.flash_failure = True
        self.board.options = option_bytes(0xD7)
        with self.assertRaises(ProgrammingError): self.programmer.program(self.firmware)
        self.assertFalse(any(exe == "options" for exe, _ in self.board.calls))

    def test_unexpected_options_change_is_failure(self):
        self.board.change_options = True
        with self.assertRaisesRegex(ProgrammingError, "unexpectedly"):
            self.programmer.program(self.firmware)

    def test_provision_failure_never_reports_success(self):
        self.board.options = option_bytes(0xD7)
        self.board.fresh_failure = True
        with self.assertRaises(ProgrammingError): self.programmer.program(self.firmware)
        self.assertEqual(json.loads((self.programmer.session / "report.json").read_text())["result"], "failed")

    def test_bad_firmware_and_incomplete_reads_cannot_flash(self):
        for data in [b"", b"\xff" * 8, b"a" * (BOOT_SIZE + 1)]:
            self.firmware.write_bytes(data)
            with self.assertRaises(ProgrammingError): self.programmer.program(self.firmware)
        self.firmware.write_bytes(self.data)
        self.board.short = True
        with self.assertRaises(ProgrammingError): self.programmer.program(self.firmware)
        self.assert_no_flash()

    def test_protected_boards_cannot_flash(self):
        for index, value in [(0, 0), (8, 0xFE)]:
            data = bytearray(option_bytes()); data[index] = value; data[index + 1] = value ^ 0xFF
            self.board.options = bytes(data)
            with self.assertRaises(ProgrammingError): self.programmer.program(self.firmware)
        self.assert_no_flash()

    def test_sessions_are_unique(self):
        self.assertNotEqual(self.programmer.program(self.firmware), self.programmer.program(self.firmware))


class OptionTests(unittest.TestCase):
    def test_all_user_values_preserve_other_settings(self):
        for user in range(256):
            original = option_bytes(user)
            changed = boot_options(original)
            self.assertEqual(changed[2], user | 0x20)
            self.assertEqual(changed[3], changed[2] ^ 0xFF)
            self.assertEqual(changed[:2] + changed[4:], original[:2] + original[4:])

    def test_corrupt_options_rejected(self):
        with self.assertRaises(ProgrammingError): validate_options(b"\x00" * 16)


class ProcessTests(unittest.TestCase):
    def test_output_and_nonzero_exit(self):
        lines = []
        self.assertEqual(run_tool(sys.executable, ["-c", "print('hello')"], lines.append), "hello")
        self.assertEqual(lines, ["hello"])
        with self.assertRaises(ProgrammingError):
            run_tool(sys.executable, ["-c", "raise SystemExit(7)"], lines.append)

    def test_silent_process_timeout(self):
        with self.assertRaisesRegex(ProgrammingError, "timed out"):
            run_tool(sys.executable, ["-c", "import time; time.sleep(20)"], lambda line: None, timeout=0.2)


if __name__ == "__main__":
    unittest.main()
