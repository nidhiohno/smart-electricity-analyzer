import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
from datetime import datetime
import re, io

try:
    import pdfplumber
    PDF_OK = True
except ImportError:
    PDF_OK = False

from db import (
    init_db, verify_user, register_user, load_supplier, save_supplier,
    get_security_question, verify_security_answer, reset_password,
    has_completed_survey, save_user_survey,
    save_entry, load_user_data, save_appliance_data,
    load_appliance_data, load_all_appliance_data,
)
from billing import (
    SUPPLIERS, APPLIANCES, MONTH_NAMES, MONTH_ORDER, CO2_FACTOR,
    SECURITY_QUESTIONS, SEASONAL_THRESHOLDS,
    calculate_bill, scale_hours_to_units,
    apply_seasonal_multipliers, get_seasonal_tip, get_user_survey_hours,
)
from ui import inject_styles, section_header, alert_card, plotly_dark

# ── Setup ─────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="VoltIQ", page_icon="⚡", layout="wide")
inject_styles()
init_db()

for key, val in [
    ("logged_in",False),("username",""),("auth_page","login"),("page","input"),
    ("forgot_step",1),("forgot_username",""),("extracted",{}),("supplier","MSEDCL"),
    ("just_saved",False),("saved_month",""),("saved_units",0.0),("saved_bill",0.0),
    ("saved_year",datetime.now().year),("saved_hours",{}),
    ("show_onboarding_survey",False),("avg_survey_hours",{}),
]:
    if key not in st.session_state:
        st.session_state[key] = val


# ══════════════════════════════════════════════════════════════════════════════
# AUTH PAGE
# ══════════════════════════════════════════════════════════════════════════════
if not st.session_state.logged_in:
    st.markdown("""
    <div style="min-height:180px;display:flex;flex-direction:column;align-items:center;
      justify-content:center;padding:48px 0 32px;position:relative;">
      <div style="position:absolute;width:300px;height:300px;border-radius:50%;
        background:radial-gradient(circle,rgba(56,189,248,.12),transparent 70%);
        top:50%;left:50%;transform:translate(-50%,-50%);pointer-events:none;"></div>
      <div style="font-size:56px;margin-bottom:10px;filter:drop-shadow(0 0 20px rgba(56,189,248,.5));">⚡</div>
      <div style="font-family:'Syne',sans-serif;font-size:42px;font-weight:800;
        background:linear-gradient(135deg,#38bdf8,#0ea5e9,#38bdf8);
        -webkit-background-clip:text;-webkit-text-fill-color:transparent;
        background-clip:text;letter-spacing:3px;line-height:1;">VOLTIQ</div>
      <div style="font-size:11px;color:#4b5563;margin-top:10px;letter-spacing:3px;">
        SMART ELECTRICITY ANALYZER · MAHARASHTRA</div>
    </div>""", unsafe_allow_html=True)

    _, col, _ = st.columns([1,1.2,1])
    with col:
        st.markdown('''<div style="background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);
            border-radius:24px;padding:36px 40px;backdrop-filter:blur(40px);
            box-shadow:0 24px 64px rgba(0,0,0,.5),inset 0 1px 0 rgba(255,255,255,.08);">
        ''', unsafe_allow_html=True)

        if st.session_state.auth_page == "login":
            st.markdown("### 🔐 Login")
            u = st.text_input("Username", key="lu")
            p = st.text_input("Password", type="password", key="lp")
            if st.button("Login", use_container_width=True):
                if not u or not p:
                    st.error("Please enter both fields.")
                elif verify_user(u, p):
                    st.session_state.logged_in = True
                    st.session_state.username  = u
                    st.session_state.supplier  = load_supplier(u)
                    st.session_state.page      = "input"
                    survey = has_completed_survey(u)
                    st.session_state.show_onboarding_survey = survey is None
                    st.session_state.avg_survey_hours       = survey or {}
                    st.rerun()
                else:
                    st.error("Invalid username or password.")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Create Account", use_container_width=True):
                    st.session_state.auth_page = "signup"; st.rerun()
            with c2:
                if st.button("Forgot Password?", use_container_width=True):
                    st.session_state.auth_page = "forgot"; st.rerun()

        elif st.session_state.auth_page == "signup":
            st.markdown("### 📝 Create Account")
            u  = st.text_input("Username", key="su")
            p  = st.text_input("Password", type="password", key="sp")
            cp = st.text_input("Confirm Password", type="password", key="sc")
            q  = st.selectbox("Security Question", SECURITY_QUESTIONS)
            a  = st.text_input("Your Answer", key="sa")
            if st.button("Create Account", use_container_width=True):
                if not u or not p or not a: st.error("Fill in all fields.")
                elif len(p) < 4: st.warning("Password must be at least 4 characters.")
                elif p != cp: st.error("Passwords do not match.")
                elif register_user(u, p, q, a):
                    st.success("Account created! Please log in.")
                    st.session_state.auth_page = "login"; st.rerun()
                else: st.error("Username already exists.")
            if st.button("Back to Login", use_container_width=True):
                st.session_state.auth_page = "login"; st.rerun()

        elif st.session_state.auth_page == "forgot":
            st.markdown("### 🔑 Reset Password")
            step = st.session_state.forgot_step
            if step == 1:
                fu = st.text_input("Username", key="fu")
                if st.button("Next", use_container_width=True):
                    if get_security_question(fu):
                        st.session_state.forgot_username = fu
                        st.session_state.forgot_step = 2; st.rerun()
                    else: st.error("Username not found.")
            elif step == 2:
                st.info(f"Question: {get_security_question(st.session_state.forgot_username)}")
                ans = st.text_input("Your Answer", key="fa")
                if st.button("Verify", use_container_width=True):
                    ok, _ = verify_security_answer(st.session_state.forgot_username, ans)
                    if ok: st.session_state.forgot_step = 3; st.rerun()
                    else: st.error("Incorrect answer.")
            elif step == 3:
                np_ = st.text_input("New Password", type="password", key="np")
                cp_ = st.text_input("Confirm", type="password", key="cp")
                if st.button("Reset Password", use_container_width=True):
                    if len(np_) < 4: st.warning("Min 4 characters.")
                    elif np_ != cp_: st.error("Passwords do not match.")
                    else:
                        reset_password(st.session_state.forgot_username, np_)
                        st.success("Password reset! Please log in.")
                        st.session_state.forgot_step = 1
                        st.session_state.auth_page = "login"; st.rerun()
            if st.button("Back to Login", use_container_width=True):
                st.session_state.auth_page = "login"
                st.session_state.forgot_step = 1; st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()


