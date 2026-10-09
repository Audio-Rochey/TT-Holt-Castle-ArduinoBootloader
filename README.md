# TT-Bootload

**A resident UART bootloader for the TerrainTronics Holt CH32V006 board.
Compile with standard WCH Arduino settings, then upload the application BIN
using Python and a USB-UART adapter.**

Install the bootloader once with WCH-LinkE. Customers can then update applications
without a programmer. No DTR/RTS wiring, Arduino linker changes, or custom Arduino
board package is required by this bootloader. Each sketch must include the reset
hook provided in the example when using the stock WCH board. The new Holt
board prototype includes that hook automatically; see [Arduino integration](Arduino/README.md).

Current release: **v0.4**, with a nominal **3-second** entry window. The maintainer
confirmed the basic stock-Arduino compilation and UART upload flow on Holt
hardware on 9 October 2026. Other chips and boards are not validated.


## WCH core provenance

The TerrainTronics Boards Manager package bundles a snapshot of our working
WCH Arduino installation, including updates from unreleased WCH development
code, updated register definitions, and local fixes present in that snapshot.
It also includes TerrainTronics' Holt Castle pin definitions and automatic
TT-Bootload reset hook.

Customers do not need to find or install those WCH updates separately, or
install the WCH board package first. Boards Manager downloads the compiler
toolchain and standalone uploader as dependencies. Separately installed
sketchbook libraries and changes outside the packaged platform are not part
of this snapshot.

The bundled core does not automatically track future WCH releases;
TerrainTronics incorporates updates through new board-package releases.
This snapshot is not claimed to match an exact upstream Git commit.
Original upstream notices are retained.

## How it works

- On entry, listen for the exact ASCII phrase `TT_ENTER_IAP` for 3 seconds.
- Without the phrase, start a present application by selecting USER mode and
  requesting a software reset.
- With the phrase, stay in IAP to accept an application upload.
- Erase application Flash, write the image, verify its bytes, and automatically
  reset into the application after successful upload.
- If application Flash is erased, remain in IAP even without the phrase.

The phrase cancels the timeout. It is an entry trigger, not authentication.
The window uses the internal HSI clock and is subject to oscillator tolerance.

## Hardware and memory

Tested target: Holt with **CH32V006F8U6**, WCH-LinkE, and a Mac host.

| Item | Value |
| --- | --- |
| UART | USART1, 460800 baud, 8N1, no flow control |
| Target TX / RX | PD5 / PD6 |
| Holt LED | PD2 / Wemos-footprint D0 |
| BOOT programming address | `0x1FFF0000` |
| BOOT capacity / v0.4 binary | 3328 / 2588 bytes |
| Application programming address | `0x08000000` |
| Application capacity | 63488 bytes / 62 KiB |
| Application link address | `0x00000000`, stock WCH Arduino setting |

Connect a **3.3 V logic** USB-UART adapter:

| Adapter | Holt |
| --- | --- |
| TX | PD6 / target RX |
| RX | PD5 / target TX |
| GND | GND |

Power the board from its normal supply. These three UART connections do not
provide power. Reset is manual; no automatic reset wiring is needed.

## Customer quick start

These steps assume TT-Bootload is installed and BOOT-at-power-on is configured.

### 1. Compile in Arduino IDE

