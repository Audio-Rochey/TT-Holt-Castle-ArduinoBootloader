"""Build on the target OS; bundle pinned tools and firmware, then smoke-test."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from backend import APP_VERSION

ROOT = Path(__file__).resolve().parent
REVISION = "626d11a2b85a6487b1e81730eade843583526226"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wlink", required=True, type=Path)
    parser.add_argument("--options", required=True, type=Path)
    args = parser.parse_args()
    # Arguments are relative to the caller's directory, not the app directory.
    args.wlink = args.wlink.resolve()
    args.options = args.options.resolve()
    os.chdir(ROOT)
    if sys.platform not in ("darwin", "win32"):
        parser.error("Build on Apple Silicon macOS or Windows x64")
    if sys.platform == "darwin" and platform.machine() != "arm64":
        parser.error("Use an Apple Silicon Python interpreter")
    suffix = ".exe" if os.name == "nt" else ""
    staging = ROOT / "build" / "staging"
    if staging.exists():
        shutil.rmtree(staging)
    (staging / "vendor").mkdir(parents=True)
    shutil.copytree(ROOT / "resources", staging / "resources")
    for source, name in [(args.wlink.resolve(), "wlink"), (args.options.resolve(), "holt-options")]:
        destination = staging / "vendor" / (name + suffix)
        shutil.copy2(source, destination)
        subprocess.run([str(destination), "--help"], check=True, capture_output=True)
    shutil.copy2(ROOT.parent / "firmware" / "TT_Bootload_Arduino_3s.bin", staging / "resources")
    shutil.copy2(ROOT / "README.md", staging / "resources" / "USER-GUIDE.md")
    # Include installed distribution notices in the packaged app.
    license_root = staging / "resources" / "licenses"
    for package in ["PySide6", "PySide6_Essentials", "shiboken6", "pyserial", "PyInstaller"]:
        distribution = importlib.metadata.distribution(package)
        for relative in distribution.files or []:
            if any(word in str(relative).lower() for word in ["license", "copying"]):
                source = Path(distribution.locate_file(relative))
                if source.is_file() and source.suffix not in (".py", ".pyc"):
                    destination = license_root / package / str(relative)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)
    manifest = {"version": APP_VERSION + "-prototype", "wlink_revision": REVISION, "sha256": {}}
    for relative in ["vendor/wlink" + suffix, "vendor/holt-options" + suffix,
                     "resources/TT_Bootload_Arduino_3s.bin"]:
        manifest["sha256"][relative] = hashlib.sha256((staging / relative).read_bytes()).hexdigest()
    (staging / "resources" / "manifest.json").write_text(json.dumps(manifest, indent=2))
    command = [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm", "--onedir",
               "--windowed", "--name", "Holt Programmer", "--distpath", str(ROOT / "dist"),
               "--workpath", str(ROOT / "build" / "pyinstaller"),
               "--add-data", f"{staging / 'resources'}:resources",
               "--add-binary", f"{staging / 'vendor' / ('wlink' + suffix)}:vendor",
               "--add-binary", f"{staging / 'vendor' / ('holt-options' + suffix)}:vendor",
               "--exclude-module", "PySide6.QtQml", "--exclude-module", "PySide6.QtQuick",
               "--exclude-module", "PySide6.QtWebEngineCore", "--exclude-module", "PySide6.QtWebEngineWidgets"]
    if sys.platform == "darwin":
        command += ["--target-arch", "arm64", "--osx-bundle-identifier", "com.terraintronics.holtprogrammer"]
    build_env = os.environ.copy()
    build_env["PYINSTALLER_CONFIG_DIR"] = str(ROOT / "build" / "cache")
    subprocess.run(command + ["app.py"], check=True, env=build_env)
    if sys.platform == "darwin":
        executable = ROOT / "dist" / "Holt Programmer.app" / "Contents" / "MacOS" / "Holt Programmer"
        packaged_root = executable.parent.parent / "Frameworks"
    else:
        executable = ROOT / "dist" / "Holt Programmer" / "Holt Programmer.exe"
        packaged_root = executable.parent / "_internal"
    # Mach-O signing modifies native executable bytes during packaging. Record
    # the actual packaged hashes, then renew only the outer app signature.
    for relative in manifest["sha256"]:
        manifest["sha256"][relative] = hashlib.sha256((packaged_root / relative).read_bytes()).hexdigest()
    (packaged_root / "resources" / "manifest.json").write_text(json.dumps(manifest, indent=2))
    if sys.platform == "darwin":
        subprocess.run(["codesign", "--force", "--sign", "-", str(executable.parent.parent.parent)], check=True)
    subprocess.run([str(executable), "--smoke-test"], check=True, timeout=60)
    print(f"Built and smoke-tested: {executable}")


if __name__ == "__main__":
    main()
