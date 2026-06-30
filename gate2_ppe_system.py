import streamlit as st
import sqlite3
import os
import cv2
import time
import requests
from datetime import datetime
from pyzbar.pyzbar import decode
from ultralytics import YOLO
from sound_manager import SoundManager  # 🔊 Import sound manager

sound_manager = SoundManager()

# ========== 1. Infrastructure Configuration ==========
DB_FILE = "industrial_ppe.db"
PPE_BASE_DIR = "ppe_captured_images"

# 🚨 Telegram Bot Config (Retained your real parameters)
TELEGRAM_BOT_TOKEN = "Insert_your_BotToken_here"
TELEGRAM_CHAT_ID = "Insert_your_ChatID_here"


def send_telegram_alert(message, image_path=None):
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "Insert_your_BotToken_here":
        print("⚠️ Warning: TELEGRAM_BOT_TOKEN not configured, skipping transmission.")
        return
    try:
        if image_path and os.path.exists(image_path):
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
            with open(image_path, 'rb') as photo:
                payload = {'chat_id': TELEGRAM_CHAT_ID, 'caption': message}
                files = {'photo': photo}
                requests.post(url, data=payload, files=files, timeout=10)
        else:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message}
            requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"❌ Telegram API Error: {e}")


@st.cache_resource
def load_yolo_model():
    return YOLO('best.pt')


