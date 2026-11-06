@echo off
setlocal
cd /d "%~dp0"

echo Starting YouTube Downloader Pro Setup for Windows...
echo ====================================================

set "PYTHON="
python -c "import sys; sys.exit(0 if sys.version_info[0] == 3 else 1)" >nul 2>&1
if not errorlevel 1 (
    set "PYTHON=python"
) else (
    py -3 -c "import sys; sys.exit(0 if sys.version_info[0] == 3 else 1)" >nul 2>&1
    if not errorlevel 1 set "PYTHON=py -3"
)

if not defined PYTHON (
    echo ERROR: Python 3 was not found. Install Python 3.10+ and try again.
    pause
    exit /b 1
)

if not exist "venv\Scripts\python.exe" (
    echo Creating virtual environment...
    %PYTHON% -m venv venv
    if errorlevel 1 (
        echo ERROR: Failed to create the virtual environment.
        pause
        exit /b 1
    )
)

echo Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
    echo ERROR: Failed to activate the virtual environment.
    pause
    exit /b 1
)

echo Installing dependencies...
python -m pip install --upgrade pip
if errorlevel 1 (
    echo ERROR: Failed to upgrade pip.
    pause
    exit /b 1
)

pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install Python dependencies.
    pause
    exit /b 1
)

echo Checking for FFmpeg...
python install_ffmpeg.py
if errorlevel 1 (
    echo WARNING: automatic FFmpeg installation failed.
    echo          yt-dlp cannot merge separate video/audio streams without it.
    echo          Install FFmpeg manually from https://www.gyan.dev/ffmpeg/builds/
)

echo Starting the application...
python app.py
if errorlevel 1 (
    echo ERROR: The application exited with an error.
    pause
    exit /b 1
)

pause
