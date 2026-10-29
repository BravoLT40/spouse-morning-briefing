# ☕ Spouse Morning Briefing ("Shit My Spouse Told Me")

> Never forget what your spouse asked you to do, where you promised to be, or what was canceled.

An automated, task-focused morning briefing delivered directly to your inbox at **6:15 AM** (or your chosen time). It scans emails and macOS text messages (SMS / iMessage) from your partner, completely filters out conversational noise, and categorizes everything into:

- 📍 **GO HERE** — Games, practices, drop-offs, pickups, appointments (with exact day, date & times pulled from `.ics` calendar invites).
- ⚡ **DO THAT** — Chores, direct requests, online forms, renewals, and commitments. Includes one-click **`👉 Start this task with AI`** action buttons for digital tasks.
- 🧠 **REMEMBER THIS** — Scheduled pickups, deadlines, cancellations, and advance notices.

---

## 🚀 Quick Start

### Option 1: AI Setup via Antigravity (`/interview-me`)
If you use Google Antigravity or a compatible coding agent, simply open the project and run:
```bash
/interview-me
```
The agent will interview you step-by-step for your partner's name, emails, phone number, and delivery preferences, and automatically configure and schedule everything for you.

---

### Option 2: Interactive Terminal Setup
In your terminal, run:
```bash
git clone https://github.com/BravoLT40/spouse-morning-briefing.git
cd spouse-morning-briefing
./setup.sh
```
Follow the interactive prompts to generate your `config.json` and install the native macOS `launchd` daily scheduler.

---

### Option 3: Manual Configuration
1. Copy the example configuration:
   ```bash
   cp config.example.json config.json
   ```
2. Edit `config.json`:
   ```json
   {
     "recipient_email": "you@example.com",
     "subject_line": "Shit My Spouse Told Me",
     "spouse_name": "Alex",
     "spouse_emails": [
       "alex@work.com",
       "alex.personal@gmail.com"
     ],
     "spouse_phone": "5551234567",
     "briefing_hour": 6,
     "briefing_minute": 15,
     "server_port": 8765
   }
   ```
3. Test a dry run:
   ```bash
   python3 briefing.py --dry-run
   ```

---

## ⚙️ Requirements & Permissions

### 1. macOS Text Messages (Full Disk Access)
To allow the script to read synced SMS and iMessage texts from your Mac's local database (`~/Library/Messages/chat.db`):
1. Open **System Settings** -> **Privacy & Security** -> **Full Disk Access**.
2. Click **`+`** and enable **Terminal** (and `/usr/bin/python3` if running directly).
*(Without Full Disk Access, only emails will be scanned).*

### 2. Google Workspace / Gmail API
The script uses standard OAuth tokens to access the Gmail API.
- If you use the **Google Workspace MCP**, your credentials in `~/.google-mcp/` are detected and refreshed automatically.
- Alternatively, place your standard Google OAuth `credentials.json` and authorized token in `~/.google-mcp/` or specify their paths via environment variables `GOOGLE_CREDS_PATH` and `GOOGLE_TOKEN_PATH`.

---

## 🛠️ Architecture & Design Philosophy

- **Zero Heavy Dependencies:** Written entirely in **Python 3 standard library** (`urllib`, `sqlite3`, `email`, `re`, `json`). No `pip install` required.
- **Mac-Native Scheduler:** Uses macOS `launchd` (runs automatically even if your computer was asleep and wakes up).
- **In-the-Moment Filter:** Intelligently ignores tactical immediate coordination (e.g., *"text Debbie"*, *"call me after doctor"*, *"I will get her"*) so your morning digest only contains forward-looking items you need to remember or plan for.

---

## 📄 License
MIT License. Feel free to modify and adapt for your household!
