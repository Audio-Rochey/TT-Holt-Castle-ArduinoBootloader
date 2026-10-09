# Installing TT-Bootload on Holt Castle with WCH-LinkE

This guide records the procedure tested on the **Holt Castle CH32V006F8U6**
using an Apple Silicon Mac and WCH-LinkE. It installs the special BOOT firmware
once; subsequent application uploads use Arduino IDE and a USB-UART adapter.

The tested firmware is [TT_Bootload_Arduino_3s.bin](firmware/TT_Bootload_Arduino_3s.bin),
2588 bytes, with a nominal three-second UART entry window. This procedure
replaces the chip's existing BOOT program. Keep the backups below.

## What you need

- Holt Castle fitted with CH32V006F8U6.
- WCH-LinkE programmer and a USB data cable.
- Connections to Holt's PD1/SWIO and GND.
- A Mac with Terminal and this repository.
- A USB-UART adapter for the final application-upload test.

**wlink** is the open-source target programmer from
[ch32-rs/wlink](https://github.com/ch32-rs/wlink).
It is different from **wlink-iap**, which updates the programmer's own firmware.
Installing wlink-iap alone does not provide the target-programming command.

## 1. Install wlink on macOS

Install [Homebrew](https://brew.sh/) using its official instructions if
`brew --version` does not work. Install Apple's command-line developer tools
if you do not already have them:

```sh
xcode-select --install
```

If macOS says they are already installed, continue. With Homebrew available:

```sh
brew install rust libusb pkg-config
cargo install --git https://github.com/ch32-rs/wlink
```

The upstream project also offers binaries on its
[nightly release page](https://github.com/ch32-rs/wlink/releases/tag/nightly).
The Cargo installation above is the route used for this project.

Cargo normally places the executable at:

```text
$HOME/.cargo/bin/wlink
```

For the development Mac, that was
`/Users/dafyddroche/.cargo/bin/wlink`. Test it using the full path:

```sh
"$HOME/.cargo/bin/wlink" --help
```

If you want to type just `wlink`, add Cargo's binary directory to your shell
PATH. On the default macOS zsh shell, add this line to `~/.zshrc`:

```sh
export PATH="$HOME/.cargo/bin:$PATH"
```

Then open a new Terminal window or run `source "$HOME/.zshrc"`.
The remaining commands deliberately use the full path so they work without
that PATH change. No Python virtual environment is needed.

## 2. Get the bootloader file

If the repository is already cloned:

```sh
cd "$HOME/Documents/github/TT-Holt-Castle-ArduinoBootloader"
git switch main
git pull --ff-only
```

For a first clone:

```sh
mkdir -p "$HOME/Documents/github"
cd "$HOME/Documents/github"
git clone https://github.com/Audio-Rochey/TT-Holt-Castle-ArduinoBootloader.git
cd TT-Holt-Castle-ArduinoBootloader
```

The BOOT binary is `firmware/TT_Bootload_Arduino_3s.bin`.
Run the following programming commands from the repository root.

## 3. Connect WCH-LinkE to Holt Castle

Use the programmer in its **RISC-V programming mode**. Refer to the
[WCH-Link documentation](https://github.com/openwch/ch32v003/tree/main/WCH-Link)
for your programmer's mode-selection procedure.

| WCH-LinkE | Holt Castle |
| --- | --- |
| SWIO / SWDIO programming signal | PD1 / SWIO programming connection |
| GND | GND |

Use the labeled programming signal on your particular LinkE; connector
layouts vary. This is the single-wire debug/programming connection, not UART.
Do not connect it to Holt's PD5/PD6 UART pins.

For this procedure, power Holt from its normal USB supply and leave the
programmer's 3.3 V and 5 V outputs disconnected. Grounds must be connected.
Close MounRiver, OpenOCD, Arduino uploads, and other tools using WCH-LinkE
before invoking wlink.

## 4. Back up the chip

Create a new timestamped backup directory for each board/session:

```sh
TT_BACKUP_DIR="$HOME/Desktop/Holt-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$TT_BACKUP_DIR"

"$HOME/.cargo/bin/wlink" dump 0x1FFF0000 3328 \
  --out "$TT_BACKUP_DIR/BOOT-original.bin"

"$HOME/.cargo/bin/wlink" dump 0x1FFFF800 16 \
  --out "$TT_BACKUP_DIR/options-original.bin"
```

For this Holt, the attached-chip output should identify
**CH32V006F8U6**, with tested ChipID **0x00620620**. Check the part identity
before programming. Retain both backup files.

The first dump reads the complete 3328-byte BOOT region. The second records
option bytes; flashing BOOT does not configure them.

## 5. Program the special bootloader

```sh
"$HOME/.cargo/bin/wlink" flash \
  --address 0x1FFF0000 \
  --no-run \
  firmware/TT_Bootload_Arduino_3s.bin
```

The physical BOOT address is **0x1FFF0000**. The application address is
**0x08000000**. Use the BOOT address for this file.

Do not use Arduino Upload or `tt-upload` to install the bootloader BIN:
those UART uploads are for application firmware.

## 6. Read back and verify

The supplied binary is 2588 bytes. Derive its length from the file so the
verification also follows the file you actually programmed:

```sh
TT_BOOT_BYTES=$(wc -c < firmware/TT_Bootload_Arduino_3s.bin)

"$HOME/.cargo/bin/wlink" dump 0x1FFF0000 "$TT_BOOT_BYTES" \
  --out "$TT_BACKUP_DIR/BOOT-readback.bin"

cmp firmware/TT_Bootload_Arduino_3s.bin "$TT_BACKUP_DIR/BOOT-readback.bin"
```

No output from `cmp` means an exact match. If it reports a difference or a
programming operation fails, resolve that before treating the board as ready.
The backup variable remains available only in the same Terminal session;
otherwise set it to the directory you created earlier.

## 7. Confirm BOOT-at-power-on configuration

```sh
"$HOME/.cargo/bin/wlink" dump 0x1FFFF800 16
```

The development board already had BOOT-at-power-on enabled. Its recorded
option-byte block was:

```text
a5 5a f7 08 00 ff 00 ff ff 00 ff 00 ff 00 ff 00
```

The tested USER option byte was **0xF7**. This is a record of the tested
device, not a command to copy the entire option-byte block onto fresh chips.

**A fresh device also needs its power-on start mode configured to BOOT.**
The SDK names the setting `OB_PowerON_Start_Mode_BOOT`. The wlink flash
command in this guide does not set it. This guide records the verified
BOOT-programming procedure for boards with that configuration already
enabled; it does not provide a validated option-byte provisioning command
for blank factory devices.

For that separate provisioning step, consult
[BOOT_Explained.md](BOOT_Explained.md),
the [WCH family SDK](https://github.com/openwch/ch32v002_004_005_006_007),
and the [CH32V00X reference manual](https://www.wch-ic.com/downloads/CH32V00XRM_PDF.html).
Preserve the device's other option fields.

## 8. Power-cycle and test an application

After programming and verification, disconnect the programmer and
cold power-cycle Holt. Install the TerrainTronics board package using this
Additional Boards Manager URL:

```text
https://github.com/Audio-Rochey/TT-Holt-Castle-ArduinoBootloader/releases/download/arduino-0.1.0/package_terraintronics_index.json
```

Select **TerrainTronics Holt Castle (CH32V006, TT-Bootload)** and compile
Arduino's ordinary Blink example. The board core automatically includes the
application reset hook; no sketch changes or linker edits are needed.

Connect a 3.3 V logic USB-UART adapter:

| Adapter | Holt Castle |
| --- | --- |
| TX | PD6 / target RX |
| RX | PD5 / target TX |
| GND | GND |

Keep the board powered from its normal supply. Select the adapter's serial
port, close Serial Monitor, and click Upload. Press RESET when prompted.
If the existing application does not yet include the hook, cold power-cycle
instead to catch the bootloader entry window.

Confirm successful application upload and automatic application startup.
Then close the uploader/monitor and check both manual RESET and cold
power-on: Blink should start after approximately three seconds.

If no application is installed, the bootloader stays in IAP awaiting upload.
Receiving the UART entry phrase also cancels the timeout; an
`--enter-only` test therefore intentionally stays in IAP rather than
starting Blink after three seconds.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| `wlink: command not found` | Use `"$HOME/.cargo/bin/wlink"` or add that directory to PATH |
| Only wlink-iap is installed | Install ch32-rs/wlink; they serve different purposes |
| Programmer not found or busy | USB data cable, RISC-V mode, and no other programmer process |
| Wrong chip or target not detected | SWIO connection, common ground, board power, actual part marking |
| Bootloader readback differs | Programming address, exact BIN, wiring, and successful flash output |
| Manual reset starts the app immediately | Upload a sketch compiled with the TerrainTronics board core |
| Cold power-on skips BOOT | Check BOOT-at-power-on option configuration |
| No Blink with an empty application area | Upload an application; BOOT deliberately waits when no app is present |
| IAP stays active after an entry test | Entry phrase cancels timeout; reset/power-cycle without sending the phrase |

## References and validation

- [wlink source and installation instructions](https://github.com/ch32-rs/wlink)
- [wlink nightly binaries](https://github.com/ch32-rs/wlink/releases/tag/nightly)
- [Homebrew](https://brew.sh/)
- [WCH family SDK](https://github.com/openwch/ch32v002_004_005_006_007)
- [Project Arduino integration](Arduino/README.md)

BOOT programming and exact readback were confirmed on the development Holt
using WCH-LinkE and macOS. Boards Manager application compilation/upload was
confirmed on Apple Silicon Mac and Windows. Those results do not establish
a tested Windows wlink installation procedure or fresh-device option-byte
provisioning procedure.
