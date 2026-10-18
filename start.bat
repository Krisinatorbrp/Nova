@echo off
title Nova
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python is not installed. Get it from https://www.python.org/downloads/
  echo IMPORTANT: tick "Add python.exe to PATH" in the installer, then run this again.
  pause
  exit /b 1
)

rem (re)install packages on first start, or when requirements.txt changed after an update
set NEEDS_INSTALL=0
if not exist ".venv\.installed" set NEEDS_INSTALL=1
if exist ".venv\.installed" fc /b requirements.txt ".venv\.installed" >nul 2>nul || set NEEDS_INSTALL=1
if "%NEEDS_INSTALL%"=="1" (
  echo Setting up Nova - first start or after an update. This can take a minute...
  if not exist ".venv\Scripts\python.exe" python -m venv .venv || goto :fail
  ".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :fail
  if not exist "%USERPROFILE%\Desktop\Nova.lnk" echo Adding a Nova shortcut to your desktop...
  if not exist "%USERPROFILE%\Desktop\Nova.lnk" powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Nova.lnk');$s.TargetPath='%~dp0.venv\Scripts\pythonw.exe';$s.Arguments='app.py';$s.WorkingDirectory='%~dp0';$s.IconLocation='%~dp0nova.ico';$s.Save()"
  copy /y requirements.txt ".venv\.installed" >nul
)

rem Nova's local brain runs on Ollama - install it if it's missing
where ollama >nul 2>nul
if errorlevel 1 if not exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" (
  echo.
  echo Installing Ollama, the free program that runs Nova's AI on this PC...
  winget install -e --id Ollama.Ollama --accept-source-agreements --accept-package-agreements
  if errorlevel 1 echo Could not install it automatically. Get it from https://ollama.com/download - Nova will still open.
)

start "" ".venv\Scripts\pythonw.exe" app.py
exit /b 0

:fail
echo Setup failed. Scroll up to see the error.
pause
