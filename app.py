"""
HireAI Enterprise — Streamlit Frontend
Version: 2.1.0

Run locally:
    streamlit run app.py

Deployed on Streamlit Cloud:
    Set BACKEND_URL in Streamlit secrets to your Render backend URL.
    Vapi widget uses base64 data URI rendering — works on local, ngrok,
    Streamlit Cloud, and Render without any local HTTP server.

LLM Backend:
    Powered by Groq (llama-3.3-70b-versatile) — free tier, no local GPU needed.
    Get your free API key at https://console.groq.com/keys

Voice AI:
    Vapi AI conducts structured voice interviews tailored to each candidate's CV.
    Interview transcripts are evaluated automatically after every call.
"""

import base64
import hashlib
import http.server
import os
import random
import socket
import socketserver
import textwrap
import threading
from datetime import datetime

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components

BACKEND_URL     = "https://hireai-backend-5wpz.onrender.com"
VAPI_PUBLIC_KEY = "0336b9be-93ff-4d9b-b222-7f026fcd1ae5"
APP_VERSION     = "3.0.0"
APP_NAME        = "HireAI"

USERS = {
    "admin": {
        "password_hash": hashlib.sha256(b"admin123").hexdigest(),
        "role": "Administrator",
        "name": "Administrator",
        "avatar": "👑",
        "color": "#F472B6",
    },
    "hr": {
        "password_hash": hashlib.sha256(b"hr2024").hexdigest(),
        "role": "HR Manager",
        "name": "HR Manager",
        "avatar": "👔",
        "color": "#60A5FA",
    },
    "recruiter": {
        "password_hash": hashlib.sha256(b"recruit2024").hexdigest(),
        "role": "Recruiter",
        "name": "Recruiter",
        "avatar": "🎯",
        "color": "#34D399",
    },
}

ROLES = [
    "Frontend Engineer","Backend Engineer","Fullstack Engineer",
    "iOS Engineer","Android Engineer","Cross-Platform Mobile Engineer",
    "Software Engineer","Senior Software Engineer","Staff Software Engineer",
    "Principal Engineer","Engineering Manager","Software Architect",
    "Embedded Systems Engineer","Game Developer",
    "SQA Engineer","QA Automation Engineer","Manual QA Tester","Performance Test Engineer",
    "DevOps Engineer","Site Reliability Engineer","Cloud Engineer",
    "Platform Engineer","Infrastructure Engineer","Network Engineer","Systems Administrator",
    "Data Scientist","Data Analyst","Data Engineer",
    "Machine Learning Engineer","MLOps Engineer","GenAI Engineer",
    "AI Research Scientist","Business Intelligence Analyst",
    "Cybersecurity Engineer","Security Analyst","Penetration Tester",
    "Security Operations (SOC) Engineer",
    "Database Administrator","Database Engineer",
    "Product Manager","Product Owner","UI/UX Designer","Product Designer","Graphic Designer",
    "Project Manager","Scrum Master","Technical Program Manager","Delivery Manager",
    "Chief Technology Officer",
    "IT Support Engineer","Helpdesk Technician","Technical Support Engineer",
    "Sales Engineer","Solutions Architect","Business Analyst","Other",
]

TIPS = [
    "Use a text-based PDF for the best parsing results. Scanned documents will not extract properly.",
    "The AI interviewer tailors every single question to the candidate's actual work history and projects.",
    "Evaluation scores are generated automatically the moment the interview call ends — no manual work.",
    "Download the Excel report from Analytics to share hiring decisions with your team in one click.",
    "Each candidate gets a unique Vapi voice assistant built specifically from their parsed CV.",
    "The Hire Shortlist tab in the Excel report is pre-filtered so HR can act on results immediately.",
    "Candidates scoring above 85 overall are automatically flagged as Strong Hire.",
    "Alex the AI interviewer asks up to 12 questions in a structured flow from warm-up through closing.",
    "Full interview transcripts are stored in the database and available for review at any time.",
    "You can regenerate the interview assistant for any candidate without losing their record or evaluation.",
    "Groq's LLaMA 3.3 70B model powers CV parsing and evaluation — fast, accurate, and free to use.",
    "The platform runs entirely on free tiers: Groq, Vapi, Render, and Streamlit Cloud.",
]

st.set_page_config(
    page_title=f"{APP_NAME} Enterprise",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Local widget HTTP server ──────────────────────────────
# Serves the Vapi interview widget from a real HTTP origin
# (http://127.0.0.1:PORT) so Daily.co's call-machine bundle
# can call window.parent.postMessage() without hitting the
# "Invalid target origin 'null'" error that both data: URIs
# and Streamlit srcdoc iframes produce.
WIDGET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_vapi_widget_cache")
os.makedirs(WIDGET_DIR, exist_ok=True)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _SilentHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=WIDGET_DIR, **kw)

    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()


@st.cache_resource
def _start_widget_server() -> int:
    port = _free_port()
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", port), _SilentHandler)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return port


WIDGET_PORT = _start_widget_server()
# ─────────────────────────────────────────────────────────

