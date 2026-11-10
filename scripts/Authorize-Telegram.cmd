@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Authorize-Telegram.ps1" -NoPause
set "status=%errorlevel%"
if not "%status%"=="0" pause
exit /b %status%
