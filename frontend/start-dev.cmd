@echo off
setlocal
pushd "%~dp0" || exit /b 1

set "VITE_CLI=node_modules\vite\bin\vite.js"
if not exist "%VITE_CLI%" (
    echo Frontend dependencies are missing. Run pnpm.cmd install --frozen-lockfile first.
    popd
    exit /b 1
)

set "NODE_EXE=node.exe"
where.exe node.exe >nul 2>&1
if errorlevel 1 set "NODE_EXE=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"

if not "%NODE_EXE%"=="node.exe" if not exist "%NODE_EXE%" (
    echo Node.js was not found. Install Node.js 24 and reopen PowerShell.
    popd
    exit /b 1
)

"%NODE_EXE%" "%VITE_CLI%" --host 127.0.0.1 %*
set "DEV_EXIT_CODE=%ERRORLEVEL%"
popd
exit /b %DEV_EXIT_CODE%
