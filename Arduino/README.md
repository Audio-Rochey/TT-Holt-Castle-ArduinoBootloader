# Holt Castle Arduino integration — Apple Silicon prototype

Selecting **TerrainTronics Holt Castle** includes the bootloader reset hook in
every normal Arduino build. Arduino's Upload button runs the tested standalone
`tt-upload` executable. Customer sketches need no bootloader code or linker edits.
TT-Bootload v0.4 must already be installed and BOOT-at-power-on configured.

This is a local prototype for testing, not yet a downloadable Boards Manager
release. It uses your working installed WCH platform and compiler, preserving
any fixes you already made for your Mac. It copies that platform to a separate
TerrainTronics sketchbook platform; the original WCH installation is unchanged.

## Install on your Mac

Keep your tested executable at `SerialUploader/dist/tt-upload`. In Terminal:

```sh
cd "$HOME/Documents/github/TT-Holt-Castle-ArduinoBootloader"
python3 Arduino/install_macos.py
```

The script defaults to the sketchbook at `~/Documents/Arduino`. If Arduino IDE
Settings shows a different Sketchbook location, specify it:

```sh
python3 Arduino/install_macos.py --sketchbook "/your/actual/sketchbook"
```

If there are multiple installed WCH versions, choose the one you successfully
compiled with, using its actual version directory:

```sh
python3 Arduino/install_macos.py --wch-core "$HOME/Library/Arduino15/packages/WCH/hardware/ch32/ACTUAL_VERSION"
```

Restart Arduino IDE. Select **Tools → Board → TerrainTronics Holt Castle**
(the platform and board menu names may form a submenu), select your UART port,
and leave the clock at its default 48 MHz internal setting.

The installer validates the WCH startup interface, original zero-address V006
application linker, and uploader architecture/CLI before installation. It does
not change BOOT firmware, option bytes, or SerialUploader/upload.py.

## Test without any hook in the sketch

Use Arduino's standard Blink example, or this ordinary sketch:

```cpp
void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
}
void loop() {
  digitalWrite(LED_BUILTIN, HIGH);
  delay(250);
  digitalWrite(LED_BUILTIN, LOW);
  delay(250);
}
```

Click **Upload**, then press RESET when the output asks you to. If the currently
installed sketch lacks the hook, cold power-cycle for this first upload. Once
this Holt build is installed, close the uploader/monitor and press reset: expect
about three seconds before blinking. Upload the same ordinary sketch again
using just RESET. This verifies that the hook is retained in a sketch with no
explicit reference to it. Test a second arbitrary sketch as well.

Blink, Fade, UART uploads, and the three-second wait after manual reset and cold power-on have been confirmed on the Holt Castle. See [Boards Manager release packaging](release/README.md) for the downloadable Mac package; its clean-install test remains outstanding.

## How automatic entry is included

WCH's Arduino `main()` calls a weak `pre_init()` before `setup()`. The overlay
adds a strong `pre_init()` in `cores/arduino/tt_bootload_hook.c`. WCH's link recipe
includes the core archive with `--whole-archive`, retaining the hook even when
the sketch never calls it.

The hook reads/clears reset flags. On an external-only reset, it selects BOOT
and software-resets. For the software reset used by TT-Bootload to return to
USER, it continues normal WCH `hw_config_init()` and then `setup()`. The original
WCH startup/clock configuration and application linker remain in use.

Do not override `pre_init()` in a customer sketch: the core owns that startup
entry point. Selecting the stock WCH board instead of Holt will omit our hook.
Omission does not permanently brick a BOOT-at-power-on-configured device:
cold power-on remains a recovery path. SWIO remains available for development.

## Pins from HoltCastle006PG3p0

| Arduino name | MCU pin | Connection |
| --- | --- | --- |
| D0 | PD0 | Wemos-footprint D0 |
| D1 / SCL | PC2 | I2C clock |
| D2 / SDA | PC1 | I2C data |
| D3 | PD3 | Header |
| D4 | PD4 | Header |
| D5 / SCK | PC5 | SPI clock |
| D6 / MISO | PC7 | SPI input |
| D7 / MOSI | PC6 | SPI output |
| D8 / SS | PC0 | Software-managed chip select |
| A0 | PA2 | Analog header |
| LED_BUILTIN | PD2 | LEDOUT and NeoPixel level-shifter input |
| Serial TX | PD5 | UART TX |
| Serial RX | PD6 | UART RX |
| HOLT_KEEPALIVE | PC4 | Powerbank keepalive transistor |

**LED_BUILTIN is PD2, not D0.** Driving it also drives the schematic's NeoPixel
level shifter. PA1 is a test pad; PC3 is a test point. PD1 is SWIO and PD7 is
RESET; leave these reserved for programming/reset. The variant uses only the
package's physical GPIOs. Its numeric GPIO indexing differs from WCH's generic
K8 variant; use the named pin constants. Peripheral mappings other than Blink
need hardware verification. For SPI, manage D8 chip select in the sketch; it is
not the peripheral's default hardware NSS pin (PC4).

## Windows and Linux later

The board/MCU code, pin mapping, protocol and argument names stay the same.
The upload recipe uses the selected serial port and compiled BIN; no Mac port
name or user directory is hardcoded in it. Platform properties select host
paths for macOS arm64, Windows x86-64 and Linux x86-64. Only the Mac executable
is installed by this prototype; the other host paths are reserved for later
tested builds. Intel Macs and Linux ARM need additional host packages.

For customer distribution, build/package each uploader with its runtime,
declare compiler and uploader dependencies in a Boards Manager index, and
test a clean installation per host. Mac signing/notarization and the supported
Linux runtime baseline should be decided for public releases. Keep one uploader
CLI: `--port PORT --baud BAUD application.bin`. Avoid making customers edit
WCH's boards.txt/platform.txt, install pip packages, or modify linkers.

## Updating and removing the prototype

Reinstall overlay changes using `python3 Arduino/install_macos.py --replace`.
Restart Arduino IDE afterwards. The copied WCH snapshot does not automatically
change when Boards Manager updates WCH; reinstall explicitly and retest.

To remove, close Arduino IDE and delete only the managed platform folder:
`<your-sketchbook>/hardware/TerrainTronics/ch32`. Keep the WCH package installed
because the prototype uses its compiler tools. Installation provenance and the
uploader checksum are recorded in `TT_HOLT_INSTALL.json` inside the copied
platform. Upstream vendor notices are preserved.
