@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Authorize-Telegram.ps1" %*
exit /b %errorlevel%
