@echo off
title Building School Management System
color 0A

echo ============================================================
echo    SCHOOL MANAGEMENT SYSTEM - BUILD ALL
echo ============================================================
echo.

echo [1/4] Installing required packages...
pip install fastapi uvicorn jinja2 reportlab pyinstaller
if errorlevel 1 (
    echo Failed to install packages!
    pause
    exit /b
)

echo.
echo [2/4] Building executable...
python build_exe.py
if errorlevel 1 (
    echo Failed to build executable!
    pause
    exit /b
)

echo.
echo [3/4] Creating installer...
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" setup.iss
    echo Installer created: installer\SchoolManagementSetup.exe
) else (
    echo.
    echo Inno Setup not found!
    echo Download from: https://jrsoftware.org/isinfo.php
    echo Or use the portable version in SchoolManagement_Portable folder
)

echo.
echo [4/4] Creating portable ZIP...
powershell Compress-Archive -Path "SchoolManagement_Portable\*" -DestinationPath "SchoolManagementSystem.zip" -Force

echo.
echo ============================================================
echo                BUILD COMPLETE!
echo ============================================================
echo.
echo Files created:
echo   1. dist\SchoolManagement.exe - Standalone EXE
echo   2. SchoolManagement_Portable\ - Portable folder
echo   3. SchoolManagementSystem.zip - Portable ZIP
echo   4. installer\SchoolManagementSetup.exe - Installer (if Inno Setup installed)
echo.
echo ============================================================
pause