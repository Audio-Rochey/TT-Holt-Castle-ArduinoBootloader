# Holt Castle Boards Manager release 0.1.0

This first release targets Apple Silicon Macs. It packages the user's working WCH 1.0.4 platform snapshot and tested standalone UART uploader. Blink, Fade, UART uploads, and the three-second wait after manual reset and cold power-on were confirmed on the Holt Castle. The Boards Manager distribution still needs a clean Mac install test.


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

## Release files

- `holt-castle-0.1.0.tar.gz`: board core, pin variant, standard linker, and automatic application reset hook.
- `tt-upload-0.1.0-macos-arm64.tar.gz`: standalone uploader; customers need no Python installation.
- `package_terraintronics_index.json`: Boards Manager index with actual archive sizes and SHA-256 checksums.
- `SHA256SUMS.txt`: checksums for release assets.

Finder metadata, the local installation marker, and the old bundled uploader are excluded. The tested source core is otherwise preserved. WCH compiler metadata is pinned to its official 8.2.0 entry; its Intel Mac compiler requires Rosetta on Apple Silicon. Intel Mac uploader, Windows, and Linux support are not included yet.

## Publish

Create a GitHub release with tag `arduino-0.1.0` and attach all four files from `Arduino/release-assets`. The index URLs point to that exact release tag. Do not change the archives after publishing without updating the version and checksums.

Customers can then add this URL in Arduino IDE Settings → Additional Boards Manager URLs:

```
https://github.com/Audio-Rochey/TT-Holt-Castle-ArduinoBootloader/releases/download/arduino-0.1.0/package_terraintronics_index.json
```

Search Boards Manager for **TerrainTronics Holt Castle**, install, and select **TerrainTronics Holt Castle (CH32V006, TT-Bootload)**. Select the serial port, click Upload, and press RESET when prompted. No application linker changes or sketch hook are needed: the board core includes the reset hook automatically.

This URL only works once the release and assets are published. Terraintronics.com can link to the same GitHub release. For future releases, host a stable copy of the package index on the repository main branch or terraintronics.com and update it to list all published versions.

## Existing prototype installation

Quit Arduino IDE. Move the existing `hardware/TerrainTronics/ch32` folder outside the sketchbook hardware directory before testing Boards Manager, retaining it as a backup. This avoids two installations with the same board identity. Keep the original WCH installation intact until the new package is verified.

On this Mac, the prototype folder is:

```
/Users/dafyddroche/Library/CloudStorage/Dropbox/Arduino/hardware/TerrainTronics/ch32
```

Test Blink compilation and UART upload, Fade, manual reset, and cold power-on. Both reset methods should wait about three seconds before the application starts. Also test on a clean Mac profile so the compiler is downloaded rather than inherited from the existing WCH installation.

## Bootloader prerequisite and recovery

Boards Manager installs application development tools; it does not initially program the chip's BOOT area. The board must already contain `TT_Bootload_Arduino_3s.bin` with BOOT-at-power-on configured. Normal UART uploads write the application area only. If the existing application lacks the hook, power-cycle to enter TT-Bootload for its first upload. If an upload is interrupted, try a cold power-cycle and upload again; SWIO/WCH-Link provides recovery if necessary.

## Rebuild

From the repository root:

```
python3 Arduino/release/build_release.py --platform /path/to/Archive.zip --uploader /path/to/tt-upload --output Arduino/release-assets
```

The script accepts the tested platform ZIP and an arm64 Mach-O uploader, generates both archives, and calculates the index checksums. It does not publish anything. Windows and Linux can later be added as additional `systems` entries for the uploader without changing the board reset hook or linker.
