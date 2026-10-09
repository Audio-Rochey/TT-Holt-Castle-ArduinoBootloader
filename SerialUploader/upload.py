#!/usr/bin/env python3
"""TT UART IAP uploader. Requires: python3 -m pip install pyserial
Example: python3 upload.py --port /dev/cu.usbserial-2110 firmware.bin
Press RESET when prompted (application reset hook required), or power-cycle.
Serial adapter must use 3.3 V logic.
"""
import argparse
import struct
import time
from pathlib import Path

PHRASE = b"TT_ENTER_IAP"
ACK_PREFIX = b"\xaa\x55\x00"
APP_SIZE = 62 * 1024

def frame(cmd, data=b""):
    if len(data) > 64:
        raise ValueError("Maximum payload is 64 bytes")
    extra = b"\x00" * 4 if cmd in (0x81, 0x82) else b""
    body = bytes((cmd, len(data))) + extra + data
    return b"\xaa\x55" + body + struct.pack("<H", sum(body)) + b"\x55\xaa"

def read_ack(port, timeout):
    deadline = time.monotonic() + timeout
    window = bytearray()
    while time.monotonic() < deadline:
        byte = port.read(1)
        if byte:
            window += byte
            if len(window) > 6:
                del window[0]
            if len(window) == 6 and window[:3] == ACK_PREFIX and window[4:] == b"\x55\xaa":
                if window[3]:
                    raise RuntimeError("Bootloader rejected the command")
                return
    raise TimeoutError("No bootloader acknowledgement")

def enter(port, seconds):
    print("Press RESET (hook required) or power-cycle the target now; waiting for its bootloader...", flush=True)
    deadline = time.monotonic() + seconds
    port.reset_input_buffer()
    while time.monotonic() < deadline:
        port.write(PHRASE)
        port.flush()
        try:
            read_ack(port, min(0.12, max(0, deadline-time.monotonic())))
            return
        except TimeoutError:
            pass
    raise TimeoutError("Entry phrase was not acknowledged; check power, wiring and baud rate")

def transact(port, cmd, data=b"", timeout=2):
    port.write(frame(cmd, data))
    port.flush()
    read_ack(port, timeout)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("firmware", type=Path, nargs="?")
    parser.add_argument("--port", required=True)
    parser.add_argument("--baud", type=int, default=460800)
    parser.add_argument("--wait", type=float, default=30)
    parser.add_argument("--enter-only", action="store_true")
    args = parser.parse_args()
    data = b""
    if not args.enter_only:
        if args.firmware is None:
            parser.error("Provide an application .bin, or use --enter-only")
        data = args.firmware.read_bytes()
        if not 4 <= len(data) <= APP_SIZE or data[:4] == b"\xff"*4:
            parser.error("Application must be 4..63488 bytes with a non-erased first word")
    import serial
    try:
        with serial.Serial(args.port, args.baud, timeout=0.01, write_timeout=2) as port:
            enter(port, args.wait)
            print("IAP entered.", flush=True)
            if args.enter_only:
                return
            transact(port, 0x81, timeout=10)
            print("Writing", len(data), "bytes...", flush=True)
            for offset in range(0, len(data), 64):
                transact(port, 0x80, data[offset:offset+64])
            print("Verifying every byte...", flush=True)
            for offset in range(0, len(data), 64):
                transact(port, 0x82, data[offset:offset+64])
            transact(port, 0x83)
            print("Verified. Application started.")
    except (OSError, RuntimeError, TimeoutError, serial.SerialException) as error:
        parser.exit(1, f"Upload failed: {error}\nPower-cycle and retry; do not assume a partial application is valid.\n")

if __name__ == "__main__":
    main()
