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
# Statistics endpoints
# =============================================================================
@app.route("/api/statistics", methods=["POST"])
def api_statistics():
    """
    New unified statistics endpoint.
    Computes monthly statistics over selected (year, tag) cells.
    
    Expects JSON body:
    {
      "years": [2025, 2024, ...],
      "tagsByYear": {"2025": [7,8,9], "2024": [10,11,12]},
      "type": "Expense" | "Income",
      "categories": ["אוכל", ...] (optional, empty = all),
      "subcategories": ["קפה", ...] (optional, only if 1 category selected),
      "quickFilter": "none" | "last3" | "last6" | "alltime" (optional)
    }
    
    Returns:
    {
      "months": [{"year": 2025, "tag": 7, "total": 8536.60, "count": 45}, ...],
      "summary": {
        "total_over_period": 24643.87,
        "avg_monthly": 8214.62,
        "median_monthly": 7433.10,
        "min_monthly": 3393.83,
        "max_monthly": 12643.87
      },
      "top_categories": [
        {"name": "אוכל", "total": 9000.0, "avg_per_month": 3000.0},
        ...
      ]
    }
    """
    user = _require_user()
    p = _ensure_user_files(user)
    
    payload = request.get_json(force=True)
    years = payload.get("years", [])
    tags_by_year = payload.get("tagsByYear", {})
    tx_type = payload.get("type", "Expense")
    categories_filter = payload.get("categories", [])
    subcategories_filter = payload.get("subcategories", [])
    quick_filter = payload.get("quickFilter", "none")
    
    past = _read_json(p["past"], [])
    
    # Handle quick filters by deriving years and tags from data
    if quick_filter in ["last3", "last6", "alltime"]:
        # Build list of (year, tag) pairs from data with dates
        year_tag_pairs = set()
        for tx in past:
            if not isinstance(tx, dict):
                continue
            date_str = tx.get("date", "")
            if not date_str or len(date_str) < 4:
                continue
            try:
                year = int(date_str[:4])
            except:
                continue
            tag = tx.get("month_tag") or tx.get("tag")
            if tag is not None:
                year_tag_pairs.add((year, int(tag)))
        
        # Sort by (year, tag) descending to get most recent first
        sorted_pairs = sorted(year_tag_pairs, reverse=True)
        
        if quick_filter == "last3":
            selected_pairs = sorted_pairs[:3]
        elif quick_filter == "last6":
            selected_pairs = sorted_pairs[:6]
        else:  # alltime
            selected_pairs = sorted_pairs
        
        # Rebuild years and tags_by_year from selected pairs
        years = sorted(list(set(y for y, t in selected_pairs)))
        tags_by_year = {}
        for y, t in selected_pairs:
            y_str = str(y)
            if y_str not in tags_by_year:
                tags_by_year[y_str] = []
            tags_by_year[y_str].append(t)
    
    # Build set of selected (year, tag) cells
    selected_cells = set()
    for year in years:
        year_str = str(year)
        tags_for_year = tags_by_year.get(year_str, [])
        for tag in tags_for_year:
            selected_cells.add((int(year), int(tag)))
    
    # Validate: must have at least 2 cells
    if len(selected_cells) < 2:
        return jsonify({
            "error": "Select at least two months to calculate statistics.",
            "months": [],
            "summary": {
                "total_over_period": 0,
                "avg_monthly": 0,
                "median_monthly": 0,
                "min_monthly": 0,
                "max_monthly": 0
            },
            "top_categories": []
        })
    
    # Filter transactions based on selection
    filtered = []
    for tx in past:
        if not isinstance(tx, dict):
            continue
        
        # Derive year from date
        date_str = tx.get("date", "")
        if not date_str or len(date_str) < 4:
            continue
        try:
            tx_year = int(date_str[:4])
        except:
            continue
        
        tx_tag = tx.get("month_tag") or tx.get("tag")
        if tx_tag is None:
            continue
        
        # Check if (year, tag) is in selected cells
        if (tx_year, int(tx_tag)) not in selected_cells:
            continue
        
        # Filter by type (must be exact match - no "All")
        if tx.get("type") != tx_type:
            continue
        
        # Filter by categories
        if categories_filter:
            if tx.get("category") not in categories_filter:
                continue
            
            # Filter by subcategories (only if exactly 1 category selected)
            if len(categories_filter) == 1 and subcategories_filter:
                if tx.get("subcategory") not in subcategories_filter:
                    continue
        
        filtered.append(tx)
    
    # Compute monthly totals for each selected cell
    monthly_totals = {}
    for year, tag in selected_cells:
        monthly_totals[(year, tag)] = {"total": 0.0, "count": 0}
    
    for tx in filtered:
        date_str = tx.get("date", "")
        try:
            tx_year = int(date_str[:4])
        except:
            continue
        tx_tag = int(tx.get("month_tag") or tx.get("tag"))
        amount = abs(float(tx.get("debit") or tx.get("amount") or 0))
        
        key = (tx_year, tx_tag)
        if key in monthly_totals:
            monthly_totals[key]["total"] += amount
            monthly_totals[key]["count"] += 1
    
    # Build months array
    months_array = []
    totals_list = []
    for (year, tag), data in sorted(monthly_totals.items()):
        months_array.append({
            "year": year,
            "tag": tag,
            "total": round(data["total"], 2),
            "count": data["count"]
        })
        totals_list.append(data["total"])
    
    # Compute summary statistics
    num_months = len(totals_list)
    total_over_period = sum(totals_list)
    avg_monthly = total_over_period / num_months if num_months > 0 else 0
    
    # Median
    sorted_totals = sorted(totals_list)
    if num_months % 2 == 0:
        median_monthly = (sorted_totals[num_months // 2 - 1] + sorted_totals[num_months // 2]) / 2 if num_months > 0 else 0
    else:
        median_monthly = sorted_totals[num_months // 2] if num_months > 0 else 0
    
    min_monthly = min(totals_list) if totals_list else 0
    max_monthly = max(totals_list) if totals_list else 0
    
    # Compute top 3 categories or subcategories
    top_categories = []
    
    if not categories_filter:
        # No category filter: group by category
        category_totals = {}
        for tx in filtered:
            cat = tx.get("category", "")
            if not cat:
                continue
            amount = abs(float(tx.get("debit") or tx.get("amount") or 0))
            if cat not in category_totals:
                category_totals[cat] = 0.0
            category_totals[cat] += amount
        
        # Sort and take top 3
        sorted_cats = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)[:3]
        for cat, total in sorted_cats:
            top_categories.append({
                "name": cat,
                "total": round(total, 2),
                "avg_per_month": round(total / num_months, 2) if num_months > 0 else 0
            })
    
    elif len(categories_filter) == 1:
        # Single category: group by subcategory
        subcategory_totals = {}
        for tx in filtered:
            sub = tx.get("subcategory", "")
            if not sub:
                continue
            amount = abs(float(tx.get("debit") or tx.get("amount") or 0))
            if sub not in subcategory_totals:
                subcategory_totals[sub] = 0.0
            subcategory_totals[sub] += amount
        
        sorted_subs = sorted(subcategory_totals.items(), key=lambda x: x[1], reverse=True)[:3]
        for sub, total in sorted_subs:
            top_categories.append({
                "name": sub,
                "total": round(total, 2),
                "avg_per_month": round(total / num_months, 2) if num_months > 0 else 0
            })
    
    else:
        # Multiple categories: group by category
        category_totals = {}
        for tx in filtered:
            cat = tx.get("category", "")
            if not cat:
                continue
            amount = abs(float(tx.get("debit") or tx.get("amount") or 0))
            if cat not in category_totals:
                category_totals[cat] = 0.0
            category_totals[cat] += amount
        
        sorted_cats = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)[:3]
        for cat, total in sorted_cats:
            top_categories.append({
                "name": cat,
                "total": round(total, 2),
                "avg_per_month": round(total / num_months, 2) if num_months > 0 else 0
            })
    
    return jsonify({
        "months": months_array,
        "summary": {
            "total_over_period": round(total_over_period, 2),
            "avg_monthly": round(avg_monthly, 2),
            "median_monthly": round(median_monthly, 2),
            "min_monthly": round(min_monthly, 2),
            "max_monthly": round(max_monthly, 2)
        },
        "top_categories": top_categories
    })


# Keep old endpoints for backward compatibility (deprecated)
@app.route("/api/statistics/summary", methods=["POST"])
def api_statistics_summary():
    """DEPRECATED - use /api/statistics instead"""
    user = _require_user()
    p = _ensure_user_files(user)
    
    payload = request.get_json(force=True)
    tags = payload.get("tags", [])
    years = payload.get("years", [])
    category = payload.get("category", "")
    subcategories = payload.get("subcategories", [])
    tx_type = payload.get("type", "All")
    
    past = _read_json(p["past"], [])
    
    # Group by tag
    by_tag = {}
    for tx in past:
        if not isinstance(tx, dict):
            continue
        
        tx_tag = tx.get("month_tag") or tx.get("tag")
        tx_year = tx.get("year")
        
        # Apply filters
        if tags and tx_tag not in tags:
            continue
        if years and tx_year not in years:
            continue
        if tx_type != "All" and tx.get("type") != tx_type:
            continue
        if category and tx.get("category") != category:
            continue
        if subcategories and tx.get("subcategory") not in subcategories:
            continue
        
        if tx_tag not in by_tag:
            by_tag[tx_tag] = []
        by_tag[tx_tag].append(abs(float(tx.get("debit", 0))))
    
    # Calculate means
    result = []
    for tag, amounts in sorted(by_tag.items()):
        result.append({
            "tag": tag,
            "mean": sum(amounts) / len(amounts) if amounts else 0,
            "count": len(amounts)
        })
    
    # Add combined mean
    all_amounts = [amt for amounts in by_tag.values() for amt in amounts]
    combined_mean = sum(all_amounts) / len(all_amounts) if all_amounts else 0
    
    return jsonify({
        "per_tag": result,
        "combined_mean": combined_mean
    })


@app.route("/api/statistics/category_last3_mean", methods=["POST"])
def api_statistics_category_last3_mean():
    """Calculate mean for a category over the last 3 months with data"""
    user = _require_user()
    p = _ensure_user_files(user)
    
    payload = request.get_json(force=True)
    category = payload.get("category", "")
    
    if not category:
        return jsonify({"months": [], "means": []})
    
    past = _read_json(p["past"], [])
    
    # Group by tag for the selected category
    by_tag = {}
    for tx in past:
        if not isinstance(tx, dict):
            continue
        if tx.get("category") != category:
            continue
        
        tx_tag = tx.get("month_tag") or tx.get("tag")
        if not tx_tag:
            continue
        
        if tx_tag not in by_tag:
            by_tag[tx_tag] = []
        by_tag[tx_tag].append(abs(float(tx.get("debit", 0))))
    
    # Get last 3 months with data
    sorted_tags = sorted(by_tag.keys(), reverse=True)[:3]
    sorted_tags.reverse()  # chronological order
    
    result = []
    for tag in sorted_tags:
        amounts = by_tag[tag]
        result.append({
            "tag": tag,
            "mean": sum(amounts) / len(amounts) if amounts else 0
        })
    
    return jsonify({"data": result})


@app.route("/api/statistics/income_means", methods=["POST"])
def api_statistics_income_means():
    """Calculate mean income grouped by category and subcategory"""
    user = _require_user()
    p = _ensure_user_files(user)
    
    payload = request.get_json(force=True)
    tags = payload.get("tags", [])
    years = payload.get("years", [])
    
    past = _read_json(p["past"], [])
    
    # Group by category -> subcategory
    by_cat_sub = {}
    for tx in past:
        if not isinstance(tx, dict):
            continue
        if tx.get("type") != "Income":
            continue
        
        tx_tag = tx.get("month_tag") or tx.get("tag")
        tx_year = tx.get("year")
        
        if tags and tx_tag not in tags:
            continue
        if years and tx_year not in years:
            continue
        
        cat = tx.get("category", "Uncategorized")
        sub = tx.get("subcategory", "—")
        
        key = (cat, sub)
        if key not in by_cat_sub:
            by_cat_sub[key] = []
        by_cat_sub[key].append(abs(float(tx.get("debit", 0))))
    
    # Calculate means
    result = []
    for (cat, sub), amounts in sorted(by_cat_sub.items()):
        result.append({
            "category": cat,
            "subcategory": sub,
            "mean": sum(amounts) / len(amounts) if amounts else 0,
            "count": len(amounts)
        })
    
    # Overall mean
    all_amounts = [amt for amounts in by_cat_sub.values() for amt in amounts]
    overall_mean = sum(all_amounts) / len(all_amounts) if all_amounts else 0
    
    return jsonify({
        "breakdown": result,
        "overall_mean": overall_mean
    })


@app.route("/api/statistics/rollup", methods=["POST"])
def api_statistics_rollup():
    """Table showing totals, means, and counts per tag×year combination"""
    user = _require_user()
    p = _ensure_user_files(user)
    
    payload = request.get_json(force=True)
    tags = payload.get("tags", [])
    years = payload.get("years", [])
    tx_type = payload.get("type", "All")
    
    past = _read_json(p["past"], [])
    
    # Group by (year, tag)
    by_year_tag = {}
    for tx in past:
        if not isinstance(tx, dict):
            continue
        
        tx_tag = tx.get("month_tag") or tx.get("tag")
        tx_year = tx.get("year")
        tx_tx_type = tx.get("type", "Expense")
        
        if tags and tx_tag not in tags:
            continue
        if years and tx_year not in years:
            continue
        if tx_type != "All" and tx_tx_type != tx_type:
            continue
        
        key = (tx_year, tx_tag)
        if key not in by_year_tag:
            by_year_tag[key] = []
        by_year_tag[key].append(abs(float(tx.get("debit", 0))))
    
    # Build result table
    result = []
    for (year, tag), amounts in sorted(by_year_tag.items()):
        result.append({
            "year": year,
            "tag": tag,
            "total": sum(amounts),
            "mean": sum(amounts) / len(amounts) if amounts else 0,
            "count": len(amounts)
        })
    
    return jsonify({"data": result})


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