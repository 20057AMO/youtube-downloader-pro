"""
FFmpeg Static Binary Installer
Downloads a static ffmpeg build for the current platform.
"""

import urllib.request
import tarfile
import os
import sys
import shutil
from pathlib import Path


def get_bin_dir():
    """Get the bin directory relative to the script's venv."""
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        return Path(sys.prefix) / "bin"
    return Path(__file__).parent / "venv" / "bin"


def install_ffmpeg():
    url = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
    bin_dir = get_bin_dir()
    bin_dir.mkdir(parents=True, exist_ok=True)

    tar_path = Path(__file__).parent / "ffmpeg.tar.xz"

    print(f"Downloading ffmpeg to {tar_path}...")
    urllib.request.urlretrieve(url, tar_path)

    print("Extracting ffmpeg and ffprobe...")
    with tarfile.open(tar_path, "r:xz") as tar:
        for member in tar.getmembers():
            if member.name.endswith("/ffmpeg") or member.name.endswith("/ffprobe"):
                member.name = os.path.basename(member.name)
                tar.extract(member, path=str(bin_dir))

    print("Cleaning up...")
    tar_path.unlink(missing_ok=True)

    for binary in ["ffmpeg", "ffprobe"]:
        target = bin_dir / binary
        if target.exists():
            target.chmod(0o755)
            print(f"  Installed: {target}")

    print("Done!")


if __name__ == "__main__":
    install_ffmpeg()
