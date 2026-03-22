import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
from datetime import datetime
import hashlib
import os
import psycopg2
import psycopg2.errors
import json
import re
import io
try:
    import pdfplumber
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

st.set_page_config(page_title="VoltIQ", page_icon="⚡", layout="wide")

# Load fonts via HTML (works on Streamlit Cloud)
st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;1,9..40,400&display=swap" rel="stylesheet">
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────
def get_connection():
    return psycopg2.connect(st.secrets["DATABASE_URL"], sslmode="require")

def init_db():
    conn = get_connection()
    try:
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
        # Add supplier column if upgrading existing DB — only catch duplicate column error
        try:
            cur.execute("ALTER TABLE users ADD COLUMN supplier TEXT NOT NULL DEFAULT 'MSEDCL'")
            conn.commit()
        except psycopg2.errors.DuplicateColumn:
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
    finally:
        conn.close()

init_db()

def section_header(icon, title, subtitle=""):
    sub_html = f'<div style="font-size:12px;color:#6b7280;margin-top:3px;font-weight:400;letter-spacing:.3px;">{subtitle}</div>' if subtitle else ""
    st.markdown(f'''
    <div style="display:flex;align-items:center;gap:14px;margin:28px 0 20px;padding-bottom:16px;
      border-bottom:1px solid rgba(255,255,255,.06);">
      <div style="width:42px;height:42px;border-radius:12px;display:flex;align-items:center;justify-content:center;
        background:linear-gradient(135deg,rgba(56,189,248,.15),rgba(245,158,11,.08));
        border:1px solid rgba(56,189,248,.2);font-size:20px;">{icon}</div>
      <div>
        <div style="font-family:'Syne','Segoe UI',system-ui,sans-serif;font-size:19px;font-weight:700;color:#f9fafb;letter-spacing:-.2px;">{title}</div>
        {sub_html}
      </div>
    </div>
    ''', unsafe_allow_html=True)

def stat_card(label, value, icon="", color="#38bdf8"):
    st.markdown(f'''
    <div style="background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.07);
      border-radius:16px;padding:18px 22px;
      box-shadow:0 4px 20px rgba(0,0,0,.25), inset 0 1px 0 rgba(255,255,255,.05);
      transition:all .3s;">
      <div style="font-size:10px;color:#6b7280;font-weight:600;text-transform:uppercase;
        letter-spacing:1.2px;font-family:'DM Sans','Segoe UI',system-ui,sans-serif;">{icon} {label}</div>
      <div style="font-family:'Syne','Segoe UI',system-ui,sans-serif;font-size:28px;font-weight:800;color:{color};
        margin-top:6px;letter-spacing:-.5px;">{value}</div>
    </div>
    ''', unsafe_allow_html=True)

def alert_card(bg_color, border_color, content):
    st.markdown(f'''
    <div style="background:{bg_color};border-left:4px solid {border_color};
      border-radius:12px;padding:14px 18px;margin:8px 0;
      box-shadow:0 2px 12px rgba(0,0,0,.2);color:#f9fafb;font-size:14px;
      font-family:'DM Sans','Segoe UI',system-ui,sans-serif;line-height:1.5;">{content}</div>
    ''', unsafe_allow_html=True)

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
    # Electricity duty applies to energy + FAC + fixed (not just energy)
    electricity_duty = (energy_charge + fac + fixed_charge) * s["duty_pct"]
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
def hash_password(password, salt=None):
    """Hash password using scrypt with a random salt. Returns 'salt$hash' string."""
    if salt is None:
        salt = os.urandom(16).hex()
    hashed = hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex()
    return f"{salt}${hashed}"

def verify_password(password, stored):
    """Verify password against stored 'salt$hash' string. Falls back to legacy sha256."""
    if "$" in stored:
        salt, _ = stored.split("$", 1)
        return hash_password(password, salt) == stored
    # Legacy sha256 fallback for existing accounts
    return hashlib.sha256(password.encode()).hexdigest() == stored

def register_user(username, password, security_question, security_answer):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (username, password, security_question, security_answer) VALUES (%s, %s, %s, %s)",
            (username, hash_password(password), security_question, hash_password(security_answer.lower().strip()))
        )
        conn.commit()
        cur.close()
        return True
    except psycopg2.IntegrityError:
        conn.rollback()
        return False
    finally:
        conn.close()

def verify_user(username, password):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT password FROM users WHERE username = %s", (username,))
        row = cur.fetchone()
        cur.close()
        return row is not None and verify_password(password, row[0])
    finally:
        conn.close()

def get_security_question(username):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT security_question FROM users WHERE username = %s", (username,))
        row = cur.fetchone()
        cur.close()
        return row[0] if row else None
    finally:
        conn.close()

def verify_security_answer(username, answer):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT security_question, security_answer FROM users WHERE username = %s", (username,))
        row = cur.fetchone()
        cur.close()
        if row is None:
            return False, None
        return verify_password(answer.lower().strip(), row[1]), row[0]
    finally:
        conn.close()

def reset_password(username, new_password):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE users SET password = %s WHERE username = %s",
                    (hash_password(new_password), username))
        conn.commit()
        cur.close()
    finally:
        conn.close()

def save_supplier(username, supplier):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE users SET supplier = %s WHERE username = %s", (supplier, username))
        conn.commit()
        cur.close()
    finally:
        conn.close()

def load_supplier(username):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT supplier FROM users WHERE username = %s", (username,))
        row = cur.fetchone()
        cur.close()
        return row[0] if row else "MSEDCL"
    finally:
        conn.close()

# ─────────────────────────────────────────────
# DATA HELPERS
# ─────────────────────────────────────────────
def save_entry(username, year, month, units, bill, rate):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO electricity_data (username, year, month, units, bill, rate)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT(username, year, month) DO UPDATE SET
                units = EXCLUDED.units, bill = EXCLUDED.bill, rate = EXCLUDED.rate
        """, (username, year, month, units, bill, rate))
        conn.commit()
        cur.close()
    finally:
        conn.close()

def delete_month_entry(username, year, month):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM electricity_data WHERE username = %s AND year = %s AND month = %s", (username, year, month))
        cur.execute("DELETE FROM appliance_data WHERE username = %s AND year = %s AND month = %s", (username, year, month))
        conn.commit()
        cur.close()
    finally:
        conn.close()

def save_appliance_data(username, year, month, appliance_hours):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO appliance_data (username, year, month, appliance_hours)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT(username, year, month) DO UPDATE SET
                appliance_hours = EXCLUDED.appliance_hours
        """, (username, year, month, json.dumps(appliance_hours)))
        conn.commit()
        cur.close()
    finally:
        conn.close()

def load_user_data(username, year):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT month, units, bill, rate FROM electricity_data WHERE username = %s AND year = %s", (username, year))
        rows = cur.fetchall()
        cur.close()
        return rows
    finally:
        conn.close()

def load_years_with_data(username):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT year FROM electricity_data WHERE username = %s ORDER BY year DESC", (username,))
        rows = cur.fetchall()
        cur.close()
        return [r[0] for r in rows]
    finally:
        conn.close()

def load_appliance_data(username, year, month):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT appliance_hours FROM appliance_data WHERE username = %s AND year = %s AND month = %s",
                    (username, year, month))
        row = cur.fetchone()
        cur.close()
        return row[0] if row else {}
    finally:
        conn.close()

def load_all_appliance_data(username, year):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT month, appliance_hours FROM appliance_data WHERE username = %s AND year = %s",
                    (username, year))
        rows = cur.fetchall()
        cur.close()
        return rows
    finally:
        conn.close()

def delete_user_data(username, year):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM electricity_data WHERE username = %s AND year = %s", (username, year))
        cur.execute("DELETE FROM appliance_data WHERE username = %s AND year = %s", (username, year))
        conn.commit()
        cur.close()
    finally:
        conn.close()

def has_completed_survey(username):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT avg_appliance_hours FROM user_survey WHERE username = %s", (username,))
        row = cur.fetchone()
        cur.close()
        return row[0] if row else None
    finally:
        conn.close()

def save_user_survey(username, avg_hours):
    conn = get_connection()
    try:
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
    finally:
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
    ("confirm_logout", False),
    ("delete_confirm_month", ""),
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

