# server/new_app.py
import os
import sys
import json
import tempfile
from pathlib import Path
from typing import Any, Dict
from threading import RLock
from datetime import datetime
import logging

from flask import Flask, request, jsonify, send_from_directory, abort, make_response

# =============================================================================
# Paths that work in BOTH dev and PyInstaller -- with PERSISTENT users/
# =============================================================================
if getattr(sys, "frozen", False):
    # PyInstaller one-file:
    # - Code/assets live in a temp dir (sys._MEIPASS) each run
    # - The executable lives at sys.executable. We persist next to that.
    BUNDLE_DIR = Path(getattr(sys, "_MEIPASS")).resolve()             # read-only assets
    APP_DIR    = Path(sys.executable).resolve().parent                # persistent folder
    CLIENT_DIR = (BUNDLE_DIR / "client").resolve()                    # serve from bundle
    USERS_DIR  = (APP_DIR / "users").resolve()                        # PERSIST HERE
else:
    # Dev/source layout: MoneyTron/
    SERVER_DIR = Path(__file__).resolve().parent
    ROOT_DIR   = SERVER_DIR.parent
    CLIENT_DIR = (ROOT_DIR / "client").resolve()
    USERS_DIR  = (ROOT_DIR / "users").resolve()

# right after CLIENT_DIR is computed
print(f"[MoneyTron] Serving client from: {CLIENT_DIR}")
print(f"[MoneyTron] Data dir: {USERS_DIR}")

# Optional override via env (handy for Docker or custom paths)
USERS_DIR = Path(os.environ.get("MONEYTRON_DATA_DIR", USERS_DIR)).resolve()
USERS_DIR.mkdir(parents=True, exist_ok=True)

