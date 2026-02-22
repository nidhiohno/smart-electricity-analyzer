import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

# ─────────────────────────────────────────
# Page config
# ─────────────────────────────────────────
st.set_page_config(
    page_title="⚡ Smart Electricity Analyzer",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────
# Custom CSS – Premium Creative Theme
# ─────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800;900&display=swap');

/* Apply Inter to text but NOT to icons */
html, body, [class*="css"], [data-testid="stAppViewContainer"] {
    font-family: 'Inter', sans-serif;
}

/* ── Animated background ── */
.stApp {
    background: #0b0d14;
    color: #e2e8f0;
}
.stApp::before {
    content: '';
    position: fixed;
    top: -50%; left: -50%;
    width: 200%; height: 200%;
    background: radial-gradient(ellipse at 20% 20%, rgba(79,110,247,0.08) 0%, transparent 50%),
                radial-gradient(ellipse at 80% 80%, rgba(167,139,250,0.07) 0%, transparent 50%),
                radial-gradient(ellipse at 50% 50%, rgba(16,185,129,0.04) 0%, transparent 60%);
    animation: bgPulse 8s ease-in-out infinite alternate;
    pointer-events: none;
    z-index: 0;
}
@keyframes bgPulse {
    0%   { transform: scale(1)   rotate(0deg); }
    100% { transform: scale(1.1) rotate(5deg); }
}

/* ── Streamlit header / toolbar ── */
header[data-testid="stHeader"] {
    background: rgba(11, 13, 20, 0.9) !important;
    backdrop-filter: blur(12px);
    border-bottom: 1px solid rgba(79,110,247,0.1) !important;
}

/* Specific fix for the sidebar arrow icon (Both Expand and Collapse) */
[data-testid="stSidebarCollapseButton"] button,
[data-testid="stSidebarNav"] button[aria-label="Collapse sidebar"],
[data-testid="stSidebar"] button[aria-label="Collapse sidebar"] {
    background-color: rgba(79, 110, 247, 0.2) !important;
    border: 1px solid rgba(79, 110, 247, 0.4) !important;
    border-radius: 8px !important;
    color: #ffffff !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    width: 38px !important;
    height: 38px !important;
    opacity: 1 !important;
    visibility: visible !important;
}

[data-testid="stSidebarCollapseButton"] svg,
[data-testid="stSidebarNav"] button[aria-label="Collapse sidebar"] svg,
[data-testid="stSidebar"] button[aria-label="Collapse sidebar"] svg {
    fill: white !important;
    width: 22px !important;
    height: 22px !important;
    opacity: 1 !important;
    visibility: visible !important;
}

/* Ensure the arrow inside the sidebar doesn't get hidden by sidebar styles */
[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] {
    position: absolute !important;
    top: 10px !important;
    right: 10px !important;
}

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: linear-gradient(160deg, #0f1225 0%, #111827 60%, #0b0d14 100%) !important;
    border-right: 1px solid rgba(79,110,247,0.2) !important;
}
section[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
section[data-testid="stSidebar"] .stMarkdown h2 {
    font-size: 1.1rem !important; font-weight: 800 !important;
    letter-spacing: 1px; text-transform: uppercase;
    color: #a5b4fc !important;
}

/* ── Buttons ── */
.stButton > button {
    background: linear-gradient(135deg, #4f6ef7 0%, #7c3aed 100%) !important;
    color: #fff !important; border: none !important;
    border-radius: 12px !important; font-weight: 700 !important;
    font-size: 14px !important; letter-spacing: 0.5px;
    transition: all 0.3s ease !important;
    box-shadow: 0 4px 20px rgba(79,110,247,0.35) !important;
}
.stButton > button:hover {
    transform: translateY(-3px) scale(1.02) !important;
    box-shadow: 0 10px 30px rgba(124,58,237,0.5) !important;
}

/* ── Metric cards – fully custom ── */
[data-testid="metric-container"] {
    background: rgba(255,255,255,0.03) !important;
    backdrop-filter: blur(12px);
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 20px !important;
    padding: 22px 20px !important;
    box-shadow: 0 8px 32px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.05);
    transition: all 0.3s ease !important;
    position: relative; overflow: hidden;
}
[data-testid="metric-container"]::before {
    content: '';
    position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, #4f6ef7, #7c3aed, #10b981);
    border-radius: 20px 20px 0 0;
}
[data-testid="metric-container"]:hover {
    transform: translateY(-4px) !important;
    border-color: rgba(79,110,247,0.3) !important;
    box-shadow: 0 16px 48px rgba(79,110,247,0.2) !important;
}
[data-testid="metric-container"] label {
    color: #94a3b8 !important; font-size: 0.72rem !important;
    font-weight: 700 !important; text-transform: uppercase; letter-spacing: 1.5px;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: #fff !important; font-size: 1.9rem !important; font-weight: 900 !important;
}
[data-testid="metric-container"] [data-testid="stMetricDelta"] svg { display: none; }
[data-testid="metric-container"] [data-testid="stMetricDelta"] {
    color: #4ade80 !important; font-weight: 700 !important; font-size: 0.82rem !important;
}

/* ── Plotly chart containers ── */
[data-testid="stPlotlyChart"] {
    background: rgba(255,255,255,0.02) !important;
    border-radius: 20px !important;
    border: 1px solid rgba(255,255,255,0.07) !important;
    padding: 12px !important;
    box-shadow: 0 8px 32px rgba(0,0,0,0.3) !important;
}

/* ── Dataframe ── */
[data-testid="stDataFrame"] {
    border-radius: 16px !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    box-shadow: 0 4px 20px rgba(0,0,0,0.3) !important;
}

/* ── Download button ── */
[data-testid="stDownloadButton"] > button {
    background: linear-gradient(135deg, rgba(16,185,129,0.15), rgba(5,150,105,0.2)) !important;
    color: #4ade80 !important; border: 1px solid rgba(16,185,129,0.3) !important;
    border-radius: 12px !important; font-weight: 700 !important;
    transition: all 0.3s ease !important;
}
[data-testid="stDownloadButton"] > button:hover {
    background: linear-gradient(135deg, rgba(16,185,129,0.25), rgba(5,150,105,0.35)) !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 20px rgba(16,185,129,0.2) !important;
}

/* ── Tabs ── */
button[data-baseweb="tab"] {
    background: rgba(255,255,255,0.04) !important; color: #64748b !important;
    border-radius: 10px 10px 0 0 !important; font-weight: 600 !important;
    border: 1px solid rgba(255,255,255,0.06) !important; border-bottom: none !important;
    font-size: 0.9rem !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
    background: linear-gradient(135deg, rgba(79,110,247,0.2), rgba(124,58,237,0.2)) !important;
    color: #a5b4fc !important;
    border-color: rgba(79,110,247,0.3) !important; border-bottom: none !important;
}

/* ── Progress bar ── */
.stProgress > div > div {
    background: linear-gradient(90deg, #4f6ef7, #7c3aed, #10b981) !important;
    border-radius: 20px !important;
}
.stProgress > div { background: rgba(255,255,255,0.06) !important; border-radius: 20px !important; }

/* ── Divider ── */
hr {
    border: none !important; height: 1px !important;
    background: linear-gradient(90deg, transparent, rgba(79,110,247,0.4), rgba(124,58,237,0.4), transparent) !important;
    margin: 28px 0 !important;
}

/* ── Section headers ── */
.section-header {
    display: inline-block;
    background: linear-gradient(135deg, rgba(79,110,247,0.12), rgba(124,58,237,0.12));
    border: 1px solid rgba(79,110,247,0.2);
    border-radius: 12px;
    padding: 10px 20px;
    margin: 24px 0 16px 0;
    font-size: 1.1rem;
    font-weight: 800;
    color: #a5b4fc;
    letter-spacing: 0.3px;
}

/* ── Alert/Success boxes ── */
.stAlert { border-radius: 14px !important; border-left-width: 4px !important; }
.stCaption {
    color: rgba(148,163,184,0.4) !important; text-align: center;
    font-size: 0.75rem !important; letter-spacing: 0.5px;
}

/* ── Radio ── */
.stRadio > label { color: #94a3b8 !important; font-weight: 600 !important; }
.stRadio [data-testid="stMarkdownContainer"] p { color: #e2e8f0 !important; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────
CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter", color="#e2e8f0", size=13),
    title_font=dict(size=15, color="#a5b4fc", family="Inter"),
    xaxis=dict(gridcolor="rgba(255,255,255,0.05)", zeroline=False,
               tickfont=dict(color="#64748b"), linecolor="rgba(255,255,255,0.05)"),
    yaxis=dict(gridcolor="rgba(255,255,255,0.05)", zeroline=False,
               tickfont=dict(color="#64748b"), linecolor="rgba(255,255,255,0.05)"),
    legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor="rgba(255,255,255,0.08)",
                borderwidth=1, font=dict(color="#94a3b8")),
    margin=dict(l=20, r=20, t=50, b=20),
    hoverlabel=dict(bgcolor="#1a1d2e", bordercolor="#4f6ef7",
                    font=dict(color="#e2e8f0", family="Inter", size=13)),
)

PALETTE = ["#4f6ef7","#a78bfa","#10b981","#f59e0b","#f87171","#34d399","#60a5fa","#fbbf24"]

def bar_color(units):
    if units <= 100:   return "#10b981"
    elif units <= 250: return "#f59e0b"
    else:              return "#f87171"

# ─────────────────────────────────────────
# Session state
# ─────────────────────────────────────────
if "monthly_data" not in st.session_state:
    st.session_state.monthly_data = []

# ─────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────
st.sidebar.markdown("""
<div style="
    background: linear-gradient(135deg, rgba(79,110,247,0.15), rgba(124,58,237,0.15));
    border: 1px solid rgba(79,110,247,0.25);
    border-radius: 16px; padding: 16px; margin-bottom: 16px; text-align: center;">
    <div style="font-size: 2rem;">⚡</div>
    <div style="font-size: 0.85rem; font-weight: 800; color: #a5b4fc !important;
                letter-spacing: 1.5px; text-transform: uppercase; margin-top: 6px;">
        Electricity Analyzer
    </div>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("**📝 Monthly Data**")
month_names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
month          = st.sidebar.selectbox("Month", month_names)
bill_amount    = st.sidebar.number_input("Total Bill (₹)",       min_value=0.0, value=2500.0, step=100.0)
rate_per_unit  = st.sidebar.number_input("Rate per Unit (₹/kWh)", min_value=0.0, value=7.5,   step=0.1)
units_consumed = st.sidebar.number_input("Units Consumed (kWh)", min_value=0.0, value=300.0,  step=10.0)

st.sidebar.markdown("---")
st.sidebar.markdown("**📊 Chart Style**")
chart_type = st.sidebar.radio("", ["Bar Chart", "Donut Chart"], index=0)

st.sidebar.markdown("---")
ca, cb = st.sidebar.columns(2)
with ca:
    analyze = st.button("🔍 Analyze", use_container_width=True)
with cb:
    if st.button("🗑️ Clear", use_container_width=True):
        st.session_state.monthly_data = []
        st.rerun()

if analyze:
    st.session_state.monthly_data.append({
        "Month": month, "Bill": bill_amount,
        "Units": units_consumed, "Rate": rate_per_unit,
    })

# ─────────────────────────────────────────
# Hero Header
# ─────────────────────────────────────────
st.markdown("""
<div style="text-align:center; padding: 30px 0 10px 0;">
    <div style="
        font-size: 3rem; font-weight: 900; letter-spacing: -1px;
        background: linear-gradient(135deg, #e2e8f0 0%, #a5b4fc 40%, #7c3aed 70%, #4f6ef7 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        background-clip: text; line-height: 1.2; margin-bottom: 8px;">
        ⚡ Smart Electricity Analyzer
    </div>
    <div style="
        color: rgba(148,163,184,0.7); font-size: 1rem; font-weight: 400;
        letter-spacing: 3px; text-transform: uppercase;">
        Track &nbsp;•&nbsp; Analyze &nbsp;•&nbsp; Predict
    </div>
    <div style="
        width: 80px; height: 3px; margin: 14px auto 0 auto;
        background: linear-gradient(90deg, #4f6ef7, #7c3aed, #10b981);
        border-radius: 10px;">
    </div>
</div>
""", unsafe_allow_html=True)

st.markdown("---")

# ─────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────
if st.session_state.monthly_data:
    df = pd.DataFrame(st.session_state.monthly_data)
    month_order = {m: i for i, m in enumerate(month_names)}
    df["Month_Order"] = df["Month"].map(month_order)
    df = df.sort_values("Month_Order").reset_index(drop=True)
    co2_factor  = 0.82
    df["CO2"]   = df["Units"] * co2_factor

    total_units  = df["Units"].sum()
    total_bill   = df["Bill"].sum()
    avg_rate     = df["Rate"].mean()
    total_co2    = df["CO2"].sum()
    last_units   = df["Units"].iloc[-1]
    last_bill    = df["Bill"].iloc[-1]
    monthly_co2  = last_units * co2_factor
    trees_needed = total_co2 / 22

    # ── SECTION: KEY METRICS ────────────────
    st.markdown("<div class='section-header'>📈 Key Metrics</div>", unsafe_allow_html=True)
    c1,c2,c3,c4,c5 = st.columns(5)
    trend = "📈 UP" if len(df)>1 and df["Units"].iloc[-1]>df["Units"].iloc[0] else "📉 DOWN"
    with c1: st.metric("⚡ Total Units",  f"{total_units:.0f} kWh")
    with c2: st.metric("💰 Total Bill",   f"₹{total_bill:.0f}")
    with c3: st.metric("📊 Avg Rate",     f"₹{avg_rate:.1f}/kWh")
    with c4: st.metric("🌍 Total CO₂",    f"{total_co2:.0f} kg")
    with c5: st.metric("📉 Trend",        trend)

    # Usage safety bar
    safe_limit = 100
    pct = min(last_units / safe_limit, 1.0)
    st.markdown("<br>", unsafe_allow_html=True)
    if last_units > safe_limit:
        st.error(f"⚠️ Latest month: **{last_units:.0f} kWh** — exceeds safe limit by **{last_units-safe_limit:.0f} kWh**")
    else:
        st.success(f"✅ Latest month: **{last_units:.0f} kWh** — within safe limit of {safe_limit} kWh")
    st.progress(pct)

    st.markdown("---")

    # ══════════════════════════════════════
    # 1. Monthly Usage & Bill
    # ══════════════════════════════════════
    st.markdown("<div class='section-header'>📊 Monthly Usage & Bill</div>", unsafe_allow_html=True)

    if chart_type == "Bar Chart":
        colors = [bar_color(u) for u in df["Units"]]
        fig = go.Figure()
        fig.add_trace(go.Bar(name="Units (kWh)", x=df["Month"], y=df["Units"],
                             marker=dict(color=colors, line_width=0,
                                         cornerradius=6),
                             opacity=0.92))
        fig.add_trace(go.Bar(name="Bill (₹)", x=df["Month"], y=df["Bill"],
                             marker=dict(color="#f59e0b", line_width=0,
                                         cornerradius=6),
                             opacity=0.85))
        fig.update_layout(**CHART_LAYOUT, barmode="group",
                          title="🟢 ≤100 kWh safe  ·  🟡 100–250 moderate  ·  🔴 >250 high",
                          height=420)
        st.plotly_chart(fig, use_container_width=True)
    else:
        t1, t2 = st.tabs(["🍕 Units Share", "💰 Bill Share"])
        with t1:
            fig_u = go.Figure(go.Pie(labels=df["Month"], values=df["Units"], hole=0.6,
                                     marker=dict(colors=PALETTE,
                                                 line=dict(color="#0b0d14", width=3))))
            fig_u.update_traces(textposition="inside", textinfo="percent+label",
                                textfont_size=12)
            fig_u.update_layout(**CHART_LAYOUT, title="Units — Monthly Share", height=400)
            st.plotly_chart(fig_u, use_container_width=True)
        with t2:
            fig_b = go.Figure(go.Pie(labels=df["Month"], values=df["Bill"], hole=0.6,
                                     marker=dict(colors=PALETTE,
                                                 line=dict(color="#0b0d14", width=3))))
            fig_b.update_traces(textposition="inside", textinfo="percent+label",
                                textfont_size=12)
            fig_b.update_layout(**CHART_LAYOUT, title="Bill — Monthly Share", height=400)
            st.plotly_chart(fig_b, use_container_width=True)

    # ══════════════════════════════════════
    # 2. Rate Per Unit
    # ══════════════════════════════════════
    st.markdown("<div class='section-header'>💡 Rate per Unit</div>", unsafe_allow_html=True)

    if chart_type == "Bar Chart":
        fig_rate = px.bar(df, x="Month", y="Rate",
                          color="Rate", color_continuous_scale=["#1e3a8a","#4f6ef7","#a5b4fc"],
                          labels={"Rate":"₹/kWh"})
        fig_rate.update_traces(marker_line_width=0)
        fig_rate.update_layout(**CHART_LAYOUT, title="Rate per Unit — Month by Month", height=360)
    else:
        fig_rate = go.Figure(go.Pie(labels=df["Month"], values=df["Rate"], hole=0.6,
                                    marker=dict(colors=PALETTE,
                                                line=dict(color="#0b0d14", width=3))))
        fig_rate.update_traces(textposition="inside", textinfo="percent+label", textfont_size=12)
        fig_rate.update_layout(**CHART_LAYOUT, title="Rate — Monthly Distribution", height=380)
    st.plotly_chart(fig_rate, use_container_width=True)

    # ══════════════════════════════════════
    # 3. Carbon Footprint
    # ══════════════════════════════════════
    st.markdown("<div class='section-header'>🌍 Carbon Footprint</div>", unsafe_allow_html=True)
    cc1, cc2 = st.columns(2)
    with cc1: st.metric("💨 Total CO₂ Emitted",       f"{total_co2:.0f} kg",
                        delta=f"{monthly_co2:.0f} kg this month")
    with cc2: st.metric("🌳 Trees to Offset (yearly)", f"{trees_needed:.1f} trees")

    if chart_type == "Bar Chart":
        fig_co2 = px.bar(df, x="Month", y="CO2",
                         color="CO2", color_continuous_scale=["#064e3b","#10b981","#6ee7b7"],
                         labels={"CO2":"CO₂ (kg)"})
        fig_co2.update_traces(marker_line_width=0)
        fig_co2.update_layout(**CHART_LAYOUT, title="CO₂ Emissions — Month by Month", height=360)
    else:
        fig_co2 = go.Figure(go.Pie(labels=df["Month"], values=df["CO2"], hole=0.6,
                                   marker=dict(colors=PALETTE,
                                               line=dict(color="#0b0d14", width=3))))
        fig_co2.update_traces(textposition="inside", textinfo="percent+label", textfont_size=12)
        fig_co2.update_layout(**CHART_LAYOUT, title="CO₂ — Monthly Share", height=380)
    st.plotly_chart(fig_co2, use_container_width=True)

    # ══════════════════════════════════════
    # 4. Prediction + Gauge
    # ══════════════════════════════════════
    st.markdown("<div class='section-header'>🔮 Next Month Prediction</div>", unsafe_allow_html=True)

    last_rate  = df["Rate"].iloc[-1]
    next_units = last_units * 1.05
    next_bill  = next_units * last_rate
    next_co2   = next_units * co2_factor

    pc1, pc2, pc3 = st.columns(3)
    with pc1: st.metric("⚡ Est. Units", f"{next_units:.0f} kWh", delta=f"+{next_units-last_units:.0f}")
    with pc2: st.metric("💰 Est. Bill",  f"₹{next_bill:.0f}",     delta=f"+₹{next_bill-last_bill:.0f}")
    with pc3: st.metric("🌍 Est. CO₂",   f"{next_co2:.0f} kg",    delta=f"+{next_co2-monthly_co2:.0f} kg")

    # Gauge
    gauge_max = max(500, next_units * 1.5)
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=next_units,
        delta={"reference": last_units, "valueformat":".0f",
               "increasing":{"color":"#f87171"}, "decreasing":{"color":"#4ade80"}},
        number={"suffix":" kWh", "font":{"color":"#e2e8f0","family":"Inter","size":32}},
        title={"text":"Predicted Next Month Usage<br><span style='font-size:0.8em;color:#64748b'>vs current month</span>",
               "font":{"color":"#a5b4fc","size":14}},
        gauge={
            "axis":{"range":[0, gauge_max], "tickcolor":"#475569",
                    "tickfont":{"color":"#475569","size":11}},
            "bar":{"color":"#4f6ef7","thickness":0.28},
            "bgcolor":"rgba(0,0,0,0)",
            "bordercolor":"rgba(0,0,0,0)",
            "steps":[
                {"range":[0, 100],         "color":"rgba(16,185,129,0.1)"},
                {"range":[100, 250],       "color":"rgba(245,158,11,0.1)"},
                {"range":[250, gauge_max], "color":"rgba(248,113,113,0.1)"},
            ],
            "threshold":{"line":{"color":"#f87171","width":3},
                         "thickness":0.8,"value":100},
        },
    ))
    fig_gauge.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", height=280,
        margin=dict(l=40, r=40, t=60, b=10),
        font=dict(family="Inter", color="#e2e8f0"),
    )
    st.plotly_chart(fig_gauge, use_container_width=True)

    # ══════════════════════════════════════
    # 5. Data Table + Export
    # ══════════════════════════════════════
    st.markdown("<div class='section-header'>📋 Data Summary</div>", unsafe_allow_html=True)
    display_df = df[["Month","Units","Bill","Rate","CO2"]].copy()
    display_df.columns = ["Month","Units (kWh)","Bill (₹)","Rate (₹/kWh)","CO₂ (kg)"]
    st.dataframe(display_df.round(1), use_container_width=True, hide_index=True)
    csv = display_df.round(2).to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Export Data as CSV", data=csv,
                       file_name="electricity_data.csv", mime="text/csv")

else:
    # ── Beautiful empty state ─────────────
    st.markdown("""
    <div style="
        text-align:center; padding: 70px 20px; margin: 40px 0;
        background: linear-gradient(135deg, rgba(79,110,247,0.05), rgba(124,58,237,0.05));
        border: 1px solid rgba(79,110,247,0.15);
        border-radius: 24px; position: relative; overflow: hidden;">
        <div style="
            position:absolute; top:-40px; left:-40px; width:200px; height:200px;
            background: radial-gradient(circle, rgba(79,110,247,0.1), transparent);
            border-radius: 50%; pointer-events: none;"></div>
        <div style="
            position:absolute; bottom:-40px; right:-40px; width:200px; height:200px;
            background: radial-gradient(circle, rgba(124,58,237,0.1), transparent);
            border-radius: 50%; pointer-events: none;"></div>
        <div style="font-size:5rem; filter: drop-shadow(0 0 20px rgba(79,110,247,0.5));">⚡</div>
        <div style="
            font-size: 1.8rem; font-weight: 900; margin: 12px 0 8px 0;
            background: linear-gradient(135deg, #e2e8f0, #a5b4fc);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            background-clip: text;">
            Ready to Analyze!
        </div>
        <p style="color: rgba(148,163,184,0.75); font-size: 1rem; max-width: 380px; margin: 0 auto; line-height: 1.7;">
            Enter your monthly electricity data in the sidebar<br>
            and click <span style="color:#a5b4fc; font-weight:700;">🔍 Analyze</span> to see your insights.
        </p>
        <div style="margin-top:28px;display:grid;grid-template-columns:repeat(2,1fr);gap:12px;max-width:480px;margin-left:auto;margin-right:auto;">
            <div style="background:rgba(79,110,247,0.1);border:1px solid rgba(79,110,247,0.25);border-radius:16px;padding:16px 12px;text-align:center;">
                <div style="font-size:2rem;">📊</div>
                <div style="font-weight:700;color:#a5b4fc;font-size:0.9rem;margin-top:6px;">Bar & Donut Charts</div>
                <div style="color:rgba(148,163,184,0.65);font-size:0.75rem;margin-top:4px;">Switch chart styles live</div>
            </div>
            <div style="background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.22);border-radius:16px;padding:16px 12px;text-align:center;">
                <div style="font-size:2rem;">🌍</div>
                <div style="font-weight:700;color:#4ade80;font-size:0.9rem;margin-top:6px;">Carbon Footprint</div>
                <div style="color:rgba(148,163,184,0.65);font-size:0.75rem;margin-top:4px;">Track your CO₂ emissions</div>
            </div>
            <div style="background:rgba(167,139,250,0.08);border:1px solid rgba(167,139,250,0.22);border-radius:16px;padding:16px 12px;text-align:center;">
                <div style="font-size:2rem;">🔮</div>
                <div style="font-weight:700;color:#a78bfa;font-size:0.9rem;margin-top:6px;">Next Month Prediction</div>
                <div style="color:rgba(148,163,184,0.65);font-size:0.75rem;margin-top:4px;">Gauge + forecast view</div>
            </div>
            <div style="background:rgba(251,191,36,0.07);border:1px solid rgba(251,191,36,0.2);border-radius:16px;padding:16px 12px;text-align:center;">
                <div style="font-size:2rem;">⬇️</div>
                <div style="font-weight:700;color:#fbbf24;font-size:0.9rem;margin-top:6px;">Export CSV</div>
                <div style="color:rgba(148,163,184,0.65);font-size:0.75rem;margin-top:4px;">Download your data</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────
# Footer
# ─────────────────────────────────────────
st.markdown("---")
st.caption("⚡ Smart Electricity Analyzer  •  Carbon: 0.82 kg CO₂/kWh (India grid avg)  •  Built with Streamlit")
