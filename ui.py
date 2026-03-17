import streamlit as st


def inject_styles():
    st.markdown("""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;1,9..40,400&display=swap" rel="stylesheet">
<style>
[data-testid="stSidebar"],[data-testid="collapsedControl"],#MainMenu,footer,header{display:none!important}
html,body,[data-testid='stAppViewContainer'],[data-testid='stApp']{font-family:'DM Sans','Segoe UI',system-ui,sans-serif!important;background:#020c18!important}
.stApp{background:#020c18!important}
.main .block-container,[data-testid="stAppViewBlockContainer"]{padding:1.8rem 3rem 4rem!important;max-width:1180px!important}
.stApp::before{content:'';position:fixed;top:0;left:0;width:100%;height:100%;
  background:radial-gradient(ellipse 60% 50% at 20% 20%,rgba(56,189,248,.08) 0%,transparent 60%),
             radial-gradient(ellipse 50% 60% at 80% 80%,rgba(6,182,212,.07) 0%,transparent 60%),
             radial-gradient(ellipse 40% 40% at 50% 50%,rgba(16,185,129,.04) 0%,transparent 50%);
  pointer-events:none;z-index:0;animation:orbpulse 8s ease-in-out infinite alternate}
@keyframes orbpulse{0%{opacity:.7;transform:scale(1)}100%{opacity:1;transform:scale(1.05)}}
[data-testid="metric-container"]{background:rgba(255,255,255,.03)!important;border:1px solid rgba(255,255,255,.08)!important;
  border-radius:18px!important;padding:20px 24px!important;backdrop-filter:blur(20px)!important;
  transition:all .3s ease!important;box-shadow:0 4px 24px rgba(0,0,0,.3),inset 0 1px 0 rgba(255,255,255,.06)!important}
[data-testid="metric-container"]:hover{border-color:rgba(56,189,248,.3)!important;transform:translateY(-2px)!important}
[data-testid="metric-container"] label{color:#6b7280!important;font-size:11px!important;font-weight:600!important;text-transform:uppercase!important;letter-spacing:1.2px!important}
[data-testid="metric-container"] [data-testid="stMetricValue"]{color:#f9fafb!important;font-size:26px!important;font-weight:800!important;letter-spacing:-.5px!important}
[data-testid="stMetricDelta"]{font-size:12px!important;font-weight:500!important}
.stButton>button{border-radius:12px!important;font-weight:600!important;font-size:14px!important;transition:all .25s cubic-bezier(.4,0,.2,1)!important;letter-spacing:.3px!important;padding:11px 22px!important}
.stButton>button[kind="primary"]{background:linear-gradient(135deg,#38bdf8,#0ea5e9,#0369a1)!important;color:#020c18!important;border:none!important;box-shadow:0 4px 16px rgba(56,189,248,.35)!important}
.stButton>button[kind="primary"]:hover{transform:translateY(-2px) scale(1.01)!important;box-shadow:0 8px 28px rgba(56,189,248,.5)!important}
.stButton>button[kind="secondary"]{background:rgba(255,255,255,.04)!important;color:#9ca3af!important;border:1px solid rgba(255,255,255,.1)!important}
.stButton>button[kind="secondary"]:hover{background:rgba(255,255,255,.08)!important;color:#f9fafb!important;border-color:rgba(56,189,248,.3)!important}
.stTextInput>div>div>input,.stNumberInput>div>div>input,.stSelectbox>div>div>div{background:rgba(255,255,255,.04)!important;border:1px solid rgba(255,255,255,.1)!important;border-radius:12px!important;color:#f9fafb!important;font-size:14px!important;transition:all .2s!important}
.stTextInput>div>div>input:focus,.stNumberInput>div>div>input:focus{border-color:rgba(56,189,248,.6)!important;box-shadow:0 0 0 3px rgba(56,189,248,.12)!important;background:rgba(255,255,255,.06)!important}
.stTabs [data-baseweb="tab-list"]{background:rgba(255,255,255,.03)!important;border:1px solid rgba(255,255,255,.07)!important;border-radius:14px!important;padding:5px!important;gap:4px!important}
.stTabs [data-baseweb="tab"]{border-radius:10px!important;color:#6b7280!important;font-weight:600!important;padding:9px 24px!important;transition:all .2s!important}
.stTabs [aria-selected="true"]{background:linear-gradient(135deg,#38bdf8,#0ea5e9)!important;color:#020c18!important;box-shadow:0 4px 12px rgba(56,189,248,.3)!important}
hr{border:none!important;height:1px!important;background:linear-gradient(90deg,transparent,rgba(255,255,255,.08),transparent)!important;margin:28px 0!important}
h1,h2,h3,h4,h5{color:#f9fafb!important;font-family:'Syne','Segoe UI',system-ui,sans-serif!important;letter-spacing:-.3px!important}
[data-testid="stMarkdownContainer"] p{color:#9ca3af!important;line-height:1.6!important}
.streamlit-expanderHeader{background:rgba(255,255,255,.03)!important;border:1px solid rgba(255,255,255,.08)!important;border-radius:10px!important;color:#9ca3af!important}
[data-testid="stAlert"]{border-radius:12px!important}
.js-plotly-plot .plotly,.js-plotly-plot{background:transparent!important}
[data-testid="stFileUploader"]{background:rgba(255,255,255,.03)!important;border:2px dashed rgba(255,255,255,.1)!important;border-radius:14px!important;padding:8px!important}
.stCaption,[data-testid="stCaptionContainer"]{color:#4b5563!important;font-size:12px!important}
.stSpinner>div{border-top-color:#38bdf8!important}
</style>""", unsafe_allow_html=True)


def section_header(icon, title, subtitle=""):
    sub = f'<div style="font-size:12px;color:#6b7280;margin-top:3px;">{subtitle}</div>' if subtitle else ""
    st.markdown(f'''
    <div style="display:flex;align-items:center;gap:14px;margin:28px 0 20px;padding-bottom:16px;border-bottom:1px solid rgba(255,255,255,.06);">
      <div style="width:42px;height:42px;border-radius:12px;display:flex;align-items:center;justify-content:center;
        background:linear-gradient(135deg,rgba(56,189,248,.15),rgba(245,158,11,.08));border:1px solid rgba(56,189,248,.2);font-size:20px;">{icon}</div>
      <div>
        <div style="font-family:'Syne','Segoe UI',system-ui,sans-serif;font-size:19px;font-weight:700;color:#f9fafb;letter-spacing:-.2px;">{title}</div>
        {sub}
      </div>
    </div>''', unsafe_allow_html=True)


def alert_card(bg, border, content):
    st.markdown(f'''
    <div style="background:{bg};border-left:4px solid {border};border-radius:12px;
      padding:12px 16px;margin:6px 0;color:#f9fafb;font-size:13px;line-height:1.5;">{content}</div>
    ''', unsafe_allow_html=True)


def plotly_dark(fig, height=400):
    fig.update_layout(height=height, template="plotly_dark",
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    return fig
