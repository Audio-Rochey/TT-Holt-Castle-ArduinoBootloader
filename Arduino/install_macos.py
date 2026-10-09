#!/usr/bin/env python3
"""Install the local Holt Arduino prototype without modifying WCH's package."""
import argparse
import hashlib
import json
import platform
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MARKER = "TT_HOLT_INSTALL.json"


def find_wch_core():
    base = Path.home() / "Library/Arduino15/packages/WCH/hardware/ch32"
    candidates = [p for p in base.glob("*") if (p / "platform.txt").is_file()]
    if len(candidates) != 1:
        versions = ", ".join(str(p) for p in candidates) or "none found"
        raise ValueError("Select your working WCH installation with --wch-core. "
                         f"Candidates: {versions}")
    return candidates[0]


def validate_core(source):
    required = ["boards.txt", "platform.txt", "cores/arduino/main.cpp",
                "cores/arduino/board.c", "system/CH32VM00X/SRC/Ld/Link.ld",
                "system/CH32VM00X/SRC/Peripheral/inc/ch32v00X.h",
                "variants/CH32VM00X/CH32V006K8/PeripheralPins.c",
                "variants/CH32VM00X/CH32V006K8/PinNamesVar.h"]
    for name in required:
        if not (source / name).is_file():
            raise ValueError(f"WCH core is missing {name}; use your working V006 core.")
    if not re.search(r"\bWEAK\s+void\s+pre_init\s*\(",
                     (source / "cores/arduino/board.c").read_text()):
        raise ValueError("Expected WCH's weak pre_init() startup hook.")
    if not re.search(r"\bpre_init\s*\(",
                     (source / "cores/arduino/main.cpp").read_text()):
        raise ValueError("WCH main() no longer calls pre_init(); integration needs review.")
    linker = re.sub(r"/\*.*?\*/", "", (source / required[4]).read_text(), flags=re.S)
    if not re.search(r"FLASH\s*\(rx\)\s*:\s*ORIGIN\s*=\s*0x0+\s*,\s*LENGTH\s*=\s*62K", linker):
        raise ValueError("Restore the stock V006 application linker (zero origin, 62K).")


def validate_uploader(uploader):
    header = uploader.read_bytes()[:8]
    if len(header) != 8 or header[:4] != b"\xcf\xfa\xed\xfe" or struct.unpack("<I", header[4:])[0] != 0x0100000C:
        raise ValueError("Uploader must be the tested native macOS arm64 executable.")
    result = subprocess.run([str(uploader), "--help"], capture_output=True, text=True)
    if result.returncode or "--port" not in result.stdout or "--baud" not in result.stdout:
        raise ValueError("Uploader --help failed or expected CLI arguments are missing.")


def install(source, uploader, destination, replace=False):
    source, uploader, destination = (p.expanduser().resolve() for p in
                                     (source, uploader, destination))
    if destination == source or source in destination.parents or destination in source.parents:
        raise ValueError("Destination must be separate from the installed WCH package.")
    validate_core(source)
    validate_uploader(uploader)
    if destination.exists() and not (replace and (destination / MARKER).is_file()):
        raise ValueError(f"Destination exists: {destination}. Use --replace only for a previous Holt install.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = destination.with_name(destination.name + ".tt-install-staging")
    if staging.exists():
        raise ValueError(f"Staging directory already exists: {staging}. Inspect/remove it before retrying.")
    try:
        shutil.copytree(source, staging, ignore=shutil.ignore_patterns(
            ".git", "__pycache__", "obj", "build", ".DS_Store"))
        overlay = HERE / "overlay"
        for p in sorted(overlay.rglob("*")):
            if not p.is_file() or p.name == "platform.local.txt":
                continue
            target = staging / p.relative_to(overlay)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, target)
        upstream_variant = source / "variants/CH32VM00X/CH32V006K8"
        target_variant = staging / "variants/CH32VM00X/HoltCastle"
        for name in ("PeripheralPins.c", "PinNamesVar.h"):
            shutil.copy2(upstream_variant / name, target_variant / name)
        local = staging / "platform.local.txt"
        inherited = local.read_text() if local.exists() else ""
        local.write_text(inherited + "\n" + (overlay / "platform.local.txt").read_text())
        tool = staging / "tools/ttupload/macos-arm64/tt-upload"
        tool.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(uploader, tool)
        tool.chmod(0o755)
        (staging / MARKER).write_text(json.dumps({
            "platform_version": "0.1.0", "wch_source": str(source),
            "host": "macos-arm64", "uploader_sha256": hashlib.sha256(tool.read_bytes()).hexdigest()
        }, indent=2) + "\n")
        if destination.exists():
            shutil.rmtree(destination)
        staging.rename(destination)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wch-core", type=Path, help="Path to your working WCH/ch32/version platform")
    parser.add_argument("--uploader", type=Path, default=HERE.parent / "SerialUploader/dist/tt-upload")
    parser.add_argument("--sketchbook", type=Path, default=Path.home() / "Documents/Arduino",
                        help="Match Arduino IDE's Sketchbook location preference")
    parser.add_argument("--replace", action="store_true", help="Replace a previous managed Holt installation")
    args = parser.parse_args()
    if sys.platform != "darwin" or platform.machine() != "arm64":
        parser.error("This first installer supports Apple Silicon macOS only.")
    try:
        source = args.wch_core or find_wch_core()
        destination = install(source, args.uploader,
                              args.sketchbook / "hardware/TerrainTronics/ch32", args.replace)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, f"Install failed: {error}\n")
    print(f"Installed: {destination}")
    print("Restart Arduino IDE. Select TerrainTronics Holt Castle and your UART port.")
    print("Compile an ordinary Blink sketch, click Upload, then press RESET when prompted.")


if __name__ == "__main__":
    main()
