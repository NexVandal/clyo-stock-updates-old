@echo off
setlocal
cd /d "%~dp0"
echo =====================================================
echo  CLYO Stock Atelier V8.3.11 - Generation EXE Windows
echo =====================================================
echo.
echo Ce script genere l'installateur :
echo   dist\installer\CLYO_Stock_Atelier_Setup_8.3.11.exe
echo.
echo Pre-requis sur ce PC :
echo   - Python 3 installe
echo   - Inno Setup 6 installe
echo.
call "%~dp0build_installer_windows.bat"