Install the [WCH Arduino core](https://github.com/openwch/arduino_core_ch32) and
select the CH32V006 configuration appropriate to your hardware. Use its normal
board settings and original linker files.

Open [the Arduino blink example](Examples/CH32V006TTBootloader/CH32V006TTBootloader.ino).
It contains the reset hook and toggles the PD2 LED every 250 ms.

Choose **Sketch → Export Compiled Binary**. Use the resulting application `.bin`,
such as `CH32V006TTBootloader.ino.bin`. The IDE's Upload button is not integrated
with this Python uploader.

### 2. Set up Python

From this repository's root directory:

```sh
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

On Windows, activate with `.venv\Scripts\activate` instead.

### 3. Upload over UART

Close any serial monitor using the adapter. On macOS, list ports with:

```sh
ls /dev/cu.*
```

Replace the port and application filename with yours:

```sh
python3 SerialUploader/upload.py --port /dev/cu.usbmodem04258F0689572 "$HOME/Downloads/CH32V006TTBootloader.ino.bin"
```

**Press RESET after the uploader prompts you.** It repeatedly sends the phrase
to catch the entry window. If the installed application lacks the reset hook,
cold power-cycle the target instead.

Expected progress includes:

```text
IAP entered.
Writing ... bytes...
Verifying every byte...
Verified. Application started.
```

No second reset is required after successful upload. Linux ports such as
`/dev/ttyUSB0` and Windows ports such as `COM5` use the same `--port` argument.
The host waits up to 30 seconds for entry; `--wait 60` extends that opportunity
without changing the MCU's 3-second window.

## The application reset hook

On the tested Holt, pressing the reset button starts the application. The hook
at the beginning of `setup()` redirects that event into TT-Bootload:

1. Read and clear accumulated reset flags.
2. For an external pin reset without power-on/software-reset flags, select BOOT
   and request a software reset.
3. TT-Bootload handles UART and the 3-second entry window.
4. On timeout or completed upload, TT-Bootload clears flags, selects USER, and
   requests a software reset.
5. The application sees a software reset and runs, avoiding a loop into BOOT.

For your own sketch, copy `ttBootloadOnManualReset()` from the Arduino example
and call it **first in `setup()`**, before configuring peripherals. Preserve
its reset-flag clearing. The hook is CH32V006-specific; it does not initialize
UART or wait for the entry phrase.

Every application needs this hook for reset-button entry. An application without
it can still use cold-power-on entry when BOOT-at-power-on is configured.
The local Holt board prototype automatically includes the hook in its core;
see [Arduino/README.md](Arduino/README.md). Watchdog reset
is not defined here as an entry method.

### Why no application linker changes are needed

The uploader writes the application at physical user Flash address `0x08000000`.
USER mode maps that Flash at address zero for execution, which matches the stock
Arduino linker. v0.4 selects USER and resets before starting the application.

Earlier development versions jumped directly to `0x08000000` while BOOT stayed
mapped at zero. If you edited Arduino's linker for those versions, restore the
original linker and force a clean rebuild. Do not install the bootloader's
`firmware/source/CH32V00X_IAP/Ld/Link.ld` into Arduino: it describes BOOT, not the application.

## One-time bootloader installation

See [Programming TT-Bootload with WCH-LinkE](PROGRAMMING_BOOTLOADER.md) for
wlink installation, wiring, backups, programming, and readback verification.

Developers/manufacturing use WCH-LinkE through SWIO. Customers do not need it
once the bootloader and boot configuration are installed.

### Install wlink on macOS

With Homebrew available:

```sh
brew install rust libusb pkg-config
cargo install --git https://github.com/ch32-rs/wlink
```

Cargo normally installs `wlink` at `$HOME/.cargo/bin/wlink`. The commands below
use that full path. [wlink](https://github.com/ch32-rs/wlink) is the target
programmer utility; `wlink-iap` is a different tool for programmer firmware
updates and is not used here.

### Back up, program, and verify

From the repository root, connect WCH-LinkE and close MounRiver and the uploader:

```sh
"$HOME/.cargo/bin/wlink" dump 0x1FFF0000 3328 --out "$HOME/Desktop/Holt_BOOT_original.bin"
"$HOME/.cargo/bin/wlink" dump 0x1FFFF800 16 --out "$HOME/Desktop/Holt_options_original.bin"
"$HOME/.cargo/bin/wlink" flash --address 0x1FFF0000 --no-run firmware/TT_Bootload_Arduino_3s.bin
"$HOME/.cargo/bin/wlink" dump 0x1FFF0000 2588 --out "$HOME/Desktop/TT_BOOT_readback.bin"
cmp firmware/TT_Bootload_Arduino_3s.bin "$HOME/Desktop/TT_BOOT_readback.bin"
```

`cmp` prints nothing when the installed image matches. Cold power-cycle after
successful programming and verification. Installing TT-Bootload replaces the
factory BOOT program; retain the backup. Do not give its BIN to `upload.py`,
which only programs application Flash.

### Configure BOOT-at-power-on

The tested Holt already had BOOT-at-power-on enabled (USER option byte `0xF7`).
The commands above **do not alter option bytes**. A fresh device must also have
power-on start configured to BOOT while preserving its other option fields.
WCH's SDK names this `OB_PowerON_Start_Mode_BOOT`; consult
[BOOT_Explained.md](BOOT_Explained.md) and the family reference manual.

Do not copy a complete option-byte value blindly to other devices. Without
BOOT-at-power-on, an application lacking the hook may require SWIO recovery.

## Building from source

`firmware/source/CH32V00X_IAP/User/main.c` is the single editable firmware C translation unit;
its WCH Flash support is appended in the same file. Startup assembly, vendor
headers, and the BOOT linker are also required and included.

Use a RISC-V GCC toolchain supporting `rv32ec_zicsr` and `ilp32e`:

```sh
make
make test
```

Default compiler prefix: `riscv64-unknown-elf-`. For another compatible toolchain:

```sh
make PREFIX=riscv-none-embed-
```

`make` generates BOOT BIN/ELF/map and a physical-address HEX under `build/` and
checks that the binary fits in 3328 bytes. The supplied bootloader binary was built
with GCC 13.2.0, `-Os`, `-nostdlib`, and section garbage collection.

For MounRiver, open/import `firmware/source/CH32V00X_IAP/CH32V00X_IAP.wvproj` with its adjacent
`.project`, `.cproject`, and `.template` files intact. Its output is normally
`firmware/source/CH32V00X_IAP/obj/CH32V00X_IAP.bin`. The Mac MounRiver downloader failed to program
BOOT during development; wlink was used instead. The supplied release was built
independently with GCC, not validated in every MounRiver version.

Configuration is near the top of `main.c`. Changing the phrase also requires
changing `PHRASE` in `upload.py`; baud settings must likewise match at both ends.

## Repository contents

| Path | Contents |
| --- | --- |
| `firmware/source/CH32V00X_IAP/` | BOOT source, headers, startup, linker, MounRiver metadata |
| `upload.py`, `requirements.txt` | UART uploader and Python dependency |
| `Examples/CH32V006TTBootloader/` | The single Arduino blink sketch, including its reset hook |
| `firmware/TT_Bootload_Arduino_3s.bin` | Compiled v0.4 bootloader, 2588 bytes |
| `tests/` | Host checks for phrase matching, Flash logic, reset handoff, protocol |
| `Docs/`, `BOOT_Explained.md` | WCH PDFs and BOOT-area explanation |
| `CHANGELOG.md`, `RELEASE_NOTES.md` | Release history and current release notes |
| `PUBLISHING.md` | Instructions for creating the GitHub repository and release |
| `NOTICE.md` | Vendor attribution and license status |

Only the bootloader BIN and its source files are kept under `firmware/`. Local
compiler output goes into ignored `build/`. Compile the included Arduino sketch
in Arduino IDE to produce your application BIN.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| No `IAP entered` | Correct port, crossed TX/RX, common ground, 3.3 V logic, reset after starting uploader |
| Reset starts application immediately | Installed app may lack the hook; cold power-cycle to update it |
| No blinking after `--enter-only` | Expected: accepting the phrase cancels timeout; close uploader and cold power-cycle without sending the phrase |
| `wlink: command not found` | Use `$HOME/.cargo/bin/wlink` or add that directory to PATH |
| MounRiver programming/verification failure | Use the wlink BOOT programming and readback commands |
| App upload rejected or app fails to run | Use an application BIN, not BOOT/ELF/HEX; check MCU selection, stock linker, and 63488-byte limit |
| Port busy | Close Serial Monitor and other serial applications |

## Validation and limits

Maintainer-confirmed hardware results include BOOT programming/readback,
UART application uploads, and the basic v0.4 flow with an Arduino-compiled
application using standard linker settings. Host checks cover phrase matching,
packet framing/ACK parsing, Flash bounds, padding and verification, the 3-second
deadline, and USER software-reset handoff.

This is prototype firmware. There is no complete-image validity marker or
rollback image; an interrupted upload can leave partial application code.
The first-word check detects erased Flash, not a complete valid program.
Recovery uses cold BOOT entry and a fresh upload on the configured Holt.
Keep SWIO accessible during development.

A local Apple Silicon prototype now integrates the Upload button and automatic
reset hook. See [Arduino/README.md](Arduino/README.md) for installation and test
instructions. Public Boards Manager packaging and other hosts remain future work.

## References and attribution

- [WCH Arduino core](https://github.com/openwch/arduino_core_ch32)
- [WCH family SDK](https://github.com/openwch/ch32v002_004_005_006_007)
- [WCH USART IAP example](https://github.com/openwch/ch32v002_004_005_006_007/tree/main/EVT/EXAM/USART_IAP)
- [CH32V00X reference manual](https://www.wch-ic.com/downloads/CH32V00XRM_PDF.html)
- [CH32V006 datasheet](https://www.wch-ic.com/downloads/CH32V006DS0_PDF.html)
- [wlink](https://github.com/ch32-rs/wlink)

Vendor notices are preserved. A project-wide license for TerrainTronics-authored
material has not been selected; see [NOTICE.md](NOTICE.md).
