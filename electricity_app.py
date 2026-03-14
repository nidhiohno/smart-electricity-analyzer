import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
from datetime import datetime
import hashlib
import psycopg2
import base64
import json

st.set_page_config(page_title="VoltIQ", page_icon="⚡", layout="wide")

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
            security_answer TEXT NOT NULL DEFAULT '',
            supplier TEXT NOT NULL DEFAULT 'MSEDCL'
        )
    """)
    # Add supplier column if upgrading existing DB
    try:
        cur.execute("ALTER TABLE users ADD COLUMN supplier TEXT NOT NULL DEFAULT 'MSEDCL'")
        conn.commit()
    except:
        conn.rollback()
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
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_survey (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            avg_appliance_hours JSONB NOT NULL,
            completed_at TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

init_db()

# ─────────────────────────────────────────────
# SUPPLIER RATES
# ─────────────────────────────────────────────
SUPPLIERS = {
    "MSEDCL": {
        "full_name": "MSEDCL (Mahavitaran)",
        "slabs": [(100, 2.90), (200, 6.50), (200, 8.00), (float('inf'), 11.85)],
        "fixed_charge": 30,
        "fac": 0.20,
        "duty_pct": 0.16,
        "color": "#e74c3c"
    },
    "Tata Power": {
        "full_name": "Tata Power Mumbai",
        "slabs": [(100, 3.34), (200, 6.68), (200, 9.29), (float('inf'), 12.43)],
        "fixed_charge": 50,
        "fac": 0.15,
        "duty_pct": 0.16,
        "color": "#2980b9"
    },
    "Adani Electricity": {
        "full_name": "Adani Electricity Mumbai",
        "slabs": [(100, 3.13), (200, 6.26), (200, 9.10), (float('inf'), 11.97)],
        "fixed_charge": 45,
        "fac": 0.18,
        "duty_pct": 0.16,
        "color": "#f39c12"
    },
    "BEST": {
        "full_name": "BEST (Brihanmumbai Electric Supply)",
        "slabs": [(100, 2.80), (200, 5.90), (200, 8.50), (float('inf'), 11.20)],
        "fixed_charge": 25,
        "fac": 0.10,
        "duty_pct": 0.16,
        "color": "#27ae60"
    },
}

# ─────────────────────────────────────────────
# BILL CALCULATOR
# ─────────────────────────────────────────────
def calculate_bill(units, supplier="MSEDCL"):
    s = SUPPLIERS.get(supplier, SUPPLIERS["MSEDCL"])
    energy_charge = 0.0
    remaining = units
    for slab_units, rate in s["slabs"]:
        if remaining <= 0:
            break
        billed = min(remaining, slab_units)
        energy_charge += billed * rate
        remaining -= billed
    fac = units * s["fac"]
    fixed_charge = s["fixed_charge"]
    electricity_duty = energy_charge * s["duty_pct"]
    total = energy_charge + fac + fixed_charge + electricity_duty
    return {
        "energy_charge": round(energy_charge, 2),
        "fac": round(fac, 2),
        "fixed_charge": fixed_charge,
        "electricity_duty": round(electricity_duty, 2),
        "total": round(total, 2)
    }

# Keep backward compat
def calculate_msedcl_bill(units, connection_type="single_phase"):
    return calculate_bill(units, "MSEDCL")

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

def save_supplier(username, supplier):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE users SET supplier = %s WHERE username = %s", (supplier, username))
    conn.commit()
    cur.close()
    conn.close()

def load_supplier(username):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT supplier FROM users WHERE username = %s", (username,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else "MSEDCL"

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

def has_completed_survey(username):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT avg_appliance_hours FROM user_survey WHERE username = %s", (username,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else None

def save_user_survey(username, avg_hours):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO user_survey (username, avg_appliance_hours)
        VALUES (%s, %s)
        ON CONFLICT(username) DO UPDATE SET
            avg_appliance_hours = EXCLUDED.avg_appliance_hours,
            completed_at = NOW()
    """, (username, json.dumps(avg_hours)))
    conn.commit()
    cur.close()
    conn.close()

