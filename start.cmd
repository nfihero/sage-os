@echo off
rem Sage OS launcher: builds the UI on first run, then serves hub + UI on http://127.0.0.1:8787
setlocal
cd /d "%~dp0"
if not exist "hub\.venv\Scripts\python.exe" (
  echo [sage-os] creating hub venv...
  python -m venv hub\.venv || exit /b 1
  hub\.venv\Scripts\python -m pip install -q -e "hub[dev]" || exit /b 1
)
if not exist "ui\dist\index.html" (
  echo [sage-os] building UI...
  pushd ui
  if not exist node_modules call npm install --no-fund --no-audit || exit /b 1
  call npm run build || exit /b 1
  popd
)
echo [sage-os] starting hub on http://127.0.0.1:8787 ... (the dashboard opens when it is ready; this window stays open while it runs)
set SAGE_OS_OPEN=1
hub\.venv\Scripts\python -m sage_os_hub
