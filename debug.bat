@echo off
cd /d "%~dp0"
echo Running Nova with a visible log (for troubleshooting)...
".venv\Scripts\python.exe" app.py
pause
