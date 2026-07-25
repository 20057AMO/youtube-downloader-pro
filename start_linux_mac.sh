#!/bin/bash
echo "Starting YouTube Downloader Pro Setup for Linux/macOS..."
echo "========================================================"

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

echo "Activating virtual environment..."
source venv/bin/activate

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Checking for FFmpeg..."
python3 install_ffmpeg.py

echo "Starting the application..."
python3 app.py
