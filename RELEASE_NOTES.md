# TT-Bootload v0.4 — standard Arduino application linking

The three-second timeout, UART phrase, baud rate and upload protocol are unchanged.
The handoff now clears reset flags, selects Start_Mode_USER and calls
NVIC_SystemReset(). This replaces the direct jump to 0x08000000 and lets the
application use the stock WCH Arduino linker (execution origin zero).

The application is still physically programmed at 0x08000000 by upload.py.
The separate bootloader is programmed at 0x1FFF0000 using WCH-LinkE/SWIO.
Customers need the application reset hook, but no Arduino linker edits.

Built 9 October 2026 with RISC-V GCC 13.2.0. BOOT binary: 2588 bytes.
Software checks passed: phrase matching, upload framing, Flash bounds and
verification, three-second deadline, and USER/software-reset handoff.
The maintainer confirmed the basic flow on the Holt board on 9 October 2026:
compile an Arduino sketch with stock settings and upload its BIN over UART.
This is a prototype validation, not exhaustive hardware qualification.