# Module-level constant — used everywhere instead of inline dicts
MONTH_ORDER = {m: i for i, m in enumerate(MONTH_NAMES)}

# CO2 emission factor — CEA 2023 grid average for India (kg CO2/kWh)
CO2_FACTOR = 0.716

def get_user_survey_hours(username):
    """Return the user's survey hours from session state or DB. Deduplicates repeated pattern."""
    return st.session_state.get("avg_survey_hours") or has_completed_survey(username) or {}

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
# SEASONAL MULTIPLIERS (Maharashtra climate)
# ─────────────────────────────────────────────
# Each value = how much to scale the survey baseline for that month.
# 1.0 = survey average. >1 = more usage. <1 = less usage.
# Based on Maharashtra seasons:
#   Hot summer  : Mar–Jun  (AC/Fan peak, Geyser off)
#   Monsoon     : Jul–Sep  (moderate AC, Fan on, no Geyser)
#   Winter      : Nov–Feb  (Geyser peak, AC off, Fan low)
#   Transition  : Oct      (mild)
SEASONAL_MULTIPLIERS = {
    #                      Jan   Feb   Mar   Apr   May   Jun   Jul   Aug   Sep   Oct   Nov   Dec
    "AC (1.5 ton)":       [0.1,  0.2,  0.7,  1.4,  2.0,  1.8,  1.2,  0.9,  0.7,  0.3,  0.1,  0.1],
    "Fan (Ceiling)":      [0.4,  0.5,  0.8,  1.3,  1.8,  1.6,  1.4,  1.3,  1.1,  0.8,  0.5,  0.4],
    "Water Heater (Geyser)":[1.8,1.6,  0.8,  0.3,  0.1,  0.1,  0.2,  0.2,  0.3,  0.7,  1.4,  1.8],
    "Refrigerator":       [0.9,  0.9,  1.0,  1.1,  1.2,  1.2,  1.1,  1.0,  1.0,  1.0,  0.9,  0.9],
    "Washing Machine":    [1.0,  1.0,  1.0,  1.0,  1.0,  1.1,  1.2,  1.2,  1.0,  1.0,  1.0,  1.0],
    "TV (LED 43 inch)":   [1.1,  1.0,  1.0,  1.0,  1.0,  1.0,  1.1,  1.1,  1.0,  1.0,  1.1,  1.2],
    "LED Bulb (10W)":     [1.1,  1.0,  0.9,  0.9,  0.9,  0.9,  1.0,  1.0,  1.0,  1.0,  1.1,  1.2],
    "Microwave":          [1.0,  1.0,  1.0,  1.0,  1.0,  1.0,  1.0,  1.0,  1.0,  1.0,  1.0,  1.0],
    "Iron":               [1.0,  1.0,  1.0,  1.0,  1.0,  1.0,  1.0,  1.0,  1.0,  1.0,  1.0,  1.0],
    "Computer/Laptop":    [1.0,  1.0,  1.0,  1.0,  1.0,  1.0,  1.0,  1.0,  1.0,  1.0,  1.0,  1.0],
}

def apply_seasonal_multipliers(base_hours: dict, month_name: str) -> dict:
    """
    Adjust survey baseline hours using seasonal weights for the given month.

    Key design principle — bill-anchored, not assumption-anchored:
    - Seasonal weights shift the *relative proportion* between appliances.
    - A minimum floor (10% of base) is kept for every appliance so that if
      the bill is unusually high (e.g. someone ran AC in January), that usage
      can surface rather than being zeroed out by the season assumption.
    - scale_hours_to_units() is always called after this, which forces the
      total kWh to match the actual meter reading. So if January shows a high
      bill, all appliances scale up proportionally — the seasonal weights only
      determine the split, not the total.
    """
    month_idx = MONTH_ORDER.get(month_name, 0)
    scaled = {}
    for appliance, hrs in base_hours.items():
        base = float(hrs)
        if base == 0:
            scaled[appliance] = 0.0
            continue
        multipliers = SEASONAL_MULTIPLIERS.get(appliance)
        if multipliers:
            seasonal_factor = multipliers[month_idx]
            # Keep a 10% floor — prevents fully zeroing out appliances when
            # the bill suggests they may have been used (e.g. AC in January)
            floor_factor    = 0.1
            effective_factor = max(seasonal_factor, floor_factor)
            scaled[appliance] = round(base * effective_factor, 4)
        else:
            scaled[appliance] = base
    return scaled

