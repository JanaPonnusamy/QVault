@echo off
setlocal

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

set "API_HOST=127.0.0.1"
set "BACKEND_PORT=8005"
set "FRONTEND_PORT=5174"
set "BACKEND_URL=http://%API_HOST%:%BACKEND_PORT%"
set "FRONTEND_URL=http://localhost:%FRONTEND_PORT%"
set "CORS_ORIGINS=http://localhost:%FRONTEND_PORT%,http://127.0.0.1:%FRONTEND_PORT%"
set "ENV_FILE=%ROOT%\config\.env"
set "BACKEND_LAUNCHER=%TEMP%\qvault_backend_launch.cmd"
set "FRONTEND_LAUNCHER=%TEMP%\qvault_frontend_launch.cmd"

set "PYTHON_EXE=%ROOT%\backend\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" set "PYTHON_EXE=python"

if /i "%PYTHON_EXE%"=="python" (
    where python >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Python was not found. Expected "%ROOT%\backend\.venv\Scripts\python.exe" or a global "python" on PATH.
        exit /b 1
    )
) else if not exist "%PYTHON_EXE%" (
    echo [ERROR] Python was not found. Expected "%ROOT%\backend\.venv\Scripts\python.exe" or a global "python" on PATH.
    exit /b 1
)

where npm.cmd >nul 2>&1
if errorlevel 1 (
    echo [ERROR] npm.cmd was not found on PATH. Install Node.js or open from a shell where npm is available.
    exit /b 1
)

if exist "%ENV_FILE%" (
    echo Using config from "%ENV_FILE%"
) else (
    echo [WARN] config\.env was not found. Backend defaults will be used.
)

echo Launching QVault backend on %BACKEND_URL%
echo One-click launch uses the backend configured in config\.env (or inherited environment variables).
> "%BACKEND_LAUNCHER%" (
    echo @echo off
    echo set "QVAULT_API_HOST=%API_HOST%"
    echo set "QVAULT_API_PORT=%BACKEND_PORT%"
    echo set "QVAULT_CORS_ORIGINS=%CORS_ORIGINS%"
    echo cd /d "%ROOT%\backend"
    echo "%PYTHON_EXE%" -m uvicorn app.main:app --reload --host %API_HOST% --port %BACKEND_PORT%
)
start "QVault Backend" cmd /k call "%BACKEND_LAUNCHER%"

echo Launching QVault frontend on %FRONTEND_URL%
> "%FRONTEND_LAUNCHER%" (
    echo @echo off
    echo cd /d "%ROOT%\frontend"
    echo call npm.cmd run dev -- --host %API_HOST% --port %FRONTEND_PORT%
)
start "QVault Frontend" cmd /k call "%FRONTEND_LAUNCHER%"

echo QVault launch commands started.
echo Backend:  %BACKEND_URL%
echo Frontend: %FRONTEND_URL%