def scale_hours_to_units(avg_hours, actual_units):
    """Scale survey appliance hours so their total kWh matches actual_units for this month."""
    if not avg_hours or actual_units == 0:
        return avg_hours
    raw_kwh_total = sum(
        (APPLIANCES[a] * float(avg_hours.get(a, 0)) * 30) / 1000
        for a in APPLIANCES if float(avg_hours.get(a, 0)) > 0
    )
    if raw_kwh_total == 0:
        return avg_hours
    scale = actual_units / raw_kwh_total
    return {
        a: round(float(avg_hours.get(a, 0)) * scale, 4)
        for a in avg_hours
    }

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
    ("supplier", "MSEDCL"),
    ("just_saved", False),
    ("saved_month", ""),
    ("saved_units", 0.0),
    ("saved_bill", 0.0),
    ("saved_year", datetime.now().year),
    ("saved_hours", {}),
    ("show_onboarding_survey", False),
    ("avg_survey_hours", {}),
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
    st.markdown("<h1 style='text-align:center'>⚡ VoltIQ</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;color:gray'>Smart Electricity Analyzer — Maharashtra</p>", unsafe_allow_html=True)
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
                    st.session_state.supplier = load_supplier(username)
                    st.session_state.page = "input"
                    # Check if onboarding survey has been filled
                    survey_data = has_completed_survey(username)
                    if survey_data is None:
                        st.session_state.show_onboarding_survey = True
                        st.session_state.avg_survey_hours = {}
                    else:
                        st.session_state.show_onboarding_survey = False
                        st.session_state.avg_survey_hours = survey_data
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
    st.markdown("### ⚡ VoltIQ")
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
# ONBOARDING SURVEY — shown only once per user
# ─────────────────────────────────────────────
if st.session_state.get("show_onboarding_survey", False):
    st.markdown("## 👋 Welcome to VoltIQ!")
    st.markdown("""
        <div style="background:#eaf4fb;border-left:5px solid #3498db;padding:16px 20px;
        border-radius:8px;font-family:sans-serif;font-size:14px;margin-bottom:16px;">
        <b>One-time setup:</b> Tell us your <b>average daily usage</b> for your appliances.
        This helps VoltIQ give you accurate next-month predictions right from your very first entry!
        </div>
    """, unsafe_allow_html=True)

    st.markdown("#### 🏠 Average Appliance Usage Survey")
    st.caption("How many hours per day do you typically use each appliance? (Enter 0 if you don't have it)")

    onboard_hours = {}
    cols_ob = st.columns(2)
    for i, (appliance, wattage) in enumerate(APPLIANCES.items()):
        with cols_ob[i % 2]:
            onboard_hours[appliance] = st.number_input(
                f"{appliance} ({wattage}W)",
                min_value=0.0, max_value=24.0,
                value=0.0, step=0.5,
                key=f"onboard_{i}",
                help="Average hours per day"
            )

    total_survey_units = sum(
        (APPLIANCES[a] * onboard_hours[a] * 30) / 1000
        for a in APPLIANCES if onboard_hours[a] > 0
    )
    if total_survey_units > 0:
        est_survey_bill = calculate_bill(total_survey_units, st.session_state.supplier)['total']
        st.info(f"📊 Based on your inputs — Estimated monthly usage: **{total_survey_units:.1f} kWh** | Estimated bill: **Rs {est_survey_bill:.0f}**")

    if st.button("✅ Save & Continue", use_container_width=True, key="save_onboard_survey"):
        save_user_survey(st.session_state.username, onboard_hours)
        st.session_state.avg_survey_hours = onboard_hours
        st.session_state.show_onboarding_survey = False
        st.success("Survey saved! You're all set.")
        st.rerun()
    st.stop()

