@echo off
echo Starting YouTube Downloader Pro Setup for Windows...
echo ====================================================

IF NOT EXIST "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Installing dependencies...
pip install -r requirements.txt

echo Checking for FFmpeg...
python install_ffmpeg.py

echo Starting the application...
python app.py

pause
