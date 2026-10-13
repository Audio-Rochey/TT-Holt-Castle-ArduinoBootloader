# Holt Programmer

Version 0.1.1 fixes an unnecessary `--no-detach` flag in the original GUI.
The app now runs the same flash arguments as the working command-line procedure:
`wlink flash --address 0x1FFF0000 --no-run firmware.bin`. Backups and readbacks
also use WLINK's normal detach-on-exit behavior. Successful memory verification
alone does not prove the board will enter IAP; confirm that on hardware.

Prototype desktop installer for Holt Castle **CH32V006F8U6** and **WCH-LinkE**.
One Python/Qt codebase; separate Apple Silicon macOS and Windows 10/11 x64
packages. macOS 13 or newer is required by the bundled Qt version.

## Use

1. Extract the download. Open **Holt Programmer.app** on Mac. On Windows keep
   the entire extracted folder together and open **Holt Programmer.exe**.
2. Power Holt from its own USB supply. Connect programmer SWIO to Holt PD1 and
   GND to Holt GND. Leave programmer power pins disconnected. Use RISC-V mode,
   connect exactly one programmer, and close other programming tools.
3. Click **PROGRAM HOLT WITH BOOTLOADER**.
4. Wait for **Bootloader verified. Power-cycle Holt.** Disconnect the programmer
   and cold power-cycle Holt. Verification does not itself exercise firmware.

WLINK, TT v0.4 BOOT firmware, and the option-byte helper are bundled. Users
do not install Python, Rust, Homebrew, or remember command-line settings.
Windows USB driver access may still require machine-specific setup; the app
does not install drivers. Check its log if the programmer cannot be opened.

The app installs BOOT at `0x1FFF0000`. **Use alternative firmware** accepts a
raw BOOT `.bin` of 4–3328 bytes. It is not an application uploader. A size
check cannot prove an arbitrary image is correct for Holt. Alternative images
must use Holt's BOOT mapping and BOOT-at-power-on configuration.

## Backups and verification

Every programming session gets a unique folder in
`Documents/Holt Programmer Backups` (change with **Backup folder…**), containing:

- Entire original 3328-byte BOOT region and original 16-byte option block.
- Exact snapshot of the selected firmware and programmed image readback.
- Option reads before/after programming and after provisioning.
- `report.json` with hashes, settings, outcome, and failure details.
- `session.log` with programmer output.

WLINK may pad an odd readback length to four bytes; the comparison uses the
actual image length. A failed flash, mismatched readback, or changed unrelated
option byte is a failure. Failed-session backups are retained.

The app refuses different/unidentified chips, multiple RISC-V programmers,
incomplete reads, invalid option complements, and read/write-protected boards.
It does not automatically remove protection or mass-erase applications. Recovery
uses WCH tools; there is no blind automatic rollback.

**Check connection** reads the chip and options without flashing. Debug access
temporarily pauses the application; WLINK detaches on successful exit. Backups,
flashing, and readbacks each use this normal command-line lifecycle. Cold
power-cycle before exercising the bootloader. Do not swap boards/programmers
during an operation. The app prevents cancellation/closure and duplicate clicks
while busy. The exact WLINK arguments are recorded in the log.

## Fresh-board configuration — hardware validation pending

For fresh boards, `holt-options` sets USER bit 5 (`0x20`,
`OB_PowerON_Start_Mode_BOOT`) only when needed. It uses one uninterrupted
WLINK library session, checks ChipID, halts the core, compares live options
with the backup, and follows the vendor option erase/buffer-load/page-program
sequence. Only the BOOT bit and its complement change. RDPR, data bytes,
reset/watchdog settings, and write protection are preserved and verified.

The sequence follows WCH SDK functions in
`firmware/source/CH32V00X_IAP/User/main.c`: `FLASH_EraseOptionBytes`,
`FLASH_OptionBytePR`, `FLASH_BufReset`, `FLASH_BufLoad`, and
`FLASH_ProgramPage_Fast`. Host tests **are not validation on a chip**.
Treat this as a development prototype until physical acceptance tests pass.
Provisioning erases and rewrites the option page; power loss can require recovery.

