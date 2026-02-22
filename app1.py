import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

# ─────────────────────────────────────────
# Page config
# ─────────────────────────────────────────
st.set_page_config(
    page_title="Smart Electricity Analyzer",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────
# Custom CSS – Dark Neon Theme
# ─────────────────────────────────────────
st.markdown("""
<style>
/* ── Google Font ── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&display=swap');

/* ── Global ── */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* ── Main background ── */
.stApp {
    background: linear-gradient(135deg, #0a0a1a 0%, #0d1b2a 50%, #0a1628 100%);
    color: #e2e8f0;
}

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0d1b2a 0%, #111827 100%);
    border-right: 1px solid rgba(0,180,216,0.2);
}
section[data-testid="stSidebar"] * {
    color: #e2e8f0 !important;
}

/* ── Sidebar header ── */
section[data-testid="stSidebar"] h1,
section[data-testid="stSidebar"] h2,
section[data-testid="stSidebar"] h3 {
    color: #00b4d8 !important;
    font-weight: 700;
    letter-spacing: 0.5px;
}

/* ── Sidebar inputs ── */
section[data-testid="stSidebar"] .stSelectbox select,
section[data-testid="stSidebar"] .stNumberInput input {
    background: rgba(0,180,216,0.08) !important;
    border: 1px solid rgba(0,180,216,0.3) !important;
    color: #e2e8f0 !important;
    border-radius: 8px !important;
}

/* ── Analyze button ── */
section[data-testid="stSidebar"] .stButton > button {
    background: linear-gradient(135deg, #00b4d8, #0077b6) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
    font-size: 15px !important;
    padding: 12px !important;
    transition: all 0.3s ease !important;
    box-shadow: 0 4px 15px rgba(0,180,216,0.4) !important;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 25px rgba(0,180,216,0.6) !important;
}

/* ── Main headings ── */
h1 {
    background: linear-gradient(90deg, #00b4d8, #90e0ef, #00b4d8);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    font-size: 2.5rem !important;
    font-weight: 800 !important;
    text-align: center;
    padding: 10px 0;
    letter-spacing: -0.5px;
}

h2, h3 {
    color: #90e0ef !important;
    font-weight: 700 !important;
    border-left: 4px solid #00b4d8;
    padding-left: 12px;
    margin-top: 30px !important;
}

/* ── Metric cards ── */
[data-testid="metric-container"] {
    background: linear-gradient(135deg, rgba(0,180,216,0.08), rgba(0,119,182,0.12));
    border: 1px solid rgba(0,180,216,0.25);
    border-radius: 16px;
    padding: 18px 20px !important;
    box-shadow: 0 4px 20px rgba(0,180,216,0.1);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
[data-testid="metric-container"]:hover {
    transform: translateY(-3px);
    box-shadow: 0 8px 30px rgba(0,180,216,0.25);
}
[data-testid="metric-container"] label {
    color: #90e0ef !important;
    font-size: 0.82rem !important;
    font-weight: 600 !important;
    text-transform: uppercase;
    letter-spacing: 1px;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: #ffffff !important;
    font-size: 1.8rem !important;
    font-weight: 800 !important;
}
[data-testid="metric-container"] [data-testid="stMetricDelta"] {
    color: #2dc653 !important;
    font-weight: 600 !important;
}

/* ── Plotly chart containers ── */
[data-testid="stPlotlyChart"] {
    background: rgba(255,255,255,0.02) !important;
    border-radius: 16px !important;
    border: 1px solid rgba(0,180,216,0.1) !important;
    padding: 10px !important;
}

/* ── Dataframe ── */
[data-testid="stDataFrame"] {
    border-radius: 12px !important;
    border: 1px solid rgba(0,180,216,0.2) !important;
    overflow: hidden;
}

/* ── Divider ── */
hr {
    border: none !important;
    height: 1px !important;
    background: linear-gradient(90deg, transparent, rgba(0,180,216,0.4), transparent) !important;
    margin: 20px 0 !important;
}

/* ── Info / Alert boxes ── */
.stAlert {
    border-radius: 12px !important;
    border-left-width: 4px !important;
}

/* ── Radio buttons ── */
.stRadio label {
    color: #90e0ef !important;
    font-weight: 600 !important;
}

/* ── Tabs ── */
button[data-baseweb="tab"] {
    background: rgba(0,180,216,0.08) !important;
    color: #90e0ef !important;
    border-radius: 8px 8px 0 0 !important;
    font-weight: 600 !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
    background: rgba(0,180,216,0.25) !important;
    color: #ffffff !important;
    border-bottom: 3px solid #00b4d8 !important;
}

/* ── Caption/footer ── */
.stCaption {
    color: rgba(144,224,239,0.5) !important;
    text-align: center;
    font-size: 0.78rem !important;
}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────
# Chart layout helper – dark glass style
# ─────────────────────────────────────────
CHART_LAYOUT = dict(
    paper_bgcolor="rgba(10,10,26,0.0)",
    plot_bgcolor="rgba(10,10,26,0.0)",
    font=dict(family="Inter", color="#e2e8f0", size=13),
    title_font=dict(size=16, color="#90e0ef", family="Inter"),
    xaxis=dict(gridcolor="rgba(144,224,239,0.08)", zeroline=False,
               tickfont=dict(color="#90e0ef")),
    yaxis=dict(gridcolor="rgba(144,224,239,0.08)", zeroline=False,
               tickfont=dict(color="#90e0ef")),
    legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor="rgba(144,224,239,0.15)",
                borderwidth=1, font=dict(color="#e2e8f0")),
    margin=dict(l=20, r=20, t=50, b=20),
    hoverlabel=dict(bgcolor="#0d1b2a", bordercolor="#00b4d8",
                    font=dict(color="#e2e8f0", family="Inter")),
)

NEON_COLORS = ["#00b4d8", "#f77f00", "#2dc653", "#e040fb", "#ffbe0b", "#ff4d6d"]

# ─────────────────────────────────────────
# Session state
# ─────────────────────────────────────────
if "monthly_data" not in st.session_state:
    st.session_state.monthly_data = []

# ─────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────
st.sidebar.markdown("## ⚡ Electricity Analyzer")
st.sidebar.markdown("---")
st.sidebar.header("📝 Enter Monthly Data")

month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

month          = st.sidebar.selectbox("1. Month", month_names)
bill_amount    = st.sidebar.number_input("2. Total Bill (₹)",       min_value=0.0, value=2500.0, step=100.0)
rate_per_unit  = st.sidebar.number_input("3. Rate/Unit (₹/kWh)",    min_value=0.0, value=7.5,   step=0.1)
units_consumed = st.sidebar.number_input("4. Units Consumed (kWh)", min_value=0.0, value=300.0, step=10.0)

st.sidebar.markdown("---")
st.sidebar.header("📊 Chart Style")
chart_type = st.sidebar.radio(
    "Select Chart Type",
    options=["Bar Chart", "Pie Chart"],
    index=0,
)

st.sidebar.markdown("---")

col_a, col_b = st.sidebar.columns(2)
with col_a:
    analyze = st.button("🔍 ANALYZE", use_container_width=True)
with col_b:
    if st.button("🗑️ Clear", use_container_width=True):
        st.session_state.monthly_data = []
        st.rerun()

if analyze:
    st.session_state.monthly_data.append({
        "Month": month,
        "Bill":  bill_amount,
        "Units": units_consumed,
        "Rate":  rate_per_unit,
    })

# ─────────────────────────────────────────
# Hero title
# ─────────────────────────────────────────
st.markdown("<h1>⚡ Smart Electricity Analyzer</h1>", unsafe_allow_html=True)
st.markdown(
    "<p style='text-align:center;color:rgba(144,224,239,0.65);margin-top:-10px;'>"
    "Track • Analyze • Predict your electricity usage</p>",
    unsafe_allow_html=True,
)
st.markdown("---")

# ─────────────────────────────────────────
# Main Dashboard
# ─────────────────────────────────────────
if st.session_state.monthly_data:
    df = pd.DataFrame(st.session_state.monthly_data)
    month_order = {m: i for i, m in enumerate(month_names)}
    df["Month_Order"] = df["Month"].map(month_order)
    df = df.sort_values("Month_Order").reset_index(drop=True)
    co2_factor = 0.82
    df["CO2"] = df["Units"] * co2_factor

    total_units  = df["Units"].sum()
    total_bill   = df["Bill"].sum()
    avg_rate     = df["Rate"].mean()
    total_co2    = df["CO2"].sum()
    last_units   = df["Units"].iloc[-1]
    last_bill    = df["Bill"].iloc[-1]
    monthly_co2  = last_units * co2_factor
    trees_needed = total_co2 / 22

    # ── KEY METRICS ──────────────────────
    st.markdown("### 📈 Key Metrics")
    c1, c2, c3, c4, c5 = st.columns(5)
    trend = "📈 UP" if len(df) > 1 and df["Units"].iloc[-1] > df["Units"].iloc[0] else "📉 DOWN"
    with c1: st.metric("Total Units",  f"{total_units:.0f} kWh")
    with c2: st.metric("Total Bill",   f"₹{total_bill:.0f}")
    with c3: st.metric("Avg Rate",     f"₹{avg_rate:.1f}/kWh")
    with c4: st.metric("Total CO₂",    f"{total_co2:.0f} kg")
    with c5: st.metric("Usage Trend",  trend)

    st.markdown("---")

    # ══════════════════════════════════════
    # 1. Monthly Usage & Bill
    # ══════════════════════════════════════
    st.markdown("### 📊 Monthly Usage & Bill")

    if chart_type == "Bar Chart":
        fig = px.bar(
            df, x="Month", y=["Units", "Bill"], barmode="group",
            labels={"value": "Amount", "variable": "Metric"},
            color_discrete_map={"Units": "#00b4d8", "Bill": "#f77f00"},
        )
        for trace in fig.data:
            trace.marker.update(opacity=0.9, line=dict(width=0))
    else:
        tab1, tab2 = st.tabs(["🔵 Units Share", "� Bill Share"])
        with tab1:
            fig_u = px.pie(df, values="Units", names="Month",
                           color_discrete_sequence=NEON_COLORS)
            fig_u.update_traces(textposition="inside", textinfo="percent+label",
                                marker=dict(line=dict(color="#0a0a1a", width=2)))
            fig_u.update_layout(**CHART_LAYOUT, title="Units Consumed — Monthly Share", height=380)
            st.plotly_chart(fig_u, use_container_width=True)
        with tab2:
            fig_b = px.pie(df, values="Bill", names="Month",
                           color_discrete_sequence=NEON_COLORS)
            fig_b.update_traces(textposition="inside", textinfo="percent+label",
                                marker=dict(line=dict(color="#0a0a1a", width=2)))
            fig_b.update_layout(**CHART_LAYOUT, title="Bill Amount — Monthly Share", height=380)
            st.plotly_chart(fig_b, use_container_width=True)
        fig = None

    if chart_type == "Bar Chart":
        fig.update_layout(**CHART_LAYOUT, height=400)
        st.plotly_chart(fig, use_container_width=True)

    # ══════════════════════════════════════
    # 2. Rate per Unit
    # ══════════════════════════════════════
    st.markdown("### 💡 Rate per Unit (₹/kWh)")

    if chart_type == "Bar Chart":
        fig_rate = px.bar(df, x="Month", y="Rate",
                          color="Rate", color_continuous_scale=["#0077b6", "#00b4d8", "#90e0ef"],
                          labels={"Rate": "₹/kWh"})
        fig_rate.update_traces(marker=dict(line=dict(width=0)))
    else:
        fig_rate = px.pie(df, values="Rate", names="Month",
                          color_discrete_sequence=NEON_COLORS)
        fig_rate.update_traces(textposition="inside", textinfo="percent+label",
                               marker=dict(line=dict(color="#0a0a1a", width=2)))

    fig_rate.update_layout(**CHART_LAYOUT, title="Rate per Unit Overview", height=380)
    st.plotly_chart(fig_rate, use_container_width=True)

    # ══════════════════════════════════════
    # 3. Carbon Footprint
    # ══════════════════════════════════════
    st.markdown("### 🌍 Carbon Footprint")
    cc1, cc2 = st.columns(2)
    with cc1:
        st.metric("Total CO₂ Emitted",       f"{total_co2:.0f} kg",
                  delta=f"{monthly_co2:.0f} kg this month")
    with cc2:
        st.metric("Trees to Offset (yearly)", f"{trees_needed:.1f} trees")

    if chart_type == "Bar Chart":
        fig_co2 = px.bar(df, x="Month", y="CO2",
                         color="CO2", color_continuous_scale=["#0d4a1e", "#2dc653", "#80ffaa"],
                         labels={"CO2": "CO₂ (kg)"})
        fig_co2.update_traces(marker=dict(line=dict(width=0)))
    else:
        fig_co2 = px.pie(df, values="CO2", names="Month",
                         color_discrete_sequence=NEON_COLORS)
        fig_co2.update_traces(textposition="inside", textinfo="percent+label",
                              marker=dict(line=dict(color="#0a0a1a", width=2)))

    fig_co2.update_layout(**CHART_LAYOUT, title="CO₂ Emissions Overview", height=380)
    st.plotly_chart(fig_co2, use_container_width=True)

    # ══════════════════════════════════════
    # 4. Next Month Prediction
    # ══════════════════════════════════════
    st.markdown("### 🔮 Next Month Prediction")

    last_rate  = df["Rate"].iloc[-1]
    next_units = last_units * 1.05
    next_bill  = next_units * last_rate
    next_co2   = next_units * co2_factor

    pc1, pc2, pc3 = st.columns(3)
    with pc1: st.metric("Estimated Units", f"{next_units:.0f} kWh", delta=f"+{next_units-last_units:.0f}")
    with pc2: st.metric("Estimated Bill",  f"₹{next_bill:.0f}",     delta=f"+₹{next_bill-last_bill:.0f}")
    with pc3: st.metric("Estimated CO₂",   f"{next_co2:.0f} kg",    delta=f"+{next_co2-monthly_co2:.0f} kg")

    pred_row = pd.DataFrame([{
        "Month": "Next ▶", "Units": next_units, "Bill": next_bill,
        "Rate": last_rate, "CO2": next_co2, "Month_Order": 12
    }])
    df_pred = pd.concat([df, pred_row], ignore_index=True)

    if chart_type == "Bar Chart":
        fig_pred = px.bar(df_pred, x="Month", y=["Units", "Bill"], barmode="group",
                          labels={"value": "Amount", "variable": "Metric"},
                          color_discrete_map={"Units": "#00b4d8", "Bill": "#f77f00"})
        fig_pred.update_traces(marker=dict(line=dict(width=0), opacity=0.9))
        # Shade predicted bar
        fig_pred.add_vrect(x0=len(df_pred)-1.5, x1=len(df_pred)-0.5,
                           fillcolor="rgba(255,255,255,0.04)", line_width=0,
                           annotation_text="Predicted", annotation_position="top right",
                           annotation_font_color="#f77f00")
    else:
        compare_df = pd.DataFrame({
            "Category": ["Actual Total Units", "Predicted Next Month"],
            "Value":    [total_units, next_units],
        })
        fig_pred = px.pie(compare_df, values="Value", names="Category",
                          color_discrete_sequence=["#00b4d8", "#f77f00"])
        fig_pred.update_traces(textposition="inside", textinfo="percent+label",
                               marker=dict(line=dict(color="#0a0a1a", width=2)))

    fig_pred.update_layout(**CHART_LAYOUT, title="Actual vs Predicted Next Month", height=400)
    st.plotly_chart(fig_pred, use_container_width=True)

    # ══════════════════════════════════════
    # 5. Alert
    # ══════════════════════════════════════
    st.markdown("### 🚨 Usage Alert")
    if last_units > 100:
        st.error(f"⚠️ HIGH USAGE: {last_units:.0f} kWh exceeds the 100 kWh safe limit!")
    else:
        st.success(f"✅ Usage is within safe limit (≤ 100 kWh). This month: {last_units:.0f} kWh")

    # ══════════════════════════════════════
    # 6. Data Table
    # ══════════════════════════════════════
    st.markdown("### 📋 Data Summary")
    display_df = df[["Month", "Units", "Bill", "Rate", "CO2"]].copy()
    display_df.columns = ["Month", "Units (kWh)", "Bill (₹)", "Rate (₹/kWh)", "CO₂ (kg)"]
    st.dataframe(display_df.round(1), use_container_width=True, hide_index=True)

else:
    st.markdown("""
    <div style="
        text-align:center;
        padding: 60px 20px;
        background: rgba(0,180,216,0.05);
        border: 1px dashed rgba(0,180,216,0.3);
        border-radius: 20px;
        margin: 40px 0;
    ">
        <div style="font-size:4rem;">⚡</div>
        <h2 style="color:#00b4d8;border:none;padding:0;margin:10px 0;">Ready to Analyze!</h2>
        <p style="color:rgba(144,224,239,0.7);font-size:1.1rem;">
            Enter your monthly electricity data in the sidebar<br>and click <strong style="color:#00b4d8;">🔍 ANALYZE</strong> to get started.
        </p>
    </div>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────
# Footer
# ─────────────────────────────────────────
st.markdown("---")
st.caption("⚡ Smart Electricity Analyzer • Carbon factor: 0.82 kg CO₂/kWh (India grid avg) • Built with Streamlit")
