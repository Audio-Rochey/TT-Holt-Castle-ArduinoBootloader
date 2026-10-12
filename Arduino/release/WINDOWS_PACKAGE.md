# Add Windows to Boards Manager 0.1.0

The Windows x86-64 standalone uploader was confirmed to upload a Blink application over COM7. The existing board platform already defines `tt-upload.exe` for Windows; no core or firmware changes are required. Arduino IDE installation, compilation and upload on Windows still need testing after publication.

This update adds `x86_64-mingw32` to the `tt-upload` 0.1.0 tool in the package index. The existing Apple Silicon uploader and board core URLs, sizes and checksums are preserved. Windows on ARM and 32-bit Windows are not validated. Linux is not enabled yet.

## Publish the Windows assets

After merging this PR, edit the existing GitHub release tagged `arduino-0.1.0`:

1. Attach `tt-upload-0.1.0-windows-x86_64.tar.gz`, keeping it compressed.
2. Remove only the existing `package_terraintronics_index.json` release attachment and upload the updated file with that same name. Existing Mac users can keep their installed package; do not replace the Mac or core archives.
3. Replace the existing `SHA256SUMS.txt` attachment with the supplied updated file. It includes the unchanged core/Mac hashes, the new Windows archive, and the updated index. The optional `SHA256SUMS-windows.txt` also records the unpacked EXE hash.
4. Save the release changes. Update the description to include Windows x86-64 and distinguish tested standalone upload from pending Windows IDE integration testing.

Customers keep the same Additional Boards Manager URL:

```
https://github.com/Audio-Rochey/TT-Holt-Castle-ArduinoBootloader/releases/download/arduino-0.1.0/package_terraintronics_index.json
```

Publishing an additional host archive and index entry extends host availability without changing any existing platform or tool binary. Do not overwrite existing binaries under the same version.

## Test Windows Arduino IDE

Add the index URL to Settings/Preferences → Additional Boards Manager URLs. Refresh Boards Manager and install **TerrainTronics Holt Castle** version 0.1.0. If a previous attempt failed, restart Arduino IDE and try the installation again after the index is updated.

Select **TerrainTronics Holt Castle (CH32V006, TT-Bootload)** and **COM7** (or the actual adapter port). Compile ordinary Blink, then click Upload and press RESET when prompted. Confirm application startup and the three-second pause after both manual reset and cold power-on. Close Serial Monitor before upload. Keep the original WCH installation intact until this test passes; isolated-profile testing is still useful to catch inherited dependencies.

The package includes the working WCH core snapshot and its register updates/local fixes. Customers do not need the separate WCH board package. Boards Manager downloads the compiler dependency and this standalone EXE automatically; no customer Python installation or sketch hook is required. TT-Bootload must already be installed on the board.

## Rebuild this host addition

From the repository root, starting with the original Mac-only index:

```
python3 Arduino/release/add_windows_tool.py --index /path/to/mac-only/package_terraintronics_index.json --uploader SerialUploader/dist/tt-upload.exe --output Arduino/windows-release-assets
```

The script verifies the Windows PE x86-64 architecture and packages the executable with fixed metadata. It adds the actual archive checksum and size without rebuilding Mac assets. It refuses an index that already includes this Windows host. The original `build_release.py` generates a Mac-only index, so do not use that output to replace a published combined index without applying this host addition.
