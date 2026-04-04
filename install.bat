@echo off
echo === Bookarr Installer ===
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH.
    echo Install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo Found Python %PYVER%

:: Get script directory
set SCRIPT_DIR=%~dp0
echo Install directory: %SCRIPT_DIR%

:: Install dependencies
echo.
echo Installing dependencies...
python -m pip install -q pillow requests beautifulsoup4
echo Dependencies installed.

:: Create covers directory
if not exist "%SCRIPT_DIR%static\covers" mkdir "%SCRIPT_DIR%static\covers"

echo.
echo === Quick Start ===
echo   python "%SCRIPT_DIR%bookarr.py"
echo.
echo Then open http://localhost:8585 in your browser.
echo.
echo First run:
echo   1. Go to Settings and configure your Prowlarr URL and API key
echo   2. Configure your NZBGet or torrent client connection
echo   3. Set your eBook and audiobook save paths
echo   4. Go to Discover and add authors or seed from curated lists
echo.
echo Documentation: https://github.com/madebythecollective/bookarr/tree/main/docs
echo.
pause