# =============================================================================
# App init
# =============================================================================
app = Flask(__name__, static_folder=None)
log_path = "moneytron.log"
logging.basicConfig(
    level=logging.DEBUG,
    format='[%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(log_path, mode='a'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("moneytron")
app.config["JSON_AS_ASCII"] = False
app.config["JSON_SORT_KEYS"] = False
app.url_map.strict_slashes = False

# CORS-ish (harmless on same-origin; helps OPTIONS)
@app.after_request
def _hdrs(resp):
    resp.headers["Access-Control-Allow-Origin"] = request.headers.get("Origin", "*")
    resp.headers["Access-Control-Allow-Credentials"] = "true"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, X-User"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return resp

@app.before_request
def _short_opts():
    if request.method == "OPTIONS":
        return ("", 200)

_glock = RLock()
_CURRENT_USER = {"name": None}

# =============================================================================
# Utilities
# =============================================================================
def _sanitize_user(u: str) -> str:
    u = "".join(ch for ch in (u or "").strip() if ch.isalnum() or ch in ("_", "-", "."))
    if not u:
        abort(400, description="Invalid user.")
    return u

def _require_user() -> str:
    if not _CURRENT_USER["name"]:
        abort(400, description="No active user. POST /api/login first.")
    return _CURRENT_USER["name"]

def _user_dir(username: str) -> Path:
    p = (USERS_DIR / username).resolve()
    if not str(p).startswith(str(USERS_DIR)):
        abort(400, description="Bad path")
    return p

def _paths(username: str) -> Dict[str, Path]:
    udir = _user_dir(username)
    return {
        "categories": (udir / "categories.json"), 
        "stage":      (udir / "current_month_transactions.json"),
        "past":       (udir / "past_data.json"),
        "settings":   (udir / "settings.json"),
    }

def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def _atomic_write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _glock:
        with tempfile.NamedTemporaryFile("w", delete=False, dir=str(path.parent), encoding="utf-8") as tmp:
            json.dump(data, tmp, ensure_ascii=False, indent=2)
            tmp.flush()
            os.fsync(tmp.fileno())
            tmppath = Path(tmp.name)
        tmppath.replace(path)

def _ensure_user_files(username: str) -> Dict[str, Path]:
    p = _paths(username)
    defaults = {
        "categories": {},                                   # { "Food": ["Groceries","Dining"], ... }
        "stage": [],                                        # staging rows (Transactions tab)
        "past": [],                                         # saved rows (Data tab)
        "settings": {
            "dateFormat": "YYYY-MM-DD",
            "currency": "ILS",
            "allowedCurrencies": ["ILS", "USD"]
        },
    }
    if not p["categories"].exists(): _atomic_write(p["categories"], defaults["categories"])
    if not p["stage"].exists():      _atomic_write(p["stage"],      defaults["stage"])
    if not p["past"].exists():       _atomic_write(p["past"],       defaults["past"])
    if not p["settings"].exists():   _atomic_write(p["settings"],   defaults["settings"])
    return p

# =============================================================================
# UI & health
# =============================================================================
@app.route("/")
def index():
    if not (CLIENT_DIR / "index.html").exists():
        return jsonify({"ok": False, "error": "client/index.html not found"}), 500
    return send_from_directory(CLIENT_DIR, "index.html")

@app.route("/client/<path:filename>")
def client_files(filename: str):
    return send_from_directory(CLIENT_DIR, filename)

@app.route("/api/health")
def health():
    return jsonify({"ok": True, "ts": datetime.utcnow().isoformat() + "Z"})

# =============================================================================
# Auth / session (simple cookie-style for local use)
# =============================================================================
@app.route("/api/users", methods=["GET"])
def api_users():
    out = []
    for p in USERS_DIR.iterdir():
        if p.is_dir():
            out.append(p.name)
    out.sort()
    return jsonify(out)

@app.route("/api/login", methods=["POST"])
def api_login():
    payload = request.get_json(force=True)
    username = _sanitize_user(payload.get("user") or payload.get("username") or payload.get("name") or "")
    _CURRENT_USER["name"] = username
    _ensure_user_files(username)
    resp = make_response(jsonify({"ok": True, "user": username}))
    # local cookie just so browser includes it (not used for security)
    resp.set_cookie("mt_user", username, httponly=True, samesite="Lax")
    return resp

@app.route("/api/logout", methods=["POST"])
def api_logout():
    _CURRENT_USER["name"] = None
    resp = make_response(jsonify({"ok": True}))
    resp.delete_cookie("mt_user")
    return resp

@app.route("/api/bootstrap", methods=["GET"])
def api_bootstrap():
    user = _CURRENT_USER["name"]
    if not user:
        return jsonify({"user": ""})
    p = _ensure_user_files(user)
    return jsonify({
        "user": user,
        "categories": _read_json(p["categories"], {}),
        "current_month": _read_json(p["stage"], []),
        "past_data": _read_json(p["past"], []),
        "settings": _read_json(p["settings"], {"dateFormat": "YYYY-MM-DD", "currency": "ILS"})
    })

# =============================================================================
# Categories
# =============================================================================
@app.route("/api/categories", methods=["GET", "POST"])
def api_categories():

    user = _require_user()
    p = _ensure_user_files(user)
    logger.debug(f"Categories API for user: {user}, path: {p['categories']}")

    if request.method == "GET":
        cats = _read_json(p["categories"], {})
        logger.debug(f"Loaded categories: {cats}")
        return jsonify(cats)

    payload = request.get_json(force=True)
    cats = payload.get("categories", {})
    if not isinstance(cats, dict):
        abort(400, description="'categories' must be an object {name: [subs...]}" )
    _atomic_write(p["categories"], cats)
    return jsonify({"ok": True})

# =============================================================================
# Current month (Transactions staging)
# =============================================================================
@app.route("/api/current-month", methods=["GET", "POST"])
def api_current_month():
    user = _require_user()
    p = _ensure_user_files(user)

    if request.method == "GET":
        return jsonify({"current_month": _read_json(p["stage"], [])})

    payload = request.get_json(force=True)
    rows = payload.get("transactions") or payload.get("items") or []
    if not isinstance(rows, list):
        abort(400, description="'transactions' must be a list")
    _atomic_write(p["stage"], rows)
    return jsonify({"ok": True})

@app.route('/api/current-month/reset', methods=['POST'])
def reset_current_month():
    user = _require_user()
    if not user:
        return jsonify({'error': 'Not logged in'}), 401

    p = _ensure_user_files(user)
    _atomic_write(p['stage'], [])
    return jsonify({'ok': True})

# =============================================================================
# Past data (Data tab)
# =============================================================================
@app.route("/api/past-data", methods=["GET", "POST"])
def api_past_data():
    user = _require_user()
    p = _ensure_user_files(user)

    if request.method == "GET":
        return jsonify({"past_data": _read_json(p["past"], [])})

    payload = request.get_json(force=True)
    rows = payload.get("past_data") or payload.get("items") or []
    if not isinstance(rows, list):
        abort(400, description="'past_data' must be a list")
    _atomic_write(p["past"], rows)
    return jsonify({"ok": True})

# =============================================================================
# Commit transactions (move from stage -> past)
# =============================================================================
@app.route("/api/transactions", methods=["POST"])
def api_transactions():
    user = _require_user()
    p = _ensure_user_files(user)

    payload = request.get_json(force=True)
    rows = payload.get("transactions") or []
    if not isinstance(rows, list):
        abort(400, description="'transactions' must be a list")

    past = _read_json(p["past"], [])
    seen = {str(x.get("id")) for x in past if isinstance(x, dict) and x.get("id") is not None}
    for r in rows:
        if not isinstance(r, dict): 
            continue
        rid = str(r.get("id"))
        if rid and rid in seen:
            continue
        past.append(r)
        if rid:
            seen.add(rid)

    _atomic_write(p["past"], past)
    _atomic_write(p["stage"], [])
    return jsonify({"ok": True, "saved": len(rows)})

# =============================================================================
# Settings
# =============================================================================
@app.route("/api/settings", methods=["GET", "POST"])
def api_settings():
    user = _require_user()
    p = _ensure_user_files(user)

    if request.method == "GET":
        return jsonify(_read_json(p["settings"], {
            "dateFormat": "YYYY-MM-DD",
            "currency": "ILS",
            "allowedCurrencies": ["ILS", "USD"]
        }))

    payload = request.get_json(force=True)
    s = payload.get("settings", {})
    if not isinstance(s, dict):
        abort(400, description="'settings' must be an object")
    cur = _read_json(p["settings"], {})
    cur.update({
        "dateFormat": s.get("dateFormat", cur.get("dateFormat", "YYYY-MM-DD")),
        "currency":   s.get("currency",   cur.get("currency", "ILS")),
        "allowedCurrencies": s.get("allowedCurrencies", cur.get("allowedCurrencies", ["ILS", "USD"]))
    })
    _atomic_write(p["settings"], cur)
    return jsonify({"ok": True})

# =============================================================================
# Import / Clear
# =============================================================================
@app.route("/api/import", methods=["POST"])
def api_import():
    user = _require_user()
    p = _ensure_user_files(user)

    payload = request.get_json(force=True)

    if "categories" in payload:
        if not isinstance(payload["categories"], dict):
            abort(400, description="'categories' must be an object")
        _atomic_write(p["categories"], payload["categories"])

    if "current_month" in payload:
        if not isinstance(payload["current_month"], list):
            abort(400, description="'current_month' must be a list")
        _atomic_write(p["stage"], payload["current_month"])

    if "past_data" in payload:
        if not isinstance(payload["past_data"], list):
            abort(400, description="'past_data' must be a list")
        _atomic_write(p["past"], payload["past_data"])

    if "settings" in payload:
        s = payload["settings"]
        if not isinstance(s, dict):
            abort(400, description="'settings' must be an object")
        _atomic_write(p["settings"], {
            "dateFormat": s.get("dateFormat", "YYYY-MM-DD"),
            "currency":   s.get("currency", "ILS")
        })

    return jsonify({"ok": True})

@app.route("/api/clear-all", methods=["POST"])
def api_clear_all():
    user = _require_user()
    p = _ensure_user_files(user)
    _atomic_write(p["categories"], {})
    _atomic_write(p["stage"], [])
    _atomic_write(p["past"], [])
    return jsonify({"ok": True})

# =============================================================================
# Entrypoint
# =============================================================================
def _port() -> int:
    try:
        return int(os.environ.get("PORT", "5003"))
    except Exception:
        return 5003

if __name__ == "__main__":
    port = _port()
    url = f"http://127.0.0.1:{port}/"
    print("\n====================================================")
    print(" MoneyTron backend is starting…")
    print(f" Open this in your browser: {url}")
    print("====================================================\n")
    try:
        from waitress import serve
        print(f"[MoneyTron] Using Waitress WSGI server")
        print(f"[MoneyTron] Serving client from: {CLIENT_DIR}")
        print(f"[MoneyTron] Data dir: {USERS_DIR}")
        serve(app, host="0.0.0.0", port=port)
    except Exception as e:
        print(f"[MoneyTron] Waitress unavailable ({e}); Flask dev server fallback")
        print(f"[MoneyTron] Serving client from: {CLIENT_DIR}")
        print(f"[MoneyTron] Data dir: {USERS_DIR}")
        app.run(host="0.0.0.0", port=port, debug=True, use_reloader=False)