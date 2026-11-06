#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "Starting YouTube Downloader Pro Setup for Linux/macOS..."
echo "========================================================"

if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 was not found. Install Python 3.10+ and try again." >&2
    exit 1
fi

if ! python3 -c 'import venv, ensurepip' >/dev/null 2>&1; then
    echo "ERROR: python3 cannot create virtual environments (venv/ensurepip missing)." >&2
    echo "  Debian/Ubuntu: sudo apt install python3-venv" >&2
    echo "  Fedora/RHEL:   sudo dnf install python3" >&2
    exit 1
fi

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

echo "Activating virtual environment..."
# shellcheck disable=SC1091
source venv/bin/activate

echo "Installing dependencies..."
python -m pip install --upgrade pip
pip install -r requirements.txt

echo "Checking for FFmpeg..."
if ! python install_ffmpeg.py; then
    echo "WARNING: automatic FFmpeg installation failed." >&2
    echo "         yt-dlp cannot merge separate video/audio streams without it." >&2
    echo "         Install FFmpeg manually (e.g. apt install ffmpeg or brew install ffmpeg)." >&2
fi

echo "Starting the application..."
exec python app.py