# ─────────────────────────────────────────────
# PAGE 2 — INPUT DATA
# ─────────────────────────────────────────────
if st.session_state.page == "input":
    st.markdown("## 📥 Enter Monthly Data")

    # Supplier selector
    col_s1, col_s2 = st.columns([2, 2])
    with col_s1:
        supplier_list = list(SUPPLIERS.keys())
        current_idx   = supplier_list.index(st.session_state.supplier) if st.session_state.supplier in supplier_list else 0
        selected_supplier = st.selectbox(
            "⚡ Your Electricity Supplier",
            supplier_list,
            index=current_idx,
            key="supplier_select",
            format_func=lambda x: SUPPLIERS[x]["full_name"]
        )
        if selected_supplier != st.session_state.supplier:
            st.session_state.supplier = selected_supplier
            save_supplier(st.session_state.username, selected_supplier)
    with col_s2:
        sup = SUPPLIERS[st.session_state.supplier]
        st.markdown(f"""
            <div style="background:{sup['color']}22;border:2px solid {sup['color']};
            padding:10px 14px;border-radius:8px;margin-top:4px;">
            <span style="font-size:13px;font-weight:bold;color:{sup['color']};">
            {sup['full_name']}</span><br>
            <span style="font-size:11px;color:#666;">
            Slabs: Rs {sup['slabs'][0][1]}/Rs {sup['slabs'][1][1]}/Rs {sup['slabs'][2][1]}/Rs {sup['slabs'][3][1]} per unit
            </span></div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # Year selector — allows entering data for any year
    selected_year = int(st.number_input(
        "📅 Year", min_value=2000, max_value=2100,
        value=datetime.now().year, step=1, key="input_year"
    ))

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
            preview = calculate_bill(units_consumed, st.session_state.supplier)
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

        st.markdown("")
        if st.button("Save & Analyze", use_container_width=True, key="manual_save"):
            if units_consumed == 0:
                st.error("Please enter units consumed.")
            else:
                bill_data      = calculate_bill(units_consumed, st.session_state.supplier)
                effective_rate = round(bill_data['total'] / units_consumed, 2)
                save_entry(st.session_state.username, selected_year, month, units_consumed, bill_data['total'], effective_rate)
                # Scale survey hours to match this month's actual units before saving
                avg_survey = st.session_state.get("avg_survey_hours") or has_completed_survey(st.session_state.username) or {}
                scaled_hours = scale_hours_to_units(avg_survey, units_consumed)
                save_appliance_data(st.session_state.username, selected_year, month, scaled_hours)
                st.session_state.just_saved       = True
                st.session_state.saved_month      = month
                st.session_state.saved_units      = units_consumed
                st.session_state.saved_bill       = bill_data['total']
                st.session_state.saved_year       = selected_year
                st.session_state.saved_hours      = scaled_hours
                st.rerun()

    # ── UPLOAD BILL ──
    with upload_tab:
        st.markdown("#### Upload your electricity bill (PDF or Image)")
        st.info("📌 PDF works best for digital bills. For Marathi or scanned bills, please use **Manual Input** tab instead.")
        uploaded_file = st.file_uploader("Choose file", type=["pdf", "jpg", "jpeg", "png"], key="bill_upload")

        if uploaded_file is not None:
            if st.button(" Extract Data ", use_container_width=True):
                with st.spinner("Reading your bill..."):
                    try:
                        import pdfplumber, re, io
                        file_bytes = uploaded_file.read()
                        mime_type  = uploaded_file.type
                        text = ""
                        if mime_type == "application/pdf":
                            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                                for page in pdf.pages:
                                    text += page.extract_text() or ""
                        else:
                            st.warning("⚠️ Image bills may not extract accurately. For best results, upload the PDF version of your bill.")
                            text = ""
                        extracted = {}
                        units_patterns = [
                            r"Units\s*Consumed[:\s]+([\d,]+\.?\d*)",
                            r"Net\s*Units[:\s]+([\d,]+\.?\d*)",
                            r"Energy\s*Consumed[:\s]+([\d,]+\.?\d*)",
                            r"Total\s*Units[:\s]+([\d,]+\.?\d*)",
                            r"Consumption[:\s]+([\d,]+\.?\d*)\s*(?:kWh|KWH|Units)",
                            r"([\d,]+\.?\d*)\s*(?:kWh|KWH|Units\s*Consumed)",
                        ]
                        for pat in units_patterns:
                            m = re.search(pat, text, re.IGNORECASE)
                            if m:
                                extracted["units"] = m.group(1).replace(",", "")
                                break
                        month_map = {"january":"Jan","february":"Feb","march":"Mar","april":"Apr",
                                     "may":"May","june":"Jun","july":"Jul","august":"Aug",
                                     "september":"Sep","october":"Oct","november":"Nov","december":"Dec",
                                     "jan":"Jan","feb":"Feb","mar":"Mar","apr":"Apr","jun":"Jun",
                                     "jul":"Jul","aug":"Aug","sep":"Sep","oct":"Oct","nov":"Nov","dec":"Dec"}
                        month_pat = r"(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
                        m = re.search(month_pat, text, re.IGNORECASE)
                        if m:
                            extracted["month"] = month_map.get(m.group(1).lower(), m.group(1)[:3].capitalize())
                        year_pat = r"(202[0-9]|203[0-9])"
                        m = re.search(year_pat, text)
                        if m:
                            extracted["year"] = m.group(1)
                        with st.expander("🔍 Debug: Raw PDF text"):
                            st.text(text[:1000])
                        if extracted.get("units"):
                            st.session_state.extracted = extracted
                            st.success(f"✅ Bill read! Units: {extracted.get('units')} | Month: {extracted.get('month','?')} | Year: {extracted.get('year','?')}")
                            st.rerun()
                        else:
                            st.warning("⚠️ Could not auto-extract units. Please fill in manually below.")
                            st.session_state.extracted = {"units": "0", "month": MONTH_NAMES[datetime.now().month-1], "year": str(datetime.now().year)}
                            st.rerun()
                    except Exception as e:
                        st.error(f"Could not read bill: {e}. Please use Manual Input instead.")

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

            col1, col2 = st.columns(2)
            with col1:
                confirmed_units = st.number_input("Units (kWh)", min_value=0.0, value=default_units, step=1.0, key="ext_units")
            with col2:
                confirmed_month = st.selectbox("Month", MONTH_NAMES, index=MONTH_NAMES.index(ext_month), key="ext_month")

            if confirmed_units > 0:
                preview2 = calculate_bill(confirmed_units, st.session_state.supplier)
                st.info(f"Estimated Bill: **Rs {preview2['total']}**")

            if st.button(" Save & Analyze", use_container_width=True, key="upload_save"):
                if confirmed_units == 0:
                    st.error("Units cannot be zero.")
                else:
                    bill_data      = calculate_bill(confirmed_units, st.session_state.supplier)
                    effective_rate = round(bill_data['total'] / confirmed_units, 2)
                    save_entry(st.session_state.username, selected_year, confirmed_month, confirmed_units, bill_data['total'], effective_rate)
                    avg_survey = st.session_state.get("avg_survey_hours") or has_completed_survey(st.session_state.username) or {}
                    scaled_hours = scale_hours_to_units(avg_survey, confirmed_units)
                    save_appliance_data(st.session_state.username, selected_year, confirmed_month, scaled_hours)
                    st.session_state.just_saved  = True
                    st.session_state.saved_month = confirmed_month
                    st.session_state.saved_units = confirmed_units
                    st.session_state.saved_bill  = bill_data['total']
                    st.session_state.saved_year  = selected_year
                    st.session_state.saved_hours = scaled_hours
                    st.session_state.extracted   = {}
                    st.rerun()

    # ── POST SAVE: Show current month summary + next month prediction ──
    if st.session_state.get("just_saved"):
        s_month  = st.session_state.saved_month
        s_units  = st.session_state.saved_units
        s_bill   = st.session_state.saved_bill
        s_year   = st.session_state.saved_year
        s_hours  = st.session_state.get("saved_hours", {})
        supplier = st.session_state.supplier

        st.markdown("---")
        st.markdown(f"### ✅ {s_month} {s_year} — Saved Successfully!")

        # Current month metrics
        c1, c2, c3 = st.columns(3)
        bill_info   = calculate_bill(s_units, supplier)
        with c1:
            st.metric("Units Consumed", f"{s_units:.0f} kWh")
        with c2:
            st.metric("Total Bill", f"Rs {s_bill:.0f}")
        with c3:
            eff_rate = round(s_bill / s_units, 2) if s_units > 0 else 0
            st.metric("Effective Rate", f"Rs {eff_rate}/kWh")

        # Current month slab
        if s_units <= 100:
            slab_msg, slab_color = f"✅ Lowest slab — Rs {SUPPLIERS[supplier]['slabs'][0][1]}/unit", "#27ae60"
        elif s_units <= 300:
            slab_msg, slab_color = f"🟡 Slab 2 — Rs {SUPPLIERS[supplier]['slabs'][1][1]}/unit", "#f1c40f"
        elif s_units <= 500:
            slab_msg, slab_color = f"🟠 Slab 3 — Rs {SUPPLIERS[supplier]['slabs'][2][1]}/unit", "#e67e22"
        else:
            slab_msg, slab_color = f"🔴 Highest slab — Rs {SUPPLIERS[supplier]['slabs'][3][1]}/unit", "#e74c3c"

        st.markdown(f"""
            <div style="background:{slab_color}22;border-left:5px solid {slab_color};
            padding:12px 18px;border-radius:8px;margin:8px 0;font-family:sans-serif;">
            <b>Current Slab:</b> {slab_msg}
            </div>
        """, unsafe_allow_html=True)

        # Load previous months for prediction
        all_rows = load_user_data(st.session_state.username, s_year)
        month_order = {m: i for i, m in enumerate(MONTH_NAMES)}
        all_df = pd.DataFrame(all_rows, columns=['Month','Units','Bill','Rate']) if all_rows else pd.DataFrame()
        if not all_df.empty:
            all_df['_order'] = all_df['Month'].map(month_order)
        all_df = all_df.sort_values('_order').drop(columns='_order').reset_index(drop=True)

        # Next month prediction
        st.markdown("---")
        st.markdown("### 🔮 Next Month Prediction")

        # Use survey avg hours as fallback if fewer than 2 months of real data
        avg_survey = st.session_state.get("avg_survey_hours") or has_completed_survey(st.session_state.username) or {}

        if not all_df.empty and len(all_df) >= 2:
            weights    = np.array([0.5, 0.3, 0.2]) if len(all_df) >= 3 else np.array([0.6, 0.4])
            last_n     = all_df['Units'].iloc[-min(len(all_df),3):].values[::-1]
            next_units = round(float(np.dot(weights[:len(last_n)], last_n[:len(weights)])), 1)
        elif avg_survey:
            # Use survey average hours to estimate expected usage
            survey_units = sum(
                (APPLIANCES[a] * float(avg_survey.get(a, 0)) * 30) / 1000
                for a in APPLIANCES if float(avg_survey.get(a, 0)) > 0
            )
            # Blend: 60% current month actual, 40% survey baseline
            next_units = round(s_units * 0.6 + survey_units * 0.4, 1) if survey_units > 0 else round(s_units * 1.05, 1)
        else:
            next_units = round(s_units * 1.05, 1)

        next_bill = calculate_bill(next_units, supplier)['total']
        curr_month_idx = MONTH_NAMES.index(s_month)
        next_month_name = MONTH_NAMES[(curr_month_idx + 1) % 12]

        n1, n2, n3 = st.columns(3)
        with n1:
            st.metric("Predicted Units", f"{next_units:.0f} kWh", delta=f"{next_units - s_units:+.0f} vs this month")
        with n2:
            st.metric("Predicted Bill", f"Rs {next_bill:.0f}", delta=f"Rs {next_bill - s_bill:+.0f} vs this month")
        with n3:
            st.metric("Next Month", next_month_name)

        # ── APPLIANCE GRAPH + ANALYSIS ──
        # Load from DB if session hours empty
        if not s_hours:
            s_hours = load_appliance_data(st.session_state.username, s_year, s_month)

        if s_hours:
            st.markdown("---")
            st.markdown(f"####  Smart Appliance Alerts & Next Month Savings — {s_month} {s_year}")
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

            total_current_units = s_units
            total_current_bill  = s_bill

            alert_data = []
            for appliance, wattage in APPLIANCES.items():
                hrs = float(s_hours.get(appliance, 0))
                if hrs == 0:
                    continue
                limit         = thresholds.get(appliance, 8)
                current_units = round((wattage * hrs * 30) / 1000, 2)
                current_cost  = round(calculate_bill(current_units, supplier)['total'], 0)
                reduced_hrs   = min(hrs, limit)
                reduced_units = round((wattage * reduced_hrs * 30) / 1000, 2)
                other_units   = total_current_units - current_units
                new_total_bill = calculate_bill(other_units + reduced_units, supplier)['total']
                bill_saving    = round(total_current_bill - new_total_bill, 0)
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
                # Bar chart
                chart_df  = pd.DataFrame(alert_data)
                fig_alert = px.bar(chart_df, x="Appliance", y=["Hrs/Day", "Limit (hrs)"],
                                   barmode="group",
                                   title=f"Your Appliance Usage vs Recommended Limit — {s_month}",
                                   color_discrete_map={"Hrs/Day": "#e74c3c", "Limit (hrs)": "#2ecc71"},
                                   labels={"value": "Hours/Day", "variable": ""})
                fig_alert.update_layout(height=360, xaxis_tickangle=-20)
                st.plotly_chart(fig_alert, use_container_width=True)

                # Total saving banner
                total_possible_saving = sum(r['Bill Saving'] for r in alert_data if r['Bill Saving'] > 0)
                if total_possible_saving > 0:
                    st.markdown(f"""
                        <div style="background:linear-gradient(135deg,#1abc9c,#27ae60);color:white;
                        padding:18px 28px;border-radius:12px;text-align:center;font-size:20px;
                        font-weight:bold;font-family:sans-serif;margin:10px 0;">
                        💰 You could save up to <u>Rs {total_possible_saving:.0f}/month</u> next month
                        by reducing over-limit appliances!
                        </div>
                    """, unsafe_allow_html=True)

                # Analysis cards for every appliance
                st.markdown("** Appliance-wise Analysis & Recommendations:**")
                for row in sorted(alert_data, key=lambda x: x['Bill Saving'], reverse=True):
                    saving_text = (
                        f"<b style='color:#27ae60;'>💰 Reduce to {row['Reduced Hrs']}hrs/day → Save Rs {row['Bill Saving']:.0f} next month!</b>"
                        if row['Bill Saving'] > 0 else
                        "<span style='color:#27ae60;'>✅ Within recommended limit — no change needed.</span>"
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
            st.markdown("---")
            st.info("Fill the appliance survey above to get smart appliance alerts and savings recommendations.")

        # Bill-level alerts — always show something
        st.markdown("---")
        st.markdown("#### 💡 Bill & Usage Alerts for Next Month")

        # Always show current vs next month comparison
        delta_units = next_units - s_units
        delta_bill  = next_bill - s_bill
        trend_icon  = "📈" if delta_units > 0 else "📉"
        trend_color = "#e74c3c" if delta_units > 0 else "#27ae60"
        st.markdown(f"""
            <div style="background:{trend_color}11;border-left:5px solid {trend_color};
            padding:14px 20px;border-radius:8px;margin:6px 0;font-family:sans-serif;">
            {trend_icon} <b>Next Month Forecast:</b> {next_units:.0f} kWh predicted
            ({"+" if delta_units >= 0 else ""}{delta_units:.0f} kWh vs this month) —
            Est. bill Rs {next_bill:.0f} ({"+" if delta_bill >= 0 else ""}{delta_bill:.0f} vs this month)
            </div>
        """, unsafe_allow_html=True)

        # Slab-based alert — always shown
        if s_units > 500:
            st.markdown(f"""<div style="background:#fff0f0;border-left:5px solid #e74c3c;
            padding:12px 18px;border-radius:8px;margin:6px 0;font-family:sans-serif;font-size:14px;">
            🔴 <b>Very High Usage!</b> You are in the highest slab (Rs {SUPPLIERS[supplier]['slabs'][3][1]}/unit).
            Reducing by {s_units - 500:.0f} kWh next month saves Rs {s_bill - calculate_bill(500, supplier)['total']:.0f}!
            </div>""", unsafe_allow_html=True)
        elif s_units > 300:
            st.markdown(f"""<div style="background:#fff4e5;border-left:5px solid #e67e22;
            padding:12px 18px;border-radius:8px;margin:6px 0;font-family:sans-serif;font-size:14px;">
            🟠 <b>High Slab Alert!</b> Reducing by {s_units - 300:.0f} kWh next month could save
            Rs {s_bill - calculate_bill(300, supplier)['total']:.0f}!
            </div>""", unsafe_allow_html=True)
        elif s_units > 100:
            st.markdown(f"""<div style="background:#fffde7;border-left:5px solid #f1c40f;
            padding:12px 18px;border-radius:8px;margin:6px 0;font-family:sans-serif;font-size:14px;">
            🟡 <b>Slab Reduction Tip:</b> Reduce by {s_units - 100:.0f} kWh next month to drop to the
            lowest slab and save Rs {s_bill - calculate_bill(100, supplier)['total']:.0f}!
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""<div style="background:#f0fff4;border-left:5px solid #27ae60;
            padding:12px 18px;border-radius:8px;margin:6px 0;font-family:sans-serif;font-size:14px;">
            ✅ <b>Excellent!</b> You are in the lowest slab (Rs {SUPPLIERS[supplier]['slabs'][0][1]}/unit).
            Keep your usage under 100 kWh next month to maintain this!
            </div>""", unsafe_allow_html=True)

        # Spike alert
        if next_units > s_units * 1.15:
            st.markdown(f"""<div style="background:#fff0f0;border-left:5px solid #e74c3c;
            padding:12px 18px;border-radius:8px;margin:6px 0;font-family:sans-serif;font-size:14px;">
            🚨 <b>Spike Predicted!</b> Next month usage may jump by {next_units - s_units:.0f} kWh.
            Check for seasonal changes or extra appliance usage.
            </div>""", unsafe_allow_html=True)

        # General tips — always 3 shown
        st.markdown("**💡 Quick Tips:**")
        tips = [
            "🔌 Unplug chargers and devices when not in use — phantom load adds up!",
            "🌙 Run washing machine and iron during off-peak hours (late night) to reduce load.",
            "💡 Switch to LED bulbs if not already done — saves up to 80% on lighting.",
            "❄️ Set AC to 24°C — each degree higher saves ~6% energy.",
            "🚿 Switch off geyser immediately after use — don't leave it on standby.",
        ]
        for tip in tips[:3]:
            st.markdown(f"""<div style="background:#f8f9fa;border-left:4px solid #3498db;
            padding:10px 16px;border-radius:6px;margin:5px 0;font-size:13px;
            font-family:sans-serif;color:#333;">{tip}</div>""", unsafe_allow_html=True)


        # ── CARBON FOOTPRINT ──
        st.markdown("---")
        st.subheader("🌍 Carbon Footprint")
        co2_total   = s_units * 0.82
        trees_equiv = co2_total / 22
        cf1, cf2 = st.columns(2)
        with cf1:
            st.metric("CO2 This Month", f"{co2_total:.1f} kg")
        with cf2:
            st.metric("Trees Needed", f"{trees_equiv:.2f} trees/year")

        # ── PREDICTED APPLIANCE-WISE COST ──
        # Use current month hours if available, else fall back to survey avg hours
        # s_hours is already scaled to this month's actual units (saved that way)
        # For display_hours fallback, scale raw survey to next_units for forward-looking charts
        display_hours = s_hours
        using_survey_fallback = False
        if not display_hours and avg_survey:
            display_hours = scale_hours_to_units(avg_survey, next_units)
            using_survey_fallback = True

        if display_hours:
            st.markdown("---")
            st.subheader("💡 Predicted Appliance-wise Cost Next Month")
            if using_survey_fallback:
                st.caption("📋 Based on your onboarding survey average usage (no appliance data entered for this month yet).")
            pred_data = []
            for appliance, wattage in APPLIANCES.items():
                hrs = float(display_hours.get(appliance, 0))
                if hrs == 0:
                    continue
                units_m = round((wattage * hrs * 30) / 1000, 2)
                cost_m  = round(calculate_bill(units_m, supplier)["total"], 0)
                pred_data.append({"Appliance": appliance, "Predicted Cost (Rs)": cost_m, "Units (kWh)": units_m})
            if pred_data:
                pred_df = pd.DataFrame(pred_data).sort_values("Predicted Cost (Rs)", ascending=False)
                fig_pred = px.bar(pred_df, x="Appliance", y="Predicted Cost (Rs)",
                                  title="Predicted Appliance-wise Cost Next Month",
                                  color="Predicted Cost (Rs)",
                                  color_continuous_scale="RdYlGn_r",
                                  text="Predicted Cost (Rs)")
                fig_pred.update_traces(texttemplate="Rs %{text:.0f}", textposition="outside")
                fig_pred.update_layout(height=400, xaxis_tickangle=-20, showlegend=False)
                st.plotly_chart(fig_pred, use_container_width=True)

        st.markdown("")
        if st.button(" View Yearly Dashboard →", use_container_width=True):
            st.session_state.page       = "dashboard"
            st.session_state.dash_year  = s_year
            st.session_state.just_saved = False
            st.rerun()

# ─────────────────────────────────────────────
# PAGE 3 — DASHBOARD
# ─────────────────────────────────────────────
elif st.session_state.page == "dashboard":
    sup_info = SUPPLIERS.get(st.session_state.supplier, SUPPLIERS["MSEDCL"])
    sc = sup_info['color']
    sn = sup_info['full_name']
    st.markdown(f"## 📊 VoltIQ Dashboard &nbsp; <span style='font-size:14px;background:{sc}22;border:1px solid {sc};padding:4px 10px;border-radius:20px;color:{sc};'>{sn}</span>", unsafe_allow_html=True)

    selected_year = int(st.number_input(
        "Select Year", min_value=2000, max_value=2100,
        value=st.session_state.get("dash_year", datetime.now().year), step=1, key="dash_year"
    ))

    rows = load_user_data(st.session_state.username, selected_year)

    if rows:
        df = pd.DataFrame(rows, columns=["Month", "Units", "Bill", "Rate"])
        month_order = {m: i for i, m in enumerate(MONTH_NAMES)}
        df["Month_Order"] = df["Month"].map(month_order)
        df = df.sort_values("Month_Order").reset_index(drop=True)

        total_units = df["Units"].sum()
        total_bill  = df["Bill"].sum()
        avg_rate    = df["Rate"].mean()
        last_units  = df["Units"].iloc[-1]
        last_bill   = df["Bill"].iloc[-1]

        st.markdown(f"#### {selected_year} Overview — {len(df)}/12 months recorded")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Units", f"{total_units:.0f} kWh")
        with col2:
            st.metric("Total Bill", f"Rs {total_bill:.0f}")
        with col3:
            st.metric("Avg Effective Rate", f"Rs {avg_rate:.2f}/kWh")
        with col4:
            trend = "📈 UP" if df["Units"].iloc[-1] > df["Units"].iloc[0] else "📉 DOWN"
            st.metric("Trend", trend)

        st.markdown("---")

        # ── CHART 1 — LINE ──
        st.subheader("1. Daily Consumption Trend")
        daily_rows = []
        for _, row in df.iterrows():
            month_idx = month_order[row["Month"]] + 1
            days_in_month = pd.Period(f"{selected_year}-{month_idx:02d}").days_in_month
            daily_avg = row["Units"] / days_in_month
            rng = np.random.default_rng(month_idx * 7)
            noise = rng.normal(0, daily_avg * 0.1, days_in_month)
            for d in range(1, days_in_month + 1):
                daily_rows.append({"Date": f"{row['Month']} {d:02d}", "Units": round(max(0.1, daily_avg + noise[d-1]), 2), "Month": row["Month"]})
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

        # ── CHART 2 — BAR ──
        st.subheader("2. Monthly Comparison")
        fig_bar = px.bar(df, x="Month", y=["Units", "Bill"], barmode="group",
                         title=f"Monthly Units & Bill Comparison ({selected_year})",
                         labels={"value": "Units (kWh) / Bill (Rs)", "variable": "Metric"},
                         color_discrete_map={"Units": "#4C78A8", "Bill": "#F58518"})
        fig_bar.update_layout(height=400)
        st.plotly_chart(fig_bar, use_container_width=True)

        st.markdown("---")

        # ── CHART 3 — PIE ──
        st.subheader("3. Appliance-wise Yearly Usage Breakdown")
        appliance_rows = load_all_appliance_data(st.session_state.username, selected_year)

        # If no per-month appliance data, fall back to onboarding survey avg hours
        using_survey_fallback = False
        if not appliance_rows:
            survey_avg = st.session_state.get("avg_survey_hours") or has_completed_survey(st.session_state.username)
            if survey_avg:
                num_months_recorded = len(df)
                # Synthesize appliance_rows using survey hours × number of recorded months
                appliance_rows = [(row["Month"], survey_avg) for _, row in df.iterrows()]
                using_survey_fallback = True

        if appliance_rows:
            if using_survey_fallback:
                st.caption(f"📋 No per-month appliance data found for {selected_year}. Using your onboarding survey averages scaled to each month's actual bill.")

            month_bill_lookup  = dict(zip(df["Month"], df["Bill"]))
            month_units_lookup = dict(zip(df["Month"], df["Units"]))
            total_actual_bill  = df["Bill"].sum()
            total_actual_units = df["Units"].sum()
            supplier           = st.session_state.supplier

            # By Units: pure raw kWh from wattage × hours (consumption focus)
            # By Cost:  standalone slab-calculated cost per appliance (billing focus)
            # These two are genuinely different because slabs are non-linear —
            # a high-wattage appliance (AC=1500W) hits expensive slabs faster than LED (10W)
            appliance_yearly_units = {}
            appliance_yearly_cost  = {}

            for month_name, hours_json in appliance_rows:
                actual_bill  = month_bill_lookup.get(month_name, 0)
                actual_units = month_units_lookup.get(month_name, 0)
                if actual_bill == 0 or actual_units == 0:
                    continue

                # Raw kWh per appliance directly from survey hours × wattage
                month_kwh = {}
                for appliance, wattage in APPLIANCES.items():
                    hrs = float(hours_json.get(appliance, 0))
                    if hrs > 0:
                        month_kwh[appliance] = (wattage * hrs * 30) / 1000

                raw_total_kwh = sum(month_kwh.values())
                if raw_total_kwh == 0:
                    continue

                # BY UNITS: scale raw kWh to actual_units so totals match the meter reading
                for appliance, raw_kwh in month_kwh.items():
                    scaled_kwh = (raw_kwh / raw_total_kwh) * actual_units
                    appliance_yearly_units[appliance] = appliance_yearly_units.get(appliance, 0) + scaled_kwh

                # BY COST: run each appliance's RAW kWh through the slab calculator independently
                # AC at 200 kWh hits slab 3 (Rs 8/unit), LED at 3 kWh stays in slab 1 (Rs 2.90/unit)
                # This produces genuinely different proportions than the kWh chart
                month_costs = {a: calculate_bill(kwh, supplier)["total"] for a, kwh in month_kwh.items()}
                raw_cost_total = sum(month_costs.values())
                for appliance, cost in month_costs.items():
                    normalised = (cost / raw_cost_total) * actual_bill
                    appliance_yearly_cost[appliance] = appliance_yearly_cost.get(appliance, 0) + normalised

            if appliance_yearly_units:
                pie_df = pd.DataFrame({
                    "Appliance":        list(appliance_yearly_units.keys()),
                    "Units (kWh)":      [round(v, 2) for v in appliance_yearly_units.values()],
                    "Yearly Cost (Rs)": [round(appliance_yearly_cost[a], 0) for a in appliance_yearly_units]
                }).sort_values("Yearly Cost (Rs)", ascending=False)

                tab_units, tab_cost = st.tabs([" By Units (kWh)", " By Cost (Rs)"])
                with tab_units:
                    fig_pie_u = px.pie(pie_df, names="Appliance", values="Units (kWh)",
                                       title=f"Appliance-wise Yearly Consumption — {selected_year} ({len(appliance_rows)} months)",
                                       hole=0.35)
                    fig_pie_u.update_traces(textposition="inside", textinfo="percent+label")
                    fig_pie_u.update_layout(height=500)
                    st.plotly_chart(fig_pie_u, use_container_width=True)
                    st.caption("📌 Shows raw kWh consumed by each appliance — based on wattage × usage hours.")
                with tab_cost:
                    fig_pie_c = px.pie(pie_df, names="Appliance", values="Yearly Cost (Rs)",
                                       title=f"Appliance-wise Yearly Bill Share — {selected_year}",
                                       hole=0.35, color_discrete_sequence=px.colors.sequential.RdBu)
                    fig_pie_c.update_traces(textposition="inside", textinfo="percent+label")
                    fig_pie_c.update_layout(height=500)
                    st.plotly_chart(fig_pie_c, use_container_width=True)
                    st.caption("📌 Shows bill share per appliance using slab-based pricing — high-wattage appliances cost disproportionately more due to higher slabs.")

                a_col1, a_col2, a_col3 = st.columns(3)
                with a_col1:
                    st.metric("Total Yearly Units", f"{total_actual_units:.0f} kWh")
                with a_col2:
                    st.metric("Total Yearly Bill", f"Rs {total_actual_bill:.0f}")
                with a_col3:
                    top_appliance = pie_df.iloc[0]["Appliance"]
                    st.metric("Top Consumer", top_appliance)
            else:
                st.info("No appliance usage recorded yet.")
        else:
            st.info("No appliance data yet. Complete the onboarding survey and add monthly entries.")

        st.markdown("---")

        # ── CHART 4 — HEATMAP ──
        st.subheader("4. Hourly Usage Pattern Heatmap")
        hourly_weights = np.array([0.3,0.2,0.2,0.2,0.2,0.3,0.5,0.8,1.0,0.7,0.6,0.7,0.8,0.6,0.5,0.5,0.6,0.8,1.0,1.2,1.2,1.0,0.8,0.5])
        hourly_weights = hourly_weights / hourly_weights.sum()
        heatmap_data = []
        for _, row in df.iterrows():
            month_idx = month_order[row["Month"]] + 1
            days_in_month = pd.Period(f"{selected_year}-{month_idx:02d}").days_in_month
            heatmap_data.append((row["Units"] / days_in_month) * hourly_weights * 24)
        fig_heat = px.imshow(np.array(heatmap_data),
                             x=[f"{h:02d}:00" for h in range(24)], y=df["Month"].tolist(),
                             color_continuous_scale="YlOrRd",
                             title=f"Hourly Usage Heatmap ({selected_year})",
                             labels={"x": "Hour of Day", "y": "Month", "color": "kWh"}, aspect="auto")
        fig_heat.update_layout(height=400)
        st.plotly_chart(fig_heat, use_container_width=True)
        st.caption("Heatmap estimated based on typical Indian household hourly usage patterns.")

        st.markdown("---")

        # ── CARBON FOOTPRINT ──
        st.subheader("🌍 Carbon Footprint")
        total_co2   = total_units * 0.82
        monthly_co2 = last_units * 0.82
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total CO2", f"{total_co2:.0f} kg", delta=f"{monthly_co2:.0f} kg this month")
        with col2:
            st.metric("Trees Equivalent", f"{total_co2/22:.1f} trees/year")

    else:
        st.info(f"No data found for {selected_year}. Go to Enter Data page to add your monthly readings!")
        if st.button("Go to Enter Data →"):
            st.session_state.page = "input"
            st.rerun()

st.markdown("---")

