def init_gate2_db():
    conn = sqlite3.connect(DB_FILE, timeout=10)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS workers (worker_id TEXT PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL, required_ppe TEXT NOT NULL, photo_path TEXT DEFAULT '')''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS checkins (
    id INTEGER PRIMARY KEY AUTOINCREMENT, attendance_id INTEGER, worker_id TEXT NOT NULL, gate_id TEXT NOT NULL, timestamp TEXT NOT NULL, required_ppe TEXT NOT NULL, raw_image_path TEXT NOT NULL, plotted_image_path TEXT NOT NULL, ai_status TEXT DEFAULT 'PENDING', missing_items TEXT DEFAULT '', FOREIGN KEY (attendance_id) REFERENCES attendance_log(id))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS reviews (id INTEGER PRIMARY KEY AUTOINCREMENT, checkin_id INTEGER NOT NULL, reviewer_id TEXT NOT NULL, gate_id TEXT NOT NULL, review_time TEXT NOT NULL, reviewer_status TEXT NOT NULL, corrected_items TEXT DEFAULT '', reviewer_notes TEXT DEFAULT '')''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS admin_overrides (id INTEGER PRIMARY KEY AUTOINCREMENT, scanned_worker_id TEXT, admin_id TEXT NOT NULL, gate_id TEXT NOT NULL, override_time TEXT NOT NULL, reason TEXT NOT NULL, snapshot_path TEXT NOT NULL)''')
    cursor.execute(
        '''CREATE TABLE IF NOT EXISTS users (user_id TEXT PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL, gate_id TEXT DEFAULT "")''')
    conn.commit()
    conn.close()


init_gate2_db()

# ========== 2. Global UI Styles ==========
CURRENT_GATE = "GATE-02"
ADMIN_PIN = os.environ.get("ADMIN_PIN", "888888")

if 'override_authorized' not in st.session_state:
    st.session_state.override_authorized = False

st.set_page_config(page_title="Gate 2 Smart Security Channel",
                   page_icon="🛡️", layout="wide")
st.markdown("""
<style>
    .stApp { background-color: #0f1117; }
    .title-box { text-align: center; color: #ffffff; padding: 10px; }
    .badge-pass { background: #00d26a22; color: #00d26a; border: 1px solid #00d26a44; border-radius: 4px; padding: 5px 10px;}
    .badge-fail { background: #ff6b3522; color: #ff6b35; border: 1px solid #ff6b3544; border-radius: 4px; padding: 5px 10px;}
</style>
""", unsafe_allow_html=True)

st.sidebar.title("🎛️ Physical Device Console")
role = st.sidebar.radio("Please select the current operating interface:", [
                        "👷‍♂️ Worker Terminal (Gate Camera)", "👨‍💼 Auditor Console"])

# ==================== 👷‍♂️ Role 1: Worker Terminal ====================
if role == "👷‍♂️ Worker Terminal (Gate Camera)":
    st.markdown(f"<div class='title-box'><h2>🛡️ Gate 2: Dynamic Smart PPE Verification Channel</h2></div>",
                unsafe_allow_html=True)

    simulate_no_auth = st.checkbox(
        "🧪 Simulate unscheduled or unknown personnel (Triggers Supervisor Override)")
    proceed_to_cv2 = False

    if not simulate_no_auth:
        st.session_state.override_authorized = False
        proceed_to_cv2 = True
    else:
        if not st.session_state.override_authorized:
            st.error(f"❌ Access Blocked: Personnel permission profile not found.")
            sound_manager.play_denied()  # 🔊
            with st.expander("⚠️ On-site Supervisor Override Channel (Admin Override)", expanded=True):
                with st.form("admin_override_form"):
                    admin_id = st.text_input("Supervisor ID (Admin ID):")
                    pin_code = st.text_input(
                        "Authorization PIN:", type="password")
                    reason = st.selectbox(
                        "Override Reason:", ["Temporary Emergency Repair", "Scheduling System Delay", "Executive Inspection", "Lost ID Card"])
                    override_snapshot = st.camera_input(
                        "📸 Face the camera for record")
                    report_to_supervisor = st.checkbox(
                        "📩 Send Alert & Photo to Supervisor", value=True)
                    submit_override = st.form_submit_button(
                        "🚨 Confirm Liability Waiver and Force Verification")

                    if submit_override and pin_code == ADMIN_PIN and admin_id and override_snapshot:
                        today_str = datetime.now().strftime("%Y-%m-%d")
                        today_dir = os.path.join(PPE_BASE_DIR, today_str)
                        os.makedirs(today_dir, exist_ok=True)
                        ts = datetime.now().strftime("%H%M%S")
                        save_path = os.path.join(
                            today_dir, f"OVERRIDE_{admin_id}_{ts}.jpg")
                        with open(save_path, "wb") as f:
                            f.write(override_snapshot.getbuffer())

                        conn = sqlite3.connect(DB_FILE)
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO admin_overrides (scanned_worker_id, admin_id, gate_id, override_time, reason, snapshot_path) VALUES (?, ?, ?, ?, ?, ?)",
                                       ("UNAUTHORIZED", admin_id, CURRENT_GATE, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), reason, save_path))
                        conn.commit()
                        conn.close()

                        if report_to_supervisor:
                            alert_msg = f"🚨 [SECURITY ALERT] Emergency Override\nGate: {CURRENT_GATE}\nAdmin ID: {admin_id}\nReason: {reason}\nAction: Allowed UNAUTHORIZED visitor."
                            send_telegram_alert(alert_msg, save_path)
                            st.success("📩 Alert dispatched to Supervisor.")

                        st.session_state.override_authorized = True
                        sound_manager.play_granted()  # 🔊 Override passed
                        st.rerun()
        else:
            st.success(
                "✅ Supervisor override activated! Initiating baseline (Helmet & Vest) verification...")
            proceed_to_cv2 = True

    if proceed_to_cv2:
        run_scanner = st.toggle(
            "🟢 Start Smart Verification Gate Camera", value=st.session_state.override_authorized)
        FRAME_WINDOW = st.image([])
        status_box = st.empty()

        if run_scanner:
            cap = cv2.VideoCapture(0)
            state = "WAITING"
            current_worker = "UNAUTHORIZED-OVERRIDE" if simulate_no_auth else None
            countdown_start = 0
            target_ppe_list = ["helmet", "vest"]
            last_scan_time = 0

            try:
                while cap.isOpened():
                    ret, frame = cap.read()
                    if not ret:
                        break

                    if state == "WAITING":
                        # During anti-continuous scan cooldown, keep visual flow smooth
                        if time.time() - last_scan_time < 3:
                            res_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            FRAME_WINDOW.image(res_rgb)
                            continue

                        if simulate_no_auth and st.session_state.override_authorized:
                            state = "COUNTDOWN"
                            countdown_start = time.time()
                        else:
                            status_box.info(
                                "🔍 Please align ID QR code with the camera to confirm identity...")
                            cv2.putText(frame, "SCAN YOUR ID CARD", (50, 50),
                                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3)

                            decoded = decode(frame)
                            if decoded:
                                current_worker = decoded[0].data.decode(
                                    'utf-8')

                                conn = sqlite3.connect(DB_FILE)
                                cursor = conn.cursor()
                                cursor.execute(
                                    "SELECT required_ppe FROM workers WHERE worker_id=?", (current_worker,))
                                row = cursor.fetchone()

                                # 🚨 Core Defense: Absolute Whitelist Blocking
                                if not row:
                                    status_box.error(
                                        f"❌ Access Blocked: System cannot find profile for ({current_worker})!")
                                    sound_manager.play_denied()
                                    last_scan_time = time.time()
                                    conn.close()
                                    continue

                                target_ppe_list = row[0].split(",")

                                # Check Gate 1 record
                                cur2 = conn.cursor()
                                cur2.execute("""
                                    SELECT id FROM attendance_log
                                    WHERE worker_id=? AND DATE(entry_time)=DATE('now')
                                    ORDER BY id DESC LIMIT 1
                                    """, (current_worker,))
                                att_row = cur2.fetchone()
                                conn.close()

                                st.session_state['current_attendance_id'] = att_row[0] if att_row else None
                                if not att_row:
                                    status_box.warning(
                                        f"⚠️ Warning: {current_worker} did not clock in at Gate 1 today, entering anomaly logging process.")
                                    sound_manager.play_alert()  # 🔊 Issue warning sound

                                state = "COUNTDOWN"
                                countdown_start = time.time()

                    elif state == "COUNTDOWN":
                        elapsed = time.time() - countdown_start
                        remaining = 3 - int(elapsed)
                        if remaining > 0:
                            ppe_hint = ", ".join(target_ppe_list).upper()
                            status_box.warning(
                                f"✅ Identity Confirmed: **{current_worker}**\n\n🎯 Your Required PPE: **{ppe_hint}**\n\n⏳ Please face the camera: **{remaining}**...")
                            cv2.putText(frame, f"FACE CAMERA: {remaining}s", (
                                20, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 255), 4)
                        else:
                            state = "SCANNING"

                    elif state == "SCANNING":
                        status_box.warning(
                            "📸 Capturing image and executing AI dynamic verification...")

                        today_str = datetime.now().strftime("%Y-%m-%d")
                        today_dir = os.path.join(PPE_BASE_DIR, today_str)
                        os.makedirs(today_dir, exist_ok=True)
                        ts = datetime.now().strftime("%H%M%S")

                        raw_path = os.path.join(
                            today_dir, f"G2_{current_worker}_{ts}_raw.jpg")
                        cv2.imwrite(raw_path, frame)

                        # Execute YOLOv8
                        model = load_yolo_model()
                        results = model(frame, conf=0.5, verbose=False)
                        detected = [model.names[int(box.cls[0])]
                                    for box in results[0].boxes]

                        missing = [
                            item for item in target_ppe_list if item not in detected]
                        ai_status = "PASS" if not missing else "FAIL"

                        res_plotted = results[0].plot()
                        plotted_path = os.path.join(
                            today_dir, f"G2_{current_worker}_{ts}_plotted.jpg")
                        cv2.imwrite(plotted_path, res_plotted)

                        # Write to DB
                        conn = sqlite3.connect(DB_FILE)
                        cursor = conn.cursor()
                        attendance_id = st.session_state.get(
                            'current_attendance_id', None)
                        cursor.execute("""INSERT INTO checkins
                            (attendance_id, worker_id, gate_id, timestamp, required_ppe,
                             raw_image_path, plotted_image_path, ai_status, missing_items)
                            VALUES (?,?,?,?,?,?,?,?,?)""",
                                       (attendance_id, current_worker, CURRENT_GATE,
                                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                        ",".join(
                                            target_ppe_list), raw_path, plotted_path,
                                        ai_status, ",".join(missing)))
                        conn.commit()
                        conn.close()

                        # 🔊 Play corresponding sound effect
                        if ai_status == "PASS":
                            sound_manager.play_granted()
                            status_box.success(
                                f"✅ AI Verification Complete: **PASS (Compliant)**. Gate opened, please proceed!")
                        else:
                            sound_manager.play_denied()
                            status_box.error(
                                f"❌ AI Verification Complete: **FAIL (Non-compliant)**. Missing equipment: {','.join(missing)}")

                        FRAME_WINDOW.image(cv2.cvtColor(
                            res_plotted, cv2.COLOR_BGR2RGB))

                        if st.session_state.override_authorized:
                            st.session_state.override_authorized = False

                        # 🔄 Core Fix: Pipeline Reset! Return to waiting state after showing results for 4 seconds
                        time.sleep(4)
                        state = "WAITING"
                        current_worker = None
                        last_scan_time = time.time()
                        status_box.info(
                            "🟢 Gate reset: Next employee, please show access code...")

                    if state != "SCANNING":
                        FRAME_WINDOW.image(cv2.cvtColor(
                            frame, cv2.COLOR_BGR2RGB))
            finally:
                if cap.isOpened():
                    cap.release()

# ==================== 👨‍💼 Role 2: Auditor Console ====================
elif role == "👨‍💼 Auditor Console":
    st.markdown(
        f"<div class='title-box'><h2>👨‍💼 Auditor Real-time Verification Dashboard ({CURRENT_GATE})</h2></div>", unsafe_allow_html=True)

    if 'reviewer_id' not in st.session_state:
        st.session_state['reviewer_id'] = None

    if not st.session_state['reviewer_id']:
        st.warning("⚠️ Please scan auditor ID card to login")
        cap = cv2.VideoCapture(0)
        frame_window = st.image([])
        frame_count = 0

        try:
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break

                frame_count += 1
                frame_window.image(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                if frame_count < 30:
                    continue

                decoded = decode(frame)
                if decoded:
                    scanned_id = decoded[0].data.decode('utf-8')
                    conn_check = sqlite3.connect(DB_FILE)
                    cur_check = conn_check.cursor()
                    cur_check.execute(
                        "SELECT name, role FROM users WHERE user_id=? AND role IN ('reviewer','admin')", (scanned_id,))
                    reviewer_row = cur_check.fetchone()
                    conn_check.close()

                    if reviewer_row:
                        st.session_state['reviewer_id'] = scanned_id
                        sound_manager.play_granted()  # 🔊 Login success sound
                        cap.release()
                        time.sleep(0.3)
                        st.rerun()
                    else:
                        st.error(
                            "❌ Invalid ID card or insufficient permissions")
                        sound_manager.play_denied()  # 🔊 Login fail sound
                        time.sleep(2)
        finally:
            if cap.isOpened():
                cap.release()
    else:
        # ===== Logged in, show auditor interface =====
        col_info, col_logout = st.columns([3, 1])
        with col_info:
            st.success(f"🟢 Logged in as: `{st.session_state['reviewer_id']}`")
        with col_logout:
            if st.button("Logout"):
                st.session_state['reviewer_id'] = None
                st.rerun()

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT c.id, c.worker_id, c.timestamp, c.required_ppe, c.plotted_image_path, c.ai_status, c.missing_items
            FROM checkins c
            LEFT JOIN reviews r ON c.id = r.checkin_id
            WHERE c.gate_id = ? AND r.id IS NULL
            ORDER BY c.id DESC LIMIT 1
        ''', (CURRENT_GATE,))
        pending_job = cursor.fetchone()
        conn.close()

        if pending_job:
            c_id, w_id, c_ts, c_required_ppe, c_plotted_path, c_ai_status, c_ai_missing = pending_job
            st.markdown(
                f"### 🚨 Access Request Received | Worker ID: `{w_id}` | Time: `{c_ts}`")

            col1, col2 = st.columns([2, 1])
            with col1:
                st.subheader("📷 AI Field Evidence Image")
                if os.path.exists(c_plotted_path):
                    st.image(c_plotted_path, use_container_width=True)

            with col2:
                st.subheader("📊 Dynamic Decision Dashboard")
                st.info(
                    f"**Specific Verification Standard for this worker:** `{c_required_ppe}`")

                st.markdown(f"**AI Determination Result A:**")
                if c_ai_status == "PASS":
                    st.markdown(
                        "<span class='badge-pass'>PASS (All Compliant)</span>", unsafe_allow_html=True)
                else:
                    st.markdown(
                        f"<span class='badge-fail'>FAIL (Non-compliant)</span>", unsafe_allow_html=True)
                    st.markdown(f"❌ AI identified missing: `{c_ai_missing}`")

                st.markdown("---")
                st.markdown("### ✍️ Manual Auditor Determination (Result B)")

                with st.form("review_submit_form"):
                    reviewer_choice = st.radio(
                        "Final Access Decision:", ["PASS (Allow Entry)", "FAIL (Block and Require Rectification)"])
                    st.markdown(
                        "**If FAIL is selected, check the actual missing equipment:**")

                    manual_missing = []
                    required_items_list = c_required_ppe.split(",")
                    for item in required_items_list:
                        if st.checkbox(f"Missing {item}"):
                            manual_missing.append(item)

                    reviewer_notes = st.text_area(
                        "📝 Auditor Notes (Optional):")
                    report_violation = st.checkbox(
                        "📩 Send Violation Report & Photo to Supervisor", value=True)
                    submit_review = st.form_submit_button(
                        "🚀 Submit Verification Result")

                if submit_review:
                    final_status = "PASS" if "PASS" in reviewer_choice else "FAIL"
                    safe_missing = ",".join(
                        manual_missing) if manual_missing else "NONE"

                    # Write to database
                    conn = sqlite3.connect(DB_FILE)
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO reviews (checkin_id, reviewer_id, gate_id, review_time, reviewer_status, corrected_items, reviewer_notes) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                   (c_id, st.session_state['reviewer_id'], CURRENT_GATE, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), final_status, safe_missing, reviewer_notes))
                    conn.commit()
                    conn.close()

                    # Generate audited image
                    audited_img = cv2.imread(c_plotted_path)
                    if audited_img is not None:
                        h, w = audited_img.shape[:2]
                        cv2.rectangle(audited_img, (0, h-80),
                                      (w, h), (0, 0, 0), -1)
                        audit_text = f"HUMAN AUDIT: {final_status}"
                        missing_text = f"MISSING: {safe_missing}" if safe_missing != "NONE" else "ALL PPE PRESENT"
                        color = (0, 255, 0) if final_status == "PASS" else (
                            0, 0, 255)
                        cv2.putText(audited_img, audit_text, (10, h-50),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
                        cv2.putText(audited_img, missing_text, (10, h-20),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                        audited_path = c_plotted_path.replace(
                            "_plotted.jpg", "_audited.jpg")
                        cv2.imwrite(audited_path, audited_img)

                    # 🔊 Play prompt sound on auditor side
                    if final_status == "PASS":
                        sound_manager.play_granted()
                    else:
                        sound_manager.play_denied()

                    if final_status == "FAIL" and report_violation:
                        alert_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        alert_msg = f"⚠️ [HSE ALERT] Access Denied\nGate: {CURRENT_GATE}\nTime: {alert_time}\nWorker ID: {w_id}\nMissing PPE: {safe_missing}\nReviewer ID: {st.session_state['reviewer_id']}"
                        if reviewer_notes:
                            alert_msg += f"\nNotes: {reviewer_notes}"
                        send_telegram_alert(alert_msg, audited_path)
                        st.success(
                            "📩 Violation report dispatched to Supervisor.")

                    st.success("✅ Review saved! Refreshing in 1.5s...")
                    time.sleep(1.5)
                    st.rerun()
        else:
            st.success("🟢 No workers currently waiting for audit.")
            if st.button("🔄 Check for new worker photos"):
                st.rerun()
