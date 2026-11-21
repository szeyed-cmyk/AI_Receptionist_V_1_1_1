@echo off
rem FrontDesk AI local starter (Windows Command Prompt).
rem From "FrontDesk Project":  start.bat
rem See HowToSetup.md, section A.
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\activate.bat" (
  call ".venv\Scripts\activate.bat"
) else if exist "venv\Scripts\activate.bat" (
  call "venv\Scripts\activate.bat"
) else (
  echo No virtual environment found in this folder.
  echo Create one first (see HowToSetup.md, section A):
  echo   py -3.12 -m venv .venv
  echo   .venv\Scripts\activate.bat
  exit /b 1
)

python -c "import uvicorn, fastapi" >nul 2>&1
if errorlevel 1 (
  echo Dependencies are missing. With the venv activated, run:
  echo   python -m pip install --require-hashes -r requirements.lock
  exit /b 1
)

if not defined PORT set PORT=10000
echo Starting FrontDesk AI on http://127.0.0.1:%PORT%  (Ctrl+C to stop)
python -m uvicorn main:app --host 0.0.0.0 --port %PORT%
