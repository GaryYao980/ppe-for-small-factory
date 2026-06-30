#!/bin/bash
# ============================================================
# PPE Detection Cluster - Auto Start Setup Script (macOS launchd)
# ============================================================

# Auto-detect working directory and Python path
WORKING_DIR=$(pwd)
PYTHON_PATH=$(which python3)

echo "====================================================="
echo " 🛡️ Configuring PPE Smart Security Cluster (Daemon Mode)"
echo "====================================================="
echo "📂 Auto-detected working directory: ${WORKING_DIR}"
echo "🐍 Python interpreter path: ${PYTHON_PATH}"
echo "-----------------------------------------------------"

# Create log directory
mkdir -p "$WORKING_DIR/logs"

# Function to generate plist
create_service() {
    local SERVICE_ID=$1
    local SCRIPT_NAME=$2
    local PORT=$3
    local PLIST_NAME="com.ppe.${SERVICE_ID}"
    local PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"

    echo "⚙️ Registering service: ${SERVICE_ID} (Port: ${PORT})..."

    cat > "$PLIST_PATH" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_NAME}</string>

    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON_PATH}</string>
        <string>-m</string>
        <string>streamlit</string>
        <string>run</string>
        <string>${WORKING_DIR}/${SCRIPT_NAME}</string>
        <string>--server.port</string>
        <string>${PORT}</string>
        <string>--server.headless</string>
        <string>true</string>
    </array>

    <key>WorkingDirectory</key>
    <string>${WORKING_DIR}</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>${WORKING_DIR}/logs/${SERVICE_ID}_out.log</string>
    <key>StandardErrorPath</key>
    <string>${WORKING_DIR}/logs/${SERVICE_ID}_err.log</string>
</dict>
</plist>
PLIST

    launchctl unload "$PLIST_PATH" 2>/dev/null
    launchctl load "$PLIST_PATH"
}

create_service "hr_admin" "qr_code.py" "8501"
create_service "gate1" "gate1_attendance.py" "8502"
create_service "gate2" "gate2_ppe_system.py" "8503"

echo "-----------------------------------------------------"
echo "✅ Cluster deployed! Background daemons have taken over."
echo ""
echo "🌐 Local Access URLs:"
echo "  👨‍💼 HR Admin : http://localhost:8501"
echo "  ⏱️ Gate 1   : http://localhost:8502"
echo "  🛡️ Gate 2   : http://localhost:8503"
echo ""
echo "📝 Log files stored at: ${WORKING_DIR}/logs/"
echo "====================================================="
echo "🛑 Emergency Control Manual:"
echo "  Because KeepAlive is true, closing the terminal or killing the process won't work (auto-respawn)."
echo "  To fully stop and unload the system, run these commands:"
echo "  launchctl unload ~/Library/LaunchAgents/com.ppe.hr_admin.plist"
echo "  launchctl unload ~/Library/LaunchAgents/com.ppe.gate1.plist"
echo "  launchctl unload ~/Library/LaunchAgents/com.ppe.gate2.plist"
echo "====================================================="