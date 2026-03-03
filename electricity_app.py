import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import hashlib
import sqlite3

# ─────────────────────────────────────────────
# DATABASE SETUP
# ─────────────────────────────────────────────
DB_FILE = "electricity.db"

def get_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS electricity_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            year INTEGER NOT NULL,
            month TEXT NOT NULL,
            units REAL NOT NULL,
            bill REAL NOT NULL,
            rate REAL NOT NULL,
            UNIQUE(username, year, month)
        )
    """)
    conn.commit()
    conn.close()

init_db()

def calculate_msedcl_bill(units, connection_type="single_phase"):
    slabs = [
        (100, 2.90),
        (200, 6.50),
        (200, 8.00),
        (float('inf'), 11.85),
    ]
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

def register_user(username, password):
    try:
        conn = get_connection()
        conn.execute("INSERT INTO users (username, password) VALUES (?, ?)",
                     (username, hash_password(password)))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        return False

def verify_user(username, password):
    conn = get_connection()
    cursor = conn.execute("SELECT password FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    return row is not None and row[0] == hash_password(password)

# ─────────────────────────────────────────────
# DATA HELPERS
# ─────────────────────────────────────────────
def save_entry(username, year, month, units, bill, rate):
    conn = get_connection()
    conn.execute("""
        INSERT INTO electricity_data (username, year, month, units, bill, rate)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(username, year, month) DO UPDATE SET
            units = excluded.units,
            bill  = excluded.bill,
            rate  = excluded.rate
    """, (username, year, month, units, bill, rate))
    conn.commit()
    conn.close()

def load_user_data(username, year):
    conn = get_connection()
    cursor = conn.execute("""
        SELECT month, units, bill, rate FROM electricity_data
        WHERE username = ? AND year = ?
    """, (username, year))
    rows = cursor.fetchall()
    conn.close()
    return rows

def delete_user_data(username, year):
    conn = get_connection()
    conn.execute("DELETE FROM electricity_data WHERE username = ? AND year = ?",
                 (username, year))
    conn.commit()
    conn.close()

def get_available_years(username):
    conn = get_connection()
    cursor = conn.execute("""
        SELECT DISTINCT year FROM electricity_data
        WHERE username = ? ORDER BY year DESC
    """, (username,))
    rows = [r[0] for r in cursor.fetchall()]
    conn.close()
    return rows if rows else [datetime.now().year]

# ─────────────────────────────────────────────
# SESSION STATE INIT
# ─────────────────────────────────────────────
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(page_title="Electricity Analyzer", layout="wide")

# ─────────────────────────────────────────────
# LOGIN / SIGNUP PAGE
# ─────────────────────────────────────────────
if not st.session_state.logged_in:
    st.title("⚡ Smart Electricity Analyzer")
    st.markdown("---")

    _, col_form, _ = st.columns([1, 1.5, 1])

    with col_form:
        mode = st.radio("", ["Login", "Sign Up"], horizontal=True)
        st.markdown(f"### {'🔐 Login' if mode == 'Login' else '📝 Create Account'}")

        username = st.text_input("Username")
        password = st.text_input("Password", type="password")

        if mode == "Sign Up":
            confirm_password = st.text_input("Confirm Password", type="password")
            if st.button("Create Account", use_container_width=True):
                if not username or not password:
                    st.error("Please fill in all fields.")
                elif len(password) < 4:
                    st.warning("Password must be at least 4 characters.")
                elif password != confirm_password:
                    st.error("Passwords do not match.")
                elif register_user(username, password):
                    st.success("Account created! Please log in.")
                else:
                    st.error("Username already exists.")
        else:
            if st.button("Login", use_container_width=True):
                if not username or not password:
                    st.error("Please enter both username and password.")
                elif verify_user(username, password):
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.rerun()
                else:
                    st.error("Invalid username or password.")
    st.stop()

# ─────────────────────────────────────────────
# MAIN APP
# ─────────────────────────────────────────────
st.title(" Smart Electricity Analyzer")
st.markdown("---")

username = st.session_state.username

# Sidebar user info & logout
st.sidebar.markdown(f"👤 **Logged in as:** `{username}`")
if st.sidebar.button("🚪 Logout", use_container_width=True):
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.rerun()

st.sidebar.markdown("---")

connection_type = "single_phase"

# Year selector
available_years = get_available_years(username)
current_year = datetime.now().year
if current_year not in available_years:
    available_years.insert(0, current_year)

selected_year = st.sidebar.selectbox("📅 Select Year", available_years)

# Sidebar inputs
st.sidebar.header(" Enter Monthly Data")
month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
month          = st.sidebar.selectbox("1. Month", month_names)

rate_per_unit  = st.sidebar.number_input("3. Rate/Unit (₹/kWh)",      min_value=0.0, value=0.0,    step=0.1)
units_consumed = st.sidebar.number_input("4. Units Consumed (kWh)",   min_value=0.0, value=0.0,  step=10.0)

if st.sidebar.button("ANALYZE & SAVE", use_container_width=True):
    bill_data = calculate_msedcl_bill(units_consumed, connection_type)
    effective_rate = round(bill_data['total'] / units_consumed, 2)
    save_entry(username, selected_year, month, units_consumed, bill_data['total'], effective_rate)
    st.sidebar.success(f"Saved! Bill: Rs {bill_data['total']}")
    st.rerun()
# ─────────────────────────────────────────────
# LOAD DATA
# ─────────────────────────────────────────────
rows = load_user_data(username, selected_year)

if rows:
    df = pd.DataFrame(rows, columns=['Month', 'Units', 'Bill', 'Rate'])
    month_order = {m: i for i, m in enumerate(month_names)}
    df['Month_Order'] = df['Month'].map(month_order)
    df = df.sort_values('Month_Order').reset_index(drop=True)

    st.markdown(f"### 📅 Data for **{selected_year}** — {len(df)}/12 months recorded")

    # KEY METRICS
    col1, col2, col3, col4 = st.columns(4)
    total_units = df['Units'].sum()
    total_bill  = df['Bill'].sum()
    avg_rate    = df['Rate'].mean()
    last_units  = df['Units'].iloc[-1]
    last_bill   = df['Bill'].iloc[-1]

    with col1:
        st.metric("Total Units", f"{total_units:.0f} kWh")
    with col2:
        st.metric("Total Bill", f"₹{total_bill:.0f}")
    with col3:
        st.metric("Avg Rate", f"₹{avg_rate:.1f}/kWh")
    with col4:
        trend = "📈 UP" if df['Units'].iloc[-1] > df['Units'].iloc[0] else "📉 DOWN"
        st.metric("Trend", trend)

    # LINE GRAPH
    st.subheader("📊 Monthly Analysis")
    fig = px.line(df, x='Month', y=['Units', 'Bill'],
                  markers=True,
                  title=f"Electricity Usage & Bill Trend ({selected_year})",
                  labels={'value': 'Units (kWh) / Bill (₹)'})
    fig.update_traces(line=dict(width=3))
    fig.update_layout(height=400, showlegend=True)
    st.plotly_chart(fig, use_container_width=True)

    # CARBON FOOTPRINT
    st.subheader("🌍 Carbon Footprint")
    co2_factor  = 0.82
    total_co2   = total_units * co2_factor
    monthly_co2 = last_units * co2_factor

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total CO2", f"{total_co2:.0f} kg",
                  delta=f"{monthly_co2:.0f} kg this month")
    with col2:
        trees_needed = total_co2 / 22
        st.metric("Trees Equivalent", f"{trees_needed:.1f} trees/year")

    # NEXT MONTH PREDICTION
    st.subheader("🔮 Next Month Estimate")
    next_units = last_units * 1.05
    next_bill  = next_units * df['Rate'].iloc[-1]

    col1, col2 = st.columns(2)
    with col1:
        st.metric("Estimated Units", f"{next_units:.0f} kWh",
                  delta=f"+{next_units - last_units:.0f}")
    with col2:
        st.metric("Estimated Bill", f"₹{next_bill:.0f}",
                  delta=f"+₹{next_bill - last_bill:.0f}")

    # ALERT
    st.subheader("🚨 Alert")
    if last_units > 100:
        st.error(f"⚠️ HIGH USAGE ALERT: {last_units:.0f} units exceeds 100 kWh limit!")
    else:
        st.success("✅ Usage within safe limit (≤100 kWh)")

   
    # CLEAR YEAR DATA
    st.sidebar.markdown("---")
    if st.sidebar.button(f"🗑️ Clear {selected_year} Data"):
        delete_user_data(username, selected_year)
        st.rerun()

else:
    st.info(f"👆 No data yet for {selected_year}. Enter data in the sidebar and click ANALYZE & SAVE!")

st.markdown("---")
