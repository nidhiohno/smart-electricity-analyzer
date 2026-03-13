import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
from datetime import datetime
import hashlib
import psycopg2
import base64
import json

st.set_page_config(page_title="Smart Electricity Analyzer", layout="wide")

# ─────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────
def get_connection():
    return psycopg2.connect(st.secrets["DATABASE_URL"], sslmode="require")

def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            security_question TEXT NOT NULL DEFAULT '',
            security_answer TEXT NOT NULL DEFAULT ''
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS electricity_data (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL,
            year INTEGER NOT NULL,
            month TEXT NOT NULL,
            units REAL NOT NULL,
            bill REAL NOT NULL,
            rate REAL NOT NULL,
            UNIQUE(username, year, month)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS appliance_data (
            id SERIAL PRIMARY KEY,
            username TEXT NOT NULL,
            year INTEGER NOT NULL,
            month TEXT NOT NULL,
            appliance_hours JSONB NOT NULL,
            UNIQUE(username, year, month)
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

init_db()

# ─────────────────────────────────────────────
# BILL CALCULATOR
# ─────────────────────────────────────────────
def calculate_msedcl_bill(units, connection_type="single_phase"):
    slabs = [(100, 2.90), (200, 6.50), (200, 8.00), (float('inf'), 11.85)]
    energy_charge = 0.0
    remaining = units
    for slab_units, rate in slabs:
        if remaining <= 0:
            break
        billed = min(remaining, slab_units)
        energy_charge += billed * rate
        remaining -= billed
    fac = units * 0.20
    fixed_charge = 30 if connection_type == "single_phase" else 100
    electricity_duty = energy_charge * 0.16
    total = energy_charge + fac + fixed_charge + electricity_duty
    return {
        "energy_charge": round(energy_charge, 2),
        "fac": round(fac, 2),
        "fixed_charge": fixed_charge,
        "electricity_duty": round(electricity_duty, 2),
        "total": round(total, 2)
    }

# ─────────────────────────────────────────────
# AUTH HELPERS
# ─────────────────────────────────────────────
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(username, password, security_question, security_answer):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (username, password, security_question, security_answer) VALUES (%s, %s, %s, %s)",
            (username, hash_password(password), security_question, hash_password(security_answer.lower().strip()))
        )
        conn.commit()
        cur.close()
        conn.close()
        return True
    except psycopg2.IntegrityError:
        conn.rollback()
        conn.close()
        return False

def verify_user(username, password):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT password FROM users WHERE username = %s", (username,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row is not None and row[0] == hash_password(password)

def get_security_question(username):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT security_question FROM users WHERE username = %s", (username,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else None

def verify_security_answer(username, answer):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT security_question, security_answer FROM users WHERE username = %s", (username,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if row is None:
        return False, None
    return row[1] == hash_password(answer.lower().strip()), row[0]

def reset_password(username, new_password):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET password = %s WHERE username = %s",
                (hash_password(new_password), username))
    conn.commit()
    cur.close()
    conn.close()

# ─────────────────────────────────────────────
# DATA HELPERS
# ─────────────────────────────────────────────
def save_entry(username, year, month, units, bill, rate):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO electricity_data (username, year, month, units, bill, rate)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT(username, year, month) DO UPDATE SET
            units = EXCLUDED.units, bill = EXCLUDED.bill, rate = EXCLUDED.rate
    """, (username, year, month, units, bill, rate))
    conn.commit()
    cur.close()
    conn.close()

def save_appliance_data(username, year, month, appliance_hours):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO appliance_data (username, year, month, appliance_hours)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT(username, year, month) DO UPDATE SET
            appliance_hours = EXCLUDED.appliance_hours
    """, (username, year, month, json.dumps(appliance_hours)))
    conn.commit()
    cur.close()
    conn.close()

def load_user_data(username, year):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT month, units, bill, rate FROM electricity_data WHERE username = %s AND year = %s", (username, year))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def load_appliance_data(username, year, month):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT appliance_hours FROM appliance_data WHERE username = %s AND year = %s AND month = %s",
                (username, year, month))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else {}

def load_all_appliance_data(username, year):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT month, appliance_hours FROM appliance_data WHERE username = %s AND year = %s",
                (username, year))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def delete_user_data(username, year):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM electricity_data WHERE username = %s AND year = %s", (username, year))
    cur.execute("DELETE FROM appliance_data WHERE username = %s AND year = %s", (username, year))
    conn.commit()
    cur.close()
    conn.close()

# ─────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────
for key, default in [
    ("logged_in", False),
    ("username", ""),
    ("auth_page", "login"),
    ("page", "input"),
    ("forgot_step", 1),
    ("forgot_username", ""),
    ("extracted", {}),
]:
    if key not in st.session_state:
        st.session_state[key] = default

SECURITY_QUESTIONS = [
    "What is your pet's name?",
    "What is your mother's maiden name?",
    "What was the name of your first school?",
    "What is your favourite movie?",
    "What city were you born in?",
]

MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

APPLIANCES = {
    "AC (1.5 ton)":          1500,
    "Refrigerator":           150,
    "Washing Machine":        500,
    "TV (LED 43 inch)":       100,
    "Fan (Ceiling)":           75,
    "LED Bulb (10W)":          10,
    "Water Heater (Geyser)": 2000,
    "Microwave":             1200,
    "Iron":                  1000,
    "Computer/Laptop":        150,
}

