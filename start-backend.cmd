@echo off
chcp 65001 >nul
setlocal
rem Start the FastAPI backend without relying on PowerShell execution policy.
rem Usage: start-backend.cmd [port]      default port = 8000
set "PORT=%~1"
if "%PORT%"=="" set "PORT=8000"

cd /d "%~dp0backend"
if not exist "%~dp0.venv\Scripts\python.exe" (
  echo [ERROR] .venv not found. Create it with: py -m venv .venv
  pause
  exit /b 1
)

echo Starting backend on http://127.0.0.1:%PORT%   (Swagger: http://127.0.0.1:%PORT%/docs)
echo Press Ctrl+C to stop.
echo.
"%~dp0.venv\Scripts\python.exe" -m uvicorn app.main:app --reload --port %PORT%
echo.
echo Backend stopped. Press any key to close.
pause >nul