# ══════════════════════════════════════════════════════════════════════════════
# NAV BAR
# ══════════════════════════════════════════════════════════════════════════════
sc = SUPPLIERS.get(st.session_state.supplier, SUPPLIERS["MSEDCL"])["color"]
sn = SUPPLIERS.get(st.session_state.supplier, SUPPLIERS["MSEDCL"])["full_name"]
st.markdown(f'''
<div style="display:flex;align-items:center;justify-content:space-between;
  background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.07);
  padding:14px 28px;border-radius:20px;margin-bottom:20px;backdrop-filter:blur(20px);
  box-shadow:0 4px 32px rgba(0,0,0,.4),inset 0 1px 0 rgba(255,255,255,.06);">
  <div style="display:flex;align-items:center;gap:14px;">
    <span style="font-size:26px;filter:drop-shadow(0 0 10px rgba(56,189,248,.6));">⚡</span>
    <div>
      <div style="font-family:'Syne',sans-serif;font-size:20px;font-weight:800;
        background:linear-gradient(135deg,#38bdf8,#0ea5e9);-webkit-background-clip:text;
        -webkit-text-fill-color:transparent;background-clip:text;letter-spacing:1.5px;">VOLTIQ</div>
      <div style="font-size:10px;color:#4b5563;letter-spacing:1px;">Smart Electricity Analyzer</div>
    </div>
  </div>
  <div style="display:flex;align-items:center;gap:10px;">
    <div style="font-size:11px;background:{sc}18;border:1px solid {sc}44;
      padding:5px 14px;border-radius:20px;color:{sc};font-weight:600;">⚡ {sn}</div>
    <div style="font-size:11px;background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);
      padding:5px 14px;border-radius:20px;color:#6b7280;">👤 {st.session_state.username}</div>
  </div>
</div>''', unsafe_allow_html=True)

n1, n2, n3 = st.columns(3)
with n1:
    if st.button("📥 Enter Data", use_container_width=True,
                 type="primary" if st.session_state.page=="input" else "secondary"):
        st.session_state.page="input"; st.session_state.just_saved=False; st.rerun()
with n2:
    if st.button("📊 Dashboard", use_container_width=True,
                 type="primary" if st.session_state.page=="dashboard" else "secondary"):
        st.session_state.page="dashboard"; st.session_state.just_saved=False; st.rerun()
with n3:
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.logged_in=False; st.session_state.username=""; st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# ONBOARDING SURVEY
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.get("show_onboarding_survey"):
    st.markdown('''<div style="text-align:center;padding:20px 0 8px;">
      <div style="font-size:44px;margin-bottom:8px;">👋</div>
      <div style="font-family:'Syne',sans-serif;font-size:28px;font-weight:800;
        background:linear-gradient(135deg,#38bdf8,#0ea5e9);-webkit-background-clip:text;
        -webkit-text-fill-color:transparent;background-clip:text;">Welcome to VoltIQ!</div>
      <div style="font-size:13px;color:#6b7280;margin-top:6px;">Set up your appliance profile</div>
    </div>''', unsafe_allow_html=True)

    st.markdown("#### 🏠 Average Appliance Usage (hours/day)")
    st.caption("Enter 0 if you don't have an appliance.")
    hrs = {}
    cols = st.columns(2)
    for i, (app, w) in enumerate(APPLIANCES.items()):
        with cols[i%2]:
            hrs[app] = st.number_input(f"{app} ({w}W)", min_value=0.0, max_value=24.0,
                                       value=0.0, step=0.5, key=f"ob_{i}")
    total = sum((APPLIANCES[a]*hrs[a]*30)/1000 for a in APPLIANCES if hrs[a]>0)
    if total > 0:
        est = calculate_bill(total, st.session_state.supplier)["total"]
        st.info(f"📊 Estimated monthly: **{total:.1f} kWh** | **Rs {est:.0f}**")
    cs, csk = st.columns([3,1])
    with cs:
        if st.button("✅ Save & Continue", use_container_width=True, key="sv_ob"):
            save_user_survey(st.session_state.username, hrs)
            st.session_state.avg_survey_hours       = hrs
            st.session_state.show_onboarding_survey = False
            st.success("Saved!"); st.rerun()
    with csk:
        if st.button("Skip", use_container_width=True, key="sk_ob"):
            st.session_state.show_onboarding_survey = False; st.rerun()
    st.stop()


