import streamlit as st

MONTH_NAMES = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
MONTH_ORDER = {m: i for i, m in enumerate(MONTH_NAMES)}
CO2_FACTOR  = 0.716  # kg CO2/kWh — CEA 2023

SECURITY_QUESTIONS = [
    "What is your pet's name?",
    "What is your mother's maiden name?",
    "What was the name of your first school?",
    "What is your favourite movie?",
    "What city were you born in?",
]

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

SUPPLIERS = {
    "MSEDCL": {
        "full_name": "MSEDCL (Mahavitaran)",
        "slabs": [(100,2.90),(200,6.50),(200,8.00),(float("inf"),11.85)],
        "fixed_charge": 30, "fac": 0.20, "duty_pct": 0.16, "color": "#e74c3c",
    },
    "Tata Power": {
        "full_name": "Tata Power Mumbai",
        "slabs": [(100,3.34),(200,6.68),(200,9.29),(float("inf"),12.43)],
        "fixed_charge": 50, "fac": 0.15, "duty_pct": 0.16, "color": "#2980b9",
    },
    "Adani Electricity": {
        "full_name": "Adani Electricity Mumbai",
        "slabs": [(100,3.13),(200,6.26),(200,9.10),(float("inf"),11.97)],
        "fixed_charge": 45, "fac": 0.18, "duty_pct": 0.16, "color": "#f39c12",
    },
    "BEST": {
        "full_name": "BEST (Brihanmumbai Electric Supply)",
        "slabs": [(100,2.80),(200,5.90),(200,8.50),(float("inf"),11.20)],
        "fixed_charge": 25, "fac": 0.10, "duty_pct": 0.16, "color": "#27ae60",
    },
}

# Seasonal thresholds — realistic daily hour limits per appliance per month
#                        Jan  Feb  Mar  Apr  May  Jun  Jul  Aug  Sep  Oct  Nov  Dec
SEASONAL_THRESHOLDS = {
    "AC (1.5 ton)":     [0,   0,   2,   5,   8,   7,   4,   3,   2,   1,   0,   0  ],
    "Fan (Ceiling)":    [4,   5,   8,   12,  16,  16,  14,  14,  12,  8,   5,   4  ],
    "Water Heater (Geyser)":[1,1,  0.5, 0.3, 0,   0,   0,   0,   0.3, 0.5, 1,   1  ],
    "Refrigerator":     [24,  24,  24,  24,  24,  24,  24,  24,  24,  24,  24,  24 ],
    "Washing Machine":  [1,   1,   1,   1,   1,   1.5, 1.5, 1.5, 1,   1,   1,   1  ],
    "TV (LED 43 inch)": [4,   4,   4,   4,   4,   4,   5,   5,   4,   4,   4,   5  ],
    "LED Bulb (10W)":   [6,   6,   5,   5,   5,   5,   6,   6,   6,   6,   6,   7  ],
    "Microwave":        [1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1  ],
    "Iron":             [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5],
    "Computer/Laptop":  [6,   6,   6,   6,   6,   6,   6,   6,   6,   6,   6,   6  ],
}

# Seasonal usage multipliers for survey baseline adjustment
#                           Jan   Feb   Mar   Apr   May   Jun   Jul   Aug   Sep   Oct   Nov   Dec
SEASONAL_MULTIPLIERS = {
    "AC (1.5 ton)":        [0.1,  0.2,  0.7,  1.4,  2.0,  1.8,  1.2,  0.9,  0.7,  0.3,  0.1,  0.1],
    "Fan (Ceiling)":       [0.4,  0.5,  0.8,  1.3,  1.8,  1.6,  1.4,  1.3,  1.1,  0.8,  0.5,  0.4],
    "Water Heater (Geyser)":[1.8, 1.6,  0.8,  0.3,  0.1,  0.1,  0.2,  0.2,  0.3,  0.7,  1.4,  1.8],
    "Refrigerator":        [0.9,  0.9,  1.0,  1.1,  1.2,  1.2,  1.1,  1.0,  1.0,  1.0,  0.9,  0.9],
    "Washing Machine":     [1.0,  1.0,  1.0,  1.0,  1.0,  1.1,  1.2,  1.2,  1.0,  1.0,  1.0,  1.0],
    "TV (LED 43 inch)":    [1.1,  1.0,  1.0,  1.0,  1.0,  1.0,  1.1,  1.1,  1.0,  1.0,  1.1,  1.2],
    "LED Bulb (10W)":      [1.1,  1.0,  0.9,  0.9,  0.9,  0.9,  1.0,  1.0,  1.0,  1.0,  1.1,  1.2],
    "Microwave":           [1.0,  1.0,  1.0,  1.0,  1.0,  1.0,  1.0,  1.0,  1.0,  1.0,  1.0,  1.0],
    "Iron":                [1.0,  1.0,  1.0,  1.0,  1.0,  1.0,  1.0,  1.0,  1.0,  1.0,  1.0,  1.0],
    "Computer/Laptop":     [1.0,  1.0,  1.0,  1.0,  1.0,  1.0,  1.0,  1.0,  1.0,  1.0,  1.0,  1.0],
}

