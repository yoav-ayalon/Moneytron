# MoneyTron V2

A simple, cross-platform personal finance tracker for families and friends. Upload your bank/credit files, categorize transactions, and view monthly summaries—all in your browser, with no cloud or account required.
<img width="2456" height="571" alt="image" src="https://github.com/user-attachments/assets/33543462-960f-4150-8527-a3a1d4f5e261" />

---

## Project Structure

```
Moneytron_V2/
├── client/                # Frontend (React, index.html)
│   └── index.html
├── server/                # Backend (Flask API)
│   └── new_app.py
├── users/                 # User data (auto-created per user)
│   └── <username>/
│       ├── categories.json
│       ├── current_month_transactions.json
│       ├── past_data.json
│       └── settings.json
├── requirements.txt       # Python dependencies
├── start.command          # Mac: Double-click to start app
├── old_versions/          # (Optional) Place old zips/backups here
└── .venv/                 # Python virtual environment (not needed for end users)
```

---

## How to Build a Standalone App (PyInstaller)

### 1. Prepare Your Environment
- Install Python 3.12 (recommended)
- Install dependencies:
  ```sh
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  pip install pyinstaller waitress flask
  ```

### 2. Build the Executable

#### MacOS
- Run:
  ```sh
  pyinstaller --onefile --add-data "client:client" server/new_app.py --name MoneyTron
  ```
- This creates `dist/MoneyTron` (the app). Test it:
  ```sh
  ./dist/MoneyTron
  ```
- Create a `start.command` file in the zip folder:
  ```sh
  #!/bin/bash
  cd "$(dirname "$0")"
  ./MoneyTron
  ```
- Make it executable:
  ```sh
  chmod +x start.command
  chmod +x MoneyTron
  ```

#### Windows
- create env:
  ```sh
  python3 -m venv .venv
  .venv\Scripts\pip install -r requirements.txt pyinstaller waitress flask

  
- Run:
  ```sh
  pyinstaller --onefile --add-data "client;client" server/new_app.py --name MoneyTron.exe
  .venv\Scripts\pyinstaller `
  --name MoneyTron `
  --onefile `
  --add-data "client;client" `
  --add-data "users;users" `
  server\new_app.py
  ```
- This creates `dist/MoneyTron.exe`.
- Create a `start.bat` file in the zip folder:
  ```bat
  @echo off
  cd /d "%~dp0"
  
  echo [Start] MoneyTron launcher
  echo [Start] Working dir: %cd%
  
  REM Kill anything still running on port 5003
  for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5003') do taskkill /F /PID %%a >nul 2>&1
  
  REM Start MoneyTron
  start "" /b dist\MoneyTron.exe
  
  REM Wait up to 40 seconds for server to be ready
  setlocal enabledelayedexpansion
  set COUNT=0
  :loop
    powershell -command "try {Invoke-WebRequest -Uri http://127.0.0.1:5003 -UseBasicParsing | Out-Null; exit 0} catch {exit 1}"
    if !errorlevel! equ 0 (
      echo [OK] Server started.
      start "" http://127.0.0.1:5003
      exit /b 0
    )
    set /a COUNT+=1
    if !COUNT! geq 40 (
      echo [ERROR] Server did not start. Check moneytron.log
      pause
      exit /b 1
    )
    timeout /t 1 >nul
  goto loop
  ```

---

## How to Package and Share
1. Copy the following to a new folder:
   - `dist/MoneyTron` (Mac) or `dist/MoneyTron.exe` (Windows)
   - `client/` folder
   - `start.command` (Mac) or `start.bat` (Windows)
   - (Optional) `users/` folder if you want to pre-populate data
2. Zip the folder and send to family/friends.
3. They unzip, double-click `start.command` (Mac) or `start.bat` (Windows), and use the app in their browser (usually opens at http://127.0.0.1:5003/).

---

## Usage Guide
- **First time:** Upload your bank/credit file, categorize transactions, and save. View the summary for insights.
- **Later:** Open the app again, view the summary, or upload new files as needed.
- **No install needed:** Just unzip and double-click the start file.

---

## Versioning & Backups
- Place old zips or backup folders in `old_versions/` for easy reference.

---

## Demo & Media
- Add screenshots to a `screenshots/` folder (create if needed).
- Add a demo video (e.g., `demo.mp4`).
- Update this README with image/video links if uploading to GitHub.
<img width="1440" height="900" alt="Screenshot 2025-08-16 at 20 55 10 (2)" src="https://github.com/user-attachments/assets/24c5b98b-ca99-4d15-b54e-7fb925dfbdc6" />
<img width="1440" height="900" alt="Screenshot 2025-08-16 at 20 55 05 (2)" src="https://github.com/user-attachments/assets/8c9a009c-ab9e-427b-8704-6cfcf753ea95" />
<img width="1440" height="900" alt="Screenshot 2025-08-16 at 20 55 21 (2)" src="https://github.com/user-attachments/assets/f12a55a9-a873-4343-a42f-24f6ec17996f" />
<img width="1440" height="900" alt="Screenshot 2025-08-16 at 20 55 29 (2)" src="https://github.com/user-attachments/assets/b3d5177f-a80c-4413-ae2e-4cfad3d584a9" />

- 

https://github.com/user-attachments/assets/0b3a2235-7104-44b0-96d2-fbed7f6b0610




