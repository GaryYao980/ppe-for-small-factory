from datetime import datetime

import streamlit as st
import qrcode
import pandas as pd
import os  # 🚨 Must import this!
import sqlite3
import time
from io import BytesIO

# ========== 1. Basic Config & Generation Functions ==========
st.set_page_config(
    page_title="Employee QR Code Management Portal", page_icon="🪪", layout="wide")
DB_FILE = "industrial_ppe.db"
os.makedirs("employee_photos", exist_ok=True)  # Ensure directory exists

ROLE_PPE_MAPPING = {
    "General Worker": ["helmet", "vest"],
    "H2S Operator": ["helmet", "vest", "mask"],
    "MWD Engineer": ["helmet", "vest", "glasses", "gloves"]
}


def init_db():
    conn = sqlite3.connect(DB_FILE, timeout=10)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS workers (
        worker_id TEXT PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL, 
        required_ppe TEXT NOT NULL, photo_path TEXT DEFAULT '')''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        role TEXT NOT NULL,
        gate_id TEXT DEFAULT ""
    )''')
    conn.commit()
    conn.close()


init_db()


def generate_qr_image(worker_id):
    qr = qrcode.QRCode(
        version=1, error_correction=qrcode.ERROR_CORRECT_H, box_size=10, border=4)
    qr.add_data(worker_id)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


# ========== 2. Page UI ==========
st.markdown("<h1 style='text-align: center;'>🪪 Access Badge and Permissions Management Center</h1>",
            unsafe_allow_html=True)
st.markdown("---")

tab1, tab2, tab3, tab4 = st.tabs(
    ["👨‍💼 HR: Employee Onboarding & Permissions", "📁 HR: Bulk Import", "👷‍♂️ Worker: Self-Service Recovery", "🔐 HR: Auditor/Admin Management"])

with tab1:
    col1, col2 = st.columns([1, 1.5])

    with col1:
        st.subheader("📝 Add/Update Employee Profile")
        with st.form("new_worker_form"):
            new_id = st.text_input("Worker ID (e.g., W-1002):")
            new_name = st.text_input("Employee Name:")
            emp_role = st.selectbox(
                "Assign Role/Position:", list(ROLE_PPE_MAPPING.keys()))
            emp_photo = st.camera_input(
                "📸 Capture ID Photo (For Front of Badge)")
            submitted = st.form_submit_button(
                "✅ Submit Profile & Generate Badge")

        if submitted and new_id and new_name and emp_photo:
            # Save photo
            path = f"employee_photos/{new_id}_{new_name}.jpg"
            with open(path, "wb") as f:
                f.write(emp_photo.getbuffer())

            # Insert into DB
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            cursor.execute("REPLACE INTO workers VALUES (?, ?, ?, ?, ?)",
                           (new_id, new_name, emp_role, ",".join(ROLE_PPE_MAPPING[emp_role]), path))
            conn.commit()
            conn.close()
            st.success(f"✅ {new_name} profile created successfully!")

    with col2:
        st.subheader("🔍 Active Roster & Management")
        search_query = st.text_input("Enter Worker ID or Name to search...")

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        query = "%" + search_query + "%"
        cursor.execute(
            "SELECT * FROM workers WHERE worker_id LIKE ? OR name LIKE ?", (query, query))
        workers = cursor.fetchall()

        for w in workers:
            w_id, w_name, w_role, w_ppe, w_path = w
            with st.expander(f"👤 {w_name} ({w_id}) - {w_role}"):
                # 🚨 Restore badge preview function
                pc1, pc2 = st.columns(2)
                with pc1:
                    if os.path.exists(w_path):
                        st.image(w_path, caption="Front (Side A)", width=150)
                with pc2:
                    st.image(generate_qr_image(w_id),
                             caption="Back (Side B)", width=150)

                # Edit form
                with st.form(f"edit_{w_id}"):
                    new_role = st.selectbox("Modify Role:", list(ROLE_PPE_MAPPING.keys()), index=list(
                        ROLE_PPE_MAPPING.keys()).index(w_role))
                    if st.form_submit_button("🔄 Update Permissions"):
                        cursor.execute("UPDATE workers SET role=?, required_ppe=? WHERE worker_id=?", (
                            new_role, ",".join(ROLE_PPE_MAPPING[new_role]), w_id))
                        conn.commit()
                        st.rerun()

                if st.button("🗑️ Revoke Permissions", key=f"del_{w_id}"):
                    if os.path.exists(w_path):
                        os.remove(w_path)
                    cursor.execute(
                        "DELETE FROM workers WHERE worker_id=?", (w_id,))
                    conn.commit()
                    st.rerun()
        conn.close()
# Auto-preview first 5 records, confirm before import. Auto-verify role validity.
# Success/failure tracked separately, failures will show reason. INSERT OR REPLACE ensures duplicate IDs update instead of error.
with tab2:
    st.subheader("📁 Bulk Import Existing Employee Profiles")
    st.markdown("**Please upload a CSV file in the following format:**")
    st.code("worker_id,name,role\nW-1001,John Doe,General Worker\nW-1002,Jane Smith,H2S Operator")

    uploaded_csv = st.file_uploader("Upload Employee List CSV", type=["csv"])

    if uploaded_csv:
        import pandas as pd
        df = pd.read_csv(uploaded_csv)

        # Check if necessary columns exist
        required_cols = {"worker_id", "name", "role"}
        if not required_cols.issubset(df.columns):
            st.error(
                f"❌ Invalid CSV format, must contain the following columns: {required_cols}")
        else:
            st.markdown("**Previewing first 5 rows:**")
            st.dataframe(df.head(), use_container_width=True)
            st.markdown(f"Total **{len(df)}** records")

            if st.button("✅ Confirm Import"):
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                success = 0
                failed = 0
                errors = []

                for _, row in df.iterrows():
                    try:
                        # Verify role validity
                        if row['role'] not in ROLE_PPE_MAPPING:
                            errors.append(
                                f"Worker ID {row['worker_id']}: Role '{row['role']}' not found in system")
                            failed += 1
                            continue

                        cursor.execute(
                            "INSERT OR REPLACE INTO workers (worker_id, name, role, required_ppe, photo_path) VALUES (?, ?, ?, ?, ?)",
                            (str(row['worker_id']), str(row['name']), str(row['role']),
                             ",".join(ROLE_PPE_MAPPING[row['role']]), ""))
                        success += 1
                    except Exception as e:
                        errors.append(f"Worker ID {row['worker_id']}: {e}")
                        failed += 1

                conn.commit()
                conn.close()

                st.success(
                    f"✅ Import Complete: {success} successful, {failed} failed")

                if errors:
                    st.warning("The following records failed to import:")
                    for err in errors:
                        st.markdown(f"- {err}")

                # Provide prompt for bulk QR code download
                if success > 0:
                    st.info(
                        "💡 QR codes for successfully imported employees can be viewed and printed in the Active Roster (Tab 1).")
with tab4:
    st.subheader("🔐 Add Auditor / Admin Account")

    with st.form("add_user_form"):
        user_id = st.text_input("ID (User ID, e.g., R-001):")
        user_name = st.text_input("Name:")
        user_role = st.selectbox("Role:", ["reviewer", "admin"])
        user_gate = st.text_input(
            "Assigned Gate (e.g., GATE-01, Admins can leave blank):")
        submit_user = st.form_submit_button("✅ Add Account")

    if submit_user and user_id and user_name:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO users (user_id, name, role, gate_id) VALUES (?, ?, ?, ?)",
            (user_id, user_name, user_role, user_gate))
        conn.commit()
        conn.close()
        st.success(f"✅ {user_name} ({user_role}) added successfully!")

        # Show QR code
        st.markdown(
            "**Scan the QR code below to log into the Auditor system:**")
        st.image(generate_qr_image(user_id), width=200)

    st.markdown("---")
    st.subheader("📋 Current Auditor/Admin List")

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT user_id, name, role, gate_id FROM users ORDER BY role")
    users = cursor.fetchall()
    conn.close()

    if users:
        for u in users:
            u_id, u_name, u_role, u_gate = u
            with st.expander(f"{'🔐' if u_role == 'admin' else '👨‍💼'} {u_name} ({u_id}) - {u_role}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**Role:** {u_role}")
                    st.markdown(
                        f"**Assigned Gate:** {u_gate if u_gate else 'All'}")
                with col2:
                    st.image(generate_qr_image(u_id),
                             width=150, caption="Login QR Code")

                if st.button("🗑️ Delete Account", key=f"del_user_{u_id}"):
                    conn = sqlite3.connect(DB_FILE)
                    cursor = conn.cursor()
                    cursor.execute(
                        "DELETE FROM users WHERE user_id=?", (u_id,))
                    conn.commit()
                    conn.close()
                    st.rerun()
    else:
        st.info("No Auditor/Admin accounts found, please add one first.")

# ========== 4. HR Real-time Dashboard & Export Module ==========
st.markdown("---")
st.subheader("📋 Field Dynamics & Hours Summary (Live & Summary)")

try:
    conn = sqlite3.connect(DB_FILE)
    today_str = datetime.now().strftime("%Y-%m-%d")
    df = pd.read_sql_query(
        "SELECT worker_id AS 'Worker ID', entry_time AS 'Entry Time', exit_time AS 'Exit Time' FROM attendance_log WHERE date = ?",
        conn, params=(today_str,)
    )
    conn.close()

    if not df.empty:
        # 1. Raw Flow Table Display
        st.markdown("**Attendance Flow Logs (Raw Logs)**")
        raw_df = df.copy()
        raw_df['Exit Time'] = raw_df['Exit Time'].fillna("🟢 On-site Working")
        st.dataframe(raw_df, width="stretch", hide_index=True)

        # 2. Work Hours Calculation Core Logic
        st.markdown(
            "**Today's Cumulative Hours Calculation (Total Hours Calculated)**")
        # Convert time string to datetime for duration calculation
        calc_df = df.copy()
        calc_df['In'] = pd.to_datetime(today_str + ' ' + calc_df['Entry Time'])
        # For those not clocked out, use current time as temp calculation node
        current_now_str = datetime.now().strftime("%H:%M:%S")
        calc_df['Exit Time_Calc'] = calc_df['Exit Time'].fillna(
            current_now_str)
        calc_df['Out'] = pd.to_datetime(
            today_str + ' ' + calc_df['Exit Time_Calc'])

        # Calculate time difference for each segment (hours)
        calc_df['Segment Hours'] = (calc_df['Out'] - calc_df['In']
                                    ).dt.total_seconds() / 3600

        # Summarize total hours by worker ID
        summary_df = calc_df.groupby('Worker ID')[
            'Segment Hours'].sum().reset_index()
        summary_df.rename(
            columns={'Segment Hours': "Today's Cumulative Hours (Hours)"}, inplace=True)
        summary_df["Today's Cumulative Hours (Hours)"] = summary_df["Today's Cumulative Hours (Hours)"].round(
            2)  # Keep two decimal places

        st.dataframe(summary_df, width="stretch", hide_index=True)

        # Prepare merged data for export
        csv_data = raw_df.to_csv(index=False).encode('utf-8-sig')

        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.download_button(
                label="📥 Export HR Attendance Summary (Export)",
                data=csv_data,
                file_name=f"Attendance_Summary_{today_str}.csv",
                mime="text/csv",
                use_container_width=True
            )
    else:
        st.info("📅 No attendance data today yet, waiting for the first employee.")
except Exception as e:
    st.error(f"Failed to load attendance dashboard: {e}")
