#!/usr/bin/env python3
"""
Build script for GS_VolumeManager (gs_vol_gui.py)

Usage:
    python build_gs_volumemanager.py          # build release executable
    python build_gs_volumemanager.py --clean  # remove build/dist first

Output:
    dist/GS_VolumeManager          (Linux)
    dist/GS_VolumeManager.exe      (Windows)
"""

import sys
import os
import shutil
import subprocess
import argparse


SPEC_FILE = "GS_VolumeManager.spec"
DIST_DIR  = "dist"
BUILD_DIR = "build"

REQUIRED_PACKAGES = ["pyinstaller", "requests"]


def run(cmd, **kwargs):
    print(f"  > {' '.join(str(c) for c in cmd)}")
    subprocess.check_call(cmd, **kwargs)


def ensure_packages():
    for pkg in REQUIRED_PACKAGES:
        try:
            __import__(pkg.replace("-", "_"))
        except ImportError:
            print(f"Installing {pkg} ...")
            cmd = [sys.executable, "-m", "pip", "install", pkg]
            if not sys.platform.startswith("win"):
                cmd.append("--break-system-packages")
            run(cmd)


def clean():
    for d in (DIST_DIR, BUILD_DIR):
        if os.path.exists(d):
            print(f"Removing {d}/")
            shutil.rmtree(d)


def build():
    # Check entry point and spec exist
    if not os.path.exists("gs_vol_gui.py"):
        print("ERROR: gs_vol_gui.py not found. Run this script from the SDS directory.")
        sys.exit(1)
    if not os.path.exists(SPEC_FILE):
        print(f"ERROR: {SPEC_FILE} not found.")
        sys.exit(1)

    run([sys.executable, "-m", "PyInstaller", "--clean", SPEC_FILE])

    # Locate the output binary
    exe_name = "GS_VolumeManager.exe" if sys.platform.startswith("win") else "GS_VolumeManager"
    output = os.path.join(DIST_DIR, exe_name)

    if os.path.exists(output):
        size_mb = os.path.getsize(output) / (1024 * 1024)
        print(f"\nBuild successful!")
        print(f"  Output : {os.path.abspath(output)}")
        print(f"  Size   : {size_mb:.1f} MB")
    else:
        print(f"\nWARNING: expected output not found at {output}")
        print("Check PyInstaller output above for errors.")


def main():
    parser = argparse.ArgumentParser(description="Build GS_VolumeManager executable")
    parser.add_argument("--clean", action="store_true",
                        help="Remove build/ and dist/ before building")
    args = parser.parse_args()

    print("=== GS_VolumeManager build ===")
    print(f"Platform : {sys.platform}")
    print(f"Python   : {sys.version.split()[0]}")
    print()

    ensure_packages()

    if args.clean:
        clean()

    build()


if __name__ == "__main__":
    main()
