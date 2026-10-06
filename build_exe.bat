@echo off
setlocal enabledelayedexpansion
title Building Fast Lightweight ProMailer Pro Executable
echo ========================================================
echo   Building COMPACT & FAST ProMailer Pro Executable
echo ========================================================
echo.

echo [*] Closing any open ProMailerPro process...
taskkill /f /im ProMailerPro.exe >nul 2>&1
timeout /t 1 /nobreak >nul 2>&1

echo [*] Cleaning previous build artifacts...
if exist "build" rd /s /q "build"
if exist "dist\ProMailerPro.exe" del /f /q "dist\ProMailerPro.exe"

echo [*] Compiling with optimized ProMailerPro.spec...
echo [*] Stripping ~180MB of unused Qt WebEngine, Quick, and QML DLLs...
echo [*] This will take about 1 to 2 minutes. Please wait...
echo.

python -m PyInstaller --noconfirm ProMailerPro.spec

if errorlevel 1 (
    echo.
    echo [X] Build encountered an error.
    pause
    exit /b 1
)

echo.
echo ========================================================
echo   [SUCCESS] Compact ProMailerPro.exe build completed!
echo   Location: %~dp0dist\ProMailerPro.exe
echo ========================================================
echo.
pause