# ─────────────────────────────────────────────
# HIDE SIDEBAR
# ─────────────────────────────────────────────
st.markdown("""
    <style>
    [data-testid="stSidebar"] {display: none;}
    [data-testid="collapsedControl"] {display: none;}
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# PAGE 1 — AUTH
# ─────────────────────────────────────────────
if not st.session_state.logged_in:
    st.markdown("<h1 style='text-align:center'>⚡ Smart Electricity Analyzer</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;color:gray'>Maharashtra (MSEDCL)</p>", unsafe_allow_html=True)
    st.markdown("---")
    _, col_form, _ = st.columns([1, 1.2, 1])
    with col_form:

        if st.session_state.auth_page == "login":
            st.markdown("### 🔐 Login")
            username = st.text_input("Username", key="login_user")
            password = st.text_input("Password", type="password", key="login_pass")
            if st.button("Login", use_container_width=True):
                if not username or not password:
                    st.error("Please enter both fields.")
                elif verify_user(username, password):
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.page = "input"
                    st.rerun()
                else:
                    st.error("Invalid username or password.")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Create Account", use_container_width=True):
                    st.session_state.auth_page = "signup"
                    st.rerun()
            with col2:
                if st.button("Forgot Password?", use_container_width=True):
                    st.session_state.auth_page = "forgot"
                    st.rerun()

        elif st.session_state.auth_page == "signup":
            st.markdown("### 📝 Create Account")
            username          = st.text_input("Username", key="signup_user")
            password          = st.text_input("Password", type="password", key="signup_pass")
            confirm_password  = st.text_input("Confirm Password", type="password", key="signup_confirm")
            security_question = st.selectbox("Security Question", SECURITY_QUESTIONS)
            security_answer   = st.text_input("Your Answer", key="signup_answer")
            if st.button("Create Account", use_container_width=True):
                if not username or not password or not security_answer:
                    st.error("Please fill in all fields.")
                elif len(password) < 4:
                    st.warning("Password must be at least 4 characters.")
                elif password != confirm_password:
                    st.error("Passwords do not match.")
                elif register_user(username, password, security_question, security_answer):
                    st.success("Account created! Please log in.")
                    st.session_state.auth_page = "login"
                    st.rerun()
                else:
                    st.error("Username already exists.")
            if st.button("Back to Login", use_container_width=True):
                st.session_state.auth_page = "login"
                st.rerun()

        elif st.session_state.auth_page == "forgot":
            st.markdown("### 🔑 Reset Password")
            if st.session_state.forgot_step == 1:
                st.markdown("**Step 1: Enter your username**")
                forgot_user = st.text_input("Username", key="forgot_user")
                if st.button("Next", use_container_width=True):
                    question = get_security_question(forgot_user)
                    if question:
                        st.session_state.forgot_username = forgot_user
                        st.session_state.forgot_step = 2
                        st.rerun()
                    else:
                        st.error("Username not found.")
            elif st.session_state.forgot_step == 2:
                question = get_security_question(st.session_state.forgot_username)
                st.markdown("**Step 2: Answer your security question**")
                st.info(f"Question: {question}")
                answer = st.text_input("Your Answer", key="forgot_answer")
                if st.button("Verify", use_container_width=True):
                    correct, _ = verify_security_answer(st.session_state.forgot_username, answer)
                    if correct:
                        st.session_state.forgot_step = 3
                        st.rerun()
                    else:
                        st.error("Incorrect answer.")
            elif st.session_state.forgot_step == 3:
                st.markdown("**Step 3: Set new password**")
                new_pass     = st.text_input("New Password", type="password", key="new_pass")
                confirm_pass = st.text_input("Confirm New Password", type="password", key="confirm_new_pass")
                if st.button("Reset Password", use_container_width=True):
                    if len(new_pass) < 4:
                        st.warning("Password must be at least 4 characters.")
                    elif new_pass != confirm_pass:
                        st.error("Passwords do not match.")
                    else:
                        reset_password(st.session_state.forgot_username, new_pass)
                        st.success("Password reset! Please log in.")
                        st.session_state.forgot_step = 1
                        st.session_state.forgot_username = ""
                        st.session_state.auth_page = "login"
                        st.rerun()
            if st.button("Back to Login", use_container_width=True):
                st.session_state.auth_page = "login"
                st.session_state.forgot_step = 1
                st.rerun()
    st.stop()

# ─────────────────────────────────────────────
# TOP NAV BAR
# ─────────────────────────────────────────────
nav_col1, nav_col2, nav_col3, nav_col4 = st.columns([2, 1, 1, 1])
with nav_col1:
    st.markdown("### ⚡ Smart Electricity Analyzer")
with nav_col2:
    if st.button("📥 Enter Data", use_container_width=True,
                 type="primary" if st.session_state.page == "input" else "secondary"):
        st.session_state.page = "input"
        st.rerun()
with nav_col3:
    if st.button("📊 Dashboard", use_container_width=True,
                 type="primary" if st.session_state.page == "dashboard" else "secondary"):
        st.session_state.page = "dashboard"
        st.rerun()
with nav_col4:
    if st.button(f"🚪 Logout ({st.session_state.username})", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.page = "input"
        st.rerun()

st.markdown("---")
connection_type = "single_phase"

# ─────────────────────────────────────────────
# PAGE 2 — INPUT DATA
# ─────────────────────────────────────────────
if st.session_state.page == "input":
    st.markdown("## 📥 Enter Monthly Data")

    col_y1, col_y2 = st.columns([1, 3])
    with col_y1:
        selected_year = int(st.number_input(
            "Year", min_value=2000, max_value=2100,
            value=datetime.now().year, step=1, key="input_year"
        ))

    st.markdown("---")
    manual_tab, upload_tab = st.tabs(["✏️ Manual Input", "📄 Upload Bill"])

    # ── MANUAL INPUT ──
    with manual_tab:
        st.markdown("#### Enter your meter reading")
        col1, col2 = st.columns(2)
        with col1:
            month = st.selectbox("Month", MONTH_NAMES, key="manual_month")
        with col2:
            units_consumed = st.number_input("Units Consumed (kWh)", min_value=0.0, value=0.0, step=10.0, key="manual_units")

        if units_consumed > 0:
            preview = calculate_msedcl_bill(units_consumed, connection_type)
            st.markdown("**📋 Estimated Bill Breakdown:**")
            bc1, bc2, bc3, bc4 = st.columns(4)
            with bc1:
                st.metric("Energy Charges", f"Rs {preview['energy_charge']}")
            with bc2:
                st.metric("FAC", f"Rs {preview['fac']}")
            with bc3:
                st.metric("Fixed + Duty", f"Rs {preview['fixed_charge'] + preview['electricity_duty']:.0f}")
            with bc4:
                st.metric("Total Bill", f"Rs {preview['total']}")

        st.markdown("---")
        st.markdown("#### 🏠 Appliance Usage Survey")
        st.caption("How many hours per day does each appliance run this month? (Enter 0 if not used)")

        # Load previously saved appliance data for this month/year if exists
        existing = load_appliance_data(st.session_state.username, selected_year, month)

        hours_input = {}
        cols = st.columns(2)
        for i, (appliance, wattage) in enumerate(APPLIANCES.items()):
            with cols[i % 2]:
                default_val = float(existing.get(appliance, 0.0)) if existing else 0.0
                hours_input[appliance] = st.number_input(
                    f"{appliance} ({wattage}W)",
                    min_value=0.0, max_value=24.0,
                    value=default_val, step=0.5,
                    key=f"survey_{i}",
                    help=f"Hours per day"
                )

        st.markdown("")
        if st.button("💾 Save Entry", use_container_width=True, key="manual_save"):
            if units_consumed == 0:
                st.error("Please enter units consumed.")
            else:
                bill_data = calculate_msedcl_bill(units_consumed, connection_type)
                effective_rate = round(bill_data['total'] / units_consumed, 2)
                save_entry(st.session_state.username, selected_year, month, units_consumed, bill_data['total'], effective_rate)
                save_appliance_data(st.session_state.username, selected_year, month, hours_input)
                st.success(f"✅ Saved {month} {selected_year}! Bill: Rs {bill_data['total']}")
                st.session_state.page = "dashboard"
                st.session_state.dash_year = selected_year
                st.rerun()

    # ── UPLOAD BILL ──
    with upload_tab:
        st.markdown("#### Upload your electricity bill (PDF or Image)")
        uploaded_file = st.file_uploader("Choose file", type=["pdf", "jpg", "jpeg", "png"], key="bill_upload")

        if uploaded_file is not None:
            if st.button("🤖 Extract Data using AI", use_container_width=True):
                with st.spinner("Reading your bill with Gemini AI..."):
                    try:
                        import google.generativeai as genai
                        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
                        model = genai.GenerativeModel("gemini-1.5-flash")
                        file_bytes = uploaded_file.read()
                        mime_type  = uploaded_file.type
                        b64 = base64.b64encode(file_bytes).decode("utf-8")
                        prompt = """
                        This is an Indian electricity bill. Extract:
                        1. Units consumed (kWh)
                        2. Bill month (3 letter: Jan/Feb/Mar etc)
                        3. Bill year (4 digits)
                        Reply ONLY in this format:
                        UNITS: <number>
                        MONTH: <3 letter month>
                        YEAR: <4 digit year>
                        If not found, write UNKNOWN.
                        """
                        response = model.generate_content([{"mime_type": mime_type, "data": b64}, prompt])
                        extracted = {}
                        for line in response.text.strip().split("\n"):
                            if "UNITS:" in line:
                                extracted["units"] = line.split("UNITS:")[1].strip()
                            elif "MONTH:" in line:
                                extracted["month"] = line.split("MONTH:")[1].strip()
                            elif "YEAR:" in line:
                                extracted["year"] = line.split("YEAR:")[1].strip()
                        st.session_state.extracted = extracted
                        st.success("✅ Bill read! Please confirm values below.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Could not read bill: {e}")

        if st.session_state.extracted:
            ext = st.session_state.extracted
            st.markdown("---")
            st.markdown("#### ✅ Confirm Extracted Values")
            try:
                default_units = float(ext.get("units", 0))
            except:
                default_units = 0.0
            ext_month = ext.get("month", MONTH_NAMES[0])
            if ext_month not in MONTH_NAMES:
                ext_month = MONTH_NAMES[0]
            try:
                ext_year = int(ext.get("year", datetime.now().year))
            except:
                ext_year = datetime.now().year

            col1, col2, col3 = st.columns(3)
            with col1:
                confirmed_units = st.number_input("Units (kWh)", min_value=0.0, value=default_units, step=1.0, key="ext_units")
            with col2:
                confirmed_month = st.selectbox("Month", MONTH_NAMES, index=MONTH_NAMES.index(ext_month), key="ext_month")
            with col3:
                confirmed_year = st.number_input("Year", min_value=2000, max_value=2100, value=ext_year, step=1, key="ext_year")

            if confirmed_units > 0:
                preview2 = calculate_msedcl_bill(confirmed_units, connection_type)
                st.info(f"Estimated Bill: **Rs {preview2['total']}**")

            st.markdown("---")
            st.markdown("#### 🏠 Appliance Usage Survey")
            st.caption("How many hours per day does each appliance run this month?")
            existing_upload = load_appliance_data(st.session_state.username, int(confirmed_year if 'confirmed_year' in dir() else ext_year), ext_month)
            hours_upload = {}
            cols2 = st.columns(2)
            for i, (appliance, wattage) in enumerate(APPLIANCES.items()):
                with cols2[i % 2]:
                    default_val = float(existing_upload.get(appliance, 0.0)) if existing_upload else 0.0
                    hours_upload[appliance] = st.number_input(
                        f"{appliance} ({wattage}W)",
                        min_value=0.0, max_value=24.0,
                        value=default_val, step=0.5,
                        key=f"upload_survey_{i}"
                    )

            if st.button("💾 Save Extracted Data", use_container_width=True, key="upload_save"):
                if confirmed_units == 0:
                    st.error("Units cannot be zero.")
                else:
                    bill_data = calculate_msedcl_bill(confirmed_units, connection_type)
                    effective_rate = round(bill_data['total'] / confirmed_units, 2)
                    save_entry(st.session_state.username, int(confirmed_year), confirmed_month, confirmed_units, bill_data['total'], effective_rate)
                    save_appliance_data(st.session_state.username, int(confirmed_year), confirmed_month, hours_upload)
                    st.success(f"✅ Saved {confirmed_month} {confirmed_year}! Bill: Rs {bill_data['total']}")
                    st.session_state.extracted = {}
                    st.session_state.page = "dashboard"
                    st.session_state.dash_year = int(confirmed_year)
                    st.rerun()

# ─────────────────────────────────────────────
# PAGE 3 — DASHBOARD
# ─────────────────────────────────────────────
elif st.session_state.page == "dashboard":
    st.markdown("## 📊 Dashboard")

    selected_year = int(st.number_input(
        "Select Year", min_value=2000, max_value=2100,
        value=st.session_state.get("dash_year", datetime.now().year), step=1, key="dash_year"
    ))

    rows = load_user_data(st.session_state.username, selected_year)

    if rows:
        df = pd.DataFrame(rows, columns=['Month', 'Units', 'Bill', 'Rate'])
        month_order = {m: i for i, m in enumerate(MONTH_NAMES)}
        df['Month_Order'] = df['Month'].map(month_order)
        df = df.sort_values('Month_Order').reset_index(drop=True)

        total_units = df['Units'].sum()
        total_bill  = df['Bill'].sum()
        avg_rate    = df['Rate'].mean()
        last_units  = df['Units'].iloc[-1]
        last_bill   = df['Bill'].iloc[-1]

        st.markdown(f"#### {selected_year} Overview — {len(df)}/12 months recorded")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Units", f"{total_units:.0f} kWh")
        with col2:
            st.metric("Total Bill", f"Rs {total_bill:.0f}")
        with col3:
            st.metric("Avg Effective Rate", f"Rs {avg_rate:.2f}/kWh")
        with col4:
            trend = "📈 UP" if df['Units'].iloc[-1] > df['Units'].iloc[0] else "📉 DOWN"
            st.metric("Trend", trend)

        st.markdown("---")

        # ═══════════════════════════════════════
        # ALERTS — TOP OF DASHBOARD
        # ═══════════════════════════════════════
        st.subheader("🚨 Alerts & Warnings")

        # ── SPIKE ALERT — Bold Banner (full width, hard to miss) ──
        if len(df) >= 2:
            prev_units = df['Units'].iloc[-2]
            spike_pct  = ((last_units - prev_units) / prev_units) * 100 if prev_units > 0 else 0
            prev_month = df['Month'].iloc[-2]
            curr_month = df['Month'].iloc[-1]
            if spike_pct >= 20:
                st.markdown(f"""
                    <div style="background:linear-gradient(135deg,#c0392b,#e74c3c);color:white;
                    padding:25px 35px;border-radius:14px;text-align:center;font-size:22px;
                    font-weight:bold;font-family:sans-serif;box-shadow:0 6px 24px rgba(0,0,0,0.4);
                    margin:8px 0;animation:pulse 1s infinite;">
                    🚨 UNUSUAL SPIKE DETECTED!<br>
                    <span style="font-size:16px;font-weight:normal;">
                    Usage jumped <b>{spike_pct:.0f}%</b> — {prev_month} ({prev_units:.0f} kWh) → {curr_month} ({last_units:.0f} kWh)<br>
                    Check for extra appliance usage or meter issues!
                    </span></div>
                """, unsafe_allow_html=True)
            elif spike_pct >= 10:
                st.markdown(f"""
                    <div style="background:linear-gradient(135deg,#e67e22,#f39c12);color:white;
                    padding:22px 32px;border-radius:14px;text-align:center;font-size:20px;
                    font-weight:bold;font-family:sans-serif;box-shadow:0 4px 18px rgba(0,0,0,0.3);
                    margin:8px 0;">
                    ⚠️ MODERATE SPIKE — Usage up <b>{spike_pct:.0f}%</b><br>
                    <span style="font-size:14px;font-weight:normal;">
                    {prev_month}: {prev_units:.0f} kWh → {curr_month}: {last_units:.0f} kWh
                    </span></div>
                """, unsafe_allow_html=True)
            elif spike_pct <= -10:
                st.markdown(f"""
                    <div style="background:linear-gradient(135deg,#27ae60,#2ecc71);color:white;
                    padding:22px 32px;border-radius:14px;text-align:center;font-size:20px;
                    font-weight:bold;font-family:sans-serif;box-shadow:0 4px 18px rgba(0,0,0,0.3);
                    margin:8px 0;">
                    ✅ GREAT IMPROVEMENT! Usage dropped <b>{abs(spike_pct):.0f}%</b><br>
                    <span style="font-size:14px;font-weight:normal;">
                    {prev_month}: {prev_units:.0f} kWh → {curr_month}: {last_units:.0f} kWh — Keep it up!
                    </span></div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                    <div style="background:linear-gradient(135deg,#2980b9,#3498db);color:white;
                    padding:18px 28px;border-radius:14px;text-align:center;font-size:18px;
                    font-weight:bold;font-family:sans-serif;box-shadow:0 4px 14px rgba(0,0,0,0.2);
                    margin:8px 0;">
                    📊 STABLE USAGE — Change from {prev_month}: {spike_pct:+.1f}%
                    </div>
                """, unsafe_allow_html=True)

        # ── HIGH BILL / USAGE — Warning Box ──
        if last_units > 500:
            box_color, box_border, icon = "#fff0f0", "#e74c3c", "🔴"
            msg = f"VERY HIGH USAGE — {last_units:.0f} kWh! You are in the highest slab (Rs 11.85/unit). Your bill is significantly above average."
        elif last_units > 300:
            box_color, box_border, icon = "#fff4e5", "#e67e22", "🟠"
            msg = f"HIGH USAGE — {last_units:.0f} kWh. You are in the Rs 8.00/unit slab. Consider reducing AC and geyser usage."
        elif last_units > 100:
            box_color, box_border, icon = "#fffde7", "#f1c40f", "🟡"
            msg = f"MODERATE USAGE — {last_units:.0f} kWh. You are in the Rs 6.50/unit slab. Small reductions can help."
        else:
            box_color, box_border, icon = "#f0fff4", "#27ae60", "🟢"
            msg = f"LOW USAGE — {last_units:.0f} kWh. Excellent! You are in the lowest slab (Rs 2.90/unit)."

        st.markdown(f"""
            <div style="background:{box_color};border-left:6px solid {box_border};
            padding:16px 22px;border-radius:8px;margin:10px 0;font-family:sans-serif;">
            <span style="font-size:20px;">{icon}</span>
            <span style="font-size:16px;font-weight:bold;color:#333;"> Bill Usage Alert</span><br>
            <span style="font-size:14px;color:#555;margin-top:6px;display:block;">{msg}</span>
            </div>
        """, unsafe_allow_html=True)

        # ── APPLIANCE SMART ALERTS — Based on stored data + next month bill impact ──
        latest_month     = df['Month'].iloc[-1]
        latest_appliance = load_appliance_data(st.session_state.username, selected_year, latest_month)

        if latest_appliance:
            st.markdown(f"#### 🏠 Smart Appliance Alerts & Next Month Savings — {latest_month} {selected_year}")
            st.caption("Based on your appliance usage, here's how reducing each appliance will impact your next month bill.")

            thresholds = {
                "AC (1.5 ton)": 8, "Refrigerator": 24, "Washing Machine": 2,
                "TV (LED 43 inch)": 6, "Fan (Ceiling)": 18, "LED Bulb (10W)": 12,
                "Water Heater (Geyser)": 2, "Microwave": 2, "Iron": 1, "Computer/Laptop": 8,
            }
            reduction_tips = {
                "AC (1.5 ton)":          "Set to 24°C instead of 18°C. Use fan alongside to feel cooler.",
                "Refrigerator":          "Keep 3/4 full, clean coils regularly, avoid placing hot food inside.",
                "Washing Machine":       "Run full loads only. Use cold water wash. Air dry instead of tumble dry.",
                "TV (LED 43 inch)":      "Reduce screen brightness. Switch off at plug instead of standby.",
                "Fan (Ceiling)":         "Turn off when leaving the room. Clean blades for better efficiency.",
                "LED Bulb (10W)":        "Use natural light during daytime. Install timers or motion sensors.",
                "Water Heater (Geyser)": "Use for max 30 mins/day. Switch off immediately after use.",
                "Microwave":             "Use for small meals instead of oven — far more energy efficient.",
                "Iron":                  "Iron clothes in bulk at one time. Unplug immediately after use.",
                "Computer/Laptop":       "Enable power saving mode. Switch off monitor when not in use.",
            }

            # Calculate total current units & bill from all appliances combined
            total_current_units = sum(
                (APPLIANCES[a] * float(latest_appliance.get(a, 0)) * 30) / 1000
                for a in APPLIANCES if float(latest_appliance.get(a, 0)) > 0
            )
            total_current_bill = calculate_msedcl_bill(total_current_units)['total']

            alert_data = []
            for appliance, wattage in APPLIANCES.items():
                hrs = float(latest_appliance.get(appliance, 0))
                if hrs == 0:
                    continue
                limit         = thresholds.get(appliance, 8)
                current_units = round((wattage * hrs * 30) / 1000, 2)
                current_cost  = round(calculate_msedcl_bill(current_units)['total'], 0)

                # What if reduced to recommended limit?
                reduced_hrs   = min(hrs, limit)
                reduced_units = round((wattage * reduced_hrs * 30) / 1000, 2)

                # Bill impact: recalculate total bill with this appliance reduced
                other_units   = total_current_units - current_units
                new_total_units = other_units + reduced_units
                new_total_bill  = calculate_msedcl_bill(new_total_units)['total']
                bill_saving     = round(total_current_bill - new_total_bill, 0)

                if hrs > limit:
                    status, bg, border = "🔴 HIGH USAGE", "#fff0f0", "#e74c3c"
                elif hrs > limit * 0.7:
                    status, bg, border = "🟡 MODERATE", "#fffde7", "#f1c40f"
                else:
                    status, bg, border = "🟢 NORMAL", "#f0fff4", "#27ae60"

                alert_data.append({
                    "Appliance": appliance, "Hrs/Day": hrs, "Limit (hrs)": limit,
                    "Current Units": current_units, "Current Cost": current_cost,
                    "Bill Saving": bill_saving, "Reduced Hrs": reduced_hrs,
                    "Status": status, "bg": bg, "border": border,
                    "tip": reduction_tips.get(appliance, "")
                })

            if alert_data:
                # Bar chart: current hours vs recommended
                chart_df = pd.DataFrame(alert_data)
                fig_alert = px.bar(
                    chart_df, x="Appliance", y=["Hrs/Day", "Limit (hrs)"],
                    barmode="group",
                    title=f"Your Appliance Usage vs Recommended Limit — {latest_month}",
                    color_discrete_map={"Hrs/Day": "#e74c3c", "Limit (hrs)": "#2ecc71"},
                    labels={"value": "Hours/Day", "variable": ""}
                )
                fig_alert.update_layout(height=360, xaxis_tickangle=-20)
                st.plotly_chart(fig_alert, use_container_width=True)

                # Summary saving metric
                total_possible_saving = sum(r['Bill Saving'] for r in alert_data if r['Bill Saving'] > 0)
                if total_possible_saving > 0:
                    st.markdown(f"""
                        <div style="background:linear-gradient(135deg,#1abc9c,#27ae60);color:white;
                        padding:18px 28px;border-radius:12px;text-align:center;font-size:20px;
                        font-weight:bold;font-family:sans-serif;margin:10px 0;">
                        💰 You could save up to <u>Rs {total_possible_saving:.0f}/month</u> next month
                        by reducing over-limit appliances to recommended levels!
                        </div>
                    """, unsafe_allow_html=True)

                # Individual appliance cards
                st.markdown("**📋 Appliance-wise Analysis & Recommendations:**")
                for row in sorted(alert_data, key=lambda x: x['Bill Saving'], reverse=True):
                    saving_text = (
                        f"<b style='color:#27ae60;'>💰 Reduce to {row['Reduced Hrs']}hrs/day → Save Rs {row['Bill Saving']:.0f} next month!</b>"
                        if row['Bill Saving'] > 0 else
                        f"<span style='color:#27ae60;'>✅ Within recommended limit — no change needed.</span>"
                    )
                    st.markdown(f"""
                        <div style="background:{row['bg']};border-left:5px solid {row['border']};
                        padding:14px 20px;border-radius:8px;margin:8px 0;font-family:sans-serif;">
                        <div style="display:flex;justify-content:space-between;">
                            <span style="font-size:15px;font-weight:bold;color:#333;">{row['Appliance']}</span>
                            <span style="font-size:13px;font-weight:bold;color:{row['border']};">{row['Status']}</span>
                        </div>
                        <span style="font-size:13px;color:#555;">
                            ⏱ <b>{row['Hrs/Day']}hrs/day</b> (recommended: {row['Limit (hrs)']}hrs) &nbsp;|&nbsp;
                            ⚡ {row['Current Units']} kWh/month &nbsp;|&nbsp;
                            💰 Rs {row['Current Cost']:.0f}/month
                        </span><br>
                        <span style="font-size:13px;margin:4px 0;display:block;">{saving_text}</span>
                        <span style="font-size:12px;color:#888;margin-top:3px;display:block;">💡 {row['tip']}</span>
                        </div>
                    """, unsafe_allow_html=True)
        else:
            st.info("Fill the appliance survey on Enter Data page to get smart appliance alerts.")

        st.markdown("---")

        # CHART 1 — LINE
        st.subheader("1. Daily Consumption Trend")
        daily_rows = []
        for _, row in df.iterrows():
            month_idx = month_order[row['Month']] + 1
            days_in_month = pd.Period(f"{selected_year}-{month_idx:02d}").days_in_month
            daily_avg = row['Units'] / days_in_month
            rng = np.random.default_rng(month_idx * 7)
            noise = rng.normal(0, daily_avg * 0.1, days_in_month)
            for d in range(1, days_in_month + 1):
                daily_rows.append({"Date": f"{row['Month']} {d:02d}", "Units": round(max(0.1, daily_avg + noise[d-1]), 2), "Month": row['Month']})
        daily_df = pd.DataFrame(daily_rows)
        fig_line = px.line(daily_df, x="Date", y="Units", color="Month",
                           title=f"Estimated Daily Consumption ({selected_year})",
                           labels={"Units": "Units (kWh)"})
        fig_line.update_traces(line=dict(width=1.5))
        fig_line.update_layout(height=400, showlegend=True)
        fig_line.update_xaxes(showticklabels=False)
        st.plotly_chart(fig_line, use_container_width=True)
        st.caption("Daily values estimated from monthly totals.")

        st.markdown("---")

        # CHART 2 — BAR
        st.subheader("2. Monthly Comparison")
        fig_bar = px.bar(df, x="Month", y=["Units", "Bill"], barmode="group",
                         title=f"Monthly Units & Bill Comparison ({selected_year})",
                         labels={"value": "Units (kWh) / Bill (Rs)", "variable": "Metric"},
                         color_discrete_map={"Units": "#4C78A8", "Bill": "#F58518"})
        fig_bar.update_layout(height=400)
        st.plotly_chart(fig_bar, use_container_width=True)

        st.markdown("---")

        # CHART 3 — PIE (auto from stored appliance data)
        st.subheader("3. Appliance-wise Usage Breakdown")
        appliance_rows = load_all_appliance_data(st.session_state.username, selected_year)

        if appliance_rows:
            # Aggregate hours across all months
            total_hours = {}
            for _, hours_json in appliance_rows:
                for appliance, hrs in hours_json.items():
                    total_hours[appliance] = total_hours.get(appliance, 0) + float(hrs)

            # Calculate units per appliance (avg hours/day * 30 days * wattage / 1000)
            num_months = len(appliance_rows)
            appliance_units = {}
            for appliance, wattage in APPLIANCES.items():
                avg_hrs = total_hours.get(appliance, 0) / num_months
                units_calc = round((wattage * avg_hrs * 30) / 1000, 2)
                if units_calc > 0:
                    appliance_units[appliance] = units_calc

            if appliance_units:
                pie_df = pd.DataFrame({
                    "Appliance": list(appliance_units.keys()),
                    "Units (kWh)": list(appliance_units.values())
                })
                fig_pie = px.pie(pie_df, names="Appliance", values="Units (kWh)",
                                 title=f"Appliance-wise Electricity Consumption ({selected_year} Average)",
                                 hole=0.3)
                fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                fig_pie.update_layout(height=500)
                st.plotly_chart(fig_pie, use_container_width=True)
                a_col1, a_col2 = st.columns(2)
                with a_col1:
                    st.metric("Total Appliance Units", f"{sum(appliance_units.values()):.1f} kWh/month")
                with a_col2:
                    st.metric("Estimated Bill", f"Rs {calculate_msedcl_bill(sum(appliance_units.values()))['total']:.0f}/month")
            else:
                st.info("No appliance usage recorded yet. Fill the survey on the Enter Data page.")
        else:
            st.info("No appliance data yet. Fill the survey when entering monthly data.")

        st.markdown("---")

        # CHART 4 — HEATMAP
        st.subheader("4. Hourly Usage Pattern Heatmap")
        hourly_weights = np.array([0.3,0.2,0.2,0.2,0.2,0.3,0.5,0.8,1.0,0.7,0.6,0.7,0.8,0.6,0.5,0.5,0.6,0.8,1.0,1.2,1.2,1.0,0.8,0.5])
        hourly_weights = hourly_weights / hourly_weights.sum()
        heatmap_data = []
        for _, row in df.iterrows():
            month_idx = month_order[row['Month']] + 1
            days_in_month = pd.Period(f"{selected_year}-{month_idx:02d}").days_in_month
            heatmap_data.append((row['Units'] / days_in_month) * hourly_weights * 24)
        fig_heat = px.imshow(np.array(heatmap_data),
                             x=[f"{h:02d}:00" for h in range(24)], y=df['Month'].tolist(),
                             color_continuous_scale="YlOrRd",
                             title=f"Hourly Usage Heatmap ({selected_year})",
                             labels={"x": "Hour of Day", "y": "Month", "color": "kWh"}, aspect="auto")
        fig_heat.update_layout(height=400)
        st.plotly_chart(fig_heat, use_container_width=True)
        st.caption("Heatmap estimated based on typical Indian household hourly usage patterns.")

        st.markdown("---")

        # CARBON FOOTPRINT
        st.subheader("🌍 Carbon Footprint")
        total_co2   = total_units * 0.82
        monthly_co2 = last_units * 0.82
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total CO2", f"{total_co2:.0f} kg", delta=f"{monthly_co2:.0f} kg this month")
        with col2:
            st.metric("Trees Equivalent", f"{total_co2/22:.1f} trees/year")

        st.markdown("---")

        # ═══════════════════════════════════════
        # NEXT MONTH PREDICTIONS
        # ═══════════════════════════════════════
        st.subheader("🔮 Next Month Predictions")

        # Predict using weighted avg of last 3 months if available
        if len(df) >= 3:
            weights    = np.array([0.5, 0.3, 0.2])
            last3      = df['Units'].iloc[-3:].values[::-1]
            next_units = round(float(np.dot(weights, last3)), 1)
        else:
            next_units = round(last_units * 1.05, 1)

        next_bill_data = calculate_msedcl_bill(next_units, connection_type)
        next_bill      = next_bill_data['total']

        # Predicted slab
        if next_units <= 100:
            pred_slab, slab_color = "Slab 1 — Rs 2.90/unit (0–100 kWh)", "#27ae60"
        elif next_units <= 300:
            pred_slab, slab_color = "Slab 2 — Rs 6.50/unit (101–300 kWh)", "#f1c40f"
        elif next_units <= 500:
            pred_slab, slab_color = "Slab 3 — Rs 8.00/unit (301–500 kWh)", "#e67e22"
        else:
            pred_slab, slab_color = "Slab 4 — Rs 11.85/unit (500+ kWh)", "#e74c3c"

        pc1, pc2, pc3 = st.columns(3)
        with pc1:
            st.metric("Predicted Units", f"{next_units:.0f} kWh",
                      delta=f"{next_units - last_units:+.0f} vs last month")
        with pc2:
            st.metric("Predicted Bill", f"Rs {next_bill:.0f}",
                      delta=f"Rs {next_bill - last_bill:+.0f} vs last month")
        with pc3:
            st.markdown(f"""
                <div style="background:{slab_color}22;border:2px solid {slab_color};
                padding:12px;border-radius:8px;text-align:center;">
                <span style="font-size:13px;color:#333;font-weight:bold;">Predicted Slab</span><br>
                <span style="font-size:12px;color:#555;">{pred_slab}</span>
                </div>
            """, unsafe_allow_html=True)

        st.markdown("")

        # Predicted appliance-wise cost next month
        if latest_appliance:
            st.markdown("#### 💡 Predicted Appliance-wise Cost Next Month")
            pred_appliance_data = []
            for appliance, wattage in APPLIANCES.items():
                hrs = float(latest_appliance.get(appliance, 0))
                if hrs == 0:
                    continue
                units_m = round((wattage * hrs * 30) / 1000, 2)
                cost_m  = round(calculate_msedcl_bill(units_m)['total'], 0)
                pred_appliance_data.append({"Appliance": appliance, "Predicted Cost (Rs)": cost_m, "Units (kWh)": units_m})

            if pred_appliance_data:
                pred_df = pd.DataFrame(pred_appliance_data).sort_values("Predicted Cost (Rs)", ascending=False)
                fig_pred = px.bar(pred_df, x="Appliance", y="Predicted Cost (Rs)",
                                  title="Predicted Appliance-wise Electricity Cost (Next Month)",
                                  color="Predicted Cost (Rs)",
                                  color_continuous_scale="RdYlGn_r",
                                  text="Predicted Cost (Rs)")
                fig_pred.update_traces(texttemplate="Rs %{text:.0f}", textposition="outside")
                fig_pred.update_layout(height=400, xaxis_tickangle=-20, showlegend=False)
                st.plotly_chart(fig_pred, use_container_width=True)

        st.markdown("")

        # Tips to reduce bill
        st.markdown("#### 💰 Tips to Reduce Your Bill Next Month")
        tips = []
        if latest_appliance:
            if float(latest_appliance.get("AC (1.5 ton)", 0)) > 6:
                tips.append("❄️ **AC** — Set temperature to 24°C instead of 18°C. Each degree saves ~6% energy.")
            if float(latest_appliance.get("Water Heater (Geyser)", 0)) > 1:
                tips.append("🚿 **Geyser** — Use for max 30 mins/day. Switch off immediately after use.")
            if float(latest_appliance.get("Washing Machine", 0)) > 1:
                tips.append("👕 **Washing Machine** — Run full loads only. Use cold water when possible.")
            if float(latest_appliance.get("TV (LED 43 inch)", 0)) > 5:
                tips.append("📺 **TV** — Reduce screen brightness. Switch off instead of standby.")
            if float(latest_appliance.get("Computer/Laptop", 0)) > 6:
                tips.append("💻 **Computer** — Enable power saving mode. Switch off monitor when not in use.")

        # General tips always shown
        tips += [
            "💡 Switch to LED bulbs if not already done — saves up to 80% on lighting.",
            "🌙 Run heavy appliances (washing machine, iron) during off-peak hours (late night).",
            "🔌 Unplug chargers and devices when not in use — phantom load adds up!",
        ]
        if next_units > 100:
            tips.append(f"📉 Reduce usage by just {max(1, next_units - 100):.0f} kWh to stay in a lower slab and save more.")

        for tip in tips[:6]:
            st.markdown(f"""
                <div style="background:#f8f9fa;border-left:4px solid #3498db;
                padding:10px 16px;border-radius:6px;margin:5px 0;font-size:14px;
                font-family:sans-serif;color:#333;">{tip}</div>
            """, unsafe_allow_html=True)

    else:
        st.info(f"No data found for {selected_year}. Go to Enter Data page to add your monthly readings!")
        if st.button("Go to Enter Data →"):
            st.session_state.page = "input"
            st.rerun()

st.markdown("---")
st.caption("Rates based on MSEDCL (Mahavitaran) Maharashtra Residential Tariff 2025.")