## Self-test

The programming flow checks SWIO connectivity, ChipID, BOOT readback, option
integrity, and BOOT-at-power-on. These are programming checks, not a complete
electrical test of the board.

**Test bootloader** uses a separate 3.3 V USB-UART adapter:

| Adapter | Holt |
| --- | --- |
| TX | PD6 (target RX) |
| RX | PD5 (target TX) |
| GND | GND |

Select its port, start the test, and cold power-cycle when prompted. The test
sends `TT_ENTER_IAP` at 460800 baud and checks the exact successful entry ACK.
It does not erase or upload an application. **Power-cycle again afterwards**:
entry intentionally leaves the bootloader awaiting upload. The test uses the
bundled firmware's phrase/baud and is disabled for alternative images.
It checks loader entry and two-way UART, not every peripheral or application startup.

Future manufacturing tests could use a dedicated test application for LED
inspection, GPIO loopback, ADC reference checks, and a UART identification
response. Installing it changes application Flash, so add it as a separate
explicit action with backup/recovery. A fixture controlling target power could
automate cold-start timing. These fixture tests are ideas, not implemented features.

## Build

Build on each target OS using Python 3.12 and Rust (Xcode command-line tools
on Mac; MSVC tools on Windows). The manual GitHub workflow
`.github/workflows/build-holt-programmer.yml` builds both packages from pinned
WLINK revision `626d11a2b85a6487b1e81730eade843583526226`.

```sh
python3 -m venv HoltProgrammer/.venv
HoltProgrammer/.venv/bin/python -m pip install -r HoltProgrammer/requirements.txt
python3 -m unittest discover -s HoltProgrammer/tests -v
cargo test --locked --manifest-path HoltProgrammer/provisioner/Cargo.toml
cargo build --release --locked --manifest-path HoltProgrammer/provisioner/Cargo.toml
```

Build WLINK at the pinned revision (see the workflow), then package:

```sh
HoltProgrammer/.venv/bin/python HoltProgrammer/build.py \
  --wlink /path/to/pinned/wlink \
  --options HoltProgrammer/provisioner/target/release/holt-options
```

Windows uses `.venv\Scripts\python.exe` and `.exe` tool names. Output is in
`HoltProgrammer/dist/`. The builder records hashes and runs a hardware-free
smoke test. Use an Apple Silicon Python interpreter for the Mac build.
Release builds should use developer signing/notarization on Mac and signing
on Windows. This prototype is ad-hoc signed locally, not notarized.

For source development, stage `holt-options` in `HoltProgrammer/vendor/` and
stage WLINK there or use the development fallback `~/.cargo/bin/wlink`.
Launch with `python HoltProgrammer/app.py`. `--preview /path/to/window.png`
renders the initial UI without USB actions. `--smoke-test` checks bundled
tools and firmware without connecting hardware.

## Hardware acceptance before release

- Existing configured board: program/verify, compare options with the original,
  cold start, then confirm UART test success.
- Fresh unprotected CH32V006F8U6: retain original options, verify only USER
  bit 5/complement changed, power-cycle, confirm UART entry.
- Compare application Flash before/after BOOT installation. Repeat an ordinary
  Arduino application upload, application startup, and manual reset.
- Repeat on Windows 10/11 with actual WCH-LinkE driver setup.
- Exercise wrong chip, unplugged/busy programmer, missing power, bad SWIO,
  verification failure, and file paths containing spaces; retain logs.

Host tests simulate programmer responses and never program a physical board.

## Notices

WLINK is used under MIT; see `resources/WLINK-LICENSE-MIT.txt`. WCH firmware
notices remain applicable; see `resources/BOOTLOADER-NOTICE.md`.
Qt/PySide6 and Python dependency notices are included during packaging.
Qt libraries are dynamically bundled and can be replaced in the app bundle
or Windows `_internal` directory. Matching source is available from
https://code.qt.io/pyside/pyside-setup.git and https://code.qt.io/qt/qtbase.git
(version 6.10.2). No project-wide license is selected by this addition.
