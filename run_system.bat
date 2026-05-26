@echo off
title School Management System
color 0A

echo ============================================================
echo    SCHOOL MANAGEMENT SYSTEM
echo ============================================================
echo.

echo Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo Python not found! Please install Python first.
    echo Download from: https://python.org
    pause
    exit /b
)

echo Installing required packages...
pip install fastapi uvicorn jinja2 reportlab -q

echo.
echo Starting School Management System...
echo.

start python main.py

echo.
echo ============================================================
echo    SYSTEM STARTED!
echo ============================================================
echo.
echo The system is running in the background.
echo Wait a few seconds then open your browser to:
echo.
echo    http://127.0.0.1:8000
echo.
echo First time? Go to: http://127.0.0.1:8000/unlock
echo Developer Password: HeroHero@1234
echo.
echo Login Credentials:
echo   Admin:    admin / admin123
echo   Teacher:  John / teacher123
echo   Student:  James / Wilson
echo.
echo ============================================================
echo Press any key to close this window (server will keep running)
pause >nul