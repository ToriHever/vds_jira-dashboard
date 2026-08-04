@echo off
setlocal

cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found in PATH. Install Python 3 and try again.
    pause
    exit /b 1
)

if not exist ".env" (
    echo [ERROR] .env file not found next to this script.
    echo Create .env with JIRA_URL, JIRA_LOGIN, JIRA_PASSWORD ^(same as jira_sync.py uses^).
    pause
    exit /b 1
)

python -c "import flask" >nul 2>nul
if errorlevel 1 (
    echo Installing dependencies from requirements_local_proxy.txt ...
    python -m pip install -r requirements_local_proxy.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies.
        pause
        exit /b 1
    )
)

echo Starting local Jira proxy on http://localhost:5057
echo Keep this window open while using comments in the dashboard.
python local_jira_proxy.py

pause
