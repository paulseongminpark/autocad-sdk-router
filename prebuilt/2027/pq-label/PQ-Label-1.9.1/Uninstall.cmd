@echo off
setlocal
title PQ Label Uninstaller
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Uninstall-PqLabel.ps1"
set "PQ_EXIT=%ERRORLEVEL%"
echo.
pause
exit /b %PQ_EXIT%
