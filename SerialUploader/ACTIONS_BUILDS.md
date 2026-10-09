# Build Mac and Linux uploaders on GitHub

Open the repository's Actions tab and select **Build Mac and Linux UART uploaders**. Click **Run workflow**, choose `main`, and select `macos-arm64`, `linux-x86_64`, or `both`. The default builds only the Apple Silicon Mac version. These builds run only when requested.

When the run completes, open its Summary and download the corresponding artifact from the Artifacts section. The downloaded ZIP contains a `.tar.gz` archive. Extract that archive to obtain `tt-upload/tt-upload` and `tt-upload/SHA256SUMS.txt`. The tar archive preserves executable permissions. Save the download; GitHub artifacts expire after 30 days.

The workflows use Python 3.12, PyInstaller 6.22.3, and pyserial 3.5. Each verifies its runner architecture and launches the compiled executable with `--help`. These checks do not test UART hardware. The Windows workflow remains available separately and uses the updated Node 24 artifact action.

## Mac testing

The Mac target is ARM64, built on macOS 15. Treat macOS 15 as the initial supported baseline until older systems are tested. Intel Macs are not included. The executable has no Developer ID signature or notarization configured.

From the extracted folder:

```sh
./tt-upload --help
./tt-upload --port /dev/cu.YOUR_SERIAL_PORT --baud 460800 /path/to/application.bin
```

Close Serial Monitor and press RESET when prompted. Confirm upload completion and application startup, plus the three-second pause after manual reset and cold power-on. Keep the already tested Mac executable until the Actions-built replacement passes these checks.

## Linux testing

The Linux target is x86-64, built on Ubuntu 22.04 (glibc 2.35). Older glibc systems and ARM Linux are not supported by this build. Hardware serial permissions and compatibility with other distributions require testing.

```sh
./tt-upload --help
./tt-upload --port /dev/ttyUSB0 --baud 460800 /path/to/application.bin
```

Use the actual adapter port, which may be `/dev/ttyACM0`. Ensure your account can access it, close Serial Monitor, and press RESET when prompted. Verify the same upload/startup/reset behavior as on Mac.

These workflows do not publish releases or update the Boards Manager index. Build artifacts must be hardware-tested and packaged with versioned URLs and checksums before customer distribution. The Python uploader source and working board package are unchanged.
