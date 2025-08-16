#!/bin/bash
set -euo pipefail

if [ -n "${BASH_SOURCE:-}" ]; then
  SRC="${BASH_SOURCE[0]}"
elif [ -n "${ZSH_VERSION:-}" ]; then
  SRC="${(%):-%N}"
else
  SRC="$0"
fi
SCRIPT_DIR="$(cd "$(dirname "$SRC")" && pwd)"
cd "$SCRIPT_DIR"

echo "[Start] MoneyTron launcher"
echo "[Start] Working dir: $(pwd)"

echo "[Start] Checking for MoneyTron executable in working dir"
echo "[Start] Users dir: $(pwd)/users"
if [ ! -f "MoneyTron" ]; then
  echo "[Error] MoneyTron executable not found in working directory. Make sure the PyInstaller build is in this folder."
  read -n1 -r -p "Press any key to close..."
  exit 1
fi


# Check if port 5003 is in use and force kill it if so
PIDS=$(lsof -ti :5003)
if [ -n "$PIDS" ]; then
  echo "[Start] Port 5003 is in use. Force killing process(es): $PIDS"
  kill -9 $PIDS 2>/dev/null || true
  sleep 1
fi

echo "[Start] Launching server..."

chmod +x "MoneyTron" || true
xattr -dr com.apple.quarantine "MoneyTron" 2>/dev/null || true

echo "[Start] Launching server..."
nohup ./MoneyTron > "moneytron.log" 2>&1 &


# Wait for server to be ready, then open browser
( 
  for i in {1..30}; do
    if curl -sSf http://127.0.0.1:5003 >/dev/null 2>&1; then
      if command -v "google-chrome" >/dev/null 2>&1; then
        "google-chrome" "http://127.0.0.1:5003"
      elif command -v "chrome" >/dev/null 2>&1; then
        "chrome" "http://127.0.0.1:5003"
      elif [ -d "/Applications/Google Chrome.app" ]; then
        open -a "Google Chrome" "http://127.0.0.1:5003"
      else
        open "http://127.0.0.1:5003"
      fi
      exit 0
    fi
    sleep 1
  done
  echo "[Warning] Server did not start in time. Please open http://127.0.0.1:5003 manually."
) &

echo "MoneyTron is launching. The app should open in your browser."
echo "If it does not, open http://127.0.0.1:5003 manually."
exit 0
