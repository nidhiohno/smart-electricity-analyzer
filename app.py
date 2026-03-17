import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np


st.set_page_config(page_title="Smart Electricity Analyser", layout="centered")
st.title("⚡ Smart Electricity Analyser")

# Month order
MONTH_ORDER = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

# Session memory
if "data" not in st.session_state:
    st.session_state.data = []

# Inputs
month = st.text_input("Month (e.g. Jan, Feb, Mar)")
units_text = st.text_input("Units Consumed")
amount_text = st.text_input("Total Bill Amount (₹)")
rate_text = st.text_input("Rate per Unit (₹)")

# Analyze button
if st.button("Analyze"):

    if month.strip() == "" or units_text.strip() == "" or amount_text.strip() == "" or rate_text.strip() == "":
        st.error("Please fill all fields.")
    else:
        try:
            units = float(units_text)
            amount = float(amount_text)
            rate = float(rate_text)

            m = month.capitalize()[:3]

            if m not in MONTH_ORDER:
                st.error("Enter valid month (Jan, Feb, Mar...)")
            else:
                st.session_state.data.append([m, units])
                df = pd.DataFrame(st.session_state.data, columns=["Month", "Units"])

                # sort months
                df["Order"] = df["Month"].apply(lambda x: MONTH_ORDER.index(x))
                df = df.sort_values("Order")

                st.success("Entry added!")

                # GRAPH
                st.subheader("📈 Yearly Electricity Usage")
                fig, ax = plt.subplots()
                ax.plot(df["Month"], df["Units"], marker="o")
                ax.set_xlabel("Month")
                ax.set_ylabel("Units")
                ax.set_title("Electricity Consumption (Year)")
                st.pyplot(fig)

                # ALERT
                if units > 250:
                    st.warning("⚠️ High electricity usage!")
                else:
                    st.success("Normal usage.")

                # CARBON
                carbon = units * 0.82
                st.write(f"🌱 Carbon Emission: {carbon:.2f} kg CO₂")

                # FORECAST
                if len(df) >= 2:
                    x = np.arange(len(df))
                    y = df["Units"]
                    m1, c1 = np.polyfit(x, y, 1)
                    next_units = m1 * len(df) + c1
                    next_bill = next_units * rate

                    st.metric("Estimated Next Month Units", round(next_units, 2))
                    st.metric("Estimated Next Bill (₹)", round(next_bill, 2))

        except:
            st.error("Please enter valid numeric values.")
