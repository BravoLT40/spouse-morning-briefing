---
name: interview-me
description: Guides new users through an interactive interview to configure their spouse/partner details, communication channels, schedule, and preferences for the morning briefing.
---

# Setup Interview for Spouse Morning Briefing

Use this skill when a user wants to set up, reconfigure, or customize their morning briefing.

## The Interview Process

Conduct a one-question-at-a-time interview with guesses attached to extract:

1. **Spouse / Partner Name:**
   - Q: What is your spouse or partner's name?
   - GUESS: E.g., Sarah, Alex, Taylor.

2. **Spouse Email Addresses:**
   - Q: What email address(es) does your spouse send emails to you from? (Include both work and personal emails if applicable).
   - GUESS: Usually 1 or 2 addresses (e.g. `partner@company.com` and `partner@gmail.com`).

3. **Spouse Mobile Number:**
   - Q: What is your spouse's mobile phone number? (Used to match iMessage and SMS conversations in macOS Messages).
   - GUESS: 10-digit number.

4. **Your Delivery Email:**
   - Q: Which email address should receive the daily morning briefing?
   - GUESS: Your primary personal or work email.

5. **Subject Line Customization:**
   - Q: What subject line would you like on your daily briefing email?
   - GUESS: `"Shit [Name] Told Me About"` or `"Morning Honey-Do Briefing"`.

6. **Delivery Time:**
   - Q: What time in the morning would you like the briefing email delivered?
   - GUESS: `6:15 AM` (local time).

---

## Action Upon Confirmation

Once the user explicitly confirms the extracted settings:

1. **Generate `config.json`:**
   Write the configuration to `config.json` in the root of this project:
   ```json
   {
     "recipient_email": "<user_email>",
     "subject_line": "<subject_line>",
     "spouse_name": "<spouse_name>",
     "spouse_emails": ["<spouse_email_1>", "<spouse_email_2>"],
     "spouse_phone": "<spouse_phone>",
     "briefing_hour": 6,
     "briefing_minute": 15,
     "server_port": 8765
   }
   ```

2. **Generate and Load macOS `launchd` Service:**
   Create `~/Library/LaunchAgents/com.user.spouse-briefing.plist` with the chosen hour and minute:
   ```xml
   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
   <plist version="1.0">
   <dict>
       <key>Label</key>
       <string>com.user.spouse-briefing</string>
       <key>ProgramArguments</key>
       <array>
           <string>/usr/bin/python3</string>
           <string><ABSOLUTE_PATH_TO_REPO>/briefing.py</string>
       </array>
       <key>StartCalendarInterval</key>
       <dict>
           <key>Hour</key>
           <integer>6</integer>
           <key>Minute</key>
           <integer>15</integer>
       </dict>
   </dict>
   </plist>
   ```
   And run `launchctl load ~/Library/LaunchAgents/com.user.spouse-briefing.plist`.

3. **Verify Permissions:**
   Remind the user to enable **Full Disk Access** for Terminal / Python under macOS **System Settings -> Privacy & Security -> Full Disk Access** so `chat.db` can be read.
