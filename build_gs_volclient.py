#!/usr/bin/env python3
"""
Build script for GS_VolClient (gs_vol_gui.py)

Usage:
    python build_gs_volclient.py          # build release executable
    python build_gs_volclient.py --clean  # remove build/dist first

Output:
    dist/GS_VolClient          (Linux)
    dist/GS_VolClient.exe      (Windows)
"""

import sys
import os
import shutil
import subprocess
import argparse


SPEC_FILE = "GS_VolClient.spec"
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
            run([sys.executable, "-m", "pip", "install", pkg,
                 "--break-system-packages"])


def clean():
    for d in (DIST_DIR, BUILD_DIR):
        if os.path.exists(d):
            print(f"Removing {d}/")
            shutil.rmtree(d)
    for f in ("GS_VolClient.spec",):
        pass  # keep the spec; only remove build artefacts


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
    exe_name = "GS_VolClient.exe" if sys.platform.startswith("win") else "GS_VolClient"
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
    parser = argparse.ArgumentParser(description="Build GS_VolClient executable")
    parser.add_argument("--clean", action="store_true",
                        help="Remove build/ and dist/ before building")
    args = parser.parse_args()

    print("=== GS_VolClient build ===")
    print(f"Platform : {sys.platform}")
    print(f"Python   : {sys.version.split()[0]}")
    print()

    ensure_packages()

    if args.clean:
        clean()

    build()


if __name__ == "__main__":
    main()
