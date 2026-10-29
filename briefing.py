#!/usr/bin/env python3
"""
Daily Task-Focused Morning Briefing for Spouses & Partners.

Scans Gmail and macOS iMessage (chat.db) for:
- GO HERE: practices, games, pickups, drop-offs, appointments (with Day, Date & Time)
- DO THAT: explicit directives, forms, chores, commitments (with Day, Date & Time)
- REMEMBER THIS: specific reminders, deadlines, schedules (with Day, Date & Time)

Filters out casual chatter, commentary, and in-the-moment tactical coordination.
"""

import os
import sys
import json
import re
import sqlite3
import base64
import urllib.request
import urllib.parse
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

CONFIG_PATH = os.path.expanduser(os.environ.get("SPOUSE_BRIEFING_CONFIG", os.path.join(os.path.dirname(__file__), "config.json")))

def load_config():
    if not os.path.exists(CONFIG_PATH):
        sample = os.path.join(os.path.dirname(__file__), "config.example.json")
        raise FileNotFoundError(f"Configuration file not found at '{CONFIG_PATH}'. Copy '{sample}' to 'config.json' and fill in your details, or run with /interview-me.")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

# --- Authentication Helpers ---

def get_gmail_access_token():
    """Refreshes and returns an access token using standard Google OAuth credentials or MCP storage."""
    # Check ~/.google-mcp/ first, fallback to current dir or environment
    creds_path = os.path.expanduser(os.environ.get("GOOGLE_CREDS_PATH", "~/.google-mcp/credentials.json"))
    token_path = os.path.expanduser(os.environ.get("GOOGLE_TOKEN_PATH", "~/.google-mcp/tokens/work.json"))

    # Also check for default single-account token.json if work.json doesn't exist
    if not os.path.exists(token_path):
        alt_token = os.path.expanduser("~/.google-mcp/tokens/default.json")
        if os.path.exists(alt_token):
            token_path = alt_token

    if not os.path.exists(creds_path) or not os.path.exists(token_path):
        raise FileNotFoundError(f"Google OAuth credentials ({creds_path}) or authorized token ({token_path}) not found. Please connect your Google account.")

    with open(creds_path, "r", encoding="utf-8") as f:
        creds = json.load(f)
    client_info = creds.get("installed") or creds.get("web")

    with open(token_path, "r", encoding="utf-8") as f:
        token_data = json.load(f)

    data = urllib.parse.urlencode({
        "client_id": client_info["client_id"],
        "client_secret": client_info["client_secret"],
        "refresh_token": token_data["refresh_token"],
        "grant_type": "refresh_token"
    }).encode("utf-8")

    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))["access_token"]


# --- Scanners ---

def parse_ics_event_time(access_token, msg_id, parts):
    """Extracts exact event datetime from attached .ics calendar file if present."""
    for p in parts:
        filename = p.get("filename", "")
        mime = p.get("mimeType", "")
        if filename.endswith(".ics") or "calendar" in mime:
            att_id = p.get("body", {}).get("attachmentId")
            if att_id:
                try:
                    att_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}/attachments/{att_id}"
                    req = urllib.request.Request(att_url, headers={"Authorization": f"Bearer {access_token}"})
                    with urllib.request.urlopen(req) as resp:
                        att_data = json.loads(resp.read().decode("utf-8"))
                        ics_text = base64.urlsafe_b64decode(att_data["data"]).decode("utf-8", errors="ignore")
                        
                        dtstart = None
                        dtend = None
                        for line in ics_text.splitlines():
                            if line.startswith("DTSTART"):
                                val = line.split(":")[-1].strip()
                                try:
                                    dtstart = datetime.strptime(val, "%Y%m%dT%H%M%S")
                                except Exception:
                                    pass
                            elif line.startswith("DTEND"):
                                val = line.split(":")[-1].strip()
                                try:
                                    dtend = datetime.strptime(val, "%Y%m%dT%H%M%S")
                                except Exception:
                                    pass
                        if dtstart:
                            time_str = dtstart.strftime("%A, %b %d, %Y • %-I:%M %p")
                            if dtend:
                                time_str += f" – {dtend.strftime('%-I:%M %p')}"
                            return time_str
                except Exception:
                    pass
    return None


