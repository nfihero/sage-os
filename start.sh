#!/bin/sh
# Sage OS launcher for macOS and Linux (start.cmd is the Windows one): builds the UI on first run, then
# serves hub + UI on http://127.0.0.1:8787. Machine-specific paths go in config.local.toml (see the example).
set -e
cd "$(dirname "$0")"
if [ ! -x hub/.venv/bin/python ]; then
  echo "[sage-os] creating hub venv..."
  python3 -m venv hub/.venv
  hub/.venv/bin/python -m pip install -q -e "hub[dev]"
fi
if [ ! -f ui/dist/index.html ]; then
  echo "[sage-os] building UI..."
  (cd ui && { [ -d node_modules ] || npm install --no-fund --no-audit; } && npm run build)
fi
echo "[sage-os] starting hub on http://127.0.0.1:8787 ... (the dashboard opens when it is ready; Ctrl+C stops it)"
SAGE_OS_OPEN=1 exec hub/.venv/bin/python -m sage_os_hub
