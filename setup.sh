#!/bin/bash
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
CONFIG_FILE="$DIR/config.json"

echo "============================================="
echo "   Spouse Morning Briefing Setup Wizard      "
echo "============================================="
echo ""

if [ -f "$CONFIG_FILE" ]; then
    read -p "config.json already exists. Overwrite? (y/N): " OVERWRITE
    if [[ ! "$OVERWRITE" =~ ^[Yy]$ ]]; then
        echo "Keeping existing config.json."
        exit 0
    fi
fi

read -p "Enter spouse/partner's name: " SPOUSE_NAME
read -p "Enter spouse's primary email address: " SPOUSE_EMAIL_1
read -p "Enter spouse's secondary email address (optional, press Enter to skip): " SPOUSE_EMAIL_2
read -p "Enter spouse's 10-digit mobile phone number (for SMS/iMessage): " SPOUSE_PHONE
read -p "Enter your email address to receive briefings: " RECIPIENT_EMAIL
read -p "Enter subject line [Default: Shit $SPOUSE_NAME Told Me About]: " SUBJECT_LINE
SUBJECT_LINE=${SUBJECT_LINE:-"Shit $SPOUSE_NAME Told Me About"}
read -p "Enter briefing delivery hour (0-23) [Default: 6]: " BRIEFING_HOUR
BRIEFING_HOUR=${BRIEFING_HOUR:-6}
read -p "Enter briefing delivery minute (0-59) [Default: 15]: " BRIEFING_MINUTE
BRIEFING_MINUTE=${BRIEFING_MINUTE:-15}

EMAILS="\"$SPOUSE_EMAIL_1\""
if [ -n "$SPOUSE_EMAIL_2" ]; then
    EMAILS="\"$SPOUSE_EMAIL_1\", \"$SPOUSE_EMAIL_2\""
fi

cat <<EOF > "$CONFIG_FILE"
{
  "recipient_email": "$RECIPIENT_EMAIL",
  "subject_line": "$SUBJECT_LINE",
  "spouse_name": "$SPOUSE_NAME",
  "spouse_emails": [$EMAILS],
  "spouse_phone": "$SPOUSE_PHONE",
  "briefing_hour": $BRIEFING_HOUR,
  "briefing_minute": $BRIEFING_MINUTE,
  "server_port": 8765
}
EOF

echo ""
echo "✅ Saved configuration to $CONFIG_FILE"

# Setup LaunchAgent
PLIST_PATH="$HOME/Library/LaunchAgents/com.user.spouse-briefing.plist"
cat <<EOF > "$PLIST_PATH"
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.spouse-briefing</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>$DIR/briefing.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>$BRIEFING_HOUR</integer>
        <key>Minute</key>
        <integer>$BRIEFING_MINUTE</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>$DIR/briefing.log</string>
    <key>StandardErrorPath</key>
    <string>$DIR/briefing_err.log</string>
</dict>
</plist>
EOF

launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load "$PLIST_PATH"

echo "✅ Scheduled daily $BRIEFING_HOUR:$(printf "%02d" $BRIEFING_MINUTE) briefing via launchd ($PLIST_PATH)"
echo ""
echo "⚠️  IMPORTANT: To allow reading text messages on macOS:"
echo "   Open System Settings -> Privacy & Security -> Full Disk Access"
echo "   and enable Terminal (or Python)."
echo ""
echo "🎉 Setup complete! Test run now with:"
echo "   python3 $DIR/briefing.py --dry-run"
