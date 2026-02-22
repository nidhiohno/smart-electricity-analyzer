import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

# ─────────────────────────────────────────
# Page config
# ─────────────────────────────────────────
st.set_page_config(page_title="Smart Electricity Analyzer", layout="wide")
st.title("⚡ Smart Electricity Analyzer Demo")
st.markdown("---")

# ─────────────────────────────────────────
# Initialize session state
# ─────────────────────────────────────────
if "monthly_data" not in st.session_state:
    st.session_state.monthly_data = []

# ─────────────────────────────────────────
# Sidebar – Inputs
# ─────────────────────────────────────────
st.sidebar.header("📝 Enter Monthly Data")

month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

month          = st.sidebar.selectbox("1. Month", month_names)
bill_amount    = st.sidebar.number_input("2. Total Bill (₹)",       min_value=0.0, value=2500.0, step=100.0)
rate_per_unit  = st.sidebar.number_input("3. Rate/Unit (₹/kWh)",    min_value=0.0, value=7.5,   step=0.1)
units_consumed = st.sidebar.number_input("4. Units Consumed (kWh)", min_value=0.0, value=300.0, step=10.0)

st.sidebar.markdown("---")

# ── Chart type selector ────────────────
st.sidebar.header("📊 Chart Settings")
chart_type = st.sidebar.radio(
    "Select Chart Type",
    options=["Bar Chart", "Pie Chart"],
    index=0,
    help="Choose how you want to visualize your data"
)

st.sidebar.markdown("---")

# ── Analyze button ─────────────────────
if st.sidebar.button("🔍 ANALYZE", use_container_width=True):
    st.session_state.monthly_data.append({
        "Month": month,
        "Bill":  bill_amount,
        "Units": units_consumed,
        "Rate":  rate_per_unit,
    })

# ── Clear data button ──────────────────
if st.sidebar.button("🗑️ Clear All Data"):
    st.session_state.monthly_data = []
    st.rerun()

