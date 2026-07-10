@echo off
setlocal
cd /d "%~dp0"
if "%CLYO_STOCK_VERSION%"=="" set "CLYO_STOCK_VERSION=8.3.11"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_installer_windows.ps1"
exit /b %ERRORLEVEL%
