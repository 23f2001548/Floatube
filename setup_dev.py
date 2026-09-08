"""
Floatube — Developer Setup Script
Creates a virtual environment, installs dependencies, downloads mpv DLL.
Run once after cloning:  python setup_dev.py
"""

import os
import sys
import subprocess
import urllib.request
import zipfile
import shutil

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(PROJECT_DIR, "venv")
ASSETS_DIR = os.path.join(PROJECT_DIR, "assets")
REQUIREMENTS = os.path.join(PROJECT_DIR, "requirements.txt")

# mpv dev build for Windows (x86_64)
MPV_URL = "https://sourceforge.net/projects/mpv-player-windows/files/libmpv/mpv-dev-x86_64-20240121-git-a39f9b6.7z/download"
MPV_DLL_NAME = "mpv-2.dll"  # Newer builds use mpv-2.dll


def main():
    print("=" * 60)
    print("  Floatube — Developer Setup")
    print("=" * 60)
    print()

    # Determine python/pip paths
    if sys.platform == "win32":
        pip = os.path.join(VENV_DIR, "Scripts", "pip.exe")
        python = os.path.join(VENV_DIR, "Scripts", "python.exe")
    else:
        pip = os.path.join(VENV_DIR, "bin", "pip")
        python = os.path.join(VENV_DIR, "bin", "python")

    # Step 1: Create virtual environment
    if not os.path.exists(VENV_DIR):
        print("[1/3] Creating virtual environment...")
        subprocess.run([sys.executable, "-m", "venv", VENV_DIR], check=True)
        print("      Done - Virtual environment created at ./venv")
    else:
        print("[1/3] Virtual environment already exists.")

    # Step 2: Install dependencies
    print("[2/3] Installing Python dependencies...")
    subprocess.run([python, "-m", "pip", "install", "--upgrade", "pip"],
                   check=True, capture_output=True)
    subprocess.run([pip, "install", "-r", REQUIREMENTS], check=True)
    print("      Done - All dependencies installed")

    # Step 3: Ensure assets directory exists
    os.makedirs(ASSETS_DIR, exist_ok=True)

    # Check if mpv DLL exists
    mpv_paths = [
        os.path.join(PROJECT_DIR, "mpv-1.dll"),
        os.path.join(PROJECT_DIR, "mpv-2.dll"),
        os.path.join(PROJECT_DIR, "libmpv-2.dll"),
        os.path.join(ASSETS_DIR, "mpv-1.dll"),
        os.path.join(ASSETS_DIR, "mpv-2.dll"),
    ]
    mpv_found = any(os.path.exists(p) for p in mpv_paths)

    if mpv_found:
        print("[3/3] mpv DLL already found ✓")
    else:
        print("[3/3] mpv DLL not found.")
        print("      Please download mpv manually:")
        print()
        print("      Option A (Recommended):")
        print("        1. Go to: https://sourceforge.net/projects/mpv-player-windows/files/libmpv/")
        print("        2. Download the latest 'mpv-dev-x86_64-*.7z'")
        print("        3. Extract 'mpv-2.dll' (or 'mpv-1.dll') to this project folder")
        print()
        print("      Option B:")
        print("        pip install mpv  (inside venv)")
        print("        This may include the DLL depending on your platform.")
        print()
        print("      ⚠  Without the mpv DLL, audio playback will not work.")

    print()
    print("=" * 60)
    print("  Setup complete!")
    print()
    print("  To run Floatube:")
    if sys.platform == "win32":
        print(f"    .\\venv\\Scripts\\python main.py")
    else:
        print(f"    ./venv/bin/python main.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
