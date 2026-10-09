# Build the Windows uploader from your Mac

GitHub Actions runs the build on a temporary Windows x64 machine. No Windows or Python installation is needed on your Mac.

1. Merge the Windows uploader workflow PR into main.
2. Open the repository Actions tab. Enable workflows if GitHub prompts you.
3. Select **Build Windows UART uploader** in the left sidebar.
4. Click **Run workflow**, leave the branch set to **main**, then click the green **Run workflow** button.
5. Refresh until the new run appears. Open it and wait for a green check mark. If it fails, open the build job and its red step to read the error.
6. On the completed run page, scroll to **Artifacts** and click **tt-upload-windows-x86_64**. GitHub downloads a ZIP containing `tt-upload.exe` and `SHA256SUMS.txt`. Artifacts expire after 30 days; save the ZIP locally. You must be signed in to download it.

The workflow builds the existing upload.py with Python 3.12 x64, PyInstaller 6.22.3 and pyserial 3.5, checks `--help`, then stores the executable and checksum. It does not change upload.py or publish a release. The launch check does not test serial hardware.

## Hardware test on Windows

Extract the ZIP, open PowerShell in that folder, and run:

```powershell
.\tt-upload.exe --help
.\tt-upload.exe --port COM5 --baud 460800 "$HOME\Downloads\CH32V006TTBootloader.ino.bin"
```

Replace COM5 and the firmware path with your actual port and BIN. Close Arduino Serial Monitor before uploading. Press RESET when prompted. Confirm successful upload, application startup, and the three-second wait after manual reset and cold power-on. Test on Windows without Python installed to verify the executable is standalone.

After testing, package the Windows executable and add its host archive to the Boards Manager index. An Actions ZIP is a temporary build download, not a published Boards Manager tool package. Keep the existing Mac release unchanged until Windows packaging is ready.
