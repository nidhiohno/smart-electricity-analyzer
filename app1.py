import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import numpy as np

# Page config
st.set_page_config(page_title="Electricity Demo", layout="wide")
st.title("⚡ Smart Electricity Analyzer Demo")
st.markdown("---")

# Initialize session state for data storage
if 'monthly_data' not in st.session_state:
    st.session_state.monthly_data = []

# Sidebar inputs
st.sidebar.header("📝 Enter Monthly Data")
month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
month = st.sidebar.selectbox("1. Month", month_names)
bill_amount = st.sidebar.number_input("2. Total Bill (₹)", min_value=0.0, value=2500.0, step=100.0)
rate_per_unit = st.sidebar.number_input("3. Rate/Unit (₹/kWh)", min_value=0.0, value=7.5, step=0.1)
units_consumed = st.sidebar.number_input("4. Units Consumed (kWh)", min_value=0.0, value=300.0, step=10.0)

# Analyze button - NO BILL VERIFICATION
if st.sidebar.button("🔍 ANALYZE", use_container_width=True):
    # Add to monthly data directly (no validation)
    st.session_state.monthly_data.append({
        'Month': month,
        'Bill': bill_amount,
        'Units': units_consumed,
        'Rate': rate_per_unit
    })

# Main dashboard
if st.session_state.monthly_data:
    df = pd.DataFrame(st.session_state.monthly_data)
    
    # Sort by month order
    month_order = {m:i for i,m in enumerate(month_names)}
    df['Month_Order'] = df['Month'].map(month_order)
    df = df.sort_values('Month_Order').reset_index(drop=True)
    
    # === KEY METRICS ===
    col1, col2, col3, col4 = st.columns(4)
    total_units = df['Units'].sum()
    total_bill = df['Bill'].sum()
    avg_rate = df['Rate'].mean()
    last_bill = df['Bill'].iloc[-1]
    last_units = df['Units'].iloc[-1]
    
    with col1:
        st.metric("Total Units", f"{total_units:.0f} kWh")
    with col2:
        st.metric("Total Bill", f"₹{total_bill:.0f}")
    with col3:
        st.metric("Avg Rate", f"₹{avg_rate:.1f}/kWh")
    with col4:
        trend = "📈 UP" if df['Units'].iloc[-1] > df['Units'].iloc[0] else "📉 DOWN"
        st.metric("Trend", trend)

    # === LINEAR GRAPH ===
    st.subheader("📊 Monthly Analysis")
    fig = px.line(df, x='Month', y=['Units', 'Bill'], 
                  markers=True,
                  title="Electricity Usage & Bill Trend",
                  labels={'value': 'Units (kWh) / Bill (₹)'})
    fig.update_traces(line=dict(width=3))
    fig.update_layout(height=400, showlegend=True)
    st.plotly_chart(fig, use_container_width=True)

    # === CARBON FOOTPRINT ===
    st.subheader("🌍 Carbon Footprint")
    co2_factor = 0.82  # kg CO2 per kWh (India grid average)
    total_co2 = total_units * co2_factor
    monthly_co2 = df['Units'].iloc[-1] * co2_factor
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total CO2", f"{total_co2:.0f} kg", 
                 delta=f"{monthly_co2:.0f} kg this month")
    with col2:
        trees_needed = total_co2 / 22  # kg CO2 absorbed per tree/year
        st.metric("Trees Equivalent", f"{trees_needed:.1f} trees/year")

    # === NEXT MONTH PREDICTION ===
    st.subheader("🔮 Next Month Estimate")
    growth_rate = 1.05  # 5% seasonal growth assumption
    last_rate = df['Rate'].iloc[-1]
    
    next_units = last_units * growth_rate
    next_bill = next_units * last_rate
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Estimated Units", f"{next_units:.0f} kWh", 
                 delta=f"+{next_units-last_units:.0f}")
    with col2:
        st.metric("Estimated Bill", f"₹{next_bill:.0f}", 
                 delta=f"+₹{next_bill-last_bill:.0f}")

    # === SIMPLE ALERT SYSTEM ===
    st.subheader("🚨 Alert")
    if last_units > 100:
        st.error(f"⚠️ HIGH USAGE ALERT: {last_units:.0f} units exceeds 100 kWh limit!")
    else:
        st.success("✅ Usage within safe limit (≤100 kWh)")

    # Data table
    st.subheader("📋 Data Summary")
    st.dataframe(df[['Month', 'Units', 'Bill', 'Rate']].round(1), 
                use_container_width=True)

else:
    st.info("👆 Enter data in sidebar and click ANALYZE to start!")

# Clear data button
if st.sidebar.button("🗑️ Clear All Data"):
    st.session_state.monthly_data = []
    st.rerun()

# Footer
st.markdown("---")
st.caption("Demo Model | Pure calculations, no ML | Carbon: 0.82kg/kWh India grid")