# ─────────────────────────────────────────────
# GLOBAL UI STYLES
# ─────────────────────────────────────────────
st.markdown("""
<style>
/* Fonts loaded via HTML link tag below */

/* ══ HIDE CHROME ══ */
[data-testid="stSidebar"],[data-testid="collapsedControl"],
#MainMenu,footer,header{display:none!important;visibility:hidden!important}

/* ══ BASE ══ */
html,body,[data-testid='stAppViewContainer'],[data-testid='stApp']{font-family:'DM Sans','Segoe UI',system-ui,sans-serif!important;background:#020c18!important}
.stApp{background:#020c18!important}
.main .block-container,
[data-testid="stAppViewBlockContainer"]{
  padding:1.8rem 3rem 4rem!important;
  max-width:1180px!important;
}

/* ══ ANIMATED BACKGROUND ORBS ══ */
.stApp::before{
  content:'';
  position:fixed;top:0;left:0;width:100%;height:100%;
  background:
    radial-gradient(ellipse 60% 50% at 20% 20%, rgba(56,189,248,.08) 0%, transparent 60%),
    radial-gradient(ellipse 50% 60% at 80% 80%, rgba(6,182,212,.07) 0%, transparent 60%),
    radial-gradient(ellipse 40% 40% at 50% 50%, rgba(16,185,129,.04) 0%, transparent 50%);
  pointer-events:none;z-index:0;
  animation:orbpulse 8s ease-in-out infinite alternate;
}
@keyframes orbpulse{
  0%{opacity:.7;transform:scale(1)}
  100%{opacity:1;transform:scale(1.05)}
}

/* ══ METRICS ══ */
[data-testid="metric-container"]{
  background:rgba(255,255,255,.03)!important;
  border:1px solid rgba(255,255,255,.08)!important;
  border-radius:18px!important;
  padding:20px 24px!important;
  backdrop-filter:blur(20px)!important;
  transition:all .3s ease!important;
  box-shadow:0 4px 24px rgba(0,0,0,.3), inset 0 1px 0 rgba(255,255,255,.06)!important;
}
[data-testid="metric-container"]:hover{
  border-color:rgba(56,189,248,.3)!important;
  box-shadow:0 8px 32px rgba(251,191,36,.1), inset 0 1px 0 rgba(255,255,255,.08)!important;
  transform:translateY(-2px)!important;
}
[data-testid="metric-container"] label{
  color:#6b7280!important;font-size:11px!important;font-weight:600!important;
  text-transform:uppercase!important;letter-spacing:1.2px!important;
  font-family:'Syne','Segoe UI',system-ui,sans-serif!important;
}
[data-testid="metric-container"] [data-testid="stMetricValue"]{
  color:#f9fafb!important;font-size:26px!important;font-weight:800!important;
  font-family:'Syne','Segoe UI',system-ui,sans-serif!important;letter-spacing:-.5px!important;
}
[data-testid="stMetricDelta"]{font-size:12px!important;font-weight:500!important}

/* ══ BUTTONS ══ */
.stButton>button{
  border-radius:12px!important;font-weight:600!important;font-size:14px!important;
  transition:all .25s cubic-bezier(.4,0,.2,1)!important;
  letter-spacing:.3px!important;padding:11px 22px!important;
  font-family:'DM Sans','Segoe UI',system-ui,sans-serif!important;
}
.stButton>button[kind="primary"]{
  background:linear-gradient(135deg,#38bdf8 0%,#0ea5e9 50%,#0369a1 100%)!important;
  color:#020c18!important;border:none!important;
  box-shadow:0 4px 16px rgba(56,189,248,.35)!important;
}
.stButton>button[kind="primary"]:hover{
  transform:translateY(-2px) scale(1.01)!important;
  box-shadow:0 8px 28px rgba(56,189,248,.5)!important;
}
.stButton>button[kind="primary"]:active{transform:translateY(0) scale(.99)!important}
.stButton>button[kind="secondary"]{
  background:rgba(255,255,255,.04)!important;
  color:#9ca3af!important;
  border:1px solid rgba(255,255,255,.1)!important;
}
.stButton>button[kind="secondary"]:hover{
  background:rgba(255,255,255,.08)!important;
  color:#f9fafb!important;border-color:rgba(56,189,248,.3)!important;
}

/* ══ INPUTS ══ */
.stTextInput>div>div>input,
.stNumberInput>div>div>input,
.stSelectbox>div>div>div{
  background:rgba(255,255,255,.04)!important;
  border:1px solid rgba(255,255,255,.1)!important;
  border-radius:12px!important;color:#f9fafb!important;
  font-size:14px!important;font-family:'DM Sans','Segoe UI',system-ui,sans-serif!important;
  transition:all .2s!important;
}
.stTextInput>div>div>input:focus,
.stNumberInput>div>div>input:focus{
  border-color:rgba(56,189,248,.6)!important;
  box-shadow:0 0 0 3px rgba(56,189,248,.12)!important;
  background:rgba(255,255,255,.06)!important;
}

/* ══ TABS ══ */
.stTabs [data-baseweb="tab-list"]{
  background:rgba(255,255,255,.03)!important;
  border:1px solid rgba(255,255,255,.07)!important;
  border-radius:14px!important;padding:5px!important;gap:4px!important;
}
.stTabs [data-baseweb="tab"]{
  border-radius:10px!important;color:#6b7280!important;
  font-weight:600!important;padding:9px 24px!important;
  font-family:'DM Sans','Segoe UI',system-ui,sans-serif!important;
  transition:all .2s!important;
}
.stTabs [aria-selected="true"]{
  background:linear-gradient(135deg,#38bdf8,#0ea5e9)!important;
  color:#020c18!important;
  box-shadow:0 4px 12px rgba(56,189,248,.3)!important;
}

/* ══ DIVIDER ══ */
hr{
  border:none!important;
  height:1px!important;
  background:linear-gradient(90deg,transparent,rgba(255,255,255,.08),transparent)!important;
  margin:28px 0!important;
}

/* ══ TYPOGRAPHY ══ */
h1,h2,h3,h4,h5{
  color:#f9fafb!important;
  font-family:'Syne','Segoe UI',system-ui,sans-serif!important;
  letter-spacing:-.3px!important;
}
[data-testid="stMarkdownContainer"] p{color:#9ca3af!important;line-height:1.6!important}

/* ══ EXPANDER ══ */
.streamlit-expanderHeader{
  background:rgba(255,255,255,.03)!important;
  border:1px solid rgba(255,255,255,.08)!important;
  border-radius:10px!important;color:#9ca3af!important;
}

/* ══ ALERTS / INFO ══ */
[data-testid="stAlert"]{border-radius:12px!important;}

/* ══ PLOTLY CHARTS ══ */
.js-plotly-plot .plotly,.js-plotly-plot{background:transparent!important}

/* ══ FILE UPLOADER ══ */
[data-testid="stFileUploader"]{
  background:rgba(255,255,255,.03)!important;
  border:2px dashed rgba(255,255,255,.1)!important;
  border-radius:14px!important;padding:8px!important;
}

/* ══ CAPTION ══ */
.stCaption,[data-testid="stCaptionContainer"]{color:#4b5563!important;font-size:12px!important}

/* ══ SPINNER ══ */
.stSpinner>div{border-top-color:#38bdf8!important}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# PAGE 1 — AUTH
# ─────────────────────────────────────────────
if not st.session_state.logged_in:
    st.markdown("""
    <div style="min-height:180px;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:48px 0 32px;position:relative;">
        <div style="position:absolute;width:300px;height:300px;border-radius:50%;
             background:radial-gradient(circle,rgba(56,189,248,.12),transparent 70%);
             top:50%;left:50%;transform:translate(-50%,-50%);pointer-events:none;"></div>
        <div style="font-size:56px;margin-bottom:10px;filter:drop-shadow(0 0 20px rgba(56,189,248,.5));">⚡</div>
        <div style="font-family:'Syne','Segoe UI',system-ui,sans-serif;font-size:42px;font-weight:800;
             background:linear-gradient(135deg,#38bdf8,#0ea5e9,#38bdf8);
             -webkit-background-clip:text;-webkit-text-fill-color:transparent;
             background-clip:text;letter-spacing:3px;line-height:1;">VOLTIQ</div>
        <div style="font-size:11px;color:#4b5563;margin-top:10px;letter-spacing:3px;font-family:'DM Sans','Segoe UI',system-ui,sans-serif;font-weight:500;">
            SMART ELECTRICITY ANALYZER · MAHARASHTRA
        </div>
    </div>
    """, unsafe_allow_html=True)
    _, col_form, _ = st.columns([1, 1.2, 1])
    with col_form:
        st.markdown('''<div style="
            background:rgba(255,255,255,.03);
            border:1px solid rgba(255,255,255,.08);
            border-radius:24px;padding:36px 40px;
            backdrop-filter:blur(40px);
            box-shadow:0 24px 64px rgba(0,0,0,.5), inset 0 1px 0 rgba(255,255,255,.08);">
        ''', unsafe_allow_html=True)

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
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# ─────────────────────────────────────────────
# TOP NAV BAR
# ─────────────────────────────────────────────
sup_color = SUPPLIERS.get(st.session_state.supplier, SUPPLIERS["MSEDCL"])["color"]
sup_name  = SUPPLIERS.get(st.session_state.supplier, SUPPLIERS["MSEDCL"])["full_name"]
st.markdown(f'''
<div style="display:flex;align-items:center;justify-content:space-between;
  background:rgba(255,255,255,.03);
  border:1px solid rgba(255,255,255,.07);
  padding:14px 28px;border-radius:20px;margin-bottom:20px;
  backdrop-filter:blur(20px);
  box-shadow:0 4px 32px rgba(0,0,0,.4), inset 0 1px 0 rgba(255,255,255,.06);">
  <div style="display:flex;align-items:center;gap:14px;">
    <span style="font-size:26px;filter:drop-shadow(0 0 10px rgba(56,189,248,.6));">⚡</span>
    <div>
      <div style="font-family:'Syne','Segoe UI',system-ui,sans-serif;font-size:20px;font-weight:800;
        background:linear-gradient(135deg,#38bdf8,#0ea5e9);
        -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
        letter-spacing:1.5px;line-height:1.1;">VOLTIQ</div>
      <div style="font-size:10px;color:#4b5563;letter-spacing:1px;margin-top:1px;">
        Smart Electricity Analyzer
      </div>
    </div>
  </div>
  <div style="display:flex;align-items:center;gap:10px;">
    <div style="font-size:11px;background:{sup_color}18;border:1px solid {sup_color}44;
      padding:5px 14px;border-radius:20px;color:{sup_color};font-weight:600;letter-spacing:.3px;">
      ⚡ {sup_name}
    </div>
    <div style="font-size:11px;background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);
      padding:5px 14px;border-radius:20px;color:#6b7280;font-weight:500;">
      👤 {st.session_state.username}
    </div>
  </div>
</div>
''', unsafe_allow_html=True)

nav_col1, nav_col2, nav_col3 = st.columns([1, 1, 1])
with nav_col1:
    if st.button("📥 Enter Data", use_container_width=True,
                 type="primary" if st.session_state.page == "input" else "secondary"):
        st.session_state.page = "input"
        st.session_state.just_saved = False
        st.rerun()
with nav_col2:
    if st.button("📊 Dashboard", use_container_width=True,
                 type="primary" if st.session_state.page == "dashboard" else "secondary"):
        st.session_state.page = "dashboard"
        st.session_state.just_saved = False
        st.rerun()
with nav_col3:
    if st.session_state.confirm_logout:
        c1, c2 = st.columns(2)
        with c1:
            if st.button("✅ Yes, logout", use_container_width=True, type="primary"):
                st.session_state.logged_in = False
                st.session_state.username = ""
                st.session_state.page = "input"
                st.session_state.confirm_logout = False
                st.rerun()
        with c2:
            if st.button("Cancel", use_container_width=True):
                st.session_state.confirm_logout = False
                st.rerun()
    else:
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.confirm_logout = True
            st.rerun()


# ─────────────────────────────────────────────
# ROLLING ALERT BANNER — shown when usage is high
# ─────────────────────────────────────────────
_alert_units = st.session_state.get("saved_units", 0)
_alert_bill  = st.session_state.get("saved_bill", 0)
_alert_month = st.session_state.get("saved_month", "")
_supplier_key = st.session_state.get("supplier", "MSEDCL")

if _alert_units > 300:
    if _alert_units > 500:
        _banner_msg = (
            f"🔴 ALERT: Very High Usage — {_alert_units:.0f} kWh in {_alert_month}! "
            f"You are in the highest billing slab. Bill: Rs {_alert_bill:.0f}. "
            f"Reduce usage by {_alert_units - 500:.0f} kWh to save Rs {_alert_bill - calculate_bill(500, _supplier_key)['total']:.0f} next month!  "
            f"⚡ Check your AC, Water Heater and Washing Machine usage immediately!  "
        )
        _banner_color = "#ef4444"
        _banner_bg    = "rgba(239,68,68,0.18)"
    else:
        _banner_msg = (
            f"🟠 HIGH USAGE ALERT: {_alert_units:.0f} kWh in {_alert_month}. "
            f"Bill: Rs {_alert_bill:.0f}. "
            f"Reduce by {_alert_units - 300:.0f} kWh to save Rs {_alert_bill - calculate_bill(300, _supplier_key)['total']:.0f}!  "
            f"⚡ You're in the high billing slab — every kWh saved now counts double!  "
        )
        _banner_color = "#f97316"
        _banner_bg    = "rgba(249,115,22,0.15)"

    # Repeat message to make the scroll feel continuous
    _scroll_text = (_banner_msg + "   ·   ") * 4

    st.markdown(f"""
    <style>
    @keyframes scrollBanner {{
        0%   {{ transform: translateX(100%); }}
        100% {{ transform: translateX(-100%); }}
    }}
    .voltiq-rolling-banner {{
        overflow: hidden;
        white-space: nowrap;
        background: {_banner_bg};
        border: 1.5px solid {_banner_color};
        border-radius: 14px;
        padding: 13px 0;
        margin-bottom: 18px;
        box-shadow: 0 0 18px {_banner_color}44;
    }}
    .voltiq-rolling-banner span {{
        display: inline-block;
        animation: scrollBanner 22s linear infinite;
        font-size: 14px;
        font-weight: 700;
        color: {_banner_color};
        letter-spacing: 0.4px;
        font-family: 'DM Sans', 'Segoe UI', system-ui, sans-serif;
        padding-left: 100%;
    }}
    </style>
    <div class="voltiq-rolling-banner">
        <span>{_scroll_text}</span>
    </div>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────────
# ONBOARDING SURVEY — shown only once per user
# ─────────────────────────────────────────────
if st.session_state.get("show_onboarding_survey", False):
    st.markdown('''<div style="text-align:center;padding:20px 0 8px;"><div style="font-size:44px;margin-bottom:8px;filter:drop-shadow(0 0 16px rgba(56,189,248,.5));">👋</div><div style="font-family:'Syne','Segoe UI',system-ui,sans-serif;font-size:28px;font-weight:800;background:linear-gradient(135deg,#38bdf8,#0ea5e9);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;">Welcome to VoltIQ!</div><div style="font-size:13px;color:#6b7280;margin-top:6px;">Let's set up your home appliance profile</div></div>''', unsafe_allow_html=True)
    st.markdown("""
    <div style="background:rgba(251,191,36,.08);border:1px solid rgba(56,189,248,.2);
      border-radius:14px;padding:16px 22px;margin-bottom:20px;display:flex;gap:14px;align-items:flex-start;">
      <div style="font-size:20px;flex-shrink:0;">🎯</div>
      <div style="font-size:14px;color:#d1d5db;line-height:1.6;">
        <b style="color:#38bdf8;">One-time setup · </b>
        Tell us your average daily appliance usage. VoltIQ uses this to give you accurate predictions and insights from your very first entry!
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("#### 🏠 Average Appliance Usage Survey")
    st.caption("For each appliance, tell us: how many you have at home, and how many hours per day you typically use them. Enter 0 if you don't have that appliance.")

    onboard_hours = {}
    onboard_counts = {}

    for i, (appliance, wattage) in enumerate(APPLIANCES.items()):
        st.markdown(f"""
        <div style="background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);
          border-radius:14px;padding:16px 20px;margin:10px 0;">
          <div style="font-family:'Syne','Segoe UI',system-ui,sans-serif;font-size:15px;font-weight:700;color:#f1f5f9;margin-bottom:10px;">
            {appliance} <span style="font-size:12px;color:#6b7280;font-weight:400;">({wattage}W)</span>
          </div>
        </div>
        """, unsafe_allow_html=True)
        col_count, col_hrs = st.columns(2)
        with col_count:
            onboard_counts[appliance] = st.number_input(
                f"How many {appliance}s do you have?",
                min_value=0, max_value=20,
                value=0, step=1,
                key=f"onboard_count_{i}",
                help=f"Number of {appliance} units at home"
            )
        with col_hrs:
            onboard_hours[appliance] = st.number_input(
                f"Hours per day used",
                min_value=0.0, max_value=24.0,
                value=0.0, step=0.5,
                key=f"onboard_hrs_{i}",
                help="Average hours per day each unit runs"
            )

    # Calculate effective hours = hours × count for each appliance
    effective_hours = {
        a: onboard_hours[a] * max(onboard_counts[a], 1 if onboard_hours[a] > 0 else 0)
        for a in APPLIANCES
    }

    total_survey_units = sum(
        (APPLIANCES[a] * effective_hours[a] * 30) / 1000
        for a in APPLIANCES if effective_hours[a] > 0
    )
    if total_survey_units > 0:
        est_survey_bill = calculate_bill(total_survey_units, st.session_state.supplier)['total']
        st.info(f"📊 Based on your inputs — Estimated monthly usage: **{total_survey_units:.1f} kWh** | Estimated bill: **Rs {est_survey_bill:.0f}**")

    col_save, col_skip = st.columns([3, 1])
    with col_save:
        if st.button("✅ Save & Continue", use_container_width=True, key="save_onboard_survey"):
            save_user_survey(st.session_state.username, effective_hours)
            st.session_state.avg_survey_hours = effective_hours
            st.session_state.show_onboarding_survey = False
            st.success("Survey saved! You're all set.")
            st.rerun()
    with col_skip:
        if st.button("Skip for now", use_container_width=True, key="skip_onboard_survey"):
            st.session_state.show_onboarding_survey = False
            st.rerun()
    st.stop()

# ─────────────────────────────────────────────
# PAGE 2 — INPUT DATA
# ─────────────────────────────────────────────
if st.session_state.page == "input":
    section_header("📥", "Enter Monthly Data", "Record your monthly electricity bill")

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

        # Per-month appliance hours override
        with st.expander("🏠 Set appliance hours for this month (optional)", expanded=False):
            st.caption("Override your survey defaults for this specific month. Leave at 0 to use your survey averages.")
            survey_defaults = get_user_survey_hours(st.session_state.username)
            manual_app_hours = {}
            app_cols = st.columns(2)
            for i, (appliance, wattage) in enumerate(APPLIANCES.items()):
                with app_cols[i % 2]:
                    default_val = float(survey_defaults.get(appliance, 0.0)) if survey_defaults else 0.0
                    manual_app_hours[appliance] = st.number_input(
                        f"{appliance} ({wattage}W)",
                        min_value=0.0, max_value=24.0,
                        value=default_val, step=0.5,
                        key=f"manual_app_{i}",
                        help="Hours per day this month"
                    )

        st.markdown("")
        if st.button("Save & Analyze", use_container_width=True, key="manual_save"):
            if units_consumed == 0:
                st.error("Please enter units consumed.")
            else:
                bill_data      = calculate_bill(units_consumed, st.session_state.supplier)
                effective_rate = round(bill_data['total'] / units_consumed, 2)
                save_entry(st.session_state.username, selected_year, month, units_consumed, bill_data['total'], effective_rate)
                # Use per-month override if filled, else scale survey hours with seasonal adjustment
                has_manual_app = any(v > 0 for v in manual_app_hours.values())
                if has_manual_app:
                    app_hours_to_save = manual_app_hours
                else:
                    avg_survey = get_user_survey_hours(st.session_state.username)
                    seasonal   = apply_seasonal_multipliers(avg_survey, month)
                    app_hours_to_save = scale_hours_to_units(seasonal, units_consumed)
                save_appliance_data(st.session_state.username, selected_year, month, app_hours_to_save)
                st.session_state.just_saved       = True
                st.session_state.saved_month      = month
                st.session_state.saved_units      = units_consumed
                st.session_state.saved_bill       = bill_data['total']
                st.session_state.saved_year       = selected_year
                st.session_state.saved_hours      = app_hours_to_save
                st.rerun()

    # ── UPLOAD BILL ──
    with upload_tab:
        st.markdown("#### Upload your electricity bill (PDF or Image)")
        st.info("📌 PDF works best for digital bills. For Marathi or scanned bills, please use **Manual Input** tab instead.")
        uploaded_file = st.file_uploader("Choose file", type=["pdf", "jpg", "jpeg", "png"], key="bill_upload")

        if uploaded_file is not None:
            mime_type = uploaded_file.type
            is_image  = mime_type in ("image/jpeg", "image/png")
            if is_image:
                st.warning("⚠️ Image files cannot be auto-extracted. Please switch to **Manual Input** tab or upload the PDF version of your bill.")
            elif not PDF_AVAILABLE:
                st.error("pdfplumber is not installed. Add `pdfplumber` to your requirements.txt and redeploy.")
            else:
                if st.button(" Extract Data ", use_container_width=True):
                    with st.spinner("Reading your bill..."):
                        try:
                            file_bytes = uploaded_file.read()
                            text = ""
                            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                                for page in pdf.pages:
                                    text += page.extract_text() or ""
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
                            month_map = {
                                "january":"Jan","february":"Feb","march":"Mar","april":"Apr",
                                "may":"May","june":"Jun","july":"Jul","august":"Aug",
                                "september":"Sep","october":"Oct","november":"Nov","december":"Dec",
                                "jan":"Jan","feb":"Feb","mar":"Mar","apr":"Apr","jun":"Jun",
                                "jul":"Jul","aug":"Aug","sep":"Sep","oct":"Oct","nov":"Nov","dec":"Dec"
                            }
                            month_pat = r"(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
                            m = re.search(month_pat, text, re.IGNORECASE)
                            if m:
                                extracted["month"] = month_map.get(m.group(1).lower(), m.group(1)[:3].capitalize())
                            year_pat = r"(202[0-9]|203[0-9])"
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
                    avg_survey   = get_user_survey_hours(st.session_state.username)
                    seasonal     = apply_seasonal_multipliers(avg_survey, confirmed_month)
                    scaled_hours = scale_hours_to_units(seasonal, confirmed_units)
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
        st.markdown(f'''<div style="background:linear-gradient(135deg,rgba(16,185,129,.15),rgba(5,150,105,.08));border:1px solid rgba(16,185,129,.3);border-radius:16px;padding:20px 24px;margin:16px 0;display:flex;align-items:center;gap:14px;"><div style="font-size:28px;">✅</div><div><div style="font-family:'Syne','Segoe UI',system-ui,sans-serif;font-size:18px;font-weight:700;color:#34d399;">{s_month} {s_year} — Saved Successfully!</div><div style="font-size:12px;color:#6b7280;margin-top:2px;">Your electricity data has been recorded</div></div></div>''', unsafe_allow_html=True)

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
            slab_msg, slab_color = f"🟠 Slab 3 — Rs {SUPPLIERS[supplier]['slabs'][2][1]}/unit", "#0284c7"
        else:
            slab_msg, slab_color = f"🔴 Highest slab — Rs {SUPPLIERS[supplier]['slabs'][3][1]}/unit", "#e74c3c"

        st.markdown(f'''<div style="background:{slab_color}18;border:1px solid {slab_color}44;
          border-radius:14px;padding:14px 20px;margin:12px 0;display:flex;align-items:center;gap:12px;">
          <div style="width:8px;height:8px;border-radius:50%;background:{slab_color};
            box-shadow:0 0 10px {slab_color};flex-shrink:0;"></div>
          <div style="font-size:14px;color:#f9fafb;"><b style="color:{slab_color};">Current Slab · </b>{slab_msg}</div>
        </div>''', unsafe_allow_html=True)

        # Load previous months for prediction
        all_rows = load_user_data(st.session_state.username, s_year)
        all_df = pd.DataFrame(all_rows, columns=['Month','Units','Bill','Rate']) if all_rows else pd.DataFrame()
        if not all_df.empty:
            all_df['_order'] = all_df['Month'].map(MONTH_ORDER)
            all_df = all_df.sort_values('_order').drop(columns='_order').reset_index(drop=True)

        # Next month prediction
        st.markdown("---")
        section_header("🔮", "Next Month Prediction", "AI-powered forecast based on your usage history")

        avg_survey = get_user_survey_hours(st.session_state.username)

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
            section_header("🏠", f"Smart Appliance Alerts — {s_month} {s_year}", "Seasonal recommendations — limits adjust based on the month")
            st.caption("Recommended limits reflect what's genuinely reasonable for this time of year in Maharashtra, not a one-size-fits-all number.")

            month_idx  = MONTH_ORDER.get(s_month, 0)
            is_summer  = month_idx in [2, 3, 4, 5]   # Mar–Jun
            is_monsoon = month_idx in [6, 7, 8]        # Jul–Sep
            is_winter  = month_idx in [10, 11, 0, 1]   # Nov–Feb

            # Realistic daily hour limits per appliance per month (Maharashtra household)
            # AC: peak summer cap = 8 hrs (nights + evening). Winter = 0. Monsoon = 3–4.
            # Geyser: winter = 1 hr max (30 min morning + 30 min evening). Summer = 0.
            # Fan: running all day in summer is fine but 18+ hrs is excessive even in May.
            SEASONAL_THRESHOLDS = {
                #                          Jan  Feb  Mar  Apr  May  Jun  Jul  Aug  Sep  Oct  Nov  Dec
                "AC (1.5 ton)":           [0,   0,   2,   5,   8,   7,   4,   3,   2,   1,   0,   0  ],
                "Fan (Ceiling)":          [4,   5,   8,   12,  16,  16,  14,  14,  12,  8,   5,   4  ],
                "Water Heater (Geyser)":  [1,   1,   0.5, 0.3, 0,   0,   0,   0,   0.3, 0.5, 1,   1  ],
                "Refrigerator":           [24,  24,  24,  24,  24,  24,  24,  24,  24,  24,  24,  24 ],
                "Washing Machine":        [1,   1,   1,   1,   1,   1.5, 1.5, 1.5, 1,   1,   1,   1  ],
                "TV (LED 43 inch)":       [4,   4,   4,   4,   4,   4,   5,   5,   4,   4,   4,   5  ],
                "LED Bulb (10W)":         [6,   6,   5,   5,   5,   5,   6,   6,   6,   6,   6,   7  ],
                "Microwave":              [1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1  ],
                "Iron":                   [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5],
                "Computer/Laptop":        [6,   6,   6,   6,   6,   6,   6,   6,   6,   6,   6,   6  ],
            }

            # Context-aware tips that change with the season
            reduction_tips = {
                "AC (1.5 ton)": (
                    "Summer peak — keep at 24°C, use fan alongside. Each degree lower adds ~6% to your bill. Set a timer to auto-off after you sleep." if is_summer else
                    "Monsoon feels warm but is cooler than summer — try fan-only mode before switching AC on." if is_monsoon else
                    "Winter — you really shouldn't need AC at all this month. Switch it off completely." if is_winter else
                    "Mild weather this month — open windows instead of running AC."
                ),
                "Fan (Ceiling)": (
                    "Essential in summer — just turn it off when you leave the room. Each fan running 24/7 adds ~Rs 55/month." if is_summer else
                    "Good airflow helps in monsoon humidity. Just avoid running in empty rooms." if is_monsoon else
                    "Winter — fans aren't needed much. Switch off when not in the room." if is_winter else
                    "Turn off fans in unoccupied rooms — that's the only saving needed."
                ),
                "Water Heater (Geyser)": (
                    "Summer — you don't need a geyser at all. Switch off the MCB entirely to avoid standby loss." if is_summer else
                    "Monsoon water is warm — geyser is mostly unnecessary. Use only if needed." if is_monsoon else
                    "Winter essential but keep it brief. Switch on 15 min before use, off immediately after. Never leave it on all day." if is_winter else
                    "Mild month — limit to 15–20 mins max, switch off the moment you're done."
                ),
                "Refrigerator":          "Always-on appliance — you can't reduce hours. Clean coils every 3 months, keep it 3/4 full, and don't put hot food inside.",
                "Washing Machine": (
                    "Extra loads due to monsoon dampness — run only full loads and air-dry instead of ironing wet clothes." if is_monsoon else
                    "Run full loads only. Cold water wash saves energy. Air-dry instead of tumble dry."
                ),
                "TV (LED 43 inch)":      "Reduce screen brightness to 50% — saves power with no visible difference. Switch off at plug, not just remote standby.",
                "LED Bulb (10W)":        "Use natural light during daytime. Group switches so you're not lighting unused rooms.",
                "Microwave":             "Efficient appliance — just avoid using it to keep food warm for long periods.",
                "Iron":                  "Iron all clothes in one batch rather than one garment at a time. Unplug immediately after use.",
                "Computer/Laptop":       "Enable power-saving/sleep mode. A laptop uses ~4× less power than a desktop — switch if possible.",
            }

            total_current_units = s_units
            total_current_bill  = s_bill

            alert_data = []
            for appliance, wattage in APPLIANCES.items():
                hrs = float(s_hours.get(appliance, 0))
                if hrs == 0:
                    continue
                # Get seasonal limit for this appliance and month
                threshold_row = SEASONAL_THRESHOLDS.get(appliance, [8]*12)
                limit         = threshold_row[month_idx]
                current_units = round((wattage * hrs * 30) / 1000, 2)
                current_cost  = round(calculate_bill(current_units, supplier)['total'], 0)
                reduced_hrs   = min(hrs, limit)
                reduced_units = round((wattage * reduced_hrs * 30) / 1000, 2)
                other_units   = total_current_units - current_units
                new_total_bill = calculate_bill(other_units + reduced_units, supplier)['total']
                bill_saving    = round(total_current_bill - new_total_bill, 0)
                if hrs > limit:
                    status = "🔴 HIGH USAGE"
                    border = "#e74c3c"
                    bg     = "rgba(231,76,60,.12)"
                    text_color = "#fca5a5"
                elif hrs > limit * 0.7:
                    status = "🟡 MODERATE"
                    border = "#f1c40f"
                    bg     = "rgba(241,196,15,.10)"
                    text_color = "#fde68a"
                else:
                    status = "🟢 NORMAL"
                    border = "#27ae60"
                    bg     = "rgba(39,174,96,.10)"
                    text_color = "#6ee7b7"
                alert_data.append({
                    "Appliance": appliance, "Hrs/Day": hrs, "Limit (hrs)": limit,
                    "Current Units": current_units, "Current Cost": current_cost,
                    "Bill Saving": bill_saving, "Reduced Hrs": reduced_hrs,
                    "Status": status, "bg": bg, "border": border, "text_color": text_color,
                    "tip": reduction_tips.get(appliance, "")
                })

            if alert_data:
                # Bar chart — dark theme
                chart_df  = pd.DataFrame(alert_data)
                fig_alert = px.bar(chart_df, x="Appliance", y=["Hrs/Day", "Limit (hrs)"],
                                   barmode="group",
                                   title=f"Your Usage vs Seasonal Recommended Limit — {s_month}",
                                   color_discrete_map={"Hrs/Day": "#e74c3c", "Limit (hrs)": "#2ecc71"},
                                   labels={"value": "Hours/Day", "variable": ""},
                                   template="plotly_dark")
                fig_alert.update_layout(height=360, xaxis_tickangle=-20,
                                        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig_alert, use_container_width=True)

                # Total saving banner
                total_possible_saving = sum(r['Bill Saving'] for r in alert_data if r['Bill Saving'] > 0)
                if total_possible_saving > 0:
                    st.markdown(f'''<div style="background:linear-gradient(135deg,rgba(16,185,129,.2),rgba(5,150,105,.1));
                      border:1px solid rgba(16,185,129,.3);border-radius:16px;
                      padding:22px 28px;text-align:center;margin:14px 0;">
                      <div style="font-size:13px;color:#6ee7b7;text-transform:uppercase;letter-spacing:1.5px;font-weight:600;margin-bottom:6px;">POTENTIAL SAVINGS</div>
                      <div style="font-family:'Syne','Segoe UI',system-ui,sans-serif;font-size:32px;font-weight:800;color:#34d399;">Rs {total_possible_saving:.0f}</div>
                      <div style="font-size:13px;color:#6b7280;margin-top:4px;">per month by reducing over-limit appliances</div>
                    </div>''', unsafe_allow_html=True)

                # Analysis cards — dark-theme colors
                st.markdown("**⚡ Appliance-wise Analysis & Recommendations:**")
                for row in sorted(alert_data, key=lambda x: x['Bill Saving'], reverse=True):
                    if row['Limit (hrs)'] == 0:
                        saving_text = f"<b style='color:#f97316;'>⚠️ Not recommended this month — switching off saves Rs {row['Bill Saving']:.0f}!</b>"
                    elif row['Bill Saving'] > 0:
                        saving_text = f"<b style='color:#34d399;'>💰 Reduce to {row['Reduced Hrs']}hrs/day → Save Rs {row['Bill Saving']:.0f} next month!</b>"
                    else:
                        saving_text = "<span style='color:#34d399;'>✅ Within seasonal limit — no change needed.</span>"
                    st.markdown(f"""
                        <div style="background:{row['bg']};border-left:5px solid {row['border']};
                        padding:14px 20px;border-radius:12px;margin:8px 0;">
                        <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
                            <span style="font-size:15px;font-weight:700;color:#f1f5f9;">{row['Appliance']}</span>
                            <span style="font-size:12px;font-weight:700;color:{row['text_color']};background:rgba(0,0,0,.2);padding:2px 10px;border-radius:20px;">{row['Status']}</span>
                        </div>
                        <span style="font-size:13px;color:#9ca3af;">
                            ⏱ <b style='color:#e2e8f0;'>{row['Hrs/Day']}hrs/day</b> (seasonal limit: {row['Limit (hrs)']}hrs) &nbsp;|&nbsp;
                            ⚡ {row['Current Units']} kWh/month &nbsp;|&nbsp;
                            💰 Rs {row['Current Cost']:.0f}/month
                        </span><br>
                        <span style="font-size:13px;margin:6px 0;display:block;">{saving_text}</span>
                        <span style="font-size:12px;color:#6b7280;margin-top:3px;display:block;">💡 {row['tip']}</span>
                        </div>
                    """, unsafe_allow_html=True)

                # ── TIPS & TRICKS SECTION ──
                st.markdown("---")
                section_header("💡", "Tips & Tricks to Reduce Your Bill", "Personalised advice based on your appliance usage this month")
                for row in sorted(alert_data, key=lambda x: x['Bill Saving'], reverse=True):
                    if not row['tip']:
                        continue
                    tip_icon = "🔴" if "HIGH" in row['Status'] else ("🟡" if "MODERATE" in row['Status'] else "🟢")
                    st.markdown(f"""
                    <div style="background:rgba(255,255,255,.04);border:1.5px solid rgba(255,255,255,.1);
                      border-left:6px solid {row['border']};
                      border-radius:16px;padding:22px 26px;margin:14px 0;
                      box-shadow:0 4px 20px rgba(0,0,0,.25);">
                      <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px;">
                        <div style="font-size:26px;">{tip_icon}</div>
                        <div>
                          <div style="font-family:'Syne','Segoe UI',system-ui,sans-serif;font-size:18px;font-weight:800;color:#f1f5f9;letter-spacing:-.2px;">{row['Appliance']}</div>
                          <div style="font-size:12px;color:#6b7280;margin-top:2px;">
                            {row['Hrs/Day']} hrs/day · {row['Current Units']} kWh/month · Rs {row['Current Cost']:.0f}/month
                          </div>
                        </div>
                        <div style="margin-left:auto;font-size:12px;font-weight:700;color:{row['text_color']};
                          background:rgba(0,0,0,.25);padding:4px 14px;border-radius:20px;">{row['Status']}</div>
                      </div>
                      <div style="font-size:15px;color:#e2e8f0;line-height:1.7;font-weight:400;
                        background:rgba(0,0,0,.15);border-radius:10px;padding:14px 18px;">
                        💡 {row['tip']}
                      </div>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.markdown("---")
            st.info("Fill the appliance survey above to get smart appliance alerts and savings recommendations.")

        # Bill-level alerts — always show something
        st.markdown("---")
        section_header("💡", "Bill & Usage Alerts", "Personalized forecast and saving opportunities")

        # Always show current vs next month comparison
        delta_units = next_units - s_units
        delta_bill  = next_bill - s_bill
        trend_icon  = "📈" if delta_units > 0 else "📉"
        trend_color = "#ef4444" if delta_units > 0 else "#10b981"
        st.markdown(f'''
        <div style="background:linear-gradient(135deg,rgba(255,255,255,.04),rgba(255,255,255,.02));
          border:1px solid rgba(255,255,255,.08);border-left:4px solid {trend_color};
          border-radius:14px;padding:18px 22px;margin:10px 0;
          box-shadow:0 4px 16px rgba(0,0,0,.2);">
          <div style="font-size:11px;color:#6b7280;font-weight:600;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;">FORECAST</div>
          <div style="font-size:22px;font-weight:800;color:#f9fafb;font-family:'Syne','Segoe UI',system-ui,sans-serif;">
            {trend_icon} {next_units:.0f} <span style="font-size:14px;color:#9ca3af;font-weight:400;">kWh predicted</span>
          </div>
          <div style="font-size:13px;color:#9ca3af;margin-top:6px;">
            <span style="color:{trend_color};font-weight:600;">{"+" if delta_units>=0 else ""}{delta_units:.0f} kWh</span> vs this month · 
            Estimated bill <span style="color:#38bdf8;font-weight:600;">Rs {next_bill:.0f}</span>
            <span style="color:{trend_color};"> ({"+" if delta_bill>=0 else ""}{delta_bill:.0f})</span>
          </div>
        </div>
        ''', unsafe_allow_html=True)

        # Slab-based alert — always shown
        if s_units > 500:
            alert_card("rgba(239,68,68,.12)","#ef4444",f"🔴 <b>Very High Usage!</b> You are in the highest slab (Rs {SUPPLIERS[supplier]['slabs'][3][1]}/unit). Reducing by {s_units-500:.0f} kWh saves Rs {s_bill-calculate_bill(500,supplier)['total']:.0f} next month!")
        elif s_units > 300:
            alert_card("rgba(249,115,22,.12)","#f97316",f"🟠 <b>High Slab Alert!</b> Reducing by {s_units-300:.0f} kWh could save Rs {s_bill-calculate_bill(300,supplier)['total']:.0f} next month!")
        elif s_units > 100:
            alert_card("rgba(234,179,8,.12)","#eab308",f"🟡 <b>Slab Reduction Tip:</b> Reduce by {s_units-100:.0f} kWh to drop to the lowest slab and save Rs {s_bill-calculate_bill(100,supplier)['total']:.0f}!")
        else:
            alert_card("rgba(16,185,129,.12)","#10b981",f"✅ <b>Excellent!</b> You are in the lowest slab (Rs {SUPPLIERS[supplier]['slabs'][0][1]}/unit). Keep usage under 100 kWh!")

        # Spike alert
        if next_units > s_units * 1.15:
            alert_card("rgba(56,189,248,.12)","#38bdf8",f"🚨 <b>Spike Predicted!</b> Next month usage may jump by {next_units-s_units:.0f} kWh. Check for seasonal changes or extra appliance usage.")

        st.markdown('''<div style="font-size:11px;color:#6b7280;font-weight:600;text-transform:uppercase;letter-spacing:1px;margin:20px 0 10px;">💡 Quick Tips</div>''', unsafe_allow_html=True)
        tips = [
            ("🔌","Unplug chargers","Phantom load from standby devices adds up to 10% of your bill."),
            ("🌙","Off-peak appliances","Run washing machine and iron late at night to reduce grid load."),
            ("❄️","AC temperature","Set AC to 24°C — each degree lower saves ~6% energy."),
        ]
        tip_html = '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:4px 0;">'
        for icon, title, desc in tips:
            tip_html += f'''<div style="background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.07);
              border-radius:14px;padding:16px 18px;transition:all .2s;">
              <div style="font-size:22px;margin-bottom:8px;">{icon}</div>
              <div style="font-size:13px;font-weight:600;color:#e2e8f0;margin-bottom:4px;">{title}</div>
              <div style="font-size:12px;color:#6b7280;line-height:1.5;">{desc}</div>
            </div>'''
        tip_html += '</div>'
        st.markdown(tip_html, unsafe_allow_html=True)


        # ── CARBON FOOTPRINT ──
        st.markdown("---")
        section_header("🌍", "Carbon Footprint", "Your environmental impact this month")
        co2_total   = s_units * CO2_FACTOR
        trees_equiv = co2_total / 22
        cf1, cf2 = st.columns(2)
        with cf1:
            st.metric("CO2 This Month", f"{co2_total:.1f} kg")
        with cf2:
            st.metric("Trees Needed", f"{trees_equiv:.2f} trees/year")
        st.caption("CO₂ factor: 0.716 kg/kWh — CEA Grid Emission Factor 2023.")

        # ── PREDICTED APPLIANCE-WISE COST ──
        # Use current month hours if available, else fall back to survey avg hours
        # with seasonal multipliers for next month (forward-looking prediction)
        display_hours = s_hours
        using_survey_fallback = False
        if not display_hours and avg_survey:
            # Apply seasonal multipliers for next_month_name (what we're predicting)
            seasonally_adjusted = apply_seasonal_multipliers(avg_survey, next_month_name)
            display_hours = scale_hours_to_units(seasonally_adjusted, next_units)
            using_survey_fallback = True

        if display_hours:
            st.markdown("---")
            section_header("💡", "Predicted Appliance-wise Cost", "Based on your current usage pattern")
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
                                  text="Predicted Cost (Rs)",
                                  template="plotly_dark")
                fig_pred.update_traces(texttemplate="Rs %{text:.0f}", textposition="outside")
                fig_pred.update_layout(height=400, xaxis_tickangle=-20, showlegend=False,
                                       paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
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
    section_header("📊", "Yearly Dashboard", f"Viewing data for {st.session_state.supplier} — {sn}")

    # Year selector using actual years with data
    with st.spinner("Loading your data..."):
        available_years = load_years_with_data(st.session_state.username)
    current_year = datetime.now().year
    if current_year not in available_years:
        available_years = [current_year] + available_years
    default_year = st.session_state.get("dash_year", current_year)
    if default_year not in available_years:
        default_year = available_years[0]
    selected_year = st.selectbox(
        "📅 Select Year", available_years,
        index=available_years.index(default_year),
        key="dash_year_select"
    )

    rows = load_user_data(st.session_state.username, selected_year)

    if rows:
        df = pd.DataFrame(rows, columns=["Month", "Units", "Bill", "Rate"])
        df["Month_Order"] = df["Month"].map(MONTH_ORDER)
        df = df.sort_values("Month_Order").reset_index(drop=True)

        total_units = df["Units"].sum()
        total_bill  = df["Bill"].sum()
        avg_rate    = df["Rate"].mean()
        last_units  = df["Units"].iloc[-1]
        last_bill   = df["Bill"].iloc[-1]

        st.markdown(f'''<div style="font-size:13px;color:#6b7280;font-weight:600;text-transform:uppercase;letter-spacing:1px;margin-bottom:16px;">{selected_year} OVERVIEW · {len(df)}/12 MONTHS RECORDED</div>''', unsafe_allow_html=True)
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

        # ── CSV EXPORT ──
        csv_data = df[["Month", "Units", "Bill", "Rate"]].copy()
        csv_data.insert(0, "Year", selected_year)
        st.download_button(
            label="⬇️ Export Data as CSV",
            data=csv_data.to_csv(index=False).encode("utf-8"),
            file_name=f"voltiq_{st.session_state.username}_{selected_year}.csv",
            mime="text/csv",
        )

        st.markdown("---")

        # ── CHART 1 — LINE ──
        section_header("📈","Daily Consumption Trend","Estimated daily usage from monthly totals")
        daily_rows = []
        for _, row in df.iterrows():
            month_idx = MONTH_ORDER[row["Month"]] + 1
            days_in_month = pd.Period(f"{selected_year}-{month_idx:02d}").days_in_month
            daily_avg = row["Units"] / days_in_month
            rng = np.random.default_rng(month_idx * 7)
            noise = rng.normal(0, daily_avg * 0.1, days_in_month)
            for d in range(1, days_in_month + 1):
                daily_rows.append({"Date": f"{row['Month']} {d:02d}", "Units": round(max(0.1, daily_avg + noise[d-1]), 2), "Month": row["Month"]})
        daily_df = pd.DataFrame(daily_rows)
        fig_line = px.line(daily_df, x="Date", y="Units", color="Month",
                           title=f"Estimated Daily Consumption ({selected_year}) — Simulated from monthly totals",
                           labels={"Units": "Units (kWh)"},
                           template="plotly_dark")
        fig_line.update_traces(line=dict(width=1.5))
        fig_line.update_layout(height=400, showlegend=True,
                               paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        fig_line.update_xaxes(showticklabels=False)
        st.plotly_chart(fig_line, use_container_width=True)
        st.caption("⚠️ Daily values are simulated from monthly totals using typical usage patterns — not actual meter readings.")

        st.markdown("---")

        # ── CHART 2 — BAR ──
        section_header("📊","Monthly Comparison","Units consumed vs bill amount per month")
        fig_bar = px.bar(df, x="Month", y=["Units", "Bill"], barmode="group",
                         title=f"Monthly Units & Bill Comparison ({selected_year})",
                         labels={"value": "Units (kWh) / Bill (Rs)", "variable": "Metric"},
                         color_discrete_map={"Units": "#38bdf8", "Bill": "#f59e0b"},
                         template="plotly_dark")
        fig_bar.update_layout(height=400,
                              paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_bar, use_container_width=True)

        st.markdown("---")

        # ── CHART 3 — PIE ──
        section_header("🥧","Appliance-wise Yearly Usage","How your energy is split across appliances")
        appliance_rows = load_all_appliance_data(st.session_state.username, selected_year)

        using_survey_fallback = False
        if not appliance_rows:
            survey_avg = get_user_survey_hours(st.session_state.username)
            if survey_avg:
                # Apply seasonal multipliers per month so summer months show
                # more AC/Fan and winter months show more Geyser — not flat static data
                appliance_rows = [
                    (row["Month"], apply_seasonal_multipliers(survey_avg, row["Month"]))
                    for _, row in df.iterrows()
                ]
                using_survey_fallback = True

        if appliance_rows:
            if using_survey_fallback:
                st.caption(f"📋 No per-month appliance data found for {selected_year}. Using your onboarding survey averages scaled to each month's actual bill.")

            month_bill_lookup  = dict(zip(df["Month"], df["Bill"]))
            month_units_lookup = dict(zip(df["Month"], df["Units"]))
            total_actual_bill  = df["Bill"].sum()
            total_actual_units = df["Units"].sum()
            supplier           = st.session_state.supplier

            appliance_yearly_units = {}
            appliance_yearly_cost  = {}

            for month_name, hours_json in appliance_rows:
                actual_bill  = month_bill_lookup.get(month_name, 0)
                actual_units = month_units_lookup.get(month_name, 0)
                if actual_bill == 0 or actual_units == 0:
                    continue

                month_kwh = {}
                for appliance, wattage in APPLIANCES.items():
                    hrs = float(hours_json.get(appliance, 0))
                    if hrs > 0:
                        month_kwh[appliance] = (wattage * hrs * 30) / 1000

                raw_total_kwh = sum(month_kwh.values())
                if raw_total_kwh == 0:
                    continue

                for appliance, raw_kwh in month_kwh.items():
                    scaled_kwh = (raw_kwh / raw_total_kwh) * actual_units
                    appliance_yearly_units[appliance] = appliance_yearly_units.get(appliance, 0) + scaled_kwh

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
                                       hole=0.35, template="plotly_dark")
                    fig_pie_u.update_traces(textposition="inside", textinfo="percent+label")
                    fig_pie_u.update_layout(height=500,
                                            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                    st.plotly_chart(fig_pie_u, use_container_width=True)
                    st.caption("📌 Shows raw kWh consumed by each appliance — based on wattage × usage hours.")
                with tab_cost:
                    fig_pie_c = px.pie(pie_df, names="Appliance", values="Yearly Cost (Rs)",
                                       title=f"Appliance-wise Yearly Bill Share — {selected_year}",
                                       hole=0.35, color_discrete_sequence=px.colors.sequential.RdBu,
                                       template="plotly_dark")
                    fig_pie_c.update_traces(textposition="inside", textinfo="percent+label")
                    fig_pie_c.update_layout(height=500,
                                            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
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
        section_header("🌡️","Hourly Usage Heatmap","Estimated usage pattern across hours of the day")
        hourly_weights = np.array([0.3,0.2,0.2,0.2,0.2,0.3,0.5,0.8,1.0,0.7,0.6,0.7,0.8,0.6,0.5,0.5,0.6,0.8,1.0,1.2,1.2,1.0,0.8,0.5])
        hourly_weights = hourly_weights / hourly_weights.sum()
        heatmap_data = []
        for _, row in df.iterrows():
            month_idx = MONTH_ORDER[row["Month"]] + 1
            days_in_month = pd.Period(f"{selected_year}-{month_idx:02d}").days_in_month
            heatmap_data.append((row["Units"] / days_in_month) * hourly_weights * 24)
        fig_heat = px.imshow(np.array(heatmap_data),
                             x=[f"{h:02d}:00" for h in range(24)], y=df["Month"].tolist(),
                             color_continuous_scale="YlOrRd",
                             title=f"Hourly Usage Heatmap ({selected_year})",
                             labels={"x": "Hour of Day", "y": "Month", "color": "kWh"},
                             aspect="auto", template="plotly_dark")
        fig_heat.update_layout(height=400,
                               paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_heat, use_container_width=True)
        st.caption("Heatmap estimated based on typical Indian household hourly usage patterns.")

        st.markdown("---")

        # ── CARBON FOOTPRINT ──
        section_header("🌍", "Carbon Footprint", "Your environmental impact this year")
        total_co2   = total_units * CO2_FACTOR
        monthly_co2 = last_units * CO2_FACTOR
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total CO2", f"{total_co2:.0f} kg", delta=f"{monthly_co2:.0f} kg last month")
        with col2:
            st.metric("Trees Equivalent", f"{total_co2/22:.1f} trees/year")
        st.caption("CO₂ factor: 0.716 kg/kWh — CEA Grid Emission Factor 2023.")

        # ── DELETE MONTH ──
        st.markdown("---")
        section_header("🗑️", "Manage Data", "Delete a specific month's entry")
        del_col1, del_col2 = st.columns([2, 1])
        with del_col1:
            month_to_delete = st.selectbox("Select month to delete", df["Month"].tolist(), key="delete_month_select")
        with del_col2:
            st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
            if st.session_state.delete_confirm_month == month_to_delete:
                if st.button(f"✅ Confirm delete {month_to_delete}", use_container_width=True, type="primary"):
                    delete_month_entry(st.session_state.username, selected_year, month_to_delete)
                    st.session_state.delete_confirm_month = ""
                    st.success(f"{month_to_delete} {selected_year} deleted.")
                    st.rerun()
            else:
                if st.button(f"🗑️ Delete {month_to_delete}", use_container_width=True):
                    st.session_state.delete_confirm_month = month_to_delete
                    st.rerun()

    else:
        st.info(f"No data found for {selected_year}. Go to Enter Data page to add your monthly readings!")
        if st.button("Go to Enter Data →"):
            st.session_state.page = "input"
            st.rerun()

st.markdown("---")







































































































