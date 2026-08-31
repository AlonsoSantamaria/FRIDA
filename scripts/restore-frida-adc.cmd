@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0restore-frida-adc.ps1"
echo.
echo This window stays open for review.
pause
