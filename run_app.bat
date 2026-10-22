@echo off
REM BootUp (React frontend + FastAPI backend). Double-click this file.
REM The older Streamlit app still works with run_demo.bat.
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Run run_demo.bat once first: it creates the Python environment and asks for the Groq key.
  goto :fail
)
call ".venv\Scripts\activate.bat"
python -c "import fastapi" 2>nul || python -m pip install -r requirements.txt || goto :fail

if not exist "index\meta.json" (
  echo Building the index from data\raw...
  python -m bootup.build || goto :fail
)

if not exist "frontend\dist\index.html" (
  where npm >nul 2>nul || (echo Node.js is needed to build the frontend once: install it from nodejs.org. & goto :fail)
  echo Building the frontend. First time only...
  pushd frontend
  if not exist "node_modules" call npm install || (popd & goto :fail)
  call npm run build || (popd & goto :fail)
  popd
)

echo Starting BootUp at http://127.0.0.1:8000 . Close this window to stop it.
start "" "http://127.0.0.1:8000"
python -m server --port 8000
goto :eof

:fail
echo.
echo Something went wrong. Read the message above.
pause
exit /b 1
