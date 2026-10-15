@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  py -m venv .venv
  if errorlevel 1 python -m venv .venv
)
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
  echo Dependency installation failed. Check your internet connection and Python installation.
  pause
  exit /b 1
)
.venv\Scripts\python.exe app.py
pause