# ─────────────────────────────────────────
# Main Dashboard
# ─────────────────────────────────────────
if st.session_state.monthly_data:
    df = pd.DataFrame(st.session_state.monthly_data)

    # Sort by calendar order
    month_order = {m: i for i, m in enumerate(month_names)}
    df["Month_Order"] = df["Month"].map(month_order)
    df = df.sort_values("Month_Order").reset_index(drop=True)

    # ── KEY METRICS ──────────────────────────
    col1, col2, col3, col4 = st.columns(4)
    total_units = df["Units"].sum()
    total_bill  = df["Bill"].sum()
    avg_rate    = df["Rate"].mean()
    last_units  = df["Units"].iloc[-1]
    last_bill   = df["Bill"].iloc[-1]

    with col1:
        st.metric("Total Units", f"{total_units:.0f} kWh")
    with col2:
        st.metric("Total Bill", f"₹{total_bill:.0f}")
    with col3:
        st.metric("Avg Rate", f"₹{avg_rate:.1f}/kWh")
    with col4:
        trend = "📈 UP" if df["Units"].iloc[-1] > df["Units"].iloc[0] else "📉 DOWN"
        st.metric("Trend", trend)

    st.markdown("---")

    # ══════════════════════════════════════════
    # 1.  MONTHLY USAGE & BILL  (trend chart)
    # ══════════════════════════════════════════
    st.subheader("📊 Monthly Usage & Bill Analysis")

    if chart_type == "Bar Chart":
        fig = px.bar(
            df, x="Month", y=["Units", "Bill"],
            barmode="group",
            title="Electricity Usage & Bill — Monthly Comparison",
            labels={"value": "Units (kWh) / Bill (₹)", "variable": "Metric"},
            color_discrete_map={"Units": "#00b4d8", "Bill": "#f77f00"},
        )

    else:  # Pie Chart
        # Pie for units distribution across months
        tab1, tab2 = st.tabs(["🍕 Units Share", "💰 Bill Share"])
        with tab1:
            fig_u = px.pie(df, values="Units", names="Month",
                           title="Units Consumed — Monthly Share",
                           color_discrete_sequence=px.colors.sequential.Blues_r)
            fig_u.update_traces(textposition="inside", textinfo="percent+label")
            st.plotly_chart(fig_u, use_container_width=True)
        with tab2:
            fig_b = px.pie(df, values="Bill", names="Month",
                           title="Bill Amount — Monthly Share",
                           color_discrete_sequence=px.colors.sequential.Oranges_r)
            fig_b.update_traces(textposition="inside", textinfo="percent+label")
            st.plotly_chart(fig_b, use_container_width=True)
        fig = None   # already rendered above

    if fig:
        fig.update_layout(height=420, showlegend=True)
        st.plotly_chart(fig, use_container_width=True)

    # ══════════════════════════════════════════
    # 2.  RATE PER UNIT  chart
    # ══════════════════════════════════════════
    st.subheader("💡 Rate per Unit (₹/kWh)")

    if chart_type == "Bar Chart":
        fig_rate = px.bar(
            df, x="Month", y="Rate",
            title="Rate per Unit — Monthly Comparison",
            labels={"Rate": "₹/kWh"},
            color="Rate",
            color_continuous_scale="Purples",
        )

    else:  # Pie Chart
        fig_rate = px.pie(
            df, values="Rate", names="Month",
            title="Rate per Unit — Monthly Distribution",
            color_discrete_sequence=px.colors.sequential.Purples_r,
        )
        fig_rate.update_traces(textposition="inside", textinfo="percent+label")

    fig_rate.update_layout(height=380)
    st.plotly_chart(fig_rate, use_container_width=True)

    # ══════════════════════════════════════════
    # 3.  CARBON FOOTPRINT
    # ══════════════════════════════════════════
    st.subheader("🌍 Carbon Footprint")

    co2_factor  = 0.82          # kg CO2 per kWh – India grid avg
    df["CO2"]   = df["Units"] * co2_factor
    total_co2   = df["CO2"].sum()
    monthly_co2 = df["Units"].iloc[-1] * co2_factor
    trees_needed = total_co2 / 22

    c1, c2 = st.columns(2)
    with c1:
        st.metric("Total CO₂ Emitted", f"{total_co2:.0f} kg",
                  delta=f"{monthly_co2:.0f} kg this month")
    with c2:
        st.metric("Trees Needed to Offset", f"{trees_needed:.1f} trees/year")

    if chart_type == "Bar Chart":
        fig_co2 = px.bar(
            df, x="Month", y="CO2",
            title="CO₂ Emissions — Monthly Comparison",
            labels={"CO2": "CO₂ (kg)"},
            color="CO2",
            color_continuous_scale="Greens",
        )

    else:  # Pie
        fig_co2 = px.pie(
            df, values="CO2", names="Month",
            title="CO₂ Emissions — Monthly Share",
            color_discrete_sequence=px.colors.sequential.Greens_r,
        )
        fig_co2.update_traces(textposition="inside", textinfo="percent+label")

    fig_co2.update_layout(height=380)
    st.plotly_chart(fig_co2, use_container_width=True)

    # ══════════════════════════════════════════
    # 4.  NEXT MONTH PREDICTION
    # ══════════════════════════════════════════
    st.subheader("🔮 Next Month Prediction")

    growth_rate = 1.05
    last_rate   = df["Rate"].iloc[-1]
    next_units  = last_units * growth_rate
    next_bill   = next_units * last_rate
    next_co2    = next_units * co2_factor

    p1, p2, p3 = st.columns(3)
    with p1:
        st.metric("Estimated Units",  f"{next_units:.0f} kWh",    delta=f"+{next_units - last_units:.0f}")
    with p2:
        st.metric("Estimated Bill",   f"₹{next_bill:.0f}",        delta=f"+₹{next_bill - last_bill:.0f}")
    with p3:
        st.metric("Estimated CO₂",    f"{next_co2:.0f} kg",       delta=f"+{next_co2 - monthly_co2:.0f} kg")

    # Prediction visual: append a "Next" row and plot
    pred_row = pd.DataFrame([{
        "Month": "Next", "Units": next_units, "Bill": next_bill,
        "Rate": last_rate, "CO2": next_co2, "Month_Order": 12
    }])
    df_pred = pd.concat([df, pred_row], ignore_index=True)

    if chart_type == "Bar Chart":
        fig_pred = px.bar(
            df_pred, x="Month", y=["Units", "Bill"], barmode="group",
            title="Actual + Predicted Next Month",
            labels={"value": "Units (kWh) / Bill (₹)", "variable": "Metric"},
            color_discrete_map={"Units": "#00b4d8", "Bill": "#f77f00"},
        )

    else:  # Pie  – compare actual vs predicted totals
        compare_df = pd.DataFrame({
            "Category": ["Actual Total Units", "Predicted Next Month Units"],
            "Value":    [total_units, next_units],
        })
        fig_pred = px.pie(
            compare_df, values="Value", names="Category",
            title="Actual Total vs Predicted Next Month (Units)",
            color_discrete_sequence=["#00b4d8", "#f77f00"],
        )
        fig_pred.update_traces(textposition="inside", textinfo="percent+label")

    fig_pred.update_layout(height=420)
    st.plotly_chart(fig_pred, use_container_width=True)

    # ══════════════════════════════════════════
    # 5.  ALERT
    # ══════════════════════════════════════════
    st.subheader("🚨 Usage Alert")
    if last_units > 100:
        st.error(f"⚠️ HIGH USAGE ALERT: {last_units:.0f} kWh exceeds the 100 kWh safe limit!")
    else:
        st.success(f"✅ Usage is within safe limit (≤ 100 kWh). This month: {last_units:.0f} kWh")

    # ── Data Summary Table ──────────────────
    st.subheader("📋 Data Summary")
    display_df = df[["Month", "Units", "Bill", "Rate", "CO2"]].copy()
    display_df.columns = ["Month", "Units (kWh)", "Bill (₹)", "Rate (₹/kWh)", "CO₂ (kg)"]
    st.dataframe(display_df.round(1), use_container_width=True)

else:
    st.info("👆 Enter your monthly data in the sidebar and click **🔍 ANALYZE** to start!")

# ─────────────────────────────────────────
# Footer
# ─────────────────────────────────────────
st.markdown("---")
st.caption("Smart Electricity Analyzer | Carbon factor: 0.82 kg CO₂/kWh (India grid average)")
