# MoneyTron V2 — README

A simple, cross-platform personal finance tracker for families and friends.  
Upload your bank/credit files, categorize transactions, and view monthly summaries — all in your browser, with **no cloud and no accounts**. Data lives in the local `users/` folder.


---


## Screenshots

Below are inline screenshots of MoneyTron in action (see the `screenshots/` folder for all images):

**Login Page**  
<img src="screenshots/login page.png" alt="Login Page" width="400" />

**Categories Tab**  
<img src="screenshots/catagories tab.png" alt="Categories Tab" width="400" />

**Settings Tab**  
<img src="screenshots/settings tab.png" alt="Settings Tab" width="400" />

**Summary Tab (no data)**  
<img src="screenshots/summary tab nd image.png" alt="Summary Tab No Data" width="400" />

**Summary Tab (with data)**  
<img src="screenshots/summary tab st image.png" alt="Summary Tab With Data" width="400" />

**Transactions Tab**  
<img src="screenshots/transactions tab.png" alt="Transactions Tab" width="400" />

---


## Demo Video

Watch the MoneyTron demo video below:

<video src="videos/demo%20video.mp4" controls width="600" poster="screenshots/login page.png">
   Your browser does not support the video tag.
</video>

---

---

## Table of contents

- [What you can do](#what-you-can-do)
- [Project structure](#project-structure)
- [How it works (high-level)](#how-it-works-high-level)
- [Quick start (dev mode)](#quick-start-dev-mode)
- [Build & package for macOS](#build--package-for-macos)
- [Build & package for Windows](#build--package-for-windows)
- [For family users (how to run it)](#for-family-users-how-to-run-it)
- [Updating the app (what-to-do-on-update)](#updating-the-app-what-to-do-on-update)
- [Troubleshooting](#troubleshooting)
- [Data & privacy](#data--privacy)

---

## What you can do

- **Multi-user:** each person has their own folder under `users/<Name>/`.
- **Transactions:** upload monthly bank/credit files (CSV/XLSX; Hebrew headers supported), review & categorize.
- **Manual add:** add single transactions if needed.
- **Summary:** view totals by category/month and make finance conclusions.
- **No internet required:** everything runs locally at `http://127.0.0.1:5003/`.

---

## Project structure

```
MoneyTron/
├─ server/
│  └─ new_app.py              # Flask backend (Waitress), serves the UI and APIs (port 5003)
├─ client/
│  └─ index.html              # Single-file React frontend
├─ users/
│  └─ Roy/
│     ├─ categories.json
│     ├─ current_month_transactions.json
│     └─ past_data.json
│     └─ settings.json
├─ start.command              # (macOS) double-click to run (kills port 5003; opens Chrome; starts app)
├─ Start_MoneyTron.bat        # (Windows) double-click to run (kills port 5003; opens browser; starts app)
└─ README.md
```

> The backend expects the **executable** (after packaging) to sit next to `client/` and `users/`.

---

## How it works (high-level)

- On launch, the backend serves `client/index.html` and static assets.  
- The `users/` directory stores all personal data (per user).  
- When you upload files, they are parsed, shown in **Transactions**, and (when you save) written to:
  - `users/<Name>/current_month_transactions.json`
  - `users/<Name>/past_data.json` (merge happens only when you explicitly save)

---

## Quick start (dev mode)

> Use this for local development, testing, or quick fixes without packaging.

1. **Python & venv**
   ```bash
   cd MoneyTron
   python3 -m venv .venv            # Windows: py -m venv .venv
   source .venv/bin/activate        # Windows: .\.venv\Scriptsctivate
   pip install -U pip flask waitress
   ```

2. **Run the server**
   ```bash
   python3 server/new_app.py        # Windows: py server
ew_app.py
   ```

3. **Open the app**  
   Go to http://127.0.0.1:5003/ in your browser.

---

## Build & package for macOS

> Requires Python 3.10–3.12 and PyInstaller.

1. **Install build deps**
   ```bash
   cd MoneyTron
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -U pip pyinstaller flask waitress
   ```

2. **Build the single-file app**
   ```bash
   pyinstaller      --name MoneyTron      --onefile      --add-data "client:client"      server/new_app.py
   ```

3. **Move the executable next to folders**
   ```bash
   mv dist/MoneyTron .
   ```

4. **Create (or update) `start.command`**  
   Save this file at `MoneyTron/start.command`:

   ```bash
   #!/bin/bash
   set -euo pipefail
   cd "$(dirname "$0")"

   # Ensure executable bits
   chmod +x MoneyTron || true

   # Kill anything on port 5003 (ignore errors)
   if lsof -ti:5003 >/dev/null 2>&1; then
     lsof -ti:5003 | xargs kill -9 || true
   fi

   # Open browser after a short delay (Chrome preferred; fallback to default)
   ( sleep 2; open -a "Google Chrome" "http://127.0.0.1:5003/" || open "http://127.0.0.1:5003/" ) &

   # Run the app (blocks)
   ./MoneyTron
   ```

   Make it executable:
   ```bash
   chmod +x start.command
   ```

5. **Prepare a zip for family**
   - Ensure the folder contains: `MoneyTron` (executable), `client/`, `users/`, `start.command`.
   - Right-click the **MoneyTron** folder → **Compress**.
   - Send the resulting `.zip`.

---

## Build & package for Windows

> Use **Command Prompt (cmd)** for the build commands below.  
> (PowerShell uses different line continuations; see Troubleshooting.)

1. **Install build deps (cmd)**
   ```bat
   cd MoneyTron
   py -m venv .venv
   .\.venv\Scriptsctivate
   pip install -U pip pyinstaller flask waitress
   ```

2. **Build the single-file app (cmd)**
   ```bat
   pyinstaller ^
     --name MoneyTron ^
     --onefile ^
     --add-data "client;client" ^
     server
ew_app.py
   ```

3. **Move the executable next to folders (cmd)**
   ```bat
   move /Y dist\MoneyTron.exe .
   ```

4. **Create (or update) `Start_MoneyTron.bat`**  
   Save this file at `MoneyTron/Start_MoneyTron.bat`:

   ```bat
   @echo off
   setlocal
   cd /d "%~dp0"

   rem Kill anything on port 5003 (ignore errors)
   for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5003') do taskkill /PID %%a /F >nul 2>&1

   rem Open browser after a short delay in a separate shell
   start "" cmd /c "timeout /t 2 >nul & start "" http://127.0.0.1:5003/"

   rem Run the app (blocks)
   MoneyTron.exe
   ```

5. **Prepare a zip for family**
   - Ensure the folder contains: `MoneyTron.exe`, `client\`, `users\`, `Start_MoneyTron.bat`.
   - Right-click the **MoneyTron** folder → **Send to → Compressed (zipped) folder**.
   - Send the `.zip`.

---

## For family users (how to run it)

### macOS (once or twice a month)

1. **Unzip** the folder you received (e.g., to Desktop).  
2. **Double-click `start.command`**.  
   - If macOS warns that it’s from the internet, right-click → **Open** → **Open**.  
   - If still blocked, see Troubleshooting.
3. The app opens in Chrome (or your default browser) at **http://127.0.0.1:5003/**.
4. Use the app:
   - **Transactions** → upload your monthly files, review & categorize → **Save**.
   - **Summary** → view your month, categories, insights.

### Windows (once or twice a month)

1. **Unzip** the folder you received (e.g., to Desktop).  
2. **Double-click `Start_MoneyTron.bat`**.  
   - If SmartScreen appears, click **More info → Run anyway**.
3. Your browser opens at **http://127.0.0.1:5003/**.
4. Use **Transactions** to upload & categorize → **Save** → check **Summary**.

> **Your data lives in the `users/` folder.** Back it up occasionally (copy that folder).

---

## Updating the app (what-to-do-on-update)

There are two common types of updates:

### 1) UI change only (`client/index.html`)
- **Developer:** rebuild the app and send a **new zip**  
  (Because the packaged executable embeds the `client/` folder.)
  - macOS: run the PyInstaller command again, update `MoneyTron` + `start.command`, zip and send.
  - Windows: run the PyInstaller command again, update `MoneyTron.exe` + `Start_MoneyTron.bat`, zip and send.
- **Family:** delete the old folder, unzip the new one. **Keep your old `users/` folder!**  
  If needed, copy your old `users/` into the new folder (replace the empty one).

### 2) Backend change (`server/new_app.py`)
- Same process as above: **rebuild and send a new zip** for macOS/Windows.

> **Fast patch (developers only, dev mode):** you can test changes by running `python server/new_app.py` locally without packaging. For family distribution, always rebuild.

---

## Troubleshooting

**A) Nothing opens / only background color**  
- Make sure `client/` was included in the build:
  - macOS: `--add-data "client:client"`
  - Windows: `--add-data "client;client"`
- Ensure the executable (`MoneyTron` or `MoneyTron.exe`) sits **next to** `client/` and `users/`.
- Open the browser console (F12) and check for 404s; if `index.html` can’t be found, rebuild.

**B) “Port 5003 already in use”**  
- The start scripts try to kill existing processes, but you can also do it manually:
  - macOS:
    ```bash
    lsof -ti:5003 | xargs kill -9
    ```
  - Windows (cmd):
    ```bat
    for /f "tokens=5" %a in ('netstat -ano ^| findstr :5003') do taskkill /PID %a /F
    ```

**C) macOS says the file is from an unidentified developer**  
- Right-click `start.command` → **Open** → **Open**.  
- Or remove quarantine:
  ```bash
  xattr -dr com.apple.quarantine .
  ```

**D) PowerShell errors like “Missing expression after unary operator --”**  
- You’re running the **Windows build command in PowerShell** with caret `^` line breaks.  
- Use **Command Prompt (cmd)**, or put it on **one line** in PowerShell:
  ```powershell
  pyinstaller --name MoneyTron --onefile --add-data "client;client" server/new_app.py
  ```

**E) 404 on “/”**  
- Run from the **project root**.
- Verify `server/new_app.py` serves the UI and that `client/index.html` exists.

---

## Data & privacy

- All your data stays local in `users/<Name>/`.
- To back up, copy the entire `users/` folder.
- To move computers, copy `users/` into the new MoneyTron folder.

**Files:**
- `categories.json` — your categories & preferences
- `current_month_transactions.json` — the month you are currently editing
- `past_data.json` — archive of saved months

---


## Build scripts (copy-paste)

### `start.command` (macOS)

```bash
#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

chmod +x MoneyTron || true

if lsof -ti:5003 >/dev/null 2>&1; then
  lsof -ti:5003 | xargs kill -9 || true
fi

( sleep 2; open -a "Google Chrome" "http://127.0.0.1:5003/" || open "http://127.0.0.1:5003/" ) &

./MoneyTron
```

Make executable:
```bash
chmod +x start.command
```

### `Start_MoneyTron.bat` (Windows)

```bat
@echo off
setlocal
cd /d "%~dp0"

for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5003') do taskkill /PID %%a /F >nul 2>&1

start "" cmd /c "timeout /t 2 >nul & start "" http://127.0.0.1:5003/"

MoneyTron.exe
```

---

## Build commands (copy-paste)

### macOS

```bash
cd MoneyTron
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip pyinstaller flask waitress

pyinstaller   --name MoneyTron   --onefile   --add-data "client:client"   server/new_app.py

mv dist/MoneyTron .
chmod +x start.command
```

### Windows (cmd)

```bat
cd MoneyTron
py -m venv .venv
.\.venv\Scriptsctivate
pip install -U pip pyinstaller flask waitress

pyinstaller ^
  --name MoneyTron ^
  --onefile ^
  --add-data "client;client" ^
  server
ew_app.py

move /Y dist\MoneyTron.exe .
```
