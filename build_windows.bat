@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
py -3.11 -m pip install -r requirements.txt
if errorlevel 1 exit /b 1
py -3.11 bootstrap_assets.py
if errorlevel 1 exit /b 1
py -3.11 -m PyInstaller --clean --noconfirm point_of_no_return.spec
if errorlevel 1 exit /b 1
echo.
echo Готово: dist\PointOfNoReturn2030.exe
endlocal
