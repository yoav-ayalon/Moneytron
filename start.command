#!/bin/bash
set -euo pipefail

# Resolve script directory robustly for bash/zsh/double-click
if [ -n "${BASH_SOURCE:-}" ]; then
  SRC="${BASH_SOURCE[0]}"
elif [ -n "${ZSH_VERSION:-}" ]; then
  SRC="${(%):-%N}"
else
  SRC="$0"
fi
SCRIPT_DIR="$(cd "$(dirname "$SRC")" && pwd)"
cd "$SCRIPT_DIR"

LOG_FILE="moneytron.log"
URL="http://127.0.0.1:5003"

echo "=============================================="
echo "[Start] MoneyTron launcher"
echo "[Info ] Working dir: $(pwd)"
echo "[Info ] Log file   : $LOG_FILE"
echo "=============================================="

echo "[Step ] Checking for MoneyTron executable..."
if [ ! -f "MoneyTron" ]; then
  echo "[Error] MoneyTron executable not found next to start.command."
  echo "        Build with PyInstaller and place 'MoneyTron' here."
  read -n1 -r -p "Press any key to close..."
  echo
  exit 1
fi

# Ensure users dir exists (app will also ensure, but this helps packaging)
mkdir -p users || true

# Remove quarantine to avoid Gatekeeper blocks (ignore errors)
xattr -dr com.apple.quarantine "MoneyTron" 2>/dev/null || true
xattr -dr com.apple.quarantine . 2>/dev/null || true

# Kill anything using port 5003 if lsof is available
if command -v lsof >/dev/null 2>&1; then
  PIDS=$(lsof -ti :5003 || true)
  if [ -n "${PIDS}" ]; then
    echo "[Step ] Port 5003 busy. Terminating PID(s): ${PIDS}"
    kill -9 ${PIDS} 2>/dev/null || true
    sleep 1
  fi
else
  echo "[Warn ] 'lsof' not found. Skipping port cleanup."
fi

echo "[Step ] Making MoneyTron executable..."
chmod +x "MoneyTron" || true

echo "[Step ] Launching server in background..."
nohup ./MoneyTron >> "$LOG_FILE" 2>&1 &
SERVER_PID=$!
echo "[Info ] MoneyTron PID: $SERVER_PID"

# Wait for server to be ready (up to 40s)
if command -v curl >/dev/null 2>&1; then
  echo "[Wait ] Probing $URL for readiness..."
  READY=0
  for i in {1..40}; do
    if curl -sSf "$URL" >/dev/null 2>&1; then
      READY=1
      break
    fi
    sleep 1
  done

  if [ "$READY" -eq 1 ]; then
    echo "[OK   ] Server is responding. Opening browser..."
    if command -v "google-chrome" >/dev/null 2>&1; then
      "google-chrome" "$URL"
    elif command -v "chrome" >/dev/null 2>&1; then
      "chrome" "$URL"
    elif [ -d "/Applications/Brave Browser.app" ]; then
      open -a "Brave Browser" "$URL"
    elif [ -d "/Applications/Google Chrome.app" ]; then
      open -a "Google Chrome" "$URL"
    elif [ -d "/Applications/Microsoft Edge.app" ]; then
      open -a "Microsoft Edge" "$URL"
    elif [ -d "/Applications/Arc.app" ]; then
      open -a "Arc" "$URL"
    else
      open "$URL"
    fi
    echo "[Done ] MoneyTron launched."
    exit 0
  else
    echo "[Error] Server did not respond within 40s."
    if ps -p "$SERVER_PID" >/dev/null 2>&1; then
      echo "[Info ] Process is running (PID $SERVER_PID) but not ready."
    else
      echo "[Info ] Process appears to have exited."
    fi
    echo "------ Last 60 lines of $LOG_FILE ------"
    tail -n 60 "$LOG_FILE" 2>/dev/null || echo "(no log yet)"
    echo "----------------------------------------"
    echo "Open $URL manually if it starts later."
    read -n1 -r -p "Press any key to close..."
    echo
    exit 1
  fi
else
  echo "[Warn ] 'curl' not found. Opening browser after a short delay..."
  sleep 3
  open "$URL"
  exit 0
fi
