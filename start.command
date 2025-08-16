
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

echo "[Start] Checking binary at: dist/MoneyTron"

if [ ! -f "dist/MoneyTron" ]; then

  echo "[Error] dist/MoneyTron not found. Make sure the PyInstaller build is in ./dist"

  read -n1 -r -p "Press any key to close..."

  exit 1

fi

if command -v lsof >/dev/null 2>&1; then

  echo "[Start] Freeing port 5003..."

  lsof -ti tcp:5003 | xargs kill -9 2>/dev/null || true

fi

chmod +x "dist/MoneyTron" || true

xattr -dr com.apple.quarantine "dist/MoneyTron" 2>/dev/null || true

echo "[Start] Launching server..."

./MoneyTron > "./moneytron.log" 2>&1 &

echo "[Start] Waiting for http://localhost:5003 ..."

for i in {1..40}; do

  if curl -sSf http://localhost:5003 >/dev/null 2>&1; then

    echo "[OK] Server is up."

    open "http://localhost:5003"

    echo "MoneyTron is running. You can close this window."

    exit 0

  fi

  sleep 1

done

echo "[Error] Server did not start. See moneytron.log in this folder."

read -n1 -r -p "Press any key to close..."

exit 1