# ══════════════════════════════════════════════════════════════════════════════
# ENTER DATA PAGE
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.page == "input":
    section_header("📥", "Enter Monthly Data", "Record your monthly electricity bill")

    c1, c2 = st.columns([2,2])
    with c1:
        sup_list = list(SUPPLIERS.keys())
        idx = sup_list.index(st.session_state.supplier) if st.session_state.supplier in sup_list else 0
        sel = st.selectbox("⚡ Supplier", sup_list, index=idx, key="sup_sel",
                           format_func=lambda x: SUPPLIERS[x]["full_name"])
        if sel != st.session_state.supplier:
            st.session_state.supplier = sel; save_supplier(st.session_state.username, sel)
    with c2:
        sup = SUPPLIERS[st.session_state.supplier]
        st.markdown(f"""<div style="background:{sup['color']}22;border:2px solid {sup['color']};
            padding:10px 14px;border-radius:8px;margin-top:4px;">
            <b style="color:{sup['color']};font-size:13px;">{sup['full_name']}</b><br>
            <span style="font-size:11px;color:#9ca3af;">
            Slabs: Rs {sup['slabs'][0][1]} / {sup['slabs'][1][1]} / {sup['slabs'][2][1]} / {sup['slabs'][3][1]} per unit
            </span></div>""", unsafe_allow_html=True)

    st.markdown("---")
    sel_year = int(st.number_input("📅 Year", min_value=2000, max_value=2100,
                                   value=datetime.now().year, step=1, key="inp_yr"))
    manual_tab, upload_tab = st.tabs(["✏️ Manual Input", "📄 Upload Bill"])

    # ── Manual input ──
    with manual_tab:
        mc1, mc2 = st.columns(2)
        with mc1: month = st.selectbox("Month", MONTH_NAMES, key="m_month")
        with mc2: units = st.number_input("Units Consumed (kWh)", min_value=0.0, value=0.0,
                                          step=10.0, key="m_units")
        if units > 0:
            p = calculate_bill(units, st.session_state.supplier)
            bc1,bc2,bc3,bc4 = st.columns(4)
            with bc1: st.metric("Energy", f"Rs {p['energy_charge']}")
            with bc2: st.metric("FAC", f"Rs {p['fac']}")
            with bc3: st.metric("Fixed+Duty", f"Rs {p['fixed_charge']+p['electricity_duty']:.0f}")
            with bc4: st.metric("Total", f"Rs {p['total']}")

        if st.button("Save & Analyze", use_container_width=True, key="m_save"):
            if units == 0: st.error("Please enter units consumed.")
            else:
                bd   = calculate_bill(units, st.session_state.supplier)
                rate = round(bd["total"]/units, 2)
                save_entry(st.session_state.username, sel_year, month, units, bd["total"], rate)
                survey  = get_user_survey_hours(st.session_state.username)
                seasonal = apply_seasonal_multipliers(survey, month)
                app_hrs  = scale_hours_to_units(seasonal, units)
                save_appliance_data(st.session_state.username, sel_year, month, app_hrs)
                st.session_state.update(dict(just_saved=True, saved_month=month,
                    saved_units=units, saved_bill=bd["total"],
                    saved_year=sel_year, saved_hours=app_hrs))
                st.rerun()

    # ── Upload bill ──
    with upload_tab:
        st.info("📌 PDF only. For scanned/Marathi bills use Manual Input.")
        uf = st.file_uploader("Choose PDF", type=["pdf","jpg","jpeg","png"], key="uf")
        if uf:
            if uf.type in ("image/jpeg","image/png"):
                st.warning("⚠️ Images can't be auto-extracted. Upload PDF or use Manual Input.")
            elif not PDF_OK:
                st.error("pdfplumber not installed. Add to requirements.txt.")
            else:
                if st.button("Extract Data", use_container_width=True):
                    with st.spinner("Reading bill..."):
                        try:
                            text = ""
                            with pdfplumber.open(io.BytesIO(uf.read())) as pdf:
                                for pg in pdf.pages: text += pg.extract_text() or ""
                            ext = {}
                            for pat in [r"Units\s*Consumed[:\s]+([\d,]+\.?\d*)",
                                        r"Net\s*Units[:\s]+([\d,]+\.?\d*)",
                                        r"Energy\s*Consumed[:\s]+([\d,]+\.?\d*)",
                                        r"Total\s*Units[:\s]+([\d,]+\.?\d*)"]:
                                m = re.search(pat, text, re.IGNORECASE)
                                if m: ext["units"] = m.group(1).replace(",",""); break
                            mm = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)", text, re.IGNORECASE)
                            if mm:
                                mmap = {v.lower():v[:3] for v in ["January","February","March","April","May","June","July","August","September","October","November","December"]}
                                ext["month"] = mmap.get(mm.group(1).lower(), mm.group(1)[:3].capitalize())
                            ym = re.search(r"(202[0-9]|203[0-9])", text)
                            if ym: ext["year"] = ym.group(1)
                            if ext.get("units"):
                                st.session_state.extracted = ext
                                st.success(f"✅ Units: {ext.get('units')} | Month: {ext.get('month','?')} | Year: {ext.get('year','?')}")
                                st.rerun()
                            else:
                                st.warning("Could not extract — fill manually below.")
                                st.session_state.extracted = {"units":"0","month":MONTH_NAMES[datetime.now().month-1],"year":str(datetime.now().year)}
                                st.rerun()
                        except Exception as e:
                            st.error(f"Could not read bill: {e}")

        if st.session_state.extracted:
            ext = st.session_state.extracted
            st.markdown("---"); st.markdown("#### ✅ Confirm Extracted Values")
            try: du = float(ext.get("units",0))
            except: du = 0.0
            em = ext.get("month", MONTH_NAMES[0])
            if em not in MONTH_NAMES: em = MONTH_NAMES[0]
            ec1,ec2 = st.columns(2)
            with ec1: cu = st.number_input("Units (kWh)", min_value=0.0, value=du, step=1.0, key="eu")
            with ec2: cm = st.selectbox("Month", MONTH_NAMES, index=MONTH_NAMES.index(em), key="em")
            if cu > 0:
                p2 = calculate_bill(cu, st.session_state.supplier)
                st.info(f"Estimated Bill: **Rs {p2['total']}**")
            if st.button("Save & Analyze", use_container_width=True, key="u_save"):
                if cu == 0: st.error("Units cannot be zero.")
                else:
                    bd   = calculate_bill(cu, st.session_state.supplier)
                    rate = round(bd["total"]/cu, 2)
                    save_entry(st.session_state.username, sel_year, cm, cu, bd["total"], rate)
                    survey   = get_user_survey_hours(st.session_state.username)
                    seasonal = apply_seasonal_multipliers(survey, cm)
                    app_hrs  = scale_hours_to_units(seasonal, cu)
                    save_appliance_data(st.session_state.username, sel_year, cm, app_hrs)
                    st.session_state.update(dict(just_saved=True, saved_month=cm,
                        saved_units=cu, saved_bill=bd["total"],
                        saved_year=sel_year, saved_hours=app_hrs, extracted={}))
                    st.rerun()

    # ── Post-save analysis ──
    if st.session_state.get("just_saved"):
        sm, su, sb, sy = (st.session_state.saved_month, st.session_state.saved_units,
                          st.session_state.saved_bill,  st.session_state.saved_year)
        sh       = st.session_state.get("saved_hours", {})
        supplier = st.session_state.supplier

        st.markdown("---")
        st.markdown(f'''<div style="background:linear-gradient(135deg,rgba(16,185,129,.15),rgba(5,150,105,.08));
          border:1px solid rgba(16,185,129,.3);border-radius:16px;padding:20px 24px;margin:16px 0;
          display:flex;align-items:center;gap:14px;">
          <div style="font-size:28px;">✅</div>
          <div><div style="font-family:'Syne',sans-serif;font-size:18px;font-weight:700;color:#34d399;">
            {sm} {sy} — Saved!</div>
            <div style="font-size:12px;color:#6b7280;">Your electricity data has been recorded.</div>
          </div></div>''', unsafe_allow_html=True)

        c1,c2,c3 = st.columns(3)
        with c1: st.metric("Units", f"{su:.0f} kWh")
        with c2: st.metric("Bill",  f"Rs {sb:.0f}")
        with c3: st.metric("Rate",  f"Rs {round(sb/su,2) if su else 0}/kWh")

        # Slab indicator
        slab_map = [(100,"#27ae60",f"✅ Slab 1 — Rs {SUPPLIERS[supplier]['slabs'][0][1]}/unit"),
                    (300,"#f1c40f",f"🟡 Slab 2 — Rs {SUPPLIERS[supplier]['slabs'][1][1]}/unit"),
                    (500,"#0284c7",f"🟠 Slab 3 — Rs {SUPPLIERS[supplier]['slabs'][2][1]}/unit"),
                    (float("inf"),"#e74c3c",f"🔴 Slab 4 — Rs {SUPPLIERS[supplier]['slabs'][3][1]}/unit")]
        sc_, msg = next((c,m) for lim,c,m in slab_map if su<=lim)
        st.markdown(f'''<div style="background:{sc_}18;border:1px solid {sc_}44;border-radius:14px;
          padding:12px 18px;margin:10px 0;display:flex;align-items:center;gap:10px;">
          <div style="width:8px;height:8px;border-radius:50%;background:{sc_};flex-shrink:0;"></div>
          <div style="font-size:14px;color:#f9fafb;"><b style="color:{sc_};">{msg}</b></div>
        </div>''', unsafe_allow_html=True)

        # Prediction
        all_rows = load_user_data(st.session_state.username, sy)
        all_df = pd.DataFrame(all_rows, columns=["Month","Units","Bill","Rate"]) if all_rows else pd.DataFrame()
        if not all_df.empty:
            all_df["_o"] = all_df["Month"].map(MONTH_ORDER)
            all_df = all_df.sort_values("_o").drop(columns="_o").reset_index(drop=True)

        avg_survey = get_user_survey_hours(st.session_state.username)
        if not all_df.empty and len(all_df) >= 2:
            w  = np.array([0.5,0.3,0.2]) if len(all_df)>=3 else np.array([0.6,0.4])
            ln = all_df["Units"].iloc[-min(len(all_df),3):].values[::-1]
            nu = round(float(np.dot(w[:len(ln)], ln[:len(w)])), 1)
        elif avg_survey:
            sv = sum((APPLIANCES[a]*float(avg_survey.get(a,0))*30)/1000
                     for a in APPLIANCES if float(avg_survey.get(a,0))>0)
            nu = round(su*0.6+sv*0.4,1) if sv>0 else round(su*1.05,1)
        else:
            nu = round(su*1.05, 1)

        nb = calculate_bill(nu, supplier)["total"]
        nm = MONTH_NAMES[(MONTH_NAMES.index(sm)+1)%12]

        st.markdown("---")
        section_header("🔮","Next Month Prediction","Based on your usage history")
        n1,n2,n3 = st.columns(3)
        with n1: st.metric("Predicted Units", f"{nu:.0f} kWh", delta=f"{nu-su:+.0f} vs now")
        with n2: st.metric("Predicted Bill",  f"Rs {nb:.0f}",  delta=f"Rs {nb-sb:+.0f} vs now")
        with n3: st.metric("Next Month", nm)

        # Appliance alerts
        if not sh: sh = load_appliance_data(st.session_state.username, sy, sm)
        if sh:
            st.markdown("---")
            section_header("🏠",f"Appliance Alerts — {sm} {sy}","Seasonal limits · one fix per appliance")
            month_idx = MONTH_ORDER.get(sm, 0)
            alert_data = []
            for app, w in APPLIANCES.items():
                hrs = float(sh.get(app, 0))
                if hrs == 0: continue
                limit  = SEASONAL_THRESHOLDS.get(app, [8]*12)[month_idx]
                cu_    = round((w*hrs*30)/1000, 2)
                cc_    = round(calculate_bill(cu_, supplier)["total"], 0)
                rh_    = min(hrs, limit) if limit > 0 else 0
                ru_    = round((w*rh_*30)/1000, 2)
                saving = round(sb - calculate_bill(su - cu_ + ru_, supplier)["total"], 0)
                tip    = get_seasonal_tip(app, sm)
                if limit == 0 or hrs > limit:
                    st_, bg_, bd_ = "🔴 HIGH", "rgba(231,76,60,.12)", "#e74c3c"
                elif hrs > limit * 0.75:
                    st_, bg_, bd_ = "🟡 MODERATE", "rgba(241,196,15,.10)", "#f1c40f"
                else:
                    st_, bg_, bd_ = "🟢 OK", "rgba(39,174,96,.10)", "#27ae60"
                alert_data.append(dict(app=app, hrs=hrs, limit=limit, cu=cu_, cc=cc_,
                                       saving=saving, rh=rh_, status=st_, bg=bg_, bd=bd_, tip=tip))

            if alert_data:
                # Chart
                cdf = pd.DataFrame([{"Appliance":r["app"],"Hrs/Day":r["hrs"],"Limit":r["limit"]} for r in alert_data])
                fig = px.bar(cdf, x="Appliance", y=["Hrs/Day","Limit"], barmode="group",
                             title=f"Usage vs Seasonal Limit — {sm}",
                             color_discrete_map={"Hrs/Day":"#e74c3c","Limit":"#2ecc71"},
                             labels={"value":"Hours/Day","variable":""}, template="plotly_dark")
                fig.update_layout(height=340, xaxis_tickangle=-20,
                                  paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig, use_container_width=True)

                # Savings banner
                total_saving = sum(r["saving"] for r in alert_data if r["saving"]>0)
                if total_saving > 0:
                    st.markdown(f'''<div style="background:linear-gradient(135deg,rgba(16,185,129,.2),rgba(5,150,105,.1));
                      border:1px solid rgba(16,185,129,.3);border-radius:16px;padding:18px 24px;
                      text-align:center;margin:12px 0;">
                      <div style="font-size:12px;color:#6ee7b7;text-transform:uppercase;letter-spacing:1.5px;font-weight:600;">POTENTIAL SAVINGS</div>
                      <div style="font-family:'Syne',sans-serif;font-size:30px;font-weight:800;color:#34d399;">Rs {total_saving:.0f}/month</div>
                    </div>''', unsafe_allow_html=True)

                # Per-appliance cards — short + actionable
                for r in sorted(alert_data, key=lambda x: x["saving"], reverse=True):
                    if r["limit"] == 0:
                        action = f"Not needed this month. → Switch off saves <b>Rs {r['saving']:.0f}</b>."
                    elif r["saving"] > 0:
                        action = f"Reduce to {r['rh']}h/day → Save <b>Rs {r['saving']:.0f}</b>. {r['tip']}"
                    else:
                        action = f"✅ Within limit. {r['tip']}"
                    st.markdown(f'''<div style="background:{r['bg']};border-left:4px solid {r['bd']};
                      padding:11px 16px;border-radius:10px;margin:6px 0;font-size:13px;color:#f9fafb;">
                      <div style="display:flex;justify-content:space-between;margin-bottom:4px;">
                        <b>{r['app']}</b>
                        <span style="color:{r['bd']};font-size:12px;">{r['status']} · {r['hrs']}h/day (limit {r['limit']}h)</span>
                      </div>
                      {action}
                    </div>''', unsafe_allow_html=True)

        # Bill alerts
        st.markdown("---")
        section_header("💡","Bill Alerts","Savings opportunities for next month")
        du, db_ = nu-su, nb-sb
        tc_ = "#ef4444" if du>0 else "#10b981"
        st.markdown(f'''<div style="border:1px solid rgba(255,255,255,.08);border-left:4px solid {tc_};
          border-radius:14px;padding:16px 20px;margin:10px 0;">
          <div style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">NEXT MONTH FORECAST</div>
          <div style="font-size:20px;font-weight:800;color:#f9fafb;font-family:'Syne',sans-serif;">
            {"📈" if du>0 else "📉"} {nu:.0f} kWh
            <span style="font-size:13px;color:{tc_};font-weight:500;margin-left:8px;">{du:+.0f} kWh</span>
          </div>
          <div style="font-size:13px;color:#9ca3af;margin-top:4px;">
            Estimated bill: <b style="color:#38bdf8;">Rs {nb:.0f}</b>
            <span style="color:{tc_};"> ({db_:+.0f})</span>
          </div></div>''', unsafe_allow_html=True)

        if su > 500:
            s = round(sb - calculate_bill(500,supplier)["total"], 0)
            alert_card("rgba(239,68,68,.12)","#ef4444",
                f"🔴 <b>Slab 4</b> — Reduce by {su-500:.0f} kWh next month → Save <b>Rs {s:.0f}</b>. Raise AC to 24°C.")
        elif su > 300:
            s = round(sb - calculate_bill(300,supplier)["total"], 0)
            alert_card("rgba(249,115,22,.12)","#f97316",
                f"🟠 <b>Slab 3</b> — Reduce by {su-300:.0f} kWh → Save <b>Rs {s:.0f}</b>. Full loads only + unplug standby.")
        elif su > 100:
            s = round(sb - calculate_bill(100,supplier)["total"], 0)
            alert_card("rgba(234,179,8,.12)","#eab308",
                f"🟡 <b>Slab 2</b> — Reduce by {su-100:.0f} kWh → Save <b>Rs {s:.0f}</b>. Off fans in empty rooms.")
        else:
            alert_card("rgba(16,185,129,.12)","#10b981",
                f"✅ <b>Slab 1</b> — Great! Keep usage under 100 kWh.")
        if nu > su*1.15:
            alert_card("rgba(56,189,248,.12)","#38bdf8",
                f"🚨 <b>Spike predicted</b> +{nu-su:.0f} kWh next month. Check seasonal appliance use.")

        # Carbon footprint
        st.markdown("---")
        section_header("🌍","Carbon Footprint","Your environmental impact")
        co2 = su * CO2_FACTOR
        cf1,cf2 = st.columns(2)
        with cf1: st.metric("CO2 This Month", f"{co2:.1f} kg")
        with cf2: st.metric("Trees Needed",   f"{co2/22:.2f} trees/year")
        st.caption("CEA 2023 grid emission factor: 0.716 kg CO₂/kWh")

        if st.button("View Yearly Dashboard →", use_container_width=True):
            st.session_state.page="dashboard"; st.session_state.just_saved=False; st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# DASHBOARD PAGE
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "dashboard":
    sup_info = SUPPLIERS.get(st.session_state.supplier, SUPPLIERS["MSEDCL"])
    section_header("📊","Yearly Dashboard", f"{sup_info['full_name']}")

    sel_year = int(st.number_input("Select Year", min_value=2000, max_value=2100,
                                   value=st.session_state.get("dash_year", datetime.now().year),
                                   step=1, key="dash_year"))
    rows = load_user_data(st.session_state.username, sel_year)

    if rows:
        df = pd.DataFrame(rows, columns=["Month","Units","Bill","Rate"])
        df["_o"] = df["Month"].map(MONTH_ORDER)
        df = df.sort_values("_o").drop(columns="_o").reset_index(drop=True)
        total_units, total_bill = df["Units"].sum(), df["Bill"].sum()
        avg_rate = df["Rate"].mean()
        supplier = st.session_state.supplier

        st.markdown(f'<div style="font-size:13px;color:#6b7280;font-weight:600;text-transform:uppercase;letter-spacing:1px;margin-bottom:16px;">{sel_year} · {len(df)}/12 MONTHS</div>', unsafe_allow_html=True)
        d1,d2,d3,d4 = st.columns(4)
        with d1: st.metric("Total Units", f"{total_units:.0f} kWh")
        with d2: st.metric("Total Bill",  f"Rs {total_bill:.0f}")
        with d3: st.metric("Avg Rate",    f"Rs {avg_rate:.2f}/kWh")
        with d4: st.metric("Trend", "📈 UP" if df["Units"].iloc[-1]>df["Units"].iloc[0] else "📉 DOWN")

        csv = df[["Month","Units","Bill","Rate"]].copy(); csv.insert(0,"Year",sel_year)
        st.download_button("⬇️ Export CSV", csv.to_csv(index=False).encode(),
                           f"voltiq_{st.session_state.username}_{sel_year}.csv","text/csv")
        st.markdown("---")

        # ── Line chart ──
        section_header("📈","Daily Consumption","Estimated from monthly totals")
        dr = []
        for _, row in df.iterrows():
            mi  = MONTH_ORDER[row["Month"]]+1
            dim = pd.Period(f"{sel_year}-{mi:02d}").days_in_month
            da  = row["Units"]/dim
            rng = np.random.default_rng(mi*7)
            ns  = rng.normal(0, da*0.1, dim)
            dr += [{"Date":f"{row['Month']} {d:02d}","Units":round(max(0.1,da+ns[d-1]),2),"Month":row["Month"]} for d in range(1,dim+1)]
        fig_l = px.line(pd.DataFrame(dr), x="Date", y="Units", color="Month",
                        title=f"Estimated Daily Consumption ({sel_year})",
                        labels={"Units":"Units (kWh)"}, template="plotly_dark")
        fig_l.update_traces(line=dict(width=1.5))
        fig_l.update_layout(height=400, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        fig_l.update_xaxes(showticklabels=False)

        # Annotations
        avg_u   = df["Units"].mean()
        pk      = df.loc[df["Units"].idxmax()]
        lw      = df.loc[df["Units"].idxmin()]
        pk_d    = pk["Units"] / pd.Period(f"{sel_year}-{MONTH_ORDER[pk['Month']]+1:02d}").days_in_month
        lw_d    = lw["Units"] / pd.Period(f"{sel_year}-{MONTH_ORDER[lw['Month']]+1:02d}").days_in_month
        fig_l.add_annotation(x=f"{pk['Month']} 15", y=pk_d,
            text=f"📈 Peak: {pk['Month']} ({pk['Units']:.0f} kWh)",
            showarrow=True, arrowhead=2, arrowcolor="#ef4444",
            bgcolor="#ef444433", bordercolor="#ef4444", borderwidth=1,
            font=dict(color="#fca5a5",size=11), ax=0, ay=-40)
        fig_l.add_annotation(x=f"{lw['Month']} 15", y=lw_d,
            text=f"📉 Lowest: {lw['Month']} ({lw['Units']:.0f} kWh)",
            showarrow=True, arrowhead=2, arrowcolor="#10b981",
            bgcolor="#10b98133", bordercolor="#10b981", borderwidth=1,
            font=dict(color="#6ee7b7",size=11), ax=0, ay=40)
        for _, sr in df[df["Units"]>avg_u*1.3].iterrows():
            if sr["Month"]==pk["Month"]: continue
            sd = sr["Units"]/pd.Period(f"{sel_year}-{MONTH_ORDER[sr['Month']]+1:02d}").days_in_month
            fig_l.add_annotation(x=f"{sr['Month']} 15", y=sd,
                text=f"⚠️ +{((sr['Units']/avg_u-1)*100):.0f}%",
                showarrow=True, arrowhead=2, arrowcolor="#f59e0b",
                bgcolor="#f59e0b33", bordercolor="#f59e0b", borderwidth=1,
                font=dict(color="#fde68a",size=11), ax=0, ay=-50)
        st.plotly_chart(fig_l, use_container_width=True)
        st.caption("⚠️ Daily values simulated from monthly totals — not actual meter readings.")

        # Line alerts
        is_summer_pk = MONTH_ORDER.get(pk["Month"],0) in [2,3,4,5]
        if pk["Units"] > avg_u*1.5:
            tip = "Set AC to 24°C + sleep timer." if is_summer_pk else "Cut geyser/heater to 30 mins/day."
            alert_card("rgba(239,68,68,.12)","#ef4444",
                f"🔴 <b>{pk['Month']}</b> peak ({pk['Units']:.0f} kWh, {((pk['Units']/avg_u-1)*100):.0f}% above avg). → {tip}")
        elif pk["Units"] > avg_u*1.3:
            alert_card("rgba(249,115,22,.12)","#f97316",
                f"🟠 <b>{pk['Month']}</b> high ({pk['Units']:.0f} kWh). → Target under {avg_u*1.1:.0f} kWh next {pk['Month']}.")
        for _, sr in df[df["Units"]>avg_u*1.3].iterrows():
            if sr["Month"]==pk["Month"]: continue
            alert_card("rgba(245,158,11,.12)","#f59e0b",
                f"⚠️ <b>{sr['Month']}</b> spiked +{((sr['Units']/avg_u-1)*100):.0f}%. → Check what was different that month.")
        if lw["Units"] < avg_u*0.7:
            alert_card("rgba(16,185,129,.12)","#10b981",
                f"✅ <b>{lw['Month']}</b> was best ({lw['Units']:.0f} kWh). → Replicate those habits year-round.")
        var = ((pk["Units"]-lw["Units"])/lw["Units"])*100
        if var > 150:
            alert_card("rgba(56,189,248,.12)","#38bdf8",
                f"📊 {var:.0f}% swing best→worst month. → A 5-star AC or solar geyser would flatten this.")

        st.markdown("---")

        # ── Bar chart ──
        section_header("📊","Monthly Comparison","Units vs bill per month")
        pk_b  = df.loc[df["Bill"].idxmax()]
        bst_b = df.loc[df["Bill"].idxmin()]
        fig_b = px.bar(df, x="Month", y=["Units","Bill"], barmode="group",
                       title=f"Monthly Units & Bill ({sel_year})",
                       labels={"value":"Units (kWh) / Bill (Rs)","variable":"Metric"},
                       color_discrete_map={"Units":"#38bdf8","Bill":"#f59e0b"},
                       template="plotly_dark")
        fig_b.update_layout(height=420, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        fig_b.add_annotation(x=pk_b["Month"], y=pk_b["Bill"],
            text=f"💸 Rs {pk_b['Bill']:.0f}",
            showarrow=True, arrowhead=2, arrowcolor="#ef4444",
            bgcolor="#ef444433", bordercolor="#ef4444", borderwidth=1,
            font=dict(color="#fca5a5",size=11), ax=0, ay=-40)
        for _, row in df[df["Units"]>500].iterrows():
            fig_b.add_annotation(x=row["Month"], y=row["Units"],
                text=f"🔴 Slab 4", showarrow=True, arrowhead=2, arrowcolor="#f97316",
                bgcolor="#f9731633", bordercolor="#f97316", borderwidth=1,
                font=dict(color="#fdba74",size=11), ax=0, ay=-40)
        for _, row in df[(df["Units"]>300)&(df["Units"]<=500)].iterrows():
            fig_b.add_annotation(x=row["Month"], y=row["Units"],
                text=f"🟠 Slab 3", showarrow=True, arrowhead=2, arrowcolor="#eab308",
                bgcolor="#eab30833", bordercolor="#eab308", borderwidth=1,
                font=dict(color="#fde68a",size=11), ax=0, ay=-40)
        if bst_b["Month"] != pk_b["Month"]:
            fig_b.add_annotation(x=bst_b["Month"], y=bst_b["Bill"],
                text=f"✅ Rs {bst_b['Bill']:.0f}", showarrow=True, arrowhead=2, arrowcolor="#10b981",
                bgcolor="#10b98133", bordercolor="#10b981", borderwidth=1,
                font=dict(color="#6ee7b7",size=11), ax=0, ay=-40)
        st.plotly_chart(fig_b, use_container_width=True)

        # Bar alerts
        for _, row in df[df["Units"]>500].iterrows():
            s = round(row["Bill"]-calculate_bill(500,supplier)["total"],0)
            alert_card("rgba(239,68,68,.12)","#ef4444",
                f"🔴 <b>{row['Month']}</b>: Slab 4 ({row['Units']:.0f} kWh). Could've saved <b>Rs {s:.0f}</b>. → Raise AC to 24°C.")
        for _, row in df[(df["Units"]>300)&(df["Units"]<=500)].iterrows():
            s = round(row["Bill"]-calculate_bill(300,supplier)["total"],0)
            alert_card("rgba(249,115,22,.12)","#f97316",
                f"🟠 <b>{row['Month']}</b>: Slab 3 ({row['Units']:.0f} kWh). Under 300 saves <b>Rs {s:.0f}</b>. → Full loads + unplug standby.")
        for _, row in df[(df["Units"]>100)&(df["Units"]<=300)].iterrows():
            s = round(row["Bill"]-calculate_bill(100,supplier)["total"],0)
            alert_card("rgba(234,179,8,.12)","#eab308",
                f"🟡 <b>{row['Month']}</b>: Slab 2 ({row['Units']:.0f} kWh). Under 100 saves <b>Rs {s:.0f}</b>. → Off fans in empty rooms.")
        alert_card("rgba(16,185,129,.12)","#10b981",
            f"✅ Best: <b>{bst_b['Month']}</b> Rs {bst_b['Bill']:.0f} · Worst: <b>{pk_b['Month']}</b> Rs {pk_b['Bill']:.0f}. "
            f"→ Closing that Rs {pk_b['Bill']-bst_b['Bill']:.0f} gap is your yearly savings target.")

        st.markdown("---")

        # ── Pie chart ──
        section_header("🥧","Appliance-wise Yearly Usage","How your energy splits across appliances")
        app_rows = load_all_appliance_data(st.session_state.username, sel_year)
        using_fallback = False
        if not app_rows:
            sv = get_user_survey_hours(st.session_state.username)
            if sv:
                app_rows = [(row["Month"], apply_seasonal_multipliers(sv, row["Month"])) for _, row in df.iterrows()]
                using_fallback = True
        if app_rows:
            if using_fallback:
                st.caption("📋 No per-month data found. Using survey averages with seasonal adjustment.")
            mb = dict(zip(df["Month"],df["Bill"]))
            mu = dict(zip(df["Month"],df["Units"]))
            ay_u, ay_c = {}, {}
            for mn, hj in app_rows:
                ab, au = mb.get(mn,0), mu.get(mn,0)
                if ab==0 or au==0: continue
                mk = {a:(APPLIANCES[a]*float(hj.get(a,0))*30)/1000 for a in APPLIANCES if float(hj.get(a,0))>0}
                rt = sum(mk.values())
                if rt==0: continue
                for a, rk in mk.items():
                    ay_u[a] = ay_u.get(a,0) + (rk/rt)*au
                mc = {a:calculate_bill(k,supplier)["total"] for a,k in mk.items()}
                rct = sum(mc.values())
                for a, c in mc.items():
                    ay_c[a] = ay_c.get(a,0) + (c/rct)*ab
            if ay_u:
                pie_df = pd.DataFrame({
                    "Appliance":    list(ay_u.keys()),
                    "Units (kWh)":  [round(v,2) for v in ay_u.values()],
                    "Cost (Rs)":    [round(ay_c[a],0) for a in ay_u],
                }).sort_values("Cost (Rs)", ascending=False)
                top_app  = pie_df.iloc[0]["Appliance"]
                top_pct  = round(pie_df.iloc[0]["Cost (Rs)"]/pie_df["Cost (Rs)"].sum()*100,1)
                top_cost = pie_df.iloc[0]["Cost (Rs)"]
                icon     = "🔴" if top_pct>40 else ("🟠" if top_pct>25 else "🟢")
                tip      = get_seasonal_tip(top_app, df["Month"].iloc[-1])

                tu, tc = st.tabs([" By Units (kWh)"," By Cost (Rs)"])
                with tu:
                    fig_pu = px.pie(pie_df, names="Appliance", values="Units (kWh)",
                                   title=f"Yearly Consumption — {sel_year}", hole=0.35, template="plotly_dark")
                    fig_pu.update_traces(textposition="inside", textinfo="percent+label")
                    fig_pu.add_annotation(text=f"<b>{top_app.split()[0]}</b><br>{round(pie_df.iloc[0]['Units (kWh)']/pie_df['Units (kWh)'].sum()*100,1)}% kWh",
                        x=0.5,y=0.5,xref="paper",yref="paper",showarrow=False,font=dict(size=13,color="#f9fafb"),align="center")
                    fig_pu.update_layout(height=480, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                    st.plotly_chart(fig_pu, use_container_width=True)
                with tc:
                    fig_pc = px.pie(pie_df, names="Appliance", values="Cost (Rs)",
                                   title=f"Yearly Bill Share — {sel_year}", hole=0.35,
                                   color_discrete_sequence=px.colors.sequential.RdBu, template="plotly_dark")
                    fig_pc.update_traces(textposition="inside", textinfo="percent+label")
                    fig_pc.add_annotation(text=f"<b>{top_app.split()[0]}</b><br>{top_pct}% bill",
                        x=0.5,y=0.5,xref="paper",yref="paper",showarrow=False,font=dict(size=13,color="#f9fafb"),align="center")
                    fig_pc.update_layout(height=480, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                    st.plotly_chart(fig_pc, use_container_width=True)
                    alert_card(
                        "rgba(239,68,68,.12)" if top_pct>40 else "rgba(245,158,11,.12)" if top_pct>25 else "rgba(16,185,129,.12)",
                        "#ef4444" if top_pct>40 else "#f59e0b" if top_pct>25 else "#10b981",
                        f"{icon} <b>{top_app}</b> = {top_pct}% of bill (Rs {top_cost:.0f}/yr). → {tip}"
                    )

                ac1,ac2,ac3 = st.columns(3)
                with ac1: st.metric("Yearly Units", f"{df['Units'].sum():.0f} kWh")
                with ac2: st.metric("Yearly Bill",  f"Rs {df['Bill'].sum():.0f}")
                with ac3: st.metric("Top Consumer", top_app)
            else:
                st.info("No appliance data yet.")
        else:
            st.info("No appliance data. Complete the survey and add monthly entries.")

        st.markdown("---")

        # ── Heatmap ──
        section_header("🌡️","Hourly Usage Heatmap","Estimated usage pattern across the day")
        hw = np.array([0.3,0.2,0.2,0.2,0.2,0.3,0.5,0.8,1.0,0.7,0.6,0.7,0.8,0.6,0.5,0.5,0.6,0.8,1.0,1.2,1.2,1.0,0.8,0.5])
        hw /= hw.sum()
        hd = []
        for _, row in df.iterrows():
            mi  = MONTH_ORDER[row["Month"]]+1
            dim = pd.Period(f"{sel_year}-{mi:02d}").days_in_month
            hd.append((row["Units"]/dim)*hw*24)
        ha = np.array(hd)
        fig_h = px.imshow(ha, x=[f"{h:02d}:00" for h in range(24)], y=df["Month"].tolist(),
                          color_continuous_scale="YlOrRd", title=f"Hourly Usage Heatmap ({sel_year})",
                          labels={"x":"Hour","y":"Month","color":"kWh"}, aspect="auto", template="plotly_dark")
        fig_h.update_layout(height=420, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        pc   = np.unravel_index(np.argmax(ha), ha.shape)
        pm_l = df["Month"].tolist()[pc[0]]
        ph_l = f"{pc[1]:02d}:00"
        fig_h.add_annotation(x=ph_l, y=pm_l,
            text=f"🔴 Peak {ha[pc]:.2f} kWh",
            showarrow=True, arrowhead=2, arrowcolor="#ef4444",
            bgcolor="#ef444466", bordercolor="#ef4444", borderwidth=1,
            font=dict(color="#fff",size=11), ax=30, ay=-30)
        ev_avg  = ha[:,19:22].mean()
        ov_avg  = ha.mean()
        if ev_avg > ov_avg*1.4:
            fig_h.add_annotation(x="20:00", y=df["Month"].tolist()[len(df)//2],
                text="⚡ Evening peak 19–21h", showarrow=False,
                bgcolor="#f59e0b44", bordercolor="#f59e0b", borderwidth=1,
                font=dict(color="#fde68a",size=11))
        st.plotly_chart(fig_h, use_container_width=True)
        st.caption("Estimated from monthly totals using typical Indian household usage patterns.")

        # Heatmap alerts
        phn = pc[1]
        if 13<=phn<=17:
            alert_card("rgba(239,68,68,.12)","#ef4444",
                f"🔴 Peak at {ph_l} in {pm_l} (afternoon). → Close west-facing curtains + raise AC to 26°C after 13:00.")
        elif 19<=phn<=22:
            alert_card("rgba(249,115,22,.12)","#f97316",
                f"🟠 Peak at {ph_l} (evening rush). → Don't run AC, TV, and microwave together — stagger them.")
        elif phn>=22 or phn<=6:
            alert_card("rgba(56,189,248,.12)","#38bdf8",
                f"💡 Peak at {ph_l} (overnight). → Set AC sleep timer — saves ~35 kWh/month.")
        if ev_avg > ov_avg*1.4:
            alert_card("rgba(245,158,11,.12)","#f59e0b",
                f"⚡ 19–21h is {((ev_avg/ov_avg-1)*100):.0f}% above average every month. → Shift washing machine to after 22:00 + off unused lights.")
        mo_avg = ha[:,10:14].mean()
        if mo_avg < ov_avg*0.7:
            alert_card("rgba(16,185,129,.12)","#10b981",
                f"✅ Low usage 10–14h — good daylight habits. → Extend to 09–15h for more savings.")

        st.markdown("---")

        # ── Carbon footprint ──
        section_header("🌍","Carbon Footprint","Your environmental impact this year")
        total_co2  = total_units * CO2_FACTOR
        last_co2   = df["Units"].iloc[-1] * CO2_FACTOR
        cf1,cf2 = st.columns(2)
        with cf1: st.metric("Total CO2", f"{total_co2:.0f} kg", delta=f"{last_co2:.0f} kg last month")
        with cf2: st.metric("Trees Equivalent", f"{total_co2/22:.1f} trees/year")
        st.caption("CEA 2023 grid emission factor: 0.716 kg CO₂/kWh")

    else:
        st.info(f"No data for {sel_year}.")
        if st.button("Go to Enter Data →"):
            st.session_state.page="input"; st.rerun()

st.markdown("---")