def fetch_recent_emails(access_token, spouse_emails, hours=24):
    """Fetches recent emails strictly from your spouse/partner."""
    after_epoch = int((datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp())
    query_parts = [f"from:{e}" for e in spouse_emails]
    q = f"({' OR '.join(query_parts)}) after:{after_epoch}"
    
    encoded_q = urllib.parse.quote(q)
    url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages?q={encoded_q}&maxResults=25"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {access_token}"})
    
    messages = []
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            msg_ids = [m["id"] for m in data.get("messages", [])]
    except Exception as e:
        print(f"Error listing Gmail messages: {e}", file=sys.stderr)
        return messages

    for mid in msg_ids:
        msg_url = f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{mid}?format=full"
        req_msg = urllib.request.Request(msg_url, headers={"Authorization": f"Bearer {access_token}"})
        try:
            with urllib.request.urlopen(req_msg) as resp:
                m_data = json.loads(resp.read().decode("utf-8"))
                headers = {h["name"].lower(): h["value"] for h in m_data.get("payload", {}).get("headers", [])}
                sender = headers.get("from", "")
                subject = headers.get("subject", "(No Subject)")
                snippet = m_data.get("snippet", "")
                parts = m_data.get("payload", {}).get("parts", [])
                
                schedule_time = parse_ics_event_time(access_token, mid, parts)
                
                if any(se.lower() in sender.lower() for se in spouse_emails):
                    messages.append({
                        "id": mid,
                        "channel": "email",
                        "sender": sender,
                        "is_from_spouse": True,
                        "subject": subject,
                        "text": snippet,
                        "date": headers.get("date", ""),
                        "schedule_time": schedule_time
                    })
        except Exception as e:
            print(f"Error fetching message {mid}: {e}", file=sys.stderr)

    return messages


def extract_text_from_attributed_body(data):
    """Extracts clean UTF-8 text from Apple's binary typedstream attributedBody."""
    if not data:
        return ""
    try:
        marker = b"\x84\x01\x2b"
        idx = data.find(marker)
        if idx != -1:
            sub = data[idx+3:]
            if len(sub) > 0:
                offset = 2 if sub[0] >= 0x80 else 1
                str_data = sub[offset:]
                end_idx = str_data.find(b"\x84")
                if end_idx != -1:
                    str_data = str_data[:end_idx]
                return str_data.decode("utf-8", errors="ignore").strip()
    except Exception:
        pass
    return ""


def fetch_recent_messages(spouse_phone, hours=24):
    """Fetches recent SMS/iMessage texts from macOS chat.db."""
    clean_phone = re.sub(r"[^\d]", "", spouse_phone)
    db_path = os.path.expanduser("~/Library/Messages/chat.db")
    if not os.path.exists(db_path):
        return [], "chat.db not found"

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cursor = conn.cursor()
        
        apple_epoch_offset = 978307200
        cutoff_apple_time = (datetime.now(timezone.utc).timestamp() - (hours * 3600) - apple_epoch_offset) * 1000000000
        
        query = """
            SELECT m.ROWID, m.text, m.attributedBody, m.is_from_me, m.date,
                   datetime(m.date/1000000000 + 978307200, 'unixepoch', 'localtime') as msg_time
            FROM message m
            JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
            JOIN chat c ON cmj.chat_id = c.ROWID
            WHERE c.chat_identifier LIKE ? AND m.date > ?
            ORDER BY m.date ASC
        """
        cursor.execute(query, (f"%{clean_phone}%", cutoff_apple_time))
        rows = cursor.fetchall()
        
        results = []
        for row in rows:
            row_id, raw_text, attr_body, is_from_me, raw_date, msg_time = row
            text = raw_text or extract_text_from_attributed_body(attr_body)
            if not text:
                continue
            results.append({
                "id": str(row_id),
                "channel": "text",
                "sender": "You" if is_from_me else "Spouse",
                "is_from_spouse": not is_from_me,
                "subject": "Text Message",
                "text": text,
                "date": msg_time,
                "schedule_time": None
            })
        conn.close()
        return results, None
    except sqlite3.OperationalError as e:
        return [], f"OperationalError ({e})"
    except Exception as e:
        return [], str(e)


# --- Schedule Extractor ---

