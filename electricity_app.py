import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
from datetime import datetime
import hashlib
import psycopg2

# ─────────────────────────────────────────────
# DATABASE CONNECTION (Supabase PostgreSQL)
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
    conn.commit()
    cur.close()
    conn.close()

init_db()

# ─────────────────────────────────────────────
# MSEDCL BILL CALCULATOR
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
            units = EXCLUDED.units,
            bill  = EXCLUDED.bill,
            rate  = EXCLUDED.rate
    """, (username, year, month, units, bill, rate))
    conn.commit()
    cur.close()
    conn.close()

def load_user_data(username, year):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT month, units, bill, rate FROM electricity_data
        WHERE username = %s AND year = %s
    """, (username, year))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def delete_user_data(username, year):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM electricity_data WHERE username = %s AND year = %s",
                (username, year))
    conn.commit()
    cur.close()
    conn.close()

# ─────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "auth_page" not in st.session_state:
    st.session_state.auth_page = "login"

st.set_page_config(page_title="Electricity Analyzer", layout="wide")

# ─────────────────────────────────────────────
# AUTH PAGES
# ─────────────────────────────────────────────
SECURITY_QUESTIONS = [
    "What is your pet's name?",
    "What is your mother's maiden name?",
    "What was the name of your first school?",
    "What is your favourite movie?",
    "What city were you born in?",
]

if not st.session_state.logged_in:
    st.title("Smart Electricity Analyzer")
    st.markdown("---")
    _, col_form, _ = st.columns([1, 1.5, 1])
    with col_form:

        if st.session_state.auth_page == "login":
            st.markdown("### Login")
            username = st.text_input("Username", key="login_user")
            password = st.text_input("Password", type="password", key="login_pass")
            if st.button("Login", use_container_width=True):
                if not username or not password:
                    st.error("Please enter both fields.")
                elif verify_user(username, password):
                    st.session_state.logged_in = True
                    st.session_state.username = username
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
            st.markdown("### Create Account")
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
            st.markdown("### Reset Password")
            if "forgot_step" not in st.session_state:
                st.session_state.forgot_step = 1
                st.session_state.forgot_username = ""
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
# MAIN APP
# ─────────────────────────────────────────────
st.title("Smart Electricity Analyzer - Maharashtra (MSEDCL)")
st.markdown("---")

username = st.session_state.username
connection_type = "single_phase"

st.sidebar.markdown(f"Logged in as: **{username}**")
if st.sidebar.button("Logout", use_container_width=True):
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.rerun()

st.sidebar.markdown("---")

selected_year = int(st.sidebar.number_input(
    "Year", min_value=2000, max_value=2100,
    value=datetime.now().year, step=1
))

st.sidebar.header("Enter Monthly Data")
month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
month          = st.sidebar.selectbox("Month", month_names)
units_consumed = st.sidebar.number_input("Units Consumed (kWh)", min_value=0.0, value=0.0, step=10.0)

if units_consumed > 0:
    preview = calculate_msedcl_bill(units_consumed, connection_type)
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Estimated Bill Breakdown:**")
    st.sidebar.markdown(f"Energy Charges: Rs {preview['energy_charge']}")
    st.sidebar.markdown(f"FAC: Rs {preview['fac']}")
    st.sidebar.markdown(f"Fixed Charge: Rs {preview['fixed_charge']}")
    st.sidebar.markdown(f"Electricity Duty (16%): Rs {preview['electricity_duty']}")
    st.sidebar.markdown(f"**Total: Rs {preview['total']}**")
    st.sidebar.markdown("---")

if st.sidebar.button("ANALYZE & SAVE", use_container_width=True):
    if units_consumed == 0:
        st.sidebar.error("Please enter units consumed.")
    else:
        bill_data = calculate_msedcl_bill(units_consumed, connection_type)
        effective_rate = round(bill_data['total'] / units_consumed, 2)
        save_entry(username, selected_year, month, units_consumed, bill_data['total'], effective_rate)
        st.sidebar.success(f"Saved {month} {selected_year}! Bill: Rs {bill_data['total']}")
        st.rerun()

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

rows = load_user_data(username, selected_year)

