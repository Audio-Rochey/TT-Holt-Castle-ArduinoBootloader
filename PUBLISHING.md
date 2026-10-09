# Create the GitHub project

Suggested repository name: **TT-Bootload**

Suggested description:

> UART bootloader for the TerrainTronics Holt CH32V006: standard Arduino
> compilation, manual-reset entry, and Python application uploads.

Create an empty repository on GitHub. Leave automatic README, .gitignore and
license generation unchecked; this package supplies the first two, and a
project license has not yet been selected.

Extract the ZIP and open a terminal in its `TT-Bootload` directory. Publish the
contents as the repository root, so README.md and upload.py appear at the top
level. The archive includes hidden MounRiver metadata files; Git includes them
even when Finder does not display them.

```sh
git init -b main
git add .
git commit -m "Add TT-Bootload v0.4 for Holt CH32V006"
git remote add origin https://github.com/YOUR_ACCOUNT/TT-Bootload.git
git push -u origin main
```

Replace `YOUR_ACCOUNT`. Create the empty remote repository before running these
commands; they do not create it.

Create a release tagged `v0.4`, use RELEASE_NOTES.md as its description, and attach:

- `firmware/TT_Bootload_Arduino_3s.bin`

GitHub supplies a source ZIP for the tag. The one Arduino example is
`Examples/CH32V006TTBootloader/CH32V006TTBootloader.ino`; compile it in Arduino IDE
when an application BIN is needed.

Suggested future issues:

- Include the reset hook automatically through a TT Arduino board package.
- Integrate the Python uploader with Arduino IDE's Upload action.
- Evaluate a shorter entry window after more customer testing.
- Add complete-image validation and interrupted-upload recovery tests.
- Select and document the license for TerrainTronics-authored material.
