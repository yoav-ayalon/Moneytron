@echo off
cd /d "%~dp0"

echo ============================================
echo [Start] MoneyTron launcher
echo [Info ] Working dir: %cd%
echo ============================================

REM Kill anything still running on port 5003
echo [Step ] Checking for existing process on port 5003...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5003') do (
  echo [Kill ] Terminating PID %%a ...
  taskkill /F /PID %%a >nul 2>&1
)

REM Start MoneyTron
echo [Step ] Launching MoneyTron.exe ...
start "" /b MoneyTron.exe

REM Wait up to 40 seconds for server to be ready
setlocal enabledelayedexpansion
set COUNT=0
:loop
  echo [Wait ] Attempt !COUNT!/40 ... probing http://127.0.0.1:5003
  powershell -command "try {Invoke-WebRequest -Uri http://127.0.0.1:5003 -UseBasicParsing | Out-Null; exit 0} catch {exit 1}"
  if !errorlevel! equ 0 (
    echo [OK   ] Server is responding on port 5003.
    echo [Step ] Opening browser...
    start "" http://127.0.0.1:5003
    echo [Done ] MoneyTron launched successfully.
    pause
    exit /b 0
  )
  set /a COUNT+=1
  if !COUNT! geq 40 (
    echo [ERROR] Server did not start after 40s. Check moneytron.log
    pause
    exit /b 1
  )
  timeout /t 1 /nobreak >nul
goto loop