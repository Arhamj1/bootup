@echo off
REM BootUp demo launcher for Windows. Double-click this file.
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install Python 3.11 or 3.12 from python.org and tick "Add python.exe to PATH".
  goto :fail
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating a virtual environment...
  python -m venv .venv
  if errorlevel 1 goto :fail
)
call ".venv\Scripts\activate.bat"
if errorlevel 1 goto :fail

if not exist ".venv\installed.flag" (
  echo Installing packages. First time only - this can take several minutes...
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
  if errorlevel 1 goto :fail
  echo ok> ".venv\installed.flag"
)

if exist ".streamlit\secrets.toml" goto :haskey
if defined GROQ_API_KEY goto :haskey
echo.
set "GROQKEY="
set /p "GROQKEY=Paste your Groq API key and press Enter (or just press Enter to skip): "
if not defined GROQKEY goto :haskey
if not exist ".streamlit" mkdir ".streamlit"
> ".streamlit\secrets.toml" echo GROQ_API_KEY = "%GROQKEY%"
echo Saved the key to .streamlit\secrets.toml (this file is never shared or committed).
:haskey

if not exist "index\meta.json" (
  echo Building the index from data\raw. The first build downloads the embedding model...
  python -m bootup.build
  if errorlevel 1 goto :fail
)

echo Starting BootUp. It opens in your browser; close this window to stop it.
python -m streamlit run app.py
goto :eof

:fail
echo.
echo Something went wrong. Read the message above.
pause
exit /b 1