# Season-aware reduction tips per appliance
SEASONAL_TIPS = {
    "AC (1.5 ton)": {
        "summer":  "Set to 24°C + use ceiling fan. Sleep timer saves ~35 kWh/month.",
        "monsoon": "Use fan-only mode when possible — humidity makes cooling less efficient.",
        "winter":  "Switch off completely — no need this month.",
        "default": "Set to 24°C. Each degree lower adds ~6% to bill.",
    },
    "Fan (Ceiling)": {
        "summer":  "Essential — just turn off when leaving the room.",
        "monsoon": "Good for airflow. Off when room is empty.",
        "winter":  "Minimal use needed. Off in empty rooms.",
        "default": "Turn off in unoccupied rooms.",
    },
    "Water Heater (Geyser)": {
        "summer":  "Not needed — switch off MCB to avoid standby loss.",
        "monsoon": "Barely needed. Use only if required.",
        "winter":  "Switch on 15 min before use. Off immediately after.",
        "default": "Max 30 mins/day. Never leave on all day.",
    },
    "Refrigerator":     "Always-on — clean coils every 3 months, keep 3/4 full.",
    "Washing Machine":  "Full loads only. Cold water wash. Air-dry.",
    "TV (LED 43 inch)": "50% brightness saves power. Switch off at plug, not standby.",
    "LED Bulb (10W)":   "Use natural light in daytime. Group switches by room.",
    "Microwave":        "Efficient — avoid using it to keep food warm for long.",
    "Iron":             "Iron in bulk. Unplug immediately after use.",
    "Computer/Laptop":  "Enable sleep mode. Laptop uses 4× less than desktop.",
}


def calculate_bill(units, supplier="MSEDCL"):
    s = SUPPLIERS.get(supplier, SUPPLIERS["MSEDCL"])
    energy_charge, remaining = 0.0, units
    for slab_units, rate in s["slabs"]:
        if remaining <= 0: break
        billed = min(remaining, slab_units)
        energy_charge += billed * rate
        remaining -= billed
    fac   = units * s["fac"]
    fixed = s["fixed_charge"]
    duty  = (energy_charge + fac + fixed) * s["duty_pct"]
    return {
        "energy_charge":    round(energy_charge, 2),
        "fac":              round(fac, 2),
        "fixed_charge":     fixed,
        "electricity_duty": round(duty, 2),
        "total":            round(energy_charge + fac + fixed + duty, 2),
    }


def scale_hours_to_units(avg_hours, actual_units):
    """Scale appliance hours so total kWh matches actual_units."""
    if not avg_hours or actual_units == 0:
        return avg_hours
    raw_total = sum(
        (APPLIANCES[a] * float(avg_hours.get(a, 0)) * 30) / 1000
        for a in APPLIANCES if float(avg_hours.get(a, 0)) > 0
    )
    if raw_total == 0:
        return avg_hours
    scale = actual_units / raw_total
    return {a: round(float(avg_hours.get(a, 0)) * scale, 4) for a in avg_hours}


def apply_seasonal_multipliers(base_hours: dict, month_name: str) -> dict:
    """
    Adjust survey baseline using seasonal weights.
    Keeps a 10% floor so unusually high bills can surface any appliance.
    Always call scale_hours_to_units() after this to anchor to the actual bill.
    """
    month_idx = MONTH_ORDER.get(month_name, 0)
    scaled = {}
    for appliance, hrs in base_hours.items():
        base = float(hrs)
        if base == 0:
            scaled[appliance] = 0.0
            continue
        mults  = SEASONAL_MULTIPLIERS.get(appliance)
        factor = max(mults[month_idx], 0.1) if mults else 1.0
        scaled[appliance] = round(base * factor, 4)
    return scaled


def get_seasonal_tip(appliance: str, month_name: str) -> str:
    month_idx  = MONTH_ORDER.get(month_name, 0)
    is_summer  = month_idx in [2,3,4,5]
    is_monsoon = month_idx in [6,7,8]
    is_winter  = month_idx in [10,11,0,1]
    tips = SEASONAL_TIPS.get(appliance)
    if isinstance(tips, dict):
        if is_summer:  return tips.get("summer",  tips["default"])
        if is_monsoon: return tips.get("monsoon", tips["default"])
        if is_winter:  return tips.get("winter",  tips["default"])
        return tips["default"]
    return tips or "Reduce usage where possible."


def get_user_survey_hours(username):
    from db import has_completed_survey
    return st.session_state.get("avg_survey_hours") or has_completed_survey(username) or {}