DEFAULTS = {
    "authenticated": False,
    "username": "",
    "user_role": "",
    "user_name": "",
    "user_avatar": "",
    "login_attempts": 0,
    "last_candidate_id": 1,
    "assistant_id": "",
    "candidate_data": {},
    "tip_index": random.randint(0, len(TIPS) - 1),
    "user_color": "#60A5FA",
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v



st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap');

/* ── Reset ── */
#MainMenu,footer,header{visibility:hidden;}
body,p,h1,h2,h3,h4,h5,h6,button,input,select,textarea,[data-testid="stMarkdownContainer"],[data-testid="stText"],[data-testid="stWidgetLabel"]{font-family:'Inter',-apple-system,BlinkMacSystemFont,sans-serif!important;}
html,body,[data-testid="stAppViewContainer"]{background:#020B18!important;color:#E2E8F0;}
[data-testid="stSidebar"]{background:#030C1A!important;border-right:1px solid #0A1E38;}
[data-testid="stMain"]{background:#020B18!important;}
[data-testid="block-container"]{padding-top:1.2rem!important;}

/* ── Inputs ── */
[data-testid="stTextInput"] input{
    background:#071220!important;border:1px solid #1E3A5F!important;
    border-radius:10px!important;color:#E2E8F0!important;font-size:0.9rem!important;
    padding:10px 14px!important;transition:all 0.25s!important;}
[data-testid="stTextInput"] input:focus{
    border-color:#3B82F6!important;
    box-shadow:0 0 0 3px rgba(59,130,246,0.15)!important;}
[data-testid="stSelectbox"]>div>div{
    background:#071220!important;border:1px solid #1E3A5F!important;
    border-radius:10px!important;color:#E2E8F0!important;}
[data-testid="stNumberInput"] input{
    background:#071220!important;border:1px solid #1E3A5F!important;
    border-radius:10px!important;color:#E2E8F0!important;}
[data-testid="stRadio"] label{font-size:0.87rem!important;padding:5px 0!important;}
[data-testid="stDataFrame"]{border:1px solid #0A1E38!important;border-radius:14px!important;}
[data-testid="stExpander"]{
    background:#071220!important;border:1px solid #0A1E38!important;
    border-radius:12px!important;}

/* ── Buttons ── */
.stButton>button{
    border-radius:10px;border:none;font-weight:700;font-size:0.88rem;
    height:44px;background:linear-gradient(135deg,#2563EB,#4F46E5);
    color:white;transition:all 0.25s;letter-spacing:0.01em;}
.stButton>button:hover{
    opacity:0.9;transform:translateY(-2px);
    box-shadow:0 12px 32px rgba(37,99,235,0.45);}
.stButton>button:active{transform:translateY(0);}

/* ── Scrollbar ── */
::-webkit-scrollbar{width:4px;height:4px;}
::-webkit-scrollbar-track{background:#020B18;}
::-webkit-scrollbar-thumb{background:#1E3A5F;border-radius:2px;}

/* ── Hover cards ── */
.hcard{transition:transform 0.25s,box-shadow 0.25s,border-color 0.25s !important;}
.hcard:hover{transform:translateY(-4px) !important;border-color:#2563EB !important;
    box-shadow:0 20px 60px rgba(37,99,235,0.18) !important;}

/* ── Animations ── */
@keyframes float{0%,100%{transform:translateY(0);}50%{transform:translateY(-10px);}}
@keyframes fadeInUp{from{opacity:0;transform:translateY(24px);}to{opacity:1;transform:translateY(0);}}
@keyframes fadeIn{from{opacity:0;}to{opacity:1;}}
@keyframes pulse-ring{0%{transform:scale(1);opacity:1;}100%{transform:scale(1.8);opacity:0;}}
@keyframes glow{0%,100%{box-shadow:0 0 6px rgba(52,211,153,0.4);}50%{box-shadow:0 0 20px rgba(52,211,153,0.9);}}
@keyframes gradientFlow{0%{background-position:0% 50%;}50%{background-position:100% 50%;}100%{background-position:0% 50%;}}
@keyframes slideLeft{from{opacity:0;transform:translateX(-16px);}to{opacity:1;transform:translateX(0);}}
@keyframes counterUp{from{opacity:0;transform:scale(0.6);}to{opacity:1;transform:scale(1);}}
@keyframes shimmer{0%{background-position:-400px 0;}100%{background-position:400px 0;}}
@keyframes spin{from{transform:rotate(0deg);}to{transform:rotate(360deg);}}
@keyframes borderPulse{0%,100%{border-color:#1E3A5F;}50%{border-color:#3B82F6;}}
@keyframes scan{0%{transform:translateY(-100%);}100%{transform:translateY(400px);}}
</style>
""", unsafe_allow_html=True)


def api_get(path, timeout=15):
    try:
        return requests.get(f"{BACKEND_URL}{path}", timeout=timeout)
    except Exception:
        return None


def api_post(path, **kwargs):
    try:
        return requests.post(f"{BACKEND_URL}{path}", **kwargs)
    except Exception:
        return None


def pill(text, color="#4F46E5", bg="rgba(99,102,241,0.12)"):
    return (f'<span style="display:inline-block;background:{bg};border:1px solid {color};'
            f'border-radius:999px;padding:3px 12px;font-size:0.74rem;font-weight:600;'
            f'color:{color};margin:3px 3px 3px 0;cursor:default;'
            f'transition:all 0.2s;">{text}</span>')


def badge(status):
    MAP = {
        "Hired":               ("#34D399","rgba(52,211,153,0.15)"),
        "Rejected":            ("#F87171","rgba(248,113,113,0.15)"),
        "On Hold":             ("#FBB724","rgba(251,191,36,0.15)"),
        "Hold":                ("#FBB724","rgba(251,191,36,0.15)"),
        "Uploaded":            ("#60A5FA","rgba(96,165,250,0.12)"),
        "Interview Generated": ("#A78BFA","rgba(167,139,250,0.12)"),
        "Interview In Progress":("#F472B6","rgba(244,114,182,0.12)"),
        "Interviewed":         ("#6EE7B7","rgba(52,211,153,0.1)"),
        "Evaluated":           ("#93C5FD","rgba(96,165,250,0.1)"),
        "Strong Hire":         ("#34D399","rgba(52,211,153,0.2)"),
    }
    c, bg = MAP.get(status, ("#94A3B8","rgba(100,116,139,0.12)"))
    return (f'<span style="display:inline-block;padding:3px 10px;border-radius:999px;'
            f'font-size:0.72rem;font-weight:700;background:{bg};color:{c};'
            f'border:1px solid {c};letter-spacing:0.02em;">{status}</span>')


def score_bar(label, value):
    c = "#34D399" if value >= 75 else "#FBB724" if value >= 50 else "#F87171"
    return (f'<div style="margin-bottom:11px;">'
            f'<div style="display:flex;justify-content:space-between;font-size:0.77rem;color:#475569;margin-bottom:5px;">'
            f'<span>{label}</span>'
            f'<span style="color:{c};font-weight:800;font-size:0.82rem;">{value}</span></div>'
            f'<div style="background:#071220;border-radius:999px;height:6px;overflow:hidden;border:1px solid #0A1E38;">'
            f'<div style="width:{value}%;height:6px;border-radius:999px;'
            f'background:linear-gradient(90deg,{c},{c}aa);'
            f'box-shadow:0 0 8px {c}55;"></div></div></div>')


def section_title(text, icon=""):
    prefix = f'<span style="margin-right:6px;">{icon}</span>' if icon else ''
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:6px;font-size:0.68rem;font-weight:800;'
        f'color:#334155;text-transform:uppercase;letter-spacing:0.14em;'
        f'border-bottom:1px solid #0A1E38;padding-bottom:10px;'
        f'margin:28px 0 16px 0;animation:fadeIn 0.5s ease;">{prefix}{text}</div>',
        unsafe_allow_html=True)


def page_header(title, subtitle):
    st.markdown(
        f'<div style="margin-bottom:24px;animation:fadeInUp 0.5s ease;">'
        f'<div style="font-size:1.85rem;font-weight:900;letter-spacing:-0.025em;'
        f'background:linear-gradient(135deg,#60A5FA 0%,#A78BFA 50%,#F472B6 100%);'
        f'background-size:200% 200%;'
        f'animation:gradientFlow 5s ease infinite;'
        f'-webkit-background-clip:text;-webkit-text-fill-color:transparent;'
        f'margin-bottom:6px;">{title}</div>'
        f'<div style="color:#334155;font-size:0.88rem;font-weight:400;">{subtitle}</div></div>',
        unsafe_allow_html=True)


def kpi_card(icon, value, label, color):
    return (f'<div class="hcard" style="background:linear-gradient(145deg,#071220,#050E1A);'
            f'border:1px solid #0A1E38;border-radius:18px;padding:20px 14px;text-align:center;">'
            f'<div style="font-size:1.5rem;margin-bottom:8px;">{icon}</div>'
            f'<div style="font-size:1.8rem;font-weight:900;color:{color};'
            f'letter-spacing:-0.02em;animation:counterUp 0.6s ease;">{value}</div>'
            f'<div style="font-size:0.62rem;color:#334155;text-transform:uppercase;'
            f'letter-spacing:0.1em;margin-top:4px;font-weight:700;">{label}</div>'
            f'</div>')


def fmt_dt(raw):
    if not raw:
        return "—"
    try:
        return datetime.fromisoformat(str(raw)).strftime("%d %b %Y, %H:%M")
    except Exception:
        return str(raw)


def check_login(username, password):
    if st.session_state.login_attempts >= 5:
        return False
    user = USERS.get(username.lower())
    if not user:
        st.session_state.login_attempts += 1
        return False
    if user["password_hash"] != hashlib.sha256(password.encode()).hexdigest():
        st.session_state.login_attempts += 1
        return False
    st.session_state.authenticated = True
    st.session_state.username = username.lower()
    st.session_state.user_role = user["role"]
    st.session_state.user_name = user["name"]
    st.session_state.user_avatar = user["avatar"]
    st.session_state.user_color = user.get("color","#60A5FA")
    st.session_state.login_attempts = 0
    return True


def show_login():
    st.markdown("""<style>[data-testid="stSidebar"]{display:none!important;}
    [data-testid="stAppViewContainer"]{background:#020B18!important;}</style>""",
    unsafe_allow_html=True)

    # Particle canvas — zero height trick to inject JS without taking space
    components.html("""<!DOCTYPE html><html><head><style>
    *{margin:0;padding:0;}body{background:transparent;overflow:hidden;width:100vw;height:100vh;}
    canvas{position:fixed;top:0;left:0;pointer-events:none;z-index:0;}
    .orb{position:fixed;border-radius:50%;filter:blur(90px);pointer-events:none;}
    .o1{width:580px;height:580px;background:radial-gradient(circle,rgba(37,99,235,0.1),transparent 70%);
        top:-180px;right:-80px;animation:f1 14s ease-in-out infinite;}
    .o2{width:480px;height:480px;background:radial-gradient(circle,rgba(124,58,237,0.08),transparent 70%);
        bottom:-160px;left:-80px;animation:f2 18s ease-in-out infinite;}
    .o3{width:360px;height:360px;background:radial-gradient(circle,rgba(236,72,153,0.05),transparent 70%);
        top:50%;left:50%;transform:translate(-50%,-50%);animation:f3 11s ease-in-out infinite;}
    @keyframes f1{0%,100%{transform:translate(0,0);}40%{transform:translate(-24px,18px);}70%{transform:translate(16px,-12px);}}
    @keyframes f2{0%,100%{transform:translate(0,0);}40%{transform:translate(18px,-22px);}70%{transform:translate(-12px,10px);}}
    @keyframes f3{0%,100%{transform:translate(-50%,-50%);}50%{transform:translate(-50%,-50%) scale(1.12);}}
    </style></head><body>
    <div class="orb o1"></div><div class="orb o2"></div><div class="orb o3"></div>
    <canvas id="c"></canvas>
    <script>
    const cv=document.getElementById('c'),ctx=cv.getContext('2d');
    cv.width=window.innerWidth;cv.height=window.innerHeight;
    const pts=[];
    for(let i=0;i<55;i++)pts.push({
        x:Math.random()*cv.width,y:Math.random()*cv.height,
        dx:(Math.random()-.5)*.35,dy:(Math.random()-.5)*.35,
        r:Math.random()*1.4+.4,o:Math.random()*.35+.08,
        c:['#3B82F6','#8B5CF6','#06B6D4','#10B981','#F472B6'][Math.floor(Math.random()*5)]
    });
    function draw(){
        ctx.clearRect(0,0,cv.width,cv.height);
        pts.forEach((p,i)=>{
            ctx.beginPath();ctx.arc(p.x,p.y,p.r,0,Math.PI*2);
            ctx.fillStyle=p.c;ctx.globalAlpha=p.o;ctx.fill();
            p.x+=p.dx;p.y+=p.dy;
            if(p.x<0||p.x>cv.width)p.dx*=-1;
            if(p.y<0||p.y>cv.height)p.dy*=-1;
            pts.slice(i+1).forEach(q=>{
                const d=Math.hypot(p.x-q.x,p.y-q.y);
                if(d<130){ctx.beginPath();ctx.moveTo(p.x,p.y);ctx.lineTo(q.x,q.y);
                    ctx.strokeStyle='#1E3A5F';ctx.globalAlpha=(1-d/130)*.25;
                    ctx.lineWidth=.5;ctx.stroke();}
            });
        });ctx.globalAlpha=1;requestAnimationFrame(draw);
    }draw();
    </script></body></html>""", height=0)

    _, center, _ = st.columns([1, 1.1, 1])
    with center:
        st.markdown("<div style='height:44px'></div>", unsafe_allow_html=True)

        # Animated logo + brand
        st.markdown("""
        <div style="text-align:center;margin-bottom:28px;animation:fadeInUp 0.6s ease;">
            <div style="position:relative;display:inline-block;margin-bottom:16px;">
                <div style="width:72px;height:72px;
                    background:linear-gradient(135deg,#2563EB,#7C3AED,#EC4899);
                    background-size:200% 200%;animation:gradientFlow 3s ease infinite;
                    border-radius:20px;display:flex;align-items:center;justify-content:center;
                    font-size:1.9rem;margin:0 auto;
                    box-shadow:0 20px 60px rgba(37,99,235,0.55),0 0 40px rgba(124,58,237,0.3);">🎯</div>
                <div style="position:absolute;top:-3px;right:-3px;width:15px;height:15px;
                    background:#34D399;border-radius:50%;border:2.5px solid #020B18;
                    animation:pulse-ring 2s infinite;"></div>
                <div style="position:absolute;top:-3px;right:-3px;width:15px;height:15px;
                    background:#34D399;border-radius:50%;border:2.5px solid #020B18;"></div>
            </div>
            <div style="font-size:1.95rem;font-weight:900;letter-spacing:-0.035em;
                background:linear-gradient(135deg,#60A5FA,#A78BFA,#F472B6);
                background-size:200% 200%;animation:gradientFlow 4s ease infinite;
                -webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:5px;">
                HireAI Enterprise
            </div>
            <div style="color:#1E3A5F;font-size:0.74rem;letter-spacing:0.14em;
                text-transform:uppercase;font-weight:700;">
                AI Powered Recruitment · v3.0.0
            </div>
        </div>""", unsafe_allow_html=True)

        # Glassmorphism login card
        st.markdown("""
        <div style="background:linear-gradient(145deg,rgba(10,22,40,0.96),rgba(5,14,28,0.98));
            border:1px solid #1E3A5F;border-radius:24px;padding:30px 26px;
            box-shadow:0 40px 80px rgba(0,0,0,0.75),0 0 0 1px rgba(255,255,255,0.03);
            animation:fadeInUp 0.75s ease 0.15s both;backdrop-filter:blur(20px);">
            <div style="font-size:1.1rem;font-weight:800;color:#E2E8F0;margin-bottom:3px;">
                Welcome back</div>
            <div style="font-size:0.79rem;color:#334155;margin-bottom:22px;">
                Sign in to access the recruitment platform</div>
        """, unsafe_allow_html=True)

        username = st.text_input("Username", placeholder="Username", key="login_user",
                                  label_visibility="collapsed")
        st.markdown('<div style="font-size:0.7rem;color:#1E3A5F;margin:-9px 0 8px 2px;">Username</div>',
                    unsafe_allow_html=True)
        password = st.text_input("Password", type="password", placeholder="Password",
                                  key="login_pass", label_visibility="collapsed")
        st.markdown('<div style="font-size:0.7rem;color:#1E3A5F;margin:-9px 0 16px 2px;">Password</div>',
                    unsafe_allow_html=True)

        if st.session_state.login_attempts >= 5:
            st.markdown("""
            <div style="background:rgba(248,113,113,0.07);border:1px solid rgba(248,113,113,0.3);
                border-radius:10px;padding:10px 13px;margin-bottom:12px;
                color:#FCA5A5;font-size:0.78rem;text-align:center;">
                🔒 Account locked after 5 failed attempts. Restart the app to reset.
            </div>""", unsafe_allow_html=True)

        if st.button("Sign In  →", use_container_width=True, key="signin"):
            if not username or not password:
                st.markdown("""
                <div style="background:rgba(251,191,36,0.06);border-left:3px solid #FBB724;
                    border-radius:8px;padding:8px 12px;color:#FDE68A;font-size:0.78rem;margin-top:8px;">
                    Please enter both username and password.
                </div>""", unsafe_allow_html=True)
            elif check_login(username, password):
                st.markdown("""
                <div style="background:rgba(52,211,153,0.07);border-left:3px solid #34D399;
                    border-radius:8px;padding:8px 12px;color:#6EE7B7;font-size:0.78rem;margin-top:8px;">
                    ✓ Authenticated. Loading platform...
                </div>""", unsafe_allow_html=True)
                st.rerun()
            else:
                rem = max(0, 5 - st.session_state.login_attempts)
                st.markdown(f"""
                <div style="background:rgba(248,113,113,0.06);border-left:3px solid #F87171;
                    border-radius:8px;padding:8px 12px;color:#FCA5A5;font-size:0.78rem;margin-top:8px;">
                    Incorrect credentials. {rem} attempt(s) remaining.
                </div>""", unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

        # Feature strip
        st.markdown(
            "<div style='display:grid;grid-template-columns:repeat(3,1fr);gap:7px;margin-top:14px;'>" +
            "".join(
                f"<div style='background:rgba(10,22,40,0.85);border:1px solid #0A1E38;"
                f"border-radius:11px;padding:11px 8px;text-align:center;'>"
                f"<div style='font-size:1.2rem;margin-bottom:3px;'>{ic}</div>"
                f"<div style='font-size:0.63rem;color:#334155;font-weight:700;"
                f"text-transform:uppercase;letter-spacing:0.07em;'>{lb}</div>"
                f"</div>"
                for ic,lb in [("🎤","Voice AI"),("🧠","Groq LLM"),("📊","Auto Eval")]
            ) + "</div>",
            unsafe_allow_html=True
        )

        # Color-coded demo credentials
        cred_html = (
            "<div style='margin-top:12px;background:rgba(37,99,235,0.04);border:1px solid #0A1E38;"
            "border-radius:12px;padding:12px 15px;'>"
            "<div style='font-size:0.6rem;font-weight:800;color:#1E3A5F;"
            "text-transform:uppercase;letter-spacing:0.12em;margin-bottom:8px;'>Demo Access</div>"
            "<div style='display:flex;gap:7px;flex-wrap:wrap;'>" +
            "".join(
                f"<div style='background:#071220;border:1px solid #0A1E38;border-radius:8px;"
                f"padding:5px 10px;font-size:0.7rem;color:#334155;'>"
                f"<span style='color:{c};font-weight:800;'>{u}</span> / {p}"
                f"</div>"
                for u,p,c in [
                    ("admin","admin123","#F472B6"),
                    ("hr","hr2024","#60A5FA"),
                    ("recruiter","recruit2024","#34D399"),
                ]
            ) +
            "</div></div>"
            "<div style='text-align:center;margin-top:12px;font-size:0.62rem;color:#0A1E38;'>"
            "HireAI Enterprise v3.0.0 · Secured with bcrypt · Groq + Vapi</div>"
        )
        st.markdown(cred_html, unsafe_allow_html=True)


if not st.session_state.authenticated:
    show_login()
    st.stop()


with st.sidebar:
    st.markdown(f"""
    <div style="padding:20px 6px 14px;text-align:center;">
        <div style="position:relative;display:inline-block;margin-bottom:10px;">
            <div style="width:46px;height:46px;
                background:linear-gradient(135deg,#2563EB,#7C3AED,#EC4899);
                background-size:200% 200%;animation:gradientFlow 4s ease infinite;
                border-radius:14px;display:flex;align-items:center;justify-content:center;
                font-size:1.4rem;margin:0 auto;
                box-shadow:0 8px 28px rgba(37,99,235,0.45);">🎯</div>
            <div style="position:absolute;bottom:-1px;right:-1px;width:11px;height:11px;
                background:#34D399;border-radius:50%;border:2px solid #030C1A;
                animation:glow 2s infinite;"></div>
        </div>
        <div style="font-size:0.9rem;font-weight:900;color:#E2E8F0;letter-spacing:-0.01em;">HireAI</div>
        <div style="font-size:0.58rem;color:#0A1E38;letter-spacing:0.14em;
            text-transform:uppercase;margin-top:2px;font-weight:700;">Enterprise · v3.0</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<hr style="border:none;border-top:1px solid #0A1E38;margin:4px 0 12px;">', unsafe_allow_html=True)

    uc = st.session_state.get("user_color","#60A5FA")
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,{uc}0D,{uc}05);
        border:1px solid {uc}22;border-radius:12px;
        padding:11px 13px;margin-bottom:14px;display:flex;align-items:center;gap:10px;">
        <div style="width:32px;height:32px;background:{uc}18;border:1px solid {uc}33;
            border-radius:10px;display:flex;align-items:center;justify-content:center;
            font-size:1.1rem;flex-shrink:0;">{st.session_state.user_avatar}</div>
        <div style="min-width:0;">
            <div style="font-size:0.81rem;font-weight:700;color:#E2E8F0;
                white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
                {st.session_state.user_name}</div>
            <div style="font-size:0.63rem;color:#334155;">{st.session_state.user_role}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    page = st.radio("Navigation", [
        "🏠  Dashboard",
        "📄  Upload Candidate",
        "🎙  Generate Interview",
        "📺  Live Interview",
        "📊  Analytics",
        "👥  Candidates",
        "⚙️   Infrastructure",
    ], label_visibility="collapsed")

    st.markdown('<hr style="border:none;border-top:1px solid #0F2540;margin:14px 0 12px;">', unsafe_allow_html=True)

    r_health = api_get("/health", timeout=4)
    connected = r_health is not None and r_health.status_code == 200

    st.markdown(
        f'<div style="font-size:0.62rem;font-weight:800;color:#1E3A5F;text-transform:uppercase;'
        f'letter-spacing:0.1em;margin-bottom:7px;">System Status</div>'
        f'<div style="display:flex;align-items:center;gap:7px;margin-bottom:4px;">'
        f'<div style="width:7px;height:7px;border-radius:50%;background:{"#34D399" if connected else "#F87171"};'
        f'{"animation:glow 2s infinite;" if connected else ""}"></div>'
        f'<span style="font-size:0.76rem;color:{"#34D399" if connected else "#F87171"};font-weight:700;">'
        f'{"CONNECTED" if connected else "OFFLINE"}</span></div>'
        f'<div style="font-size:0.64rem;color:#0F2540;word-break:break-all;margin-bottom:12px;">{BACKEND_URL}</div>',
        unsafe_allow_html=True)

    if st.session_state.assistant_id:
        st.markdown(
            f'<div style="background:rgba(52,211,153,0.06);border:1px solid rgba(52,211,153,0.25);animation:borderPulse 3s infinite;'
            f'border-radius:10px;padding:10px 12px;margin-bottom:12px;">'
            f'<div style="font-size:0.62rem;color:#34D399;font-weight:800;text-transform:uppercase;'
            f'letter-spacing:0.1em;margin-bottom:4px;">Active Session</div>'
            f'<div style="font-size:0.75rem;color:#6EE7B7;font-weight:600;">'
            f'Candidate #{st.session_state.last_candidate_id}</div>'
            f'<div style="font-size:0.62rem;color:#064E3B;margin-top:2px;word-break:break-all;">'
            f'{st.session_state.assistant_id[:22]}...</div></div>',
            unsafe_allow_html=True)

    tip = TIPS[st.session_state.tip_index % len(TIPS)]
    st.markdown(
        f'<div style="background:rgba(99,102,241,0.05);border:1px solid #1E3A5F;'
        f'border-radius:10px;padding:10px 12px;margin-bottom:12px;">'
        f'<div style="font-size:0.62rem;color:#A78BFA;font-weight:800;text-transform:uppercase;'
        f'letter-spacing:0.1em;margin-bottom:5px;">Pro Tip</div>'
        f'<div style="font-size:0.74rem;color:#475569;line-height:1.55;">{tip}</div></div>',
        unsafe_allow_html=True)

    # LLM info chip
    st.markdown(
        '<div style="background:rgba(52,211,153,0.05);border:1px solid #0F2540;' +
        'border-radius:10px;padding:9px 12px;margin-bottom:10px;">' +
        '<div style="font-size:0.62rem;color:#34D399;font-weight:800;text-transform:uppercase;' +
        'letter-spacing:0.1em;margin-bottom:4px;">AI Engine</div>' +
        '<div style="font-size:0.74rem;color:#475569;line-height:1.5;">' +
        'Groq · LLaMA 3.3 70B</div>' +
        '<div style="font-size:0.68rem;color:#1E3A5F;margin-top:2px;">Free tier · 14,400 req/day</div>' +
        '</div>',
        unsafe_allow_html=True)

    st.markdown('<hr style="border:none;border-top:1px solid #0F2540;margin:4px 0 10px;">', unsafe_allow_html=True)

    if st.button("Sign Out", use_container_width=True):
        for k in DEFAULTS:
            st.session_state[k] = DEFAULTS[k]
        st.rerun()

    st.markdown(f'<div style="font-size:0.62rem;color:#0F2540;text-align:center;padding-top:8px;">v{APP_VERSION}</div>', unsafe_allow_html=True)


if page == "🏠  Dashboard":

    # Hero built with native Streamlit components only — zero raw
    # HTML strings, so there is no possibility of markup leaking
    # through as visible text regardless of indentation.
    with st.container(border=True):
        st.caption("Enterprise AI Recruitment Platform")
        st.markdown("# Hire Smarter. :blue[Move Faster.]")
        st.write(
            "HireAI runs live technical voice interviews for every candidate, "
            "scores them across five dimensions the moment the call ends, "
            "and puts a clear hiring recommendation in front of your team "
            "before you would have finished reading a single resume."
        )
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Roles Covered", "56")
        s2.metric("Questions Per Call", "12")
        s3.metric("Scoring Dimensions", "5")
        s4.metric("Evaluation Turnaround", "Under 60s")

    r = api_get("/candidates?limit=1000", timeout=8)
    all_c = r.json() if r and r.status_code == 200 else []

    total       = len(all_c)
    interviewed = sum(1 for c in all_c if c.get("status") in ("Interviewed","Evaluated","Hired","Rejected"))
    hired       = sum(1 for c in all_c if c.get("status") == "Hired")
    rejected    = sum(1 for c in all_c if c.get("status") == "Rejected")
    pending     = sum(1 for c in all_c if c.get("status") in ("Uploaded","Interview Generated"))
    hire_rate   = f"{round(hired/interviewed*100)}%" if interviewed else "0%"

    k1,k2,k3,k4,k5,k6 = st.columns(6)
    for col,icon,val,lbl,clr in [
        (k1,"👥",total,      "Total",        "#60A5FA"),
        (k2,"⏳",pending,    "Pending",      "#FBB724"),
        (k3,"🎤",interviewed,"Interviewed",  "#A78BFA"),
        (k4,"✅",hired,      "Hired",        "#34D399"),
        (k5,"❌",rejected,   "Rejected",     "#F87171"),
        (k6,"📈",hire_rate,  "Hire Rate",    "#60A5FA"),
    ]:
        col.markdown(kpi_card(icon,val,lbl,clr), unsafe_allow_html=True)

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    col_flow, col_activity = st.columns([1.4, 1])

    with col_flow:
        section_title("HOW IT WORKS", "⚡")
        for icon, title, desc in [
            ("📎","Upload Resume","Upload any text-based PDF resume. The AI reads it and extracts a structured profile including skills, years of experience, notable projects, and contact details."),
            ("🧠","Build the Interview","The AI reads the candidate's actual CV and writes a 12-question script built around what that specific person has worked on. Every interview is different because every candidate is different."),
            ("🎤","Run the Interview","Alex, your AI interviewer, runs a live voice call with the candidate. Alex listens to every answer and adapts the conversation naturally, the same way a senior recruiter would."),
            ("📊","Review the Scores","The moment the call ends, every answer is scored across five dimensions and a written recruiter summary lands on your screen. You get a clear Hire, Hold or Pass recommendation with the reasoning behind it."),
            ("📥","Download Report","A colour-coded Excel report is updated after every interview. Download from Analytics and distribute to your hiring team immediately."),
        ]:
            st.markdown(f"""
            <div class="hcard" style="display:flex;gap:14px;align-items:flex-start;
                padding:14px;margin-bottom:7px;
                background:linear-gradient(145deg,#071220,#050E1A);
                border:1px solid #0A1E38;border-radius:13px;cursor:default;">
                <div style="min-width:38px;height:38px;
                    background:linear-gradient(135deg,rgba(37,99,235,0.18),rgba(124,58,237,0.1));
                    border:1px solid #1E3A5F;border-radius:11px;display:flex;align-items:center;
                    justify-content:center;font-size:1.15rem;flex-shrink:0;">{icon}</div>
                <div>
                    <div style="font-weight:700;color:#E2E8F0;font-size:0.87rem;margin-bottom:3px;">{title}</div>
                    <div style="color:#334155;font-size:0.79rem;line-height:1.55;">{desc}</div>
                </div>
            </div>""", unsafe_allow_html=True)

    with col_activity:
        section_title("RECENT ACTIVITY", "🕐")
        recent = sorted(all_c, key=lambda x: x.get("created_at") or "", reverse=True)[:8]
        if recent:
            for c in recent:
                st.markdown(f"""
                <div class="hcard" style="display:flex;align-items:center;justify-content:space-between;
                    padding:9px 13px;margin-bottom:5px;cursor:default;
                    background:#071220;border:1px solid #0A1E38;border-radius:10px;">
                    <div>
                        <div style="font-size:0.8rem;font-weight:600;color:#CBD5E1;">{c.get("name","—")}</div>
                        <div style="font-size:0.67rem;color:#334155;margin-top:1px;">{c.get("applied_role","")[:26]}</div>
                    </div>
                    {badge(c.get("status","—"))}
                </div>""", unsafe_allow_html=True)
        else:
            st.markdown('<div style="text-align:center;padding:28px;color:#1E3A5F;font-size:0.83rem;">No candidates yet.</div>', unsafe_allow_html=True)

        section_title("SCORING DIMENSIONS", "🎯")
        for icon, name, clr in [
            ("🔬","Technical Depth","#60A5FA"),
            ("💬","Communication","#A78BFA"),
            ("🧩","Problem Solving","#34D399"),
            ("📋","Experience Alignment","#FBB724"),
            ("🤝","Culture Fit","#F472B6"),
        ]:
            st.markdown(f"""
            <div class="hcard" style="display:flex;align-items:center;gap:9px;padding:7px 11px;margin-bottom:4px;
                background:#071220;border:1px solid #0A1E38;border-radius:8px;cursor:default;">
                <span style="font-size:0.95rem;">{icon}</span>
                <span style="font-size:0.78rem;color:#94A3B8;">{name}</span>
                <div style="margin-left:auto;width:7px;height:7px;border-radius:50%;background:{clr};box-shadow:0 0 7px {clr}88;"></div>
            </div>""", unsafe_allow_html=True)

    section_title("TECHNOLOGY STACK", "🛠️")
    t1,t2,t3 = st.columns(3)
    for col,icon,title,desc,clr,bg in [
        (t1,"🎤","AI Voice Interviews",
         "Vapi AI and Daily.co WebRTC power real-time voice sessions. Alex the interviewer adapts every question based on what the candidate actually says.",
         "#60A5FA","rgba(37,99,235,0.08)"),
        (t2,"📊","Smart Evaluation Engine",
         "Five-dimension scoring with automatic Hire or Reject or Hold decisions. Colour-coded Excel reports ready to download after every session.",
         "#A78BFA","rgba(124,58,237,0.08)"),
        (t3,"🧠","Groq CV Intelligence",
         "LLaMA 3.3 70B parses every resume and writes a 12-question interview script personalised to that specific candidate and their applied role.",
         "#34D399","rgba(16,185,129,0.08)"),
    ]:
        col.markdown(f"""
        <div class="hcard" style="background:linear-gradient(145deg,#071220,#050E1A);
            border:1px solid #0A1E38;border-radius:16px;padding:20px;margin-bottom:10px;cursor:default;">
            <div style="width:44px;height:44px;background:{bg};border:1px solid {clr}22;
                border-radius:13px;display:flex;align-items:center;justify-content:center;
                font-size:1.4rem;margin-bottom:14px;
                box-shadow:0 0 20px {clr}22;">{icon}</div>
            <div style="font-weight:800;color:#E2E8F0;font-size:0.9rem;margin-bottom:7px;">{title}</div>
            <div style="color:#334155;font-size:0.77rem;line-height:1.6;">{desc}</div>
            <div style="width:28px;height:2px;background:{clr};margin-top:14px;
                border-radius:999px;box-shadow:0 0 8px {clr}88;"></div>
        </div>""", unsafe_allow_html=True)

    st.markdown(
        "<div style='display:flex;flex-wrap:wrap;gap:7px;margin-top:6px;'>" +
        "".join(pill(t) for t in [
            "FastAPI","SQLAlchemy","Pydantic v2","Vapi AI","Daily.co WebRTC",
            "Deepgram STT","ElevenLabs TTS","GPT-4o","Groq API","LLaMA 3.3 70B",
            "OpenPyXL","Streamlit Cloud","Python 3.11","Render","bcrypt Auth",
        ]) + "</div>",
        unsafe_allow_html=True)


elif page == "📄  Upload Candidate":

    page_header("📄 Upload Candidate",
                "Upload a candidate resume and the platform parses it automatically using local AI.")

    st.markdown("""
    <div style="background:rgba(37,99,235,0.07);border-left:4px solid #3B82F6;
        border-radius:10px;padding:13px 17px;margin-bottom:22px;color:#93C5FD;font-size:0.86rem;">
        Upload a <strong>text-based PDF</strong> resume. The AI reads the document, extracts structured
        data including skills, work history, and contact details, then stores everything ready for
        the interview generation step. Scanned or image-only PDFs will not parse correctly.
    </div>
    """, unsafe_allow_html=True)

    col_form, col_info = st.columns([2, 1])

    with col_form:
        with st.form("upload_form", clear_on_submit=False):
            st.markdown(
                '<div style="font-size:0.67rem;font-weight:800;color:#334155;text-transform:uppercase;'
                'letter-spacing:0.12em;border-bottom:1px solid #0F2540;padding-bottom:9px;'
                'margin-bottom:18px;">Candidate Details</div>',
                unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            with c1:
                candidate_name = st.text_input("Full Name", placeholder="e.g. Ali Raza")
            with c2:
                role = st.selectbox("Applied Role", ROLES)
            uploaded_file = st.file_uploader("Resume PDF (max 10 MB)", type=["pdf"])
            submitted = st.form_submit_button("Upload and Parse Resume", use_container_width=True)

        if submitted:
            if not candidate_name.strip():
                st.error("Candidate name is required.")
            elif not uploaded_file:
                st.error("Please upload a PDF resume.")
            else:
                with st.spinner("Parsing CV with Groq LLaMA 3.3 70B. Usually 10 to 20 seconds."):
                    resp = api_post(
                        "/candidates/upload",
                        files={"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")},
                        data={"name": candidate_name.strip(), "role": role},
                        timeout=180,
                    )
                if resp is None:
                    st.error("Cannot reach the backend. Check BACKEND_URL and ensure ngrok is running.")
                elif resp.status_code in (200, 201):
                    result = resp.json()
                    st.session_state.last_candidate_id = result["id"]
                    st.session_state.candidate_data = result
                    st.session_state.tip_index += 1
                    st.markdown(f"""
                    <div style="background:rgba(52,211,153,0.07);border-left:4px solid #34D399;
                        border-radius:10px;padding:13px 17px;margin:10px 0;color:#6EE7B7;font-size:0.86rem;">
                        Candidate uploaded successfully. ID: <strong>#{result['id']}</strong> for
                        <strong>{result['name']}</strong>. Head to Generate Interview to create the voice assistant.
                    </div>""", unsafe_allow_html=True)
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Candidate ID", f"#{result['id']}")
                    m2.metric("Years Experience", result.get("years_experience") or "Unknown")
                    m3.metric("Skills Detected", len(result.get("skills") or []))
                    if result.get("skills"):
                        st.markdown(
                            "<div style='margin-top:12px;font-size:0.68rem;font-weight:800;color:#334155;"
                            "text-transform:uppercase;letter-spacing:0.1em;margin-bottom:8px;'>Detected Skills</div>" +
                            "".join(pill(s) for s in result["skills"]),
                            unsafe_allow_html=True)
                    if result.get("cv_summary"):
                        with st.expander("View Candidate Summary"):
                            st.markdown(result["cv_summary"])
                else:
                    st.error(f"Upload failed ({resp.status_code}): {resp.text}")

    with col_info:
        st.markdown("""
        <div style="background:linear-gradient(145deg,#071220,#050E1A);border:1px solid #0A1E38;
            border-radius:16px;padding:20px;">
            <div style="font-size:0.6rem;font-weight:800;color:#1E3A5F;text-transform:uppercase;
                letter-spacing:0.14em;margin-bottom:16px;">Upload Guidelines</div>
            <div style="margin-bottom:16px;">
                <div style="color:#34D399;font-weight:700;font-size:0.8rem;margin-bottom:7px;">Accepted</div>
                <div style="color:#475569;font-size:0.78rem;line-height:2.1;">
                    Text-based PDF resumes only<br>
                    Maximum 10 MB per file<br>
                    Up to 30 pages<br>
                    English language
                </div>
            </div>
            <div style="margin-bottom:16px;">
                <div style="color:#F87171;font-weight:700;font-size:0.8rem;margin-bottom:7px;">Not Accepted</div>
                <div style="color:#475569;font-size:0.78rem;line-height:2.1;">
                    Scanned or image-only PDFs<br>
                    Word documents<br>
                    Password-protected files
                </div>
            </div>
            <div style="margin-bottom:16px;">
                <div style="color:#FBB724;font-weight:700;font-size:0.8rem;margin-bottom:7px;">Processing Time</div>
                <div style="color:#475569;font-size:0.78rem;line-height:1.7;">
                    Parsing usually takes 10 to 20 seconds.
                    Keep the tab open while the spinner is running.
                </div>
            </div>
            <div>
                <div style="color:#A78BFA;font-weight:700;font-size:0.8rem;margin-bottom:7px;">What Gets Extracted</div>
                <div style="color:#475569;font-size:0.78rem;line-height:2.1;">
                    Name and contact details<br>
                    Technical skills and tools<br>
                    Years of experience<br>
                    Projects and education background<br>
                    A written professional summary
                </div>
            </div>
        </div>""", unsafe_allow_html=True)

        # SVG decorative element instead of external image
        st.markdown("""
        <div style="margin-top:10px;background:linear-gradient(145deg,#071220,#050E1A);
            border:1px solid #0A1E38;border-radius:13px;padding:18px;text-align:center;">
            <svg width="48" height="48" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect width="48" height="48" rx="12" fill="rgba(37,99,235,0.1)"/>
                <path d="M24 14v14M17 21l7-7 7 7" stroke="#3B82F6" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                <path d="M14 34h20" stroke="#3B82F6" stroke-width="2" stroke-linecap="round"/>
            </svg>
            <div style="font-size:0.72rem;color:#1E3A5F;margin-top:8px;font-weight:600;">
                Drag & drop or click to upload
            </div>
        </div>""", unsafe_allow_html=True)


elif page == "🎙  Generate Interview":

    page_header("🎙 Generate Interview",
                "Create a personalised interview for this candidate based on what is actually in their CV.")

    col_gen, col_side = st.columns([1.6, 1])

    with col_gen:
        candidate_id = st.number_input("Candidate ID", min_value=1,
                                        value=int(st.session_state.last_candidate_id))
        preview = api_get(f"/candidates/{candidate_id}", timeout=8)
        if preview and preview.status_code == 200:
            c = preview.json()
            st.markdown(f"""
            <div class="hcard" style="background:linear-gradient(145deg,#071220,#050E1A);border:1px solid #0A1E38;
                border-radius:13px;padding:16px;margin:10px 0 18px;cursor:default;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
                    <div style="font-weight:800;color:#E2E8F0;font-size:0.95rem;">{c['name']}</div>
                    {badge(c['status'])}
                </div>
                <div style="font-size:0.76rem;color:#475569;display:flex;gap:16px;flex-wrap:wrap;">
                    <span>🎯 {c['applied_role']}</span>
                    <span>📅 {c.get('years_experience') or '?'} yrs experience</span>
                    <span>🗓 {fmt_dt(c.get('created_at'))}</span>
                </div>
                {"<div style='margin-top:8px;'>" + "".join(pill(s) for s in (c.get('skills') or [])[:5]) + "</div>" if c.get('skills') else ""}
            </div>""", unsafe_allow_html=True)
        elif preview and preview.status_code == 404:
            st.markdown("""
            <div style="background:rgba(248,113,113,0.07);border-left:4px solid #F87171;
                border-radius:10px;padding:11px 15px;color:#FCA5A5;font-size:0.83rem;margin-bottom:12px;">
                No candidate found with that ID. Upload a candidate first.
            </div>""", unsafe_allow_html=True)

        if st.button("Generate AI Interview Assistant", use_container_width=True):
            with st.spinner("Building interview prompt and creating Vapi assistant. About 30 seconds."):
                resp = api_post(f"/vapi/generate/{candidate_id}", timeout=90)
            if resp is None:
                st.error("Backend unreachable. Check ngrok and uvicorn.")
            elif resp.status_code == 200:
                result = resp.json()
                asst_id = result["vapi"]["assistant_id"]
                st.session_state.assistant_id = asst_id
                st.session_state.last_candidate_id = candidate_id
                st.session_state.tip_index += 1
                st.markdown(f"""
                <div style="background:rgba(52,211,153,0.07);border-left:4px solid #34D399;
                    border-radius:10px;padding:13px 17px;color:#6EE7B7;font-size:0.86rem;margin-top:10px;">
                    Interview assistant created for <strong>{result['candidate_name']}</strong>
                    applying for <strong>{result['applied_role']}</strong>.
                    The assistant has read the CV and knows exactly what questions to ask.
                    Go to Live Interview when you are ready to start the call.
                </div>""", unsafe_allow_html=True)
                st.code(f"Assistant ID: {asst_id}", language=None)
            else:
                try:
                    err = resp.json().get("detail", resp.text)
                except Exception:
                    err = resp.text
                st.error(f"Failed ({resp.status_code}): {err}")

    with col_side:
        st.markdown(
            '<div style="background:linear-gradient(145deg,#071220,#050E1A);'
            'border:1px solid #0A1E38;border-radius:16px;padding:20px;">'
            '<div style="font-size:0.6rem;font-weight:800;color:#1E3A5F;'
            'text-transform:uppercase;letter-spacing:0.14em;margin-bottom:16px;">What Happens Inside</div>' +
            "".join(f"""
            <div style="display:flex;gap:12px;align-items:flex-start;margin-bottom:14px;">
                <div style="min-width:28px;height:28px;background:linear-gradient(135deg,#2563EB,#4F46E5);
                    border-radius:50%;display:flex;align-items:center;justify-content:center;
                    font-size:0.75rem;font-weight:900;color:white;flex-shrink:0;">{n}</div>
                <div>
                    <div style="font-weight:700;color:#CBD5E1;font-size:0.82rem;margin-bottom:2px;">{t}</div>
                    <div style="color:#334155;font-size:0.75rem;line-height:1.5;">{d}</div>
                </div>
            </div>""" for n,t,d in [
                (1,"Profile Loaded","Everything collected from the resume at upload time is pulled in and ready to use."),
                (2,"Interview Script Built","The LLM writes a 12-question plan tailored to this candidate's CV and the role they applied for."),
                (3,"Vapi Assistant Created","A dedicated Vapi assistant is created with the personalised script injected as its system prompt."),
                (4,"Ready to Interview","The assistant ID is saved in your session. Head to Live Interview to start the call."),
            ]) + "</div>",
            unsafe_allow_html=True)

        st.markdown("""
        <div style="margin-top:10px;background:linear-gradient(145deg,#071220,#050E1A);
            border:1px solid #0A1E38;border-radius:13px;padding:18px;text-align:center;">
            <svg width="48" height="48" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect width="48" height="48" rx="12" fill="rgba(124,58,237,0.1)"/>
                <circle cx="24" cy="20" r="6" stroke="#8B5CF6" stroke-width="2"/>
                <path d="M14 36c0-5.523 4.477-10 10-10s10 4.477 10 10" stroke="#8B5CF6" stroke-width="2" stroke-linecap="round"/>
            </svg>
            <div style="font-size:0.72rem;color:#1E3A5F;margin-top:8px;font-weight:600;">
                Candidate-specific interview
            </div>
        </div>""", unsafe_allow_html=True)


elif page == "📺  Live Interview":

    page_header("📺 Live Voice Interview",
                "Alex the AI interviewer conducts the session live. Every question comes directly from the candidate's CV.")

    assistant_id = st.session_state.assistant_id

    if not assistant_id:
        st.markdown("""
        <div style="background:rgba(251,191,36,0.07);border-left:4px solid #FBB724;
            border-radius:10px;padding:15px 19px;color:#FDE68A;font-size:0.87rem;">
            No interview session is active. Go to Generate Interview, pick a candidate,
            create the assistant, then come back here and click Start.
        </div>""", unsafe_allow_html=True)

    else:
        st.markdown(f"""
        <div style="background:rgba(52,211,153,0.06);border-left:4px solid #34D399;
            border-radius:10px;padding:11px 17px;margin-bottom:14px;
            display:flex;align-items:center;gap:11px;">
            <div style="width:7px;height:7px;border-radius:50%;background:#34D399;
                box-shadow:0 0 10px #34D399;flex-shrink:0;"></div>
            <div style="color:#6EE7B7;font-size:0.84rem;">
                <strong>Interview assistant ready.</strong>
                Candidate #{st.session_state.last_candidate_id}
                &nbsp;&nbsp;<code style="font-size:0.76rem;">{assistant_id[:22]}...</code>
            </div>
        </div>""", unsafe_allow_html=True)

        # ── PERMANENT FIX FOR postMessage null-origin error ──
        # Every iframe approach (components.html, components.iframe,
        # data: URI) produces a sandboxed null origin that Daily.co's
        # call-machine bundle rejects with postMessage errors.
        # The ONLY reliable fix: inject the Vapi SDK directly into
        # the Streamlit page (not an iframe). This runs in the real
        # browser window with a real HTTPS or localhost origin.
        # Works identically on local, ngrok, and Streamlit Cloud.

        _vapi_key = VAPI_PUBLIC_KEY
        _asst_id  = assistant_id
        vapi_js = f"""
<div id="hireai-widget" style="
    background:linear-gradient(145deg,#071220,#050E1A);
    border:1px solid #0A1E38;border-radius:20px;
    padding:22px;margin-bottom:12px;
    box-shadow:0 20px 60px rgba(0,0,0,0.6);
    font-family:-apple-system,BlinkMacSystemFont,'Inter',sans-serif;
">
<!-- TOP BAR -->
<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:18px;">
    <div>
        <div style="font-size:1rem;font-weight:800;letter-spacing:-0.01em;
            background:linear-gradient(135deg,#60A5FA,#A78BFA);
            -webkit-background-clip:text;-webkit-text-fill-color:transparent;">
            HireAI Live Interview
        </div>
        <div style="font-size:0.66rem;color:#1E3A5F;margin-top:2px;">
            Enterprise Voice Platform · Vapi AI
        </div>
    </div>
    <div style="display:flex;align-items:center;gap:7px;background:#030A16;
        padding:6px 13px;border-radius:999px;border:1px solid #0A1E38;">
        <div id="hw-dot" style="width:8px;height:8px;border-radius:50%;
            background:#1E3A5F;flex-shrink:0;transition:all 0.4s;"></div>
        <span id="hw-status-chip" style="font-size:0.68rem;color:#1E3A5F;font-weight:600;">READY</span>
    </div>
</div>

<!-- MIC BANNER -->
<div id="hw-mic-banner" style="background:rgba(251,191,36,0.07);border:1px solid rgba(251,191,36,0.25);
    border-radius:11px;padding:11px 14px;margin-bottom:14px;display:flex;align-items:center;gap:10px;
    font-size:0.78rem;color:#FDE68A;">
    <span style="font-size:1.1rem;">🎤</span>
    <span>Click <strong>Start Interview</strong> then allow microphone access when your browser asks.
    If blocked, click the lock icon in the address bar and set Microphone to Allow.</span>
</div>

<!-- RETRY BANNER -->
<div id="hw-retry-banner" style="display:none;background:rgba(96,165,250,0.07);
    border:1px solid rgba(96,165,250,0.25);border-radius:11px;padding:10px 14px;
    margin-bottom:14px;align-items:center;justify-content:space-between;gap:10px;
    font-size:0.78rem;color:#93C5FD;">
    <span id="hw-retry-msg">Connection dropped. Click Resume to continue.</span>
    <button id="hw-resume" style="background:#2563EB;color:white;border:none;
        border-radius:8px;padding:6px 14px;font-size:0.74rem;font-weight:700;cursor:pointer;">
        Resume
    </button>
</div>

<!-- BUTTONS -->
<div style="display:flex;gap:10px;margin-bottom:14px;">
    <button id="hw-start" style="flex:1;border:none;padding:14px;
        border-radius:12px;background:linear-gradient(135deg,#2563EB,#4F46E5);
        color:white;font-size:0.88rem;font-weight:800;cursor:pointer;
        box-shadow:0 6px 20px rgba(37,99,235,0.35);transition:all 0.25s;
        font-family:inherit;">
        🚀 Start Interview
    </button>
    <button id="hw-stop" disabled style="flex:1;border:none;padding:14px;
        border-radius:12px;background:linear-gradient(135deg,#991B1B,#7F1D1D);
        color:white;font-size:0.88rem;font-weight:800;cursor:pointer;opacity:0.3;
        transition:all 0.25s;font-family:inherit;">
        🛑 End Interview
    </button>
</div>

<!-- STATUS -->
<div style="background:#030A16;border:1px solid #0A1E38;border-radius:11px;
    padding:13px 15px;margin-bottom:13px;">
    <div id="hw-status" style="font-size:0.88rem;font-weight:700;color:#34D399;">
        System ready — click Start Interview to begin.
    </div>
</div>

<!-- METRICS GRID -->
<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:13px;">
    <div style="background:#030A16;border:1px solid #0A1E38;border-radius:11px;padding:10px 11px;">
        <div style="color:#1E3A5F;font-size:0.56rem;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:3px;font-weight:800;">Timer</div>
        <div id="hw-timer" style="font-size:0.86rem;font-weight:800;color:#E2E8F0;">0:00</div>
    </div>
    <div id="hw-mc-conn" style="background:#030A16;border:1px solid #0A1E38;border-radius:11px;padding:10px 11px;">
        <div style="color:#1E3A5F;font-size:0.56rem;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:3px;font-weight:800;">Connection</div>
        <div id="hw-conn" style="font-size:0.75rem;font-weight:800;color:#E2E8F0;">IDLE</div>
    </div>
    <div id="hw-mc-audio" style="background:#030A16;border:1px solid #0A1E38;border-radius:11px;padding:10px 11px;">
        <div style="color:#1E3A5F;font-size:0.56rem;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:3px;font-weight:800;">Microphone</div>
        <div id="hw-audio" style="font-size:0.75rem;font-weight:800;color:#E2E8F0;">STANDBY</div>
    </div>
    <div id="hw-mc-ai" style="background:#030A16;border:1px solid #0A1E38;border-radius:11px;padding:10px 11px;">
        <div style="color:#1E3A5F;font-size:0.56rem;text-transform:uppercase;letter-spacing:0.1em;margin-bottom:3px;font-weight:800;">AI Status</div>
        <div id="hw-ai" style="font-size:0.75rem;font-weight:800;color:#E2E8F0;">—</div>
    </div>
</div>

<!-- WAVEFORM -->
<div style="margin-bottom:13px;">
    <div style="color:#1E3A5F;font-size:0.63rem;font-weight:700;text-transform:uppercase;letter-spacing:0.09em;margin-bottom:5px;">Audio Waveform</div>
    <canvas id="hw-wave" style="width:100%;height:44px;border-radius:8px;background:#030A16;border:1px solid #0A1E38;display:block;"></canvas>
</div>

<!-- LIVE TRANSCRIPT -->
<div style="margin-bottom:13px;">
    <div style="display:flex;justify-content:space-between;align-items:center;
        color:#1E3A5F;font-size:0.63rem;font-weight:700;text-transform:uppercase;
        letter-spacing:0.09em;margin-bottom:5px;">
        <span>Live Transcript</span>
        <span id="hw-turn-count">0 turns</span>
    </div>
    <div id="hw-transcript" style="background:#020810;border:1px solid #0A1E38;
        border-radius:11px;padding:13px;height:220px;overflow-y:auto;">
        <div id="hw-transcript-empty" style="display:flex;align-items:center;
            justify-content:center;height:100%;color:#1E3A5F;font-size:0.76rem;text-align:center;">
            The conversation will appear here as it happens.
        </div>
    </div>
</div>

<!-- ACTIVITY LOG -->
<div>
    <div style="color:#1E3A5F;font-size:0.63rem;font-weight:700;text-transform:uppercase;letter-spacing:0.09em;margin-bottom:5px;">Activity Log</div>
    <div id="hw-logs" style="background:#020810;border:1px solid #0A1E38;
        border-radius:11px;padding:11px;height:120px;overflow-y:auto;"></div>
</div>

</div>

<script type="module">
// ── Load Vapi SDK directly in the page — no iframe ────────
import Vapi from "https://esm.sh/@vapi-ai/web@1.2.1";

const VAPI_KEY      = "{_vapi_key}";
const ASSISTANT_ID  = "{_asst_id}";

// ── Helpers ───────────────────────────────────────────────
const $ = id => document.getElementById(id);
let vapi = null, active = false, init = false;
let t0 = null, timerInt = null, reg = false;
let volumeLevel = 0, turnCount = 0;
let lastPEl = null, lastPRole = null;
let callClean = false, dropped = false;

function log(msg, type="info") {{
    const colors = {{info:"#334155",error:"#F87171",success:"#34D399",warning:"#FBB724",system:"#A78BFA"}};
    const row = document.createElement("div");
    row.style.cssText = "display:flex;gap:8px;padding:5px 0;border-bottom:1px solid #030A16;font-size:0.7rem;";
    const ts = document.createElement("span");
    ts.style.cssText = "color:#0A1E38;font-size:0.62rem;flex-shrink:0;font-family:monospace;";
    ts.textContent = new Date().toLocaleTimeString();
    const txt = document.createElement("span");
    txt.style.color = colors[type] || colors.info;
    txt.textContent = msg;
    row.append(ts, txt);
    $("hw-logs").append(row);
    $("hw-logs").scrollTop = $("hw-logs").scrollHeight;
}}

function setStatus(msg, color="#34D399") {{
    $("hw-status").textContent = msg;
    $("hw-status").style.color = color;
}}

function setBtns(on) {{
    $("hw-start").disabled = on;
    $("hw-start").style.opacity = on ? "0.3" : "1";
    $("hw-stop").disabled = !on;
    $("hw-stop").style.opacity = on ? "1" : "0.3";
}}

function startTimer() {{
    t0 = Date.now(); clearInterval(timerInt);
    timerInt = setInterval(() => {{
        if (!active) return;
        const s = Math.floor((Date.now() - t0) / 1000);
        $("hw-timer").textContent = Math.floor(s/60) + ":" + String(s%60).padStart(2,"0");
    }}, 1000);
}}

async function cleanup() {{
    clearInterval(timerInt);
    volumeLevel = 0;
    $("hw-dot").style.background = "#1E3A5F";
    $("hw-dot").style.boxShadow = "";
    $("hw-status-chip").textContent = "READY";
    $("hw-conn").textContent = "IDLE";
    $("hw-audio").textContent = "STANDBY";
    $("hw-ai").textContent = "—";
    setBtns(false);
    active = false; init = false;
    if (vapi) {{ try {{ await vapi.stop(); }} catch(_) {{}} }}
    vapi = null;
}}

// ── Waveform ──────────────────────────────────────────────
const cv = $("hw-wave"), ctx = cv.getContext("2d");
function resizeWave() {{
    cv.width = cv.offsetWidth * devicePixelRatio;
    cv.height = cv.offsetHeight * devicePixelRatio;
    ctx.scale(devicePixelRatio, devicePixelRatio);
}}
resizeWave();
window.addEventListener("resize", resizeWave);
let bars = new Array(48).fill(0);
function drawWave() {{
    const W = cv.offsetWidth, H = cv.offsetHeight;
    ctx.clearRect(0, 0, W, H);
    const bw = W / bars.length, gap = 2;
    bars.forEach((v, i) => {{
        const h = Math.max(2, v * H * 0.85);
        const x = i * bw + gap/2;
        const alpha = active ? 0.9 : 0.25;
        const r = v > 0.6 ? "248,113,113" : v > 0.3 ? "96,165,250" : "52,211,153";
        ctx.fillStyle = active ? `rgba(${{r}},${{alpha}})` : "rgba(30,58,95,0.5)";
        ctx.beginPath();
        ctx.roundRect(x, (H-h)/2, bw-gap, h, 2);
        ctx.fill();
    }});
    bars.shift();
    bars.push(active ? Math.min(1, volumeLevel + Math.random()*0.06) : Math.random()*0.04);
    requestAnimationFrame(drawWave);
}}
drawWave();

// ── Sentiment ─────────────────────────────────────────────
const HESITANT = [" um "," uh ","i think","maybe","not sure","i guess","sort of","kind of","probably","i suppose","to be honest","i feel like"];
const CONFIDENT = ["i built","i led","i designed","i implemented","i deployed","i created","i launched","specifically","exactly","absolutely","definitely","in my experience","we shipped","production"];
function sentiment(t) {{
    const tx = " " + t.toLowerCase() + " ";
    const h = HESITANT.filter(m => tx.includes(m)).length;
    const c = CONFIDENT.filter(m => tx.includes(m)).length;
    return c > h && c > 0 ? "confident" : h > c && h > 0 ? "hesitant" : "neutral";
}}

// ── Transcript ────────────────────────────────────────────
const sentColors = {{confident:"#34D399", neutral:"#64748B", hesitant:"#FBB724"}};
const sentBg     = {{confident:"rgba(52,211,153,0.1)", neutral:"rgba(100,116,139,0.1)", hesitant:"rgba(251,191,36,0.1)"}};

function addTurn(role, text, isFinal) {{
    const empty = $("hw-transcript-empty");
    if (empty) empty.remove();
    const panel = $("hw-transcript");
    if (!isFinal && lastPEl && lastPRole === role) {{
        lastPEl.querySelector(".hw-turn-text").textContent = text;
        panel.scrollTop = panel.scrollHeight;
        return;
    }}
    const wrap = document.createElement("div");
    wrap.style.cssText = "display:flex;gap:9px;align-items:flex-start;padding:9px 0;border-bottom:1px solid #030A16;";
    const isAI = role === "assistant";
    const av = document.createElement("div");
    av.style.cssText = `min-width:24px;height:24px;border-radius:7px;display:flex;align-items:center;justify-content:center;font-size:0.7rem;font-weight:800;background:${{isAI?"rgba(167,139,250,0.15)":"rgba(52,211,153,0.15)"}};color:${{isAI?"#A78BFA":"#34D399"}};flex-shrink:0;`;
    av.textContent = isAI ? "AI" : "C";
    const body = document.createElement("div");
    body.style.cssText = "flex:1;min-width:0;";
    const head = document.createElement("div");
    head.style.cssText = "display:flex;align-items:center;gap:7px;margin-bottom:3px;";
    const nm = document.createElement("span");
    nm.style.cssText = "font-size:0.7rem;font-weight:700;color:#64748B;";
    nm.textContent = isAI ? "Alex" : "Candidate";
    head.appendChild(nm);
    if (!isAI && isFinal) {{
        const s = sentiment(text);
        const tag = document.createElement("span");
        tag.style.cssText = `font-size:0.58rem;font-weight:700;padding:1px 7px;border-radius:999px;text-transform:uppercase;background:${{sentBg[s]}};color:${{sentColors[s]}};`;
        tag.textContent = s;
        head.appendChild(tag);
    }}
    const txt = document.createElement("div");
    txt.className = "hw-turn-text";
    txt.style.cssText = `font-size:0.76rem;line-height:1.5;color:${{isFinal?"#CBD5E1":"#334155"}};font-style:${{isFinal?"normal":"italic"}};`;
    txt.textContent = text;
    body.append(head, txt);
    wrap.append(av, body);
    panel.appendChild(wrap);
    panel.scrollTop = panel.scrollHeight;
    if (!isFinal) {{ lastPEl = wrap; lastPRole = role; }}
    else {{
        lastPEl = null; lastPRole = null;
        turnCount++;
        $("hw-turn-count").textContent = turnCount + (turnCount === 1 ? " turn" : " turns");
    }}
}}

// ── Event wiring ──────────────────────────────────────────
function wireEvents() {{
    if (reg) return; reg = true;

    vapi.on("call-start", () => {{
        active = true; dropped = false;
        $("hw-retry-banner").style.display = "none";
        startTimer();
        setStatus("Interview is live — Alex is speaking first", "#34D399");
        $("hw-dot").style.background = "#34D399";
        $("hw-dot").style.boxShadow = "0 0 12px #34D399";
        $("hw-status-chip").textContent = "LIVE";
        $("hw-conn").textContent = "CONNECTED";
        $("hw-ai").textContent = "ACTIVE";
        log("Interview started", "success");
    }});

    vapi.on("speech-start", () => {{
        setStatus("Alex is speaking — listen carefully", "#A78BFA");
        $("hw-audio").textContent = "AI SPEAKING";
        $("hw-ai").textContent = "SPEAKING";
    }});

    vapi.on("speech-end", () => {{
        setStatus("Your turn to respond — speak clearly", "#34D399");
        $("hw-audio").textContent = "LISTENING";
        $("hw-ai").textContent = "LISTENING";
    }});

    vapi.on("volume-level", v => {{ volumeLevel = v; }});

    vapi.on("message", msg => {{
        if (msg?.type === "transcript" && msg?.transcript) {{
            addTurn(msg.role, msg.transcript, msg.transcriptType === "final");
        }}
    }});

    vapi.on("error", e => {{
        const msg = e?.message || e?.errorMsg || JSON.stringify(e);
        log("Error: " + msg, "error");
        setStatus("Connection error — see log for details", "#EF4444");
        $("hw-conn").textContent = "ERROR";
        if (active && !callClean) dropped = true;
    }});

    vapi.on("call-end", async () => {{
        const wasActive = active;
        if (wasActive && !callClean && dropped) {{
            log("Call dropped — you can resume", "warning");
            setStatus("Connection dropped. Click Resume to continue.", "#FBB724");
            $("hw-retry-banner").style.display = "flex";
        }} else {{
            log("Interview complete — evaluation processing now", "warning");
            setStatus("Done! Scores appear in Candidates within 60 seconds.", "#FBB724");
        }}
        $("hw-status-chip").textContent = "ENDED";
        await cleanup();
    }});
}}

// ── Start ─────────────────────────────────────────────────
async function hwStart() {{
    if (init || active) {{ log("Session already active", "warning"); return; }}
    init = true; setBtns(true); callClean = false;
    $("hw-mic-banner").style.display = "none";
    $("hw-retry-banner").style.display = "none";

    try {{
        log("Requesting microphone...", "system");
        setStatus("Requesting microphone access — allow when prompted", "#F59E0B");

        if (!navigator.mediaDevices?.getUserMedia) {{
            throw new Error("Microphone API unavailable. Open this page over HTTPS.");
        }}

        let stream;
        try {{
            stream = await navigator.mediaDevices.getUserMedia({{
                audio: {{ echoCancellation:true, noiseSuppression:true, sampleRate:16000 }}
            }});
        }} catch (micErr) {{
            const n = micErr.name;
            if (n==="NotAllowedError"||n==="PermissionDeniedError")
                throw new Error("Microphone denied. Click the lock icon in your address bar → Microphone → Allow → refresh.");
            if (n==="NotFoundError"||n==="DevicesNotFoundError")
                throw new Error("No microphone found. Plug in a headset and try again.");
            if (n==="NotReadableError"||n==="TrackStartError")
                throw new Error("Microphone in use by another app. Close other tabs and try again.");
            throw micErr;
        }}

        log("Microphone granted", "success");
        $("hw-audio").textContent = "MIC READY";
        stream.getTracks().forEach(t => t.stop());

        log("Loading Vapi SDK...", "system");
        setStatus("Initialising Vapi SDK...", "#3B82F6");
        vapi = new Vapi(VAPI_KEY);
        window._hwVapi = vapi;
        log("Vapi SDK ready", "success");

        wireEvents();

        log("Connecting to assistant...", "system");
        setStatus("Connecting to your interview assistant...", "#3B82F6");
        $("hw-conn").textContent = "CONNECTING";

        // Use vapi transport to avoid Daily.co null-origin postMessage error
        // Pass transport options - avoids Daily.co iframe null-origin error
        await vapi.start(ASSISTANT_ID, {{
            metadata: {{}},
        }});
        log("Connected — interview starting", "success");

    }} catch(err) {{
        const msg = err?.message || String(err);
        log("Error: " + msg, "error");
        setStatus(msg, "#EF4444");
        $("hw-mic-banner").style.display = "flex";
        await cleanup();
    }} finally {{
        init = false;
    }}
}}

// ── Stop ──────────────────────────────────────────────────
async function hwStop() {{
    try {{
        callClean = true; dropped = false;
        setStatus("Ending session...", "#F59E0B");
        log("Ending interview", "warning");
        if (window._hwVapi) await window._hwVapi.stop();
        await cleanup();
        setStatus("Interview ended. Check Candidates for your scores.", "#475569");
        log("Session ended", "success");
    }} catch(err) {{
        log("Stop error: " + (err?.message||String(err)), "error");
    }}
}}

// ── Resume ────────────────────────────────────────────────
async function hwResume() {{
    $("hw-retry-banner").style.display = "none";
    log("Resuming session...", "system");
    await hwStart();
}}

// Wire buttons via event listeners (module scope fix)
// onclick= attributes cannot reach module-scoped functions,
// so we attach listeners directly to the DOM elements.
document.getElementById("hw-start").addEventListener("click", hwStart);
document.getElementById("hw-stop").addEventListener("click", hwStop);
const resumeBtn = document.getElementById("hw-resume");
if (resumeBtn) resumeBtn.addEventListener("click", hwResume);

window.addEventListener("beforeunload", async () => {{ await cleanup(); }});

log("HireAI interview platform ready", "success");
</script>
"""
        # components.html() executes JS — st.markdown strips it
        components.html(vapi_js, height=1050, scrolling=False)

        st.markdown("""
        <div style="background:rgba(37,99,235,0.07);border-left:4px solid #3B82F6;
            border-radius:10px;padding:11px 15px;margin-top:10px;color:#93C5FD;font-size:0.81rem;">
            Allow microphone access when the browser asks.
            Scores and a written summary appear in the Candidates page within about 60 seconds of the call finishing.
        </div>""", unsafe_allow_html=True)


elif page == "📊  Analytics":

    page_header("📊 Recruitment Analytics",
                "A live view of where every candidate stands across your pipeline.")

    r = api_get("/candidates?limit=1000", timeout=15)
    if r is None or r.status_code != 200:
        st.error("Cannot reach backend. Check your connection and BACKEND_URL.")
        st.stop()
    raw = r.json()
    if not raw:
        st.markdown("""
        <div style="text-align:center;padding:48px;background:linear-gradient(145deg,#071220,#050E1A);
            border:1px solid #0A1E38;border-radius:16px;color:#334155;">
            <div style="font-size:2rem;margin-bottom:12px;">📭</div>
            <div style="font-size:0.95rem;font-weight:600;color:#475569;margin-bottom:6px;">
                No candidates yet</div>
            <div style="font-size:0.82rem;">Upload resumes and run interviews to see analytics here.</div>
        </div>""", unsafe_allow_html=True)
        st.stop()

    df = pd.DataFrame(raw)
    total       = len(df)
    interviewed = int(df["status"].isin(["Interviewed","Evaluated","Hired","Rejected"]).sum())
    hired       = int((df["status"] == "Hired").sum())
    rejected    = int((df["status"] == "Rejected").sum())
    on_hold     = int((df["status"].isin(["On Hold","Evaluated"])).sum())
    pending     = int((df["status"].isin(["Uploaded","Interview Generated"])).sum())
    hire_rate   = f"{round(hired/interviewed*100)}%" if interviewed else "0%"
    rejection_rate = f"{round(rejected/interviewed*100)}%" if interviewed else "0%"

    # KPI row
    k1,k2,k3,k4,k5,k6 = st.columns(6)
    for col,icon,val,lbl,clr in [
        (k1,"👥",total,         "Total",        "#60A5FA"),
        (k2,"⏳",pending,       "Pending",      "#FBB724"),
        (k3,"🎤",interviewed,   "Interviewed",  "#A78BFA"),
        (k4,"✅",hired,         "Hired",        "#34D399"),
        (k5,"❌",rejected,      "Rejected",     "#F87171"),
        (k6,"📈",hire_rate,     "Hire Rate",    "#60A5FA"),
    ]:
        col.markdown(kpi_card(icon,val,lbl,clr), unsafe_allow_html=True)

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # Pipeline funnel
    section_title("PIPELINE OVERVIEW", "🔀")
    stages = [
        ("Uploaded", pending, "#60A5FA"),
        ("Interviewed", interviewed, "#A78BFA"),
        ("Evaluated/Hold", on_hold, "#FBB724"),
        ("Hired", hired, "#34D399"),
    ]
    funnel_cols = st.columns(4)
    for col,(lbl,val,clr) in zip(funnel_cols, stages):
        pct = round(val/total*100) if total else 0
        col.markdown(f"""
        <div style="background:linear-gradient(145deg,#071220,#050E1A);border:1px solid #0A1E38;
            border-radius:14px;padding:16px;text-align:center;position:relative;overflow:hidden;">
            <div style="position:absolute;bottom:0;left:0;right:0;height:{pct}%;
                background:{clr}0D;transition:height 0.6s ease;"></div>
            <div style="position:relative;z-index:1;">
                <div style="font-size:1.6rem;font-weight:900;color:{clr};">{val}</div>
                <div style="font-size:0.7rem;color:{clr}88;font-weight:700;margin:3px 0;">{pct}%</div>
                <div style="font-size:0.62rem;color:#334155;text-transform:uppercase;
                    letter-spacing:0.1em;">{lbl}</div>
                <div style="width:100%;height:3px;background:#0A1E38;border-radius:999px;margin-top:10px;">
                    <div style="width:{pct}%;height:3px;background:{clr};border-radius:999px;"></div>
                </div>
            </div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    # Charts
    section_title("BY ROLE AND STATUS", "📈")
    ch1, ch2 = st.columns(2)
    with ch1:
        role_c = df["applied_role"].value_counts().head(10).reset_index()
        role_c.columns = ["Role","Count"]
        st.bar_chart(role_c.set_index("Role"), use_container_width=True)
    with ch2:
        stat_c = df["status"].value_counts().reset_index()
        stat_c.columns = ["Status","Count"]
        st.bar_chart(stat_c.set_index("Status"), use_container_width=True)

    # Download
    section_title("EXPORT REPORT", "📥")
    dl1, dl2, _ = st.columns([1, 1, 2])
    with dl1:
        if st.button("⬇ Download Excel Report", use_container_width=True):
            with st.spinner("Generating report..."):
                dl_r = api_get("/candidates/export/excel", timeout=30)
            if dl_r and dl_r.status_code == 200:
                st.download_button(
                    "💾 Save candidates.xlsx",
                    data=dl_r.content,
                    file_name=f"hireai_candidates_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True)
            else:
                st.error("Export failed. Run at least one interview first.")
    with dl2:
        st.markdown("""
        <div style="background:linear-gradient(145deg,#071220,#050E1A);border:1px solid #0A1E38;
            border-radius:10px;padding:10px 14px;font-size:0.74rem;color:#334155;line-height:1.6;">
            3 sheets: All Candidates · Hire Shortlist · Rejected<br>
            Colour-coded rows · Auto-sized columns
        </div>""", unsafe_allow_html=True)

    # Table
    section_title("ALL CANDIDATES", "👥")
    disp = [c for c in ["id","name","applied_role","status","years_experience","created_at"] if c in df.columns]
    st.dataframe(df[disp].head(100), use_container_width=True, hide_index=True)


elif page == "👥  Candidates":

    page_header("👥 Candidate Manager",
                "Every candidate in one place. See their scores, read the evaluation summary and make your hiring call.")

    f1, f2, f3 = st.columns([2, 1, 1])
    with f1:
        search = st.text_input("Search by name", placeholder="Type to filter...")
    with f2:
        status_filter = st.selectbox("Status", [
            "All","Uploaded","Interview Generated","Interviewed",
            "Evaluated","Hired","Rejected","On Hold",
        ])
    with f3:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        if st.button("Refresh", use_container_width=True):
            st.rerun()

    r = api_get("/candidates?limit=1000", timeout=15)
    if r is None or r.status_code != 200:
        st.error("Cannot reach backend.")
        st.stop()

    candidates = r.json()
    if search:
        candidates = [c for c in candidates if search.lower() in c.get("name","").lower()]
    if status_filter != "All":
        candidates = [c for c in candidates if c.get("status") == status_filter]

    if not candidates:
        st.markdown("""
        <div style="text-align:center;padding:32px;background:linear-gradient(145deg,#071220,#050E1A);
            border:1px solid #0A1E38;border-radius:14px;margin-top:12px;">
            <div style="font-size:1.6rem;margin-bottom:8px;">🔍</div>
            <div style="color:#475569;font-size:0.85rem;font-weight:600;">No candidates match these filters</div>
            <div style="color:#1E3A5F;font-size:0.76rem;margin-top:4px;">Try clearing the search or changing the status filter.</div>
        </div>""", unsafe_allow_html=True)
        st.stop()

    st.markdown(f'<div style="font-size:0.7rem;color:#1E3A5F;font-weight:700;margin-bottom:14px;text-transform:uppercase;letter-spacing:0.1em;">{len(candidates)} CANDIDATES FOUND</div>', unsafe_allow_html=True)

    for c in candidates[:60]:
        with st.expander(f"#{c['id']} | {c['name']} | {c['applied_role']} | {c['status']}"):
            left, right = st.columns(2)

            with left:
                rows_html = "".join(
                    f'<div style="display:flex;justify-content:space-between;padding:8px 0;'
                    f'border-bottom:1px solid #0A1628;font-size:0.8rem;">'
                    f'<span style="color:#334155;">{k}</span>'
                    f'<span style="color:#CBD5E1;font-weight:600;">{v}</span></div>'
                    for k, v in [
                        ("Name", c["name"]),
                        ("Role", c["applied_role"]),
                        ("Status", c["status"]),
                        ("Email", c.get("email") or "Not found"),
                        ("Experience", f"{c.get('years_experience') or '?'} years"),
                        ("Uploaded", fmt_dt(c.get("created_at"))),
                    ]
                )
                st.markdown(
                    f'<div style="background:linear-gradient(145deg,#071220,#050E1A);'
                    f'border:1px solid #0A1E38;border-radius:13px;padding:16px;margin-bottom:10px;">'
                    f'<div style="font-size:0.6rem;font-weight:800;color:#1E3A5F;text-transform:uppercase;'
                    f'letter-spacing:0.14em;border-bottom:1px solid #0A1E38;padding-bottom:9px;'
                    f'margin-bottom:12px;">CANDIDATE PROFILE</div>{rows_html}</div>',
                    unsafe_allow_html=True)
                if c.get("skills"):
                    st.markdown(
                        "<div style='font-size:0.7rem;color:#334155;font-weight:700;margin-bottom:7px;'>Skills</div>" +
                        "".join(pill(s) for s in c["skills"]),
                        unsafe_allow_html=True)
                st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
                if st.button(f"Delete #{c['id']}", key=f"del_{c['id']}", help="Permanently remove this candidate"):
                    del_r = api_get.__class__  # just to get requests
                    import requests as _req
                    try:
                        dr = _req.delete(f"{BACKEND_URL}/candidates/{c['id']}", timeout=10)
                        if dr.status_code in (200, 204):
                            st.success(f"{c['name']} removed.")
                            st.rerun()
                        else:
                            st.error(f"Delete failed: {dr.status_code}")
                    except Exception as e:
                        st.error(f"Cannot reach backend: {e}")

            with right:
                full_r = api_get(f"/candidates/{c['id']}", timeout=8)
                if full_r and full_r.status_code == 200:
                    full = full_r.json()
                    ev = full.get("evaluation") if isinstance(full.get("evaluation"), dict) else None
                    if ev:
                        overall = ev.get("overall_score", 0)
                        decision = ev.get("final_decision", "Hold")
                        clr = "#34D399" if decision == "Hire" else "#F87171" if decision == "Reject" else "#FBB724"
                        st.markdown(f"""
                        <div style="background:linear-gradient(145deg,#071220,#050E1A);
                            border:1px solid #0A1E38;border-radius:13px;padding:16px;margin-bottom:10px;">
                            <div style="font-size:0.62rem;font-weight:800;color:#1E3A5F;text-transform:uppercase;
                                letter-spacing:0.12em;border-bottom:1px solid #0F2540;
                                padding-bottom:9px;margin-bottom:14px;">Evaluation Results</div>
                            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;">
                                <div>
                                    <div style="font-size:2.4rem;font-weight:900;color:{clr};letter-spacing:-0.03em;text-shadow:0 0 20px {clr}55;">{overall}</div>
                                    <div style="font-size:0.6rem;color:#1E3A5F;text-transform:uppercase;letter-spacing:0.1em;margin-top:2px;">Overall Score</div>
                                </div>
                                {badge(decision)}
                            </div>
                            {score_bar("Technical Depth", ev.get("technical_score", 0))}
                            {score_bar("Communication", ev.get("communication_score", 0))}
                            {score_bar("Problem Solving", ev.get("problem_solving_score", 0))}
                            {score_bar("Experience Alignment", ev.get("experience_alignment_score", 0))}
                            {score_bar("Culture Fit", ev.get("culture_fit_score", 0))}
                        </div>""", unsafe_allow_html=True)
                        if ev.get("remarks"):
                            st.markdown(f"""
                            <div style="background:rgba(37,99,235,0.04);border:1px solid #0A1E38;
                                border-radius:11px;padding:13px 15px;margin-bottom:8px;">
                                <div style="font-size:0.6rem;font-weight:800;color:#1E3A5F;
                                    text-transform:uppercase;letter-spacing:0.14em;margin-bottom:7px;">
                                    Evaluation Summary</div>
                                <div style="color:#475569;font-size:0.8rem;line-height:1.65;">
                                    {ev['remarks']}</div>
                            </div>""", unsafe_allow_html=True)
                        cs, ca = st.columns(2)
                        with cs:
                            if ev.get("strengths"):
                                st.markdown("<div style='font-size:0.7rem;color:#34D399;font-weight:700;margin-bottom:5px;'>Strengths</div>", unsafe_allow_html=True)
                                for s in ev["strengths"]:
                                    st.markdown(f"<div style='font-size:0.76rem;color:#475569;padding:2px 0;'>✓ {s}</div>", unsafe_allow_html=True)
                        with ca:
                            if ev.get("areas_for_improvement"):
                                st.markdown("<div style='font-size:0.7rem;color:#FBB724;font-weight:700;margin-bottom:5px;'>To Improve</div>", unsafe_allow_html=True)
                                for a in ev["areas_for_improvement"]:
                                    st.markdown(f"<div style='font-size:0.76rem;color:#475569;padding:2px 0;'>△ {a}</div>", unsafe_allow_html=True)
                    else:
                        st.markdown("""
                        <div style="background:#030A16;border:1px solid #0A1E38;
                            border-radius:12px;padding:28px;text-align:center;">
                            <div style="font-size:1.6rem;margin-bottom:10px;">⏳</div>
                            <div style="color:#475569;font-size:0.84rem;font-weight:600;">No evaluation yet</div>
                            <div style="color:#1E3A5F;font-size:0.75rem;margin-top:5px;">Run the voice interview to see evaluation scores and a hiring recommendation.</div>
                        </div>""", unsafe_allow_html=True)



elif page == "⚖️   Compare":

    page_header("⚖️ Compare Candidates",
                "Pick two or three candidates for the same role and see their scores side by side.")

    r_all = api_get("/candidates?limit=1000", timeout=15)
    if r_all is None or r_all.status_code != 200:
        st.error("Cannot reach backend.")
        st.stop()

    all_cands = r_all.json()
    evaluated = [c for c in all_cands if c.get("status") in ("Evaluated","Hired","Rejected","On Hold","Interviewed")]

    if len(evaluated) < 2:
        st.markdown("""
        <div style="text-align:center;padding:48px;background:linear-gradient(145deg,#071220,#050E1A);
            border:1px solid #0A1E38;border-radius:16px;">
            <div style="font-size:2rem;margin-bottom:12px;">⚖️</div>
            <div style="color:#475569;font-size:0.9rem;font-weight:600;margin-bottom:6px;">
                Not enough evaluated candidates yet</div>
            <div style="color:#1E3A5F;font-size:0.8rem;">
                You need at least two completed interviews to compare candidates.</div>
        </div>""", unsafe_allow_html=True)
        st.stop()

    name_map = {f"#{c['id']} · {c['name']} ({c['applied_role']})": c["id"] for c in evaluated}

    st.markdown('<div style="font-size:0.72rem;color:#1E3A5F;font-weight:700;margin-bottom:12px;text-transform:uppercase;letter-spacing:0.1em;">Select candidates to compare</div>', unsafe_allow_html=True)

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        pick_a = st.selectbox("Candidate A", list(name_map.keys()), key="cmp_a")
    with col_b:
        pick_b = st.selectbox("Candidate B", list(name_map.keys()), key="cmp_b",
                              index=min(1, len(name_map)-1))
    with col_c:
        pick_c = st.selectbox("Candidate C (optional)", ["None"] + list(name_map.keys()), key="cmp_c")

    picks = [pick_a, pick_b]
    if pick_c != "None":
        picks.append(pick_c)

    if len(set(picks)) < len(picks):
        st.warning("Please select different candidates for each slot.")
        st.stop()

    # Fetch full profiles
    profiles = []
    for pick in picks:
        cid = name_map[pick]
        r_c = api_get(f"/candidates/{cid}", timeout=8)
        if r_c and r_c.status_code == 200:
            profiles.append(r_c.json())

    if not profiles:
        st.error("Could not load candidate profiles.")
        st.stop()

    # ── Score comparison table ──────────────────────────────
    section_title("SCORE COMPARISON", "📊")

    DIMS = [
        ("Overall",              "overall_score"),
        ("Technical Depth",      "technical_score"),
        ("Communication",        "communication_score"),
        ("Problem Solving",      "problem_solving_score"),
        ("Experience Alignment", "experience_alignment_score"),
        ("Culture Fit",          "culture_fit_score"),
    ]

    cols = st.columns(len(profiles) + 1)
    cols[0].markdown('<div style="font-size:0.7rem;color:#1E3A5F;font-weight:700;padding:10px 0;">Dimension</div>', unsafe_allow_html=True)
    for i, p in enumerate(profiles):
        dec = (p.get("evaluation") or {}).get("final_decision","—")
        clr = "#34D399" if dec=="Hire" else "#F87171" if dec=="Reject" else "#FBB724"
        cols[i+1].markdown(
            f'<div style="text-align:center;padding:8px 4px;">'
            f'<div style="font-size:0.82rem;font-weight:800;color:#E2E8F0;">{p["name"]}</div>'
            f'<div style="font-size:0.68rem;color:#334155;margin:2px 0;">{p["applied_role"][:22]}</div>'
            f'<span style="font-size:0.68rem;font-weight:700;color:{clr};">{dec}</span>'
            f'</div>', unsafe_allow_html=True)

    st.markdown('<hr style="border:none;border-top:1px solid #0A1E38;margin:4px 0 8px;">', unsafe_allow_html=True)

    for dim_label, dim_key in DIMS:
        row_cols = st.columns(len(profiles) + 1)
        row_cols[0].markdown(
            f'<div style="font-size:0.78rem;color:#64748B;padding:8px 0;">{dim_label}</div>',
            unsafe_allow_html=True)
        scores = []
        for p in profiles:
            ev = p.get("evaluation") or {}
            scores.append(ev.get(dim_key, 0) or 0)
        best = max(scores) if scores else 0
        for i, (p, score) in enumerate(zip(profiles, scores)):
            is_best = score == best and best > 0
            clr = "#34D399" if score >= 75 else "#FBB724" if score >= 50 else "#F87171"
            best_tag = '<div style="font-size:0.6rem;color:#34D399;font-weight:700;">BEST</div>' if is_best else ""
            row_cols[i+1].markdown(
                f'<div style="text-align:center;padding:6px 4px;">'
                f'<div style="font-size:1.1rem;font-weight:900;color:{clr};">{score}</div>'
                f'{best_tag}'
                f'</div>', unsafe_allow_html=True)

    # ── Visual bar comparison ───────────────────────────────
    section_title("VISUAL BREAKDOWN", "📈")

    COLORS = ["#60A5FA", "#A78BFA", "#F472B6"]
    bar_dims = [d for d in DIMS if d[1] != "overall_score"]

    for dim_label, dim_key in bar_dims:
        st.markdown(f'<div style="font-size:0.74rem;color:#64748B;margin-bottom:6px;">{dim_label}</div>', unsafe_allow_html=True)
        for i, p in enumerate(profiles):
            ev = p.get("evaluation") or {}
            score = ev.get(dim_key, 0) or 0
            clr = COLORS[i % len(COLORS)]
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:4px;">'
                f'<div style="font-size:0.7rem;color:#334155;width:80px;flex-shrink:0;">'
                f'{p["name"].split()[0]}</div>'
                f'<div style="flex:1;background:#071220;border-radius:999px;height:8px;overflow:hidden;">'
                f'<div style="width:{score}%;height:8px;background:{clr};border-radius:999px;'
                f'box-shadow:0 0 6px {clr}55;"></div></div>'
                f'<div style="font-size:0.74rem;font-weight:800;color:{clr};width:30px;">{score}</div>'
                f'</div>', unsafe_allow_html=True)
        st.markdown('<div style="height:8px;"></div>', unsafe_allow_html=True)

    # ── Side by side summaries ──────────────────────────────
    section_title("EVALUATION SUMMARIES", "📝")
    sum_cols = st.columns(len(profiles))
    for i, p in enumerate(profiles):
        ev = p.get("evaluation") or {}
        with sum_cols[i]:
            st.markdown(
                f'<div style="background:linear-gradient(145deg,#071220,#050E1A);'
                f'border:1px solid #0A1E38;border-radius:13px;padding:16px;">'
                f'<div style="font-size:0.72rem;font-weight:800;color:#E2E8F0;margin-bottom:8px;">'
                f'{p["name"]}</div>'
                f'<div style="font-size:0.75rem;color:#475569;line-height:1.6;">'
                f'{ev.get("remarks") or "No evaluation summary available."}</div>'
                f'</div>', unsafe_allow_html=True)

elif page == "⚙️   Infrastructure":

    page_header("⚙️ Infrastructure",
                "Live health checks for every service the platform depends on, plus full API reference.")

    section_title("SERVICE HEALTH","🔗")

    def svc(label, url, icon):
        try:
            if url.startswith("/"):
                r = api_get(url, timeout=4)
                ok = r is not None and r.status_code == 200
            else:
                ok = requests.get(url, timeout=4).status_code == 200
        except Exception:
            ok = False
        clr = "#34D399" if ok else "#F87171"
        glow = f'box-shadow:0 0 10px {clr};animation:glow 2s infinite;' if ok else ''
        return (f'<div class="hcard" style="display:flex;align-items:center;justify-content:space-between;'
                f'background:linear-gradient(145deg,#071220,#050E1A);border:1px solid #0A1E38;'
                f'border-radius:12px;padding:13px 16px;margin-bottom:7px;cursor:default;">'
                f'<div style="display:flex;align-items:center;gap:10px;">'
                f'<span style="font-size:1.1rem;">{icon}</span>'
                f'<span style="font-weight:600;color:#CBD5E1;font-size:0.85rem;">{label}</span></div>'
                f'<div style="display:flex;align-items:center;gap:7px;">'
                f'<div style="width:7px;height:7px;border-radius:50%;background:{clr};{glow}"></div>'
                f'<span style="color:{clr};font-weight:700;font-size:0.76rem;">{"Online" if ok else "Offline"}</span>'
                f'</div></div>')

    s1, s2 = st.columns(2)
    with s1:
        st.markdown(svc("FastAPI Backend", "/health", "⚡"), unsafe_allow_html=True)
        st.markdown(svc("Database", "/candidates?limit=1", "🗄️"), unsafe_allow_html=True)
    with s2:
        st.markdown(svc("Vapi Config", "/vapi/config", "🎙"), unsafe_allow_html=True)
        st.markdown(svc("Groq API", "https://api.groq.com", "🧠"), unsafe_allow_html=True)

    section_title("CONFIGURATION","🔧")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"""
        <div style="background:linear-gradient(145deg,#071220,#050E1A);border:1px solid #0A1E38;
            border-radius:13px;padding:16px;margin-bottom:10px;">
            <div style="font-size:0.6rem;font-weight:800;color:#1E3A5F;text-transform:uppercase;
                letter-spacing:0.14em;margin-bottom:12px;">BACKEND ENDPOINTS</div>
            <div style="font-size:0.78rem;color:#475569;line-height:2.3;">
                <strong style="color:#334155;">API Base:</strong>
                <code style="color:#60A5FA;font-size:0.72rem;"> {BACKEND_URL}</code><br>
                <strong style="color:#334155;">Swagger:</strong>
                <code style="color:#60A5FA;font-size:0.72rem;"> {BACKEND_URL}/docs</code><br>
                <strong style="color:#334155;">Webhook:</strong>
                <code style="color:#60A5FA;font-size:0.72rem;"> {BACKEND_URL}/webhooks/vapi</code><br>
                <strong style="color:#334155;">LLM:</strong>
                <code style="color:#34D399;font-size:0.72rem;"> Groq · llama-3.3-70b-versatile</code>
            </div>
        </div>""", unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div style="background:linear-gradient(145deg,#071220,#050E1A);border:1px solid #0A1E38;
            border-radius:13px;padding:16px;margin-bottom:10px;">
            <div style="font-size:0.6rem;font-weight:800;color:#1E3A5F;text-transform:uppercase;
                letter-spacing:0.14em;margin-bottom:12px;">VAPI WIDGET</div>
            <div style="font-size:0.78rem;color:#475569;line-height:2.3;">
                <strong style="color:#334155;">Method:</strong>
                <span style="color:#34D399;font-size:0.72rem;"> Streamlit native iframe</span><br>
                <strong style="color:#334155;">Works on:</strong>
                <span style="color:#60A5FA;font-size:0.72rem;"> Local, ngrok, Streamlit Cloud, Render</span><br>
                <strong style="color:#334155;">Purpose:</strong>
                <span style="color:#334155;font-size:0.73rem;"> Uses Streamlit srcdoc iframe with a resolvable origin so Daily.co's call bundle can postMessage successfully</span>
            </div>
        </div>""", unsafe_allow_html=True)

    section_title("DATABASE PERSISTENCE FIX","🗄️")
    st.markdown("""
    <div style="background:rgba(248,113,113,0.06);border-left:4px solid #F87171;
        border-radius:10px;padding:16px 20px;margin-bottom:12px;">
        <div style="font-size:0.75rem;font-weight:800;color:#F87171;margin-bottom:8px;">
            Why your data disappears when the app restarts</div>
        <div style="font-size:0.81rem;color:#475569;line-height:1.7;">
            Render free tier uses an ephemeral filesystem. Every restart or redeploy wipes
            the SQLite file. All candidates, interviews and evaluations are lost.
            Fix: switch to Render's free PostgreSQL which persists permanently.
        </div>
    </div>
    <div style="background:rgba(52,211,153,0.05);border-left:4px solid #34D399;
        border-radius:10px;padding:16px 20px;margin-bottom:16px;">
        <div style="font-size:0.75rem;font-weight:800;color:#34D399;margin-bottom:10px;">
            Fix it in 5 minutes</div>
        <div style="font-size:0.79rem;color:#475569;line-height:2.2;">
            1. Render dashboard → New → PostgreSQL → Free → Create<br>
            2. Copy the External Database URL from the PostgreSQL page<br>
            3. Your backend → Environment → DATABASE_URL → paste the PostgreSQL URL<br>
            4. Add psycopg2-binary==2.9.9 to your backend requirements.txt<br>
            5. Push to GitHub. Render redeploys. Data persists permanently from now on.
        </div>
    </div>""", unsafe_allow_html=True)

    section_title("API REFERENCE","📋")
    rows = "".join(f"""
    <div style="display:flex;align-items:center;gap:12px;padding:9px 0;
        border-bottom:1px solid #0A1628;font-size:0.78rem;">
        <span style="background:{'rgba(52,211,153,0.1)' if m=='GET' else 'rgba(251,191,36,0.1)' if m=='POST' else 'rgba(248,113,113,0.1)'};
            color:{'#34D399' if m=='GET' else '#FBB724' if m=='POST' else '#F87171'};
            border-radius:5px;padding:2px 9px;font-weight:800;min-width:56px;text-align:center;
            font-size:0.66rem;letter-spacing:0.05em;">{m}</span>
        <code style="color:#60A5FA;font-size:0.74rem;">{path}</code>
        <span style="color:#1E3A5F;font-size:0.74rem;margin-left:auto;">{desc}</span>
    </div>""" for m, path, desc in [
        ("POST",  "/candidates/upload",       "Upload candidate PDF and parse CV"),
        ("GET",   "/candidates",              "List all candidates"),
        ("GET",   "/candidates/{id}",         "Get candidate with evaluation"),
        ("DELETE","/candidates/{id}",         "Delete candidate"),
        ("GET",   "/candidates/export/excel", "Download Excel report"),
        ("POST",  "/vapi/generate/{id}",      "Create Vapi assistant from CV"),
        ("GET",   "/vapi/assistant/{id}",     "Retrieve existing assistant ID"),
        ("GET",   "/vapi/config",             "Vapi public key for browser SDK"),
        ("POST",  "/webhooks/vapi",           "Receive Vapi call events"),
        ("GET",   "/health",                  "Backend health check"),
    ])
    st.markdown(
        f'<div style="background:linear-gradient(145deg,#071220,#050E1A);'
        f'border:1px solid #0A1E38;border-radius:13px;padding:16px;border-radius:14px;">{rows}</div>',
        unsafe_allow_html=True)


st.markdown(f"""
<div style="margin-top:52px;padding-top:16px;border-top:1px solid #0A1E38;">
    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
        <div style="display:flex;align-items:center;gap:9px;">
            <div style="width:22px;height:22px;
                background:linear-gradient(135deg,#2563EB,#7C3AED);
                border-radius:7px;display:flex;align-items:center;
                justify-content:center;font-size:0.72rem;">🎯</div>
            <span style="font-size:0.7rem;color:#1E3A5F;">
                <strong style="color:#334155;">HireAI Enterprise</strong>
                &nbsp;·&nbsp; v{APP_VERSION}
                &nbsp;·&nbsp; {st.session_state.user_avatar} {st.session_state.user_name}
                &nbsp;·&nbsp; <span style="color:#0A1E38;">Groq · LLaMA 3.3 70B · Vapi AI</span>
            </span>
        </div>
        <div style="font-size:0.66rem;color:#0A1E38;">{datetime.now().strftime("%d %b %Y · %H:%M")}</div>
    </div>
</div>
""", unsafe_allow_html=True)