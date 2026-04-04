@echo off
REM Build Bookarr.exe for Windows using PyInstaller
REM Output: dist\Bookarr\Bookarr.exe
REM
REM Prerequisites:
REM   pip install pyinstaller
REM   Inno Setup 6 (for installer packaging): https://jrsoftware.org/isinfo.php

set VERSION=0.2.0
set SCRIPT_DIR=%~dp0
set PROJECT_DIR=%SCRIPT_DIR%..

cd /d "%PROJECT_DIR%"

echo === Building Bookarr %VERSION% for Windows ===
echo.

REM Clean previous builds
if exist build\pyinstaller rmdir /s /q build\pyinstaller
if exist dist\Bookarr rmdir /s /q dist\Bookarr

REM Build with PyInstaller
echo Running PyInstaller...
pyinstaller build\bookarr.spec --distpath dist --workpath build\pyinstaller --clean

echo.
echo Executable created at dist\Bookarr\Bookarr.exe

REM Build installer if Inno Setup is available
set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist %ISCC% (
    echo.
    echo Building installer with Inno Setup...
    %ISCC% build\installer.iss
    echo.
    echo Installer created at dist\Bookarr-%VERSION%-windows-setup.exe
) else (
    echo.
    echo Skipping installer creation (Inno Setup 6 not found at %ISCC%)
    echo Download from: https://jrsoftware.org/isinfo.php
)

echo.
echo === Build complete ===
pause
