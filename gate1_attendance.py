import streamlit as st
import sqlite3
import os
import cv2
import time
import pandas as pd
from pyzbar.pyzbar import decode  # Import industrial-grade core
from datetime import datetime
from sound_manager import SoundManager  # Load sound manager

sound_manager = SoundManager()  # Initialize sound manager

# ========== 1. Infrastructure ==========
DB_FILE = "industrial_ppe.db"
ATTENDANCE_DIR = "attendance_snapshots"
os.makedirs(ATTENDANCE_DIR, exist_ok=True)


def init_db():
    conn = sqlite3.connect(DB_FILE, timeout=10)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id TEXT NOT NULL,
            date TEXT NOT NULL,
            entry_time TEXT NOT NULL,
            entry_snapshot TEXT NOT NULL,
            exit_time TEXT,
            exit_snapshot TEXT,
            gate1_status TEXT DEFAULT 'COMPLETED'
        )
    ''')
    conn.commit()
    conn.close()


init_db()

# ========== 2. UI Layout ==========
st.set_page_config(page_title="Gate 1: Seamless Attendance",
                   page_icon="⏱️", layout="centered")
st.markdown("""
<style>
    .stApp { background-color: #1e1e1e; }
    .main-title { font-size: 2rem; font-weight: bold; color: #ffffff; text-align: center; }
    .success-box { background: #00d26a22; border-left: 4px solid #00d26a; padding: 15px; border-radius: 5px; color: #ffffff; text-align: center; font-size: 1.2rem; margin-bottom: 10px;}
    .exit-box { background: #007bff22; border-left: 4px solid #007bff; padding: 15px; border-radius: 5px; color: #ffffff; text-align: center; font-size: 1.2rem; margin-bottom: 10px;}
    .alert-box { background: #ff000033; border-left: 4px solid #ff0000; padding: 15px; border-radius: 5px; color: #ffffff; text-align: center; font-size: 1.2rem; margin-bottom: 10px;}
    .denied-box { background: #ff6b3522; border-left: 4px solid #ff6b35; padding: 15px; border-radius: 5px; color: #ffffff; text-align: center; font-size: 1.2rem; margin-bottom: 10px;}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">🚪 Gate 1: Seamless Attendance Channel</div>',
            unsafe_allow_html=True)
st.markdown("---")

run_scanner = st.toggle("🟢 Start Dynamic Scanner Camera (PyZbar Engine)")

FRAME_WINDOW = st.image([])
status_box = st.empty()

# ========== 3. PyZbar Brute Force Capture & Attendance Loop Logic ==========
if run_scanner:
    cap = cv2.VideoCapture(0)
    status_box.info(
        "⏳ Camera warming up and adjusting exposure, please wait...")

    # Anti-continuous scan and alarm control variables
    last_scanned_worker = None
    last_scan_time = 0
    COOLDOWN_SECONDS = 4
    invalid_scan_count = 0  # 🚨 New: Record continuous illegal scan count

    try:
        frame_count = 0

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                status_box.error(
                    "Failed to capture frame! Camera might be blocked by system privacy settings.")
                break

            frame_count += 1

            if frame_count < 30:
                res_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                FRAME_WINDOW.image(res_rgb)
                continue
            elif frame_count == 30:
                status_box.info(
                    "🟢 Exposure adjusted! Scanning engine online, please show your access code.")

            decoded_objects = decode(frame)

            if decoded_objects:
                obj = decoded_objects[0]
                worker_id = obj.data.decode('utf-8')

                # 🛡️ Anti-continuous scan cooldown
                if worker_id == last_scanned_worker and (time.time() - last_scan_time) < COOLDOWN_SECONDS:
                    res_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    FRAME_WINDOW.image(res_rgb)
                    continue

                # Draw green box
                points = obj.polygon
                if len(points) == 4:
                    pts = [(points[i].x, points[i].y) for i in range(4)]
                    for i in range(4):
                        cv2.line(frame, pts[i], pts[(i+1) % 4], (0, 255, 0), 4)

                now = datetime.now()
                current_date = now.strftime("%Y-%m-%d")
                current_time = now.strftime("%H:%M:%S")
                timestamp_str = now.strftime("%Y%m%d_%H%M%S")

                try:
                    conn = sqlite3.connect(DB_FILE, timeout=10)
                    cursor = conn.cursor()

                    # 🔍 Core Modification 1: Identity Whitelist Verification
                    cursor.execute(
                        "SELECT name FROM workers WHERE worker_id = ?", (worker_id,))
                    worker_info = cursor.fetchone()

                    if not worker_info:
                        # ❌ Profile not found: Execute block logic
                        invalid_scan_count += 1

                        if invalid_scan_count >= 3:
                            # 🚨 3 consecutive break-in attempts: Trigger max level alert
                            sound_manager.play_alert()
                            status_box.markdown(
                                f'<div class="alert-box">🚨 <b>SECURITY BREACH</b><br>{invalid_scan_count} consecutive unauthorized access attempts!<br>Unknown ID: {worker_id}</div>', unsafe_allow_html=True)
                        else:
                            # ❌ Standard block
                            sound_manager.play_denied()
                            status_box.markdown(
                                f'<div class="denied-box">❌ <b>Access Denied</b><br>Employee profile not found in system!<br>ID: {worker_id}</div>', unsafe_allow_html=True)

                        last_scanned_worker = worker_id
                        last_scan_time = time.time()

                        res_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        FRAME_WINDOW.image(res_rgb)

                        conn.close()
                        # Pause slightly to let alarm sound play out
                        time.sleep(2.5)
                        status_box.info(
                            "🟢 Gate reset: Next employee, please show your access code...")
                        continue

                    # ✅ Verification passed, reset illegal scan counter
                    invalid_scan_count = 0
                    worker_name = worker_info[0]

                    # 👇 Below is the original valid employee entry/exit attendance logic
                    cursor.execute('''
                        SELECT id, entry_time, exit_time 
                        FROM attendance_log 
                        WHERE worker_id = ? AND date = ? 
                        ORDER BY id DESC LIMIT 1
                    ''', (worker_id, current_date))
                    record = cursor.fetchone()

                    if record is None or record[2] is not None:
                        filename = f"G1_IN_{worker_id}_{timestamp_str}.jpg"
                        save_path = os.path.join(ATTENDANCE_DIR, filename)
                        cv2.imwrite(save_path, frame)

                        cursor.execute('''
                            INSERT INTO attendance_log (worker_id, date, entry_time, entry_snapshot)
                            VALUES (?, ?, ?, ?)
                        ''', (worker_id, current_date, current_time, save_path))

                        status_box.markdown(
                            f'<div class="success-box">🌅 <b>{worker_name} ({worker_id})</b> Entry Successful!<br>Current Time: {current_time}</div>', unsafe_allow_html=True)
                    else:
                        record_id = record[0]
                        entry_time = record[1]

                        filename = f"G1_OUT_{worker_id}_{timestamp_str}.jpg"
                        save_path = os.path.join(ATTENDANCE_DIR, filename)
                        cv2.imwrite(save_path, frame)

                        cursor.execute('''
                            UPDATE attendance_log 
                            SET exit_time = ?, exit_snapshot = ? 
                            WHERE id = ?
                        ''', (current_time, save_path, record_id))

                        status_box.markdown(
                            f'<div class="exit-box">🌇 <b>{worker_name} ({worker_id})</b> Exit Successful!<br>Duration: {entry_time} ➡️ {current_time}</div>', unsafe_allow_html=True)

                    conn.commit()
                    conn.close()

                    sound_manager.play_granted()
                    last_scanned_worker = worker_id
                    last_scan_time = time.time()

                    res_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    FRAME_WINDOW.image(res_rgb)

                    time.sleep(2)
                    status_box.info(
                        "🟢 Gate reset: Next employee, please show your access code...")

                except Exception as e:
                    status_box.error(f"System Error: {e}")
                    sound_manager.play_denied()
                    time.sleep(2)

            else:
                # 🛡️ Core Modification 2: Remove redundant blank frame error logic to keep smooth visual flow
                res_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                FRAME_WINDOW.image(res_rgb)

    finally:
        if cap.isOpened():
            cap.release()
else:
    status_box.warning("Camera is turned off.")

# ========== 4. HR Real-time Dashboard & Export Module ==========
st.markdown("---")
st.subheader("📋 Today's Live Attendance Dashboard")

try:
    conn = sqlite3.connect(DB_FILE)
    today_str = datetime.now().strftime("%Y-%m-%d")
    df = pd.read_sql_query(
        "SELECT worker_id AS 'Worker ID', entry_time AS 'Entry Time', exit_time AS 'Exit Time' FROM attendance_log WHERE date = ?",
        conn, params=(today_str,)
    )
    conn.close()

    if not df.empty:
        df['Exit Time'] = df['Exit Time'].fillna("🟢 On-site Working")
        st.dataframe(df, width="stretch", hide_index=True)

        csv_data = df.to_csv(index=False).encode('utf-8-sig')

        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.download_button(
                label="📥 Export Today's Attendance Report (Export for HR System)",
                data=csv_data,
                file_name=f"HSE_Attendance_Report_{today_str}.csv",
                mime="text/csv",
                use_container_width=True
            )
    else:
        st.info("📅 No attendance data today yet, waiting for the first employee.")
except Exception as e:
    st.error(f"Failed to load attendance dashboard: {e}")