def determine_task_schedule(item):
    """Returns a clean 'Day, Date • Time' string for the task."""
    if item.get("schedule_time"):
        return item["schedule_time"]

    text = item["text"]
    lower = text.lower()
    raw_date = item.get("date", "")
    
    base_dt = None
    try:
        if "," in raw_date:
            import email.utils
            base_dt = email.utils.parsedate_to_datetime(raw_date).astimezone()
        else:
            base_dt = datetime.strptime(raw_date[:19], "%Y-%m-%d %H:%M:%S")
    except Exception:
        base_dt = datetime.now()

    day_label = base_dt.strftime("%A, %b %d, %Y")

    if "before tomorrow" in lower:
        target = base_dt + timedelta(days=1)
        return f"Due: Tomorrow ({target.strftime('%A, %b %d')})"
    if "around 8" in lower:
        return f"{day_label} • Around 8:00 PM"
    if "after doctor" in lower or "after the doctor" in lower:
        return f"{day_label} • After doctor appointment"
    
    time_m = re.search(r'\b(\d{1,2}:\d{2}\s*(?:am|pm)?|\d{3,4}\s*(?:am|pm))\b', f"{item.get('subject','')} {text}".lower())
    if time_m:
        raw_t = time_m.group(0).upper().strip()
        if len(raw_t) in [5, 6] and raw_t[-2:] in ["AM", "PM"] and ":" not in raw_t:
            raw_t = f"{raw_t[:-4]}:{raw_t[-4:]}"
        return f"{day_label} • {raw_t}"

    return f"{day_label} • {base_dt.strftime('%-I:%M %p')} (Requested)"


# --- Strict Task-Focused Filter ---

IGNORE_SNIPPETS = [
    'pissed', 'ammo', 'pissing me off', 'feel the warm', 'idk', 'hahaha',
    'all good', 'good call', 'reprieve', 'omitting', 'fever free', 'love you',
    'in cup holder', 'walk in woo hoo', 'scoring was boring', 'play defense',
    'keys are in', 'just saw the nurse', 'stay home until', 'poor girly'
]

IN_THE_MOMENT_PATTERNS = [
    r'\btext\s+[a-zA-Z]+\s+directly\b',
    r'\bcall\s+me\b',
    r'\bcall\s+me\s+after\b',
    r'\btext\s+me\s+when\b',
    r'\bcall\s+u\b',
    r'\b(?:i\s*will|i\'ll)\s+(?:get|pick\s+up)\s+(?:her|him|them)\b',
    r'\bare\s+you\s+gonna\s+take\b',
    r'\bon\s+(?:my|your)\s+way\b'
]

def extract_task(item):
    text = item['text'].strip()
    subj = item.get('subject', '').strip()
    full = f"{subj} {text}".strip()
    lower = text.lower()
    full_lower = full.lower()
    is_spouse = item['is_from_spouse']

    # Filter out casual banter and chatter
    if any(ig in full_lower for ig in IGNORE_SNIPPETS):
        return None

    # Filter out in-the-moment immediate tactical actions
    if any(re.search(pat, full_lower) for pat in IN_THE_MOMENT_PATTERNS):
        return None

    schedule = determine_task_schedule(item)

    # --- EMAILS ---
    if item['channel'] == 'email':
        if 'canceled' in full_lower:
            clean_title = subj.replace('Canceled:', '').replace('CANCELED:', '').strip()
            return ('REMEMBER_THIS', f"Canceled: {clean_title}", text, schedule, False)
        if 'sign up' in full_lower or 'signup' in full_lower:
            return ('DO_THAT', f"Complete {subj}", text, schedule, True)
        if 'game' in full_lower or 'practice' in full_lower:
            return ('GO_HERE', subj, text, schedule, False)
        if 'reminder' in full_lower or 'festival' in full_lower:
            return ('REMEMBER_THIS', subj, text, schedule, True)
        return None

    # --- TEXTS (Forward-looking items to plan for, remember, or be part of) ---
    
    # 1. Online renewals or forms
    if any(kw in lower for kw in ['website', 'renew', 'registration', 'form', 'sign up']):
        return ('DO_THAT', f"Handle: {text}", text, schedule, True)

    # 2. Upcoming Chores / Project directives with deadlines
    if re.search(r'\b(?:need\s+to|make\s+sure\s+we)\s+(?:do|take|bring|get|finish)\b', lower) or 'before tomorrow' in lower:
        return ('DO_THAT', text, text, schedule, False)

    # 3. Scheduled pickups or deliveries
    if any(kw in lower for kw in ['picking up', 'grab', 'drop off', 'delivery']) and ('around' in lower or 'at' in lower):
        return ('REMEMBER_THIS', text, text, schedule, False)

    # 4. Explicit non-immediate reminders
    if 'reminder' in lower and is_spouse:
        m = re.search(r'reminder\s+([^.!]+)', text, re.I)
        if m:
            clean_rem = m.group(1).strip()
            if not any(re.search(pat, clean_rem.lower()) for pat in IN_THE_MOMENT_PATTERNS):
                return ('REMEMBER_THIS', clean_rem.capitalize(), text, schedule, False)

    return None


# --- Email Composer & Sender ---

def build_action_url(task_title, server_port):
    param = urllib.parse.quote(task_title)
    return f"http://127.0.0.1:{server_port}/start?task={param}"

def generate_email_html(tasks, config, imsg_err=None):
    go_here = [t for t in tasks if t['type'] == 'GO_HERE']
    do_that = [t for t in tasks if t['type'] == 'DO_THAT']
    remember_this = [t for t in tasks if t['type'] == 'REMEMBER_THIS']
    server_port = config.get("server_port", 8765)

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; color: #1e293b; background: #f8fafc; padding: 24px; margin: 0; }}
        .card {{ background: #ffffff; border-radius: 12px; max-width: 620px; margin: 0 auto; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.07); border: 1px solid #e2e8f0; overflow: hidden; }}
        .header {{ background: #0f172a; color: #ffffff; padding: 22px 28px; }}
        .header h1 {{ margin: 0; font-size: 20px; font-weight: 700; letter-spacing: -0.3px; }}
        .header p {{ margin: 6px 0 0; color: #94a3b8; font-size: 13px; }}
        .section {{ padding: 20px 28px; border-bottom: 1px solid #f1f5f9; }}
        .section-title {{ font-size: 14px; font-weight: 800; letter-spacing: 0.6px; text-transform: uppercase; margin-bottom: 14px; }}
        .title-go {{ color: #2563eb; }}
        .title-do {{ color: #dc2626; }}
        .title-rem {{ color: #d97706; }}
        .task-card {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px 16px; margin-bottom: 12px; }}
        .task-card.agent {{ border-left: 4px solid #16a34a; background: #f0fdf4; }}
        .task-title {{ font-size: 15px; font-weight: 700; color: #0f172a; line-height: 1.4; }}
        .task-schedule {{ font-size: 13px; color: #0284c7; background: #e0f2fe; display: inline-block; padding: 3px 8px; border-radius: 4px; font-weight: 600; margin-top: 6px; }}
        .task-quote {{ font-size: 12px; color: #64748b; margin-top: 6px; font-style: italic; }}
        .task-meta {{ font-size: 11px; color: #94a3b8; margin-top: 6px; }}
        .btn {{ display: inline-block; margin-top: 10px; padding: 7px 14px; background: #16a34a; color: #ffffff !important; text-decoration: none; border-radius: 6px; font-size: 12px; font-weight: 600; }}
        .empty {{ font-size: 13px; color: #94a3b8; margin: 0; }}
        .footer {{ padding: 16px 28px; font-size: 11px; color: #94a3b8; text-align: center; }}
      </style>
    </head>
    <body>
      <div class="card">
        <div class="header">
          <h1>{config.get("subject_line", "Morning Briefing")}</h1>
          <p>Daily Action Briefing • {datetime.now().strftime('%A, %B %d, %Y')}</p>
        </div>
    """

    # 1. GO HERE
    html += '<div class="section"><div class="section-title title-go">📍 GO HERE (Places, Games & Practices)</div>'
    if go_here:
        for t in go_here:
            html += f"""
            <div class="task-card">
              <div class="task-title">{t['title']}</div>
              <div class="task-schedule">📅 <strong>{t['schedule']}</strong></div>
              <div class="task-meta">{t['channel'].upper()}</div>
            </div>
            """
    else:
        html += '<p class="empty">No locations or scheduled games/practices today.</p>'
    html += '</div>'

    # 2. DO THAT
    html += '<div class="section"><div class="section-title title-do">⚡ DO THAT (Action Items & Chores)</div>'
    if do_that:
        for t in do_that:
            agent_class = " agent" if t['is_agent'] else ""
            action_btn = f'<a href="{build_action_url(t["title"], server_port)}" class="btn">👉 Start this task with AI</a>' if t['is_agent'] else ""
            html += f"""
            <div class="task-card{agent_class}">
              <div class="task-title">{t['title']}</div>
              <div class="task-schedule">📅 <strong>{t['schedule']}</strong></div>
              <div class="task-quote">"{t['details']}"</div>
              <div class="task-meta">{t['channel'].upper()}</div>
              {action_btn}
            </div>
            """
    else:
        html += '<p class="empty">No direct action items found.</p>'
    html += '</div>'

    # 3. REMEMBER THIS
    html += '<div class="section"><div class="section-title title-rem">🧠 REMEMBER THIS (Reminders & Deadlines)</div>'
    if remember_this:
        for t in remember_this:
            agent_class = " agent" if t['is_agent'] else ""
            action_btn = f'<a href="{build_action_url(t["title"], server_port)}" class="btn">👉 Start this task with AI</a>' if t['is_agent'] else ""
            html += f"""
            <div class="task-card{agent_class}">
              <div class="task-title">{t['title']}</div>
              <div class="task-schedule">📅 <strong>{t['schedule']}</strong></div>
              <div class="task-quote">"{t['details']}"</div>
              <div class="task-meta">{t['channel'].upper()}</div>
              {action_btn}
            </div>
            """
    else:
        html += '<p class="empty">No reminders for today.</p>'
    html += '</div>'

    html += f"""
        <div class="footer">
          Generated automatically • Only tasks and directives are captured. Banter filtered out.
        </div>
      </div>
    </body>
    </html>
    """
    return html


def send_briefing_email(access_token, recipient, subject, html_content):
    """Sends the briefing email using Gmail API."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = "me"
    msg["To"] = recipient

    plain_text = f"{subject}\n\nPlease view in an HTML email client to view your task breakdown."
    msg.attach(MIMEText(plain_text, "plain"))
    msg.attach(MIMEText(html_content, "html"))

    raw_base64 = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
    url = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
    data = json.dumps({"raw": raw_base64}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    })
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))


# --- Pipeline ---

def run_briefing(send_email=True, hours=24):
    config = load_config()
    print(f"[{datetime.now()}] Gathering communications for past {hours} hours...")
    access_token = get_gmail_access_token()
    
    emails = fetch_recent_emails(access_token, config["spouse_emails"], hours=hours)
    messages, imsg_err = fetch_recent_messages(config["spouse_phone"], hours=hours)
    
    all_raw = emails + messages
    print(f"Scanning {len(emails)} emails and {len(messages)} texts strictly for tasks...")
    
    tasks = []
    seen_titles = set()

    for item in all_raw:
        task = extract_task(item)
        if task:
            cat, title, details, schedule, is_agent = task
            norm = title.lower().strip()
            if norm not in seen_titles:
                seen_titles.add(norm)
                tasks.append({
                    "type": cat,
                    "title": title,
                    "details": details,
                    "schedule": schedule,
                    "is_agent": is_agent,
                    "channel": item["channel"],
                    "date": item["date"]
                })

    print(f"Extracted {len(tasks)} distinct tasks with day/date/time.")

    html = generate_email_html(tasks, config, imsg_err)
    
    if send_email:
        print(f"Sending task-focused briefing to {config['recipient_email']}...")
        res = send_briefing_email(access_token, config["recipient_email"], config["subject_line"], html)
        print(f"Sent! Gmail Message ID: {res.get('id')}")
    else:
        print("Dry run complete.")

    return html


# --- Server ---

def run_server():
    from http.server import HTTPServer, BaseHTTPRequestHandler
    config = load_config()
    port = config.get("server_port", 8765)

    class TaskHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == "/start":
                params = urllib.parse.parse_qs(parsed.query)
                task = params.get("task", ["Unknown Task"])[0]
                
                clean_task = task.replace('"', '\\"')
                os.system(f'osascript -e \'display notification "{clean_task}" with title "Briefing Task Started"\'')

                queue_path = os.path.join(os.path.dirname(__file__), "tasks_queue.json")
                queue = []
                if os.path.exists(queue_path):
                    try:
                        with open(queue_path, "r") as f:
                            queue = json.load(f)
                    except Exception:
                        pass
                queue.append({"task": task, "timestamp": datetime.now().isoformat()})
                with open(queue_path, "w") as f:
                    json.dump(queue, f, indent=2)

                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                resp_html = f"""
                <!DOCTYPE html>
                <html>
                <head><title>Task Started</title><meta name="viewport" content="width=device-width, initial-scale=1"></head>
                <body style="font-family: -apple-system, sans-serif; padding: 40px; text-align: center; background: #f0fdf4;">
                  <h1 style="color: #166534;">🚀 Agent Task Initiated!</h1>
                  <p style="font-size: 16px; color: #1e293b;"><strong>Task:</strong> {task}</p>
                  <p style="color: #64748b;">Logged to queue and notification delivered to your Mac.</p>
                </body>
                </html>
                """
                self.wfile.write(resp_html.encode("utf-8"))
            else:
                self.send_response(404)
                self.end_headers()

    server = HTTPServer(("127.0.0.1", port), TaskHandler)
    print(f"Action trigger server running at http://127.0.0.1:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    if "--serve" in sys.argv:
        run_server()
    elif "--dry-run" in sys.argv:
        run_briefing(send_email=False, hours=72)
    else:
        hours = 72 if "--weekend" in sys.argv else 24
        run_briefing(send_email=True, hours=hours)
