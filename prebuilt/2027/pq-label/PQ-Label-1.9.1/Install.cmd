@echo off
setlocal
title PQ Label 1.9.1 Installer
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-PqLabel.ps1"
set "PQ_EXIT=%ERRORLEVEL%"
echo.
if not "%PQ_EXIT%"=="0" echo Installation failed with exit code %PQ_EXIT%.
pause
exit /b %PQ_EXIT%
