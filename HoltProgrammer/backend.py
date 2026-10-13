"""Holt programming workflow. No GUI imports and no shell command strings."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone

BOOT = 0x1FFF0000
BOOT_SIZE = 3328
OPTIONS = 0x1FFFF800
CHIP_ID = "00620620"
WLINK_REV = "626d11a2b85a6487b1e81730eade843583526226"
APP_VERSION = "0.1.1"
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


class ProgrammingError(RuntimeError):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def resource_root():
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def default_firmware():
    bundled = resource_root() / "resources" / "TT_Bootload_Arduino_3s.bin"
    return bundled if bundled.exists() else Path(__file__).resolve().parent.parent / "firmware" / bundled.name


def find_tool(name):
    filename = name + (".exe" if os.name == "nt" else "")
    # Packaged builds use only bundled tools. Source builds can use a staged tool.
    paths = [resource_root() / "vendor" / filename]
    if not getattr(sys, "frozen", False) and name == "wlink":
        paths.append(Path.home() / ".cargo" / "bin" / filename)
    for path in paths:
        if path.is_file():
            return path
    raise ProgrammingError(f"Missing bundled {filename}. Rebuild the app with both programmer tools.")


def run_tool(executable, args, log, timeout=120):
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        process = subprocess.Popen([str(executable), *map(str, args)], stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                                   errors="replace", creationflags=flags, bufsize=1)
    except OSError as error:
        raise ProgrammingError(f"Could not start {Path(executable).name}: {error}") from error
    lines = queue.Queue()
    output = []

    def read():
        try:
            for line in process.stdout:
                lines.put(ANSI.sub("", line).rstrip())
        finally:
            lines.put(None)

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    deadline = time.monotonic() + timeout
    try:
        while True:
            if time.monotonic() >= deadline:
                raise ProgrammingError("Programmer timed out. Keep the backup; reconnect and retry.")
            try:
                line = lines.get(timeout=0.1)
            except queue.Empty:
                continue
            if line is None:
                break
            output.append(line)
            log(line)
        code = process.wait(timeout=max(0.1, deadline - time.monotonic()))
        if code:
            raise ProgrammingError(f"{Path(executable).name} failed (exit {code}). "
                                   "Check the log, board power, SWIO, common ground, and programmer mode.")
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        reader.join(timeout=1)
        process.stdout.close()
    return "\n".join(output)


def validate_options(data):
    if len(data) != 16:
        raise ProgrammingError("Option-byte read was incomplete.")
    if any((data[i] ^ data[i + 1]) != 0xFF for i in range(0, 16, 2)):
        raise ProgrammingError("Option-byte complements are invalid. Stop and inspect with WCH tools.")
    if data[0] != 0xA5:
        raise ProgrammingError("Read protection is enabled. This app will not unlock or erase protected boards.")
    if data[8::2] != b"\xff" * 4:
        raise ProgrammingError("Flash write protection is enabled. Inspect the board with WCH tools first.")
    return bool(data[2] & 0x20)


def boot_options(data):
    validate_options(data)
    result = bytearray(data)
    result[2] |= 0x20
    result[3] = result[2] ^ 0xFF
    return bytes(result)


class Programmer:
    def __init__(self, log=print, progress=lambda value, text: None, backup_root=None,
                 runner=run_tool, wlink=None, options_tool=None):
        self.log, self.progress, self.runner = log, progress, runner
        self.wlink = Path(wlink) if wlink else find_tool("wlink")
        self.options_tool = Path(options_tool) if options_tool else None
        self.backup_root = Path(backup_root) if backup_root else Path.home() / "Documents" / "Holt Programmer Backups"
        self.session = None

    def command(self, *args):
        # Use the normal CLI lifecycle: attach for the operation, then detach
        # on successful exit. --no-run skips the reset stage; it is NOT a
        # reason to keep the debug connection attached with --no-detach.
        # In particular the final readback must release the debug connection.
        self.log("WLINK: " + subprocess.list2cmdline(list(map(str, args))))
        result = self.runner(self.wlink, list(args), self.log)
        # Every attached command must positively identify the same supported part.
        if args[0] != "list":
            ids = re.findall(r"ChipID:\s*0x([0-9a-fA-F]{8})", result)
            if not ids or any(value.lower() != CHIP_ID for value in ids):
                raise ProgrammingError("Expected Holt CH32V006F8U6 (ChipID 0x00620620). "
                                       "The detected chip is different or unidentified.")
        return result

    def dump(self, address, size, path):
        self.command("dump", hex(address), str(size), "--out", path)
        data = Path(path).read_bytes()
        padded_size = (size + 3) & ~3
        if len(data) != padded_size:
            raise ProgrammingError(f"Incomplete read at {hex(address)}: {len(data)} bytes, expected {padded_size}.")
        return data[:size]

    def check(self):
        probes = self.command("list")
        count = probes.count("(RV mode)")
        if count != 1:
            raise ProgrammingError("Connect exactly one WCH-LinkE in RISC-V mode. "
                                   f"Found {count} RISC-V programmers.")
        with tempfile.TemporaryDirectory(prefix="holt-check-") as folder:
            # This read positively identifies the target without flashing it.
            data = self.dump(OPTIONS, 16, Path(folder) / "options.bin")
        configured = validate_options(data)
        self.log("Holt CH32V006F8U6 detected. BOOT-at-power-on: " + ("enabled." if configured else "needs configuration."))
        return data

    def program(self, firmware, configure_fresh=True):
        data = Path(firmware).read_bytes()
        if Path(firmware).suffix.lower() != ".bin" or not 4 <= len(data) <= BOOT_SIZE or data[:4] == b"\xff" * 4:
            raise ProgrammingError("Choose a raw BOOT .bin, 4–3328 bytes, with a non-erased first word.")
        self.progress(5, "Checking programmer and Holt…")
        initial = self.check()
        if not initial[2] & 0x20:
            if not configure_fresh:
                raise ProgrammingError("Fresh board requires BOOT-at-power-on configuration.")
            if self.options_tool is None:
                self.options_tool = find_tool("holt-options")
        self.backup_root.mkdir(parents=True, exist_ok=True)
        self.session = Path(tempfile.mkdtemp(prefix=datetime.now().strftime("%Y%m%d-%H%M%S-"), dir=self.backup_root))
        self.log(f"Backup folder: {self.session}")
        report = {"started_utc": datetime.now(timezone.utc).isoformat(), "chip_id": CHIP_ID,
                  "app_version": APP_VERSION, "detach_mode": "wlink-default",
                  "firmware_file": str(firmware), "firmware_sha256": digest(data),
                  "firmware_bytes": len(data), "wlink_revision": WLINK_REV, "result": "incomplete"}
        report_file = self.session / "report.json"
        report_file.write_text(json.dumps(report, indent=2))
        try:
            self.progress(15, "Saving original BOOT and settings…")
            original = self.dump(BOOT, BOOT_SIZE, self.session / "BOOT-original.bin")
            options = self.dump(OPTIONS, 16, self.session / "options-original.bin")
            validate_options(options)
            if options != initial:
                raise ProgrammingError("Board settings changed during connection checks. Reconnect and retry.")
            desired = boot_options(options)
            # Snapshot the chosen file so it cannot change between programming and verification.
            snapshot = self.session / "BOOT-programmed.bin"
            snapshot.write_bytes(data)
            report.update(boot_original_sha256=digest(original), options_original_hex=options.hex())
            self.progress(35, "Programming bootloader…")
            self.command("flash", "--address", hex(BOOT), "--no-run", snapshot)
            self.progress(65, "Verifying every bootloader byte…")
            readback = self.dump(BOOT, len(data), self.session / "BOOT-readback.bin")
            if readback != data:
                raise ProgrammingError("BOOT readback does not match the firmware. Programming FAILED.")
            after_flash = self.dump(OPTIONS, 16, self.session / "options-after-flash.bin")
            if after_flash != options:
                raise ProgrammingError("BOOT programming changed option bytes unexpectedly. Stop and inspect the backups.")
            if desired != options:
                self.progress(80, "Configuring fresh board for BOOT-at-power-on…")
                self.log("Fresh-board setup is a prototype and awaits hardware validation.")
                self.runner(self.options_tool, ["--expected", self.session / "options-original.bin",
                            "--out", self.session / "options-helper-readback.bin"], self.log)
            verified_options = self.dump(OPTIONS, 16, self.session / "options-readback.bin")
            if verified_options != desired:
                raise ProgrammingError("BOOT-at-power-on verification failed, or another option changed.")
            report.update(result="verified", options_verified_hex=verified_options.hex(),
                          fresh_configuration=desired != options)
            self.progress(100, "Bootloader verified. Power-cycle Holt.")
            self.log("PASS: exact BOOT readback and option-byte verification. Power-cycle Holt.")
        except Exception as error:
            report.update(result="failed", error=str(error))
            raise
        finally:
            report_file.write_text(json.dumps(report, indent=2))
        return self.session


def uart_check(port_name, log):
    """Non-flashing check of the bundled TT bootloader's entry acknowledgement."""
    import serial
    log("Power-cycle Holt now. Waiting up to 30 seconds for TT bootloader entry…")
    # Configure before opening to avoid asserting a reset/control line unnecessarily.
    port = serial.Serial(port=None, baudrate=460800, timeout=0.01, write_timeout=2)
    port.dtr = False
    port.rts = False
    port.port = port_name
    with port:
        port.reset_input_buffer()
        deadline = time.monotonic() + 30
        window = bytearray()
        while time.monotonic() < deadline:
            port.write(b"TT_ENTER_IAP")
            port.flush()
            until = min(deadline, time.monotonic() + 0.12)
            while time.monotonic() < until:
                window.extend(port.read(1))
                window[:] = window[-6:]
                if window == b"\xaa\x55\x00\x00\x55\xaa":
                    log("PASS: TT bootloader acknowledged over UART. No application was erased. "
                        "Power-cycle again to leave upload mode.")
                    return
    raise ProgrammingError("No TT bootloader acknowledgement. Check the UART adapter, 3.3 V logic, "
                           "crossed TX/RX, ground, and power-cycle timing.")
