"""PyInstaller build script for DictateMe.

Produces a single-directory distribution (or single .exe) with all
dependencies bundled. Run from the project root:

    python scripts/build.py

The output goes to dist/DictateMe/
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"
ENTRY_POINT = PROJECT_ROOT / "src" / "dictateme" / "__main__.py"
ICON_SCRIPT = None  # Will generate if needed
APP_NAME = "DictateMe"


def clean() -> None:
    """Remove previous build artifacts."""
    for d in [DIST_DIR, BUILD_DIR]:
        if d.exists():
            shutil.rmtree(d)
            print(f"Cleaned {d}")


def build() -> None:
    """Run PyInstaller to create the distribution."""
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", APP_NAME,
        "--noconfirm",
        "--clean",
        # Windowed app (no console window)
        "--windowed",
        # Add the source package
        "--paths", str(PROJECT_ROOT / "src"),
        # Bundle the default config
        "--add-data", f"{PROJECT_ROOT / 'config.default.toml'};.",
        # Hidden imports that PyInstaller can't detect
        "--hidden-import", "faster_whisper",
        "--hidden-import", "ctranslate2",
        "--hidden-import", "sounddevice",
        "--hidden-import", "litellm",
        "--hidden-import", "keyboard",
        "--hidden-import", "pystray",
        "--hidden-import", "win32clipboard",
        "--hidden-import", "win32api",
        "--hidden-import", "win32process",
        "--hidden-import", "win32con",
        "--hidden-import", "webview",
        "--hidden-import", "clr_loader",
        "--hidden-import", "psutil",
        # Exclude unnecessary large packages
        "--exclude-module", "matplotlib",
        "--exclude-module", "scipy",
        "--exclude-module", "pandas",
        "--exclude-module", "IPython",
        "--exclude-module", "jupyter",
        "--exclude-module", "notebook",
        # Entry point
        str(ENTRY_POINT),
    ]

    print(f"Running: {' '.join(cmd[:6])}...")
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))

    if result.returncode != 0:
        print(f"Build failed with exit code {result.returncode}")
        sys.exit(1)

    print(f"\nBuild complete! Output: {DIST_DIR / APP_NAME}")
    print(f"Run with: {DIST_DIR / APP_NAME / 'DictateMe.exe'}")


def create_portable_zip() -> None:
    """Create a portable .zip archive of the distribution."""
    dist_path = DIST_DIR / APP_NAME
    if not dist_path.exists():
        print("Distribution not found. Run build first.")
        return

    zip_path = DIST_DIR / f"{APP_NAME}-v0.1.0-win64"
    shutil.make_archive(str(zip_path), "zip", str(DIST_DIR), APP_NAME)
    print(f"Created: {zip_path}.zip")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build DictateMe for distribution")
    parser.add_argument("--clean", action="store_true", help="Clean build artifacts only")
    parser.add_argument("--zip", action="store_true", help="Also create portable .zip")
    args = parser.parse_args()

    if args.clean:
        clean()
    else:
        clean()
        build()
        if args.zip:
            create_portable_zip()
