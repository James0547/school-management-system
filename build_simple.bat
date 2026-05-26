@echo off
title Building School Management System - SIMPLE
color 0A

echo ============================================================
echo    SCHOOL MANAGEMENT SYSTEM - SIMPLE BUILDER
echo ============================================================
echo.

echo [1/3] Installing required packages...
pip install pyinstaller fastapi uvicorn jinja2 reportlab
if errorlevel 1 (
    echo Failed to install packages!
    echo Trying with --user flag...
    pip install --user pyinstaller fastapi uvicorn jinja2 reportlab
)

echo.
echo [2/3] Building executable...
python build_exe.py

echo.
echo [3/3] Build complete!
echo.
echo ============================================================
echo    INSTRUCTIONS
echo ============================================================
echo.
echo If build was successful:
echo   1. Look in the 'dist' folder for SchoolManagement.exe
echo   2. Or use the 'SchoolManagement_Portable' folder
echo   3. Double-click the EXE file to run
echo.
echo If build failed:
echo   1. Make sure Python is installed
echo   2. Run as Administrator
echo   3. Check antivirus isn't blocking
echo.
pause