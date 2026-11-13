@echo off
rem Starts Nichescope. The first run creates the Python environment and builds the web client.
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creating the Python environment...
    py -3 -m venv .venv 2>nul || python -m venv .venv
    if not exist ".venv\Scripts\python.exe" (
        echo Python 3.10 or newer is required: https://www.python.org/downloads/
        pause
        exit /b 1
    )
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -e .
    if errorlevel 1 goto failed
)

if not exist "src\nichescope\web\index.html" (
    where npm >nul 2>nul || (
        echo Node.js is required to build the web client: https://nodejs.org/
        pause
        exit /b 1
    )
    echo Building the web client...
    pushd web
    call npm install && call npm run build
    popd
    if not exist "src\nichescope\web\index.html" goto failed
)

if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo First run: add your Gemini key in Settings once the app opens.
)

echo Nichescope is starting at http://127.0.0.1:8765  (close this window to stop it)
".venv\Scripts\python.exe" -m nichescope serve
if errorlevel 1 pause
exit /b %errorlevel%

:failed
echo Setup failed; see the messages above.
pause
exit /b 1