if rows:
    df = pd.DataFrame(rows, columns=['Month', 'Units', 'Bill', 'Rate'])
    month_order = {m: i for i, m in enumerate(month_names)}
    df['Month_Order'] = df['Month'].map(month_order)
    df = df.sort_values('Month_Order').reset_index(drop=True)

    total_units = df['Units'].sum()
    total_bill  = df['Bill'].sum()
    avg_rate    = df['Rate'].mean()
    last_units  = df['Units'].iloc[-1]
    last_bill   = df['Bill'].iloc[-1]

    st.markdown(f"### {selected_year} Overview — {len(df)}/12 months recorded")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Units", f"{total_units:.0f} kWh")
    with col2:
        st.metric("Total Bill", f"Rs {total_bill:.0f}")
    with col3:
        st.metric("Avg Effective Rate", f"Rs {avg_rate:.2f}/kWh")
    with col4:
        trend = "UP" if df['Units'].iloc[-1] > df['Units'].iloc[0] else "DOWN"
        st.metric("Trend", trend)

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
    st.caption("Daily values are estimated from monthly totals using realistic variation.")

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

    # CHART 3 — PIE
    st.subheader("3. Appliance-wise Usage Breakdown")
    st.markdown("Set daily usage hours for each appliance:")
    hours_input = {}
    cols = st.columns(2)
    for i, (appliance, wattage) in enumerate(APPLIANCES.items()):
        with cols[i % 2]:
            hours_input[appliance] = st.number_input(
                f"{appliance} ({wattage}W) — hrs/day",
                min_value=0.0, max_value=24.0, value=0.0, step=0.5,
                key=f"appliance_{i}"
            )
    appliance_units = {
        name: round((watt * hours_input[name] * 30) / 1000, 2)
        for name, watt in APPLIANCES.items() if hours_input[name] > 0
    }
    if appliance_units:
        pie_df = pd.DataFrame({"Appliance": list(appliance_units.keys()), "Units (kWh)": list(appliance_units.values())})
        fig_pie = px.pie(pie_df, names="Appliance", values="Units (kWh)",
                         title="Appliance-wise Electricity Consumption (Monthly Estimate)", hole=0.3)
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        fig_pie.update_layout(height=500)
        st.plotly_chart(fig_pie, use_container_width=True)
        a_col1, a_col2 = st.columns(2)
        with a_col1:
            st.metric("Total Appliance Units", f"{sum(appliance_units.values()):.1f} kWh/month")
        with a_col2:
            st.metric("Estimated Bill", f"Rs {calculate_msedcl_bill(sum(appliance_units.values()))['total']:.0f}/month")
    else:
        st.info("Enter hours/day for at least one appliance to see the pie chart.")

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
    st.caption("Heatmap is estimated based on typical Indian household hourly usage patterns.")

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

    # NEXT MONTH ESTIMATE
    st.subheader("🔮 Next Month Estimate")
    next_units = last_units * 1.05
    next_bill  = calculate_msedcl_bill(next_units, connection_type)['total']
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Estimated Units", f"{next_units:.0f} kWh", delta=f"+{next_units - last_units:.0f}")
    with col2:
        st.metric("Estimated Bill", f"Rs {next_bill:.0f}", delta=f"+Rs {next_bill - last_bill:.0f}")

    st.markdown("---")

    # ALERT BANNER
    if last_units > 500:
        alert_msg, alert_color = f"🚨 VERY HIGH USAGE<br>{last_units:.0f} units<br>Highest slab (Rs 11.85/unit)!", "#ff4444"
    elif last_units > 300:
        alert_msg, alert_color = f"⚠️ HIGH USAGE<br>{last_units:.0f} units<br>Rs 8.00/unit slab.", "#ff8800"
    elif last_units > 100:
        alert_msg, alert_color = f"ℹ️ MODERATE USAGE<br>{last_units:.0f} units<br>Rs 6.50/unit slab.", "#f0c040"
    else:
        alert_msg, alert_color = f"✅ LOW USAGE<br>{last_units:.0f} units<br>Lowest slab (Rs 2.90/unit)!", "#44bb44"

    st.markdown(f"""
        <div style="background:{alert_color};color:white;padding:30px 40px;border-radius:16px;
        text-align:center;font-size:20px;font-weight:bold;font-family:sans-serif;
        box-shadow:0 4px 20px rgba(0,0,0,0.3);margin:10px 0;">{alert_msg}</div>
    """, unsafe_allow_html=True)

    st.sidebar.markdown("---")
    if st.sidebar.button(f"Clear {selected_year} Data"):
        delete_user_data(username, selected_year)
        st.rerun()

else:
    st.info(f"No data yet for {selected_year}. Enter units in the sidebar and click ANALYZE & SAVE!")

st.markdown("---")
st.caption("Rates based on MSEDCL (Mahavitaran) Maharashtra Residential Tariff 2025.")
