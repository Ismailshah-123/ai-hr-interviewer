"""
=================================================================
AI HR INTERVIEWER — STREAMLIT ENTERPRISE FRONTEND
=================================================================
Run:   streamlit run app.py
Needs: BACKEND_URL pointing to your running FastAPI server.
=================================================================
"""

import os
import socket
import socketserver
import http.server
import threading
import time
from datetime import datetime

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components

# ─────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────

BACKEND_URL  = "https://hireai-backend-1-fd4w.onrender.com"
VAPI_PUBLIC_KEY = "0336b9be-93ff-4d9b-b222-7f026fcd1ae5"
APP_VERSION  = "2.0.0"
COMPANY_NAME = "AI HR Interviewer"

# All 56 roles — kept in sync with backend TechRoleEnum
ROLES = [
    # Software Engineering
    "Frontend Engineer", "Backend Engineer", "Fullstack Engineer",
    "iOS Engineer", "Android Engineer", "Cross-Platform Mobile Engineer",
    "Software Engineer", "Senior Software Engineer", "Staff Software Engineer",
    "Principal Engineer", "Engineering Manager", "Software Architect",
    "Embedded Systems Engineer", "Game Developer",
    # QA / Testing
    "SQA Engineer", "QA Automation Engineer", "Manual QA Tester",
    "Performance Test Engineer",
    # DevOps / Cloud
    "DevOps Engineer", "Site Reliability Engineer", "Cloud Engineer",
    "Platform Engineer", "Infrastructure Engineer", "Network Engineer",
    "Systems Administrator",
    # Data / AI / ML
    "Data Scientist", "Data Analyst", "Data Engineer",
    "Machine Learning Engineer", "MLOps Engineer", "GenAI Engineer",
    "AI Research Scientist", "Business Intelligence Analyst",
    # Security
    "Cybersecurity Engineer", "Security Analyst", "Penetration Tester",
    "Security Operations (SOC) Engineer",
    # Database
    "Database Administrator", "Database Engineer",
    # Product / Design
    "Product Manager", "Product Owner", "UI/UX Designer",
    "Product Designer", "Graphic Designer",
    # Project / Management
    "Project Manager", "Scrum Master", "Technical Program Manager",
    "Delivery Manager", "Chief Technology Officer",
    # IT / Support
    "IT Support Engineer", "Helpdesk Technician", "Technical Support Engineer",
    # Sales / Business
    "Sales Engineer", "Solutions Architect", "Business Analyst",
    # Other
    "Other",
]

# ─────────────────────────────────────────────────────────────
# PAGE CONFIG  (must be first Streamlit call)
# ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title=f"{COMPANY_NAME} Enterprise",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────

defaults = {
    "last_candidate_id": 1,
    "assistant_id": "",
    "candidate_data": {},
    "page": "🏠 Overview",
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─────────────────────────────────────────────────────────────
# LOCAL WIDGET SERVER  (fixes Daily.co postMessage null-origin)
# ─────────────────────────────────────────────────────────────

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
    srv  = socketserver.ThreadingTCPServer(("127.0.0.1", port), _SilentHandler)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return port


WIDGET_PORT = _start_widget_server()

# ─────────────────────────────────────────────────────────────
# GLOBAL CSS
# ─────────────────────────────────────────────────────────────

st.markdown("""
<style>
/* ── Base ── */
#MainMenu, footer, header { visibility: hidden; }

html, body, [data-testid="stAppViewContainer"] {
    background: #050D1A !important;
    color: #E2E8F0;
    font-family: 'Inter', 'Segoe UI', sans-serif;
}

[data-testid="stSidebar"] {
    background: #0A1628 !important;
    border-right: 1px solid #1E3A5F;
}

/* ── Typography helpers ── */
.page-title {
    font-size: 2rem; font-weight: 800;
    background: linear-gradient(135deg, #60A5FA, #A78BFA);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    margin-bottom: 4px;
}
.page-subtitle {
    color: #64748B; font-size: 0.95rem; margin-bottom: 24px;
}

/* ── Cards ── */
.card {
    background: linear-gradient(145deg, #0F1E35, #0D1B30);
    border: 1px solid #1E3A5F;
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 16px;
}
.card-hover {
    transition: transform 0.2s, border-color 0.2s;
}
.card-hover:hover {
    transform: translateY(-3px);
    border-color: #3B82F6;
}

/* ── KPI metric cards ── */
.kpi-card {
    background: linear-gradient(145deg, #0F1E35, #0D1B30);
    border: 1px solid #1E3A5F;
    border-radius: 16px;
    padding: 22px 20px;
    text-align: center;
    transition: border-color 0.2s;
}
.kpi-card:hover { border-color: #3B82F6; }
.kpi-icon  { font-size: 2rem; margin-bottom: 8px; }
.kpi-value { font-size: 2rem; font-weight: 800; color: #60A5FA; }
.kpi-label { font-size: 0.8rem; color: #64748B; text-transform: uppercase; letter-spacing: 0.05em; }
.kpi-delta { font-size: 0.8rem; margin-top: 4px; }
.delta-up   { color: #34D399; }
.delta-down { color: #F87171; }

/* ── Status badges ── */
.badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 600;
}
.badge-hired     { background: rgba(52,211,153,0.15); color: #34D399; border: 1px solid #34D399; }
.badge-rejected  { background: rgba(248,113,113,0.15); color: #F87171; border: 1px solid #F87171; }
.badge-hold      { background: rgba(251,191,36,0.15);  color: #FBB724; border: 1px solid #FBB724; }
.badge-uploaded  { background: rgba(96,165,250,0.15);  color: #60A5FA; border: 1px solid #60A5FA; }
.badge-default   { background: rgba(100,116,139,0.15); color: #94A3B8; border: 1px solid #475569; }

/* ── Section dividers ── */
.section-header {
    font-size: 1.1rem; font-weight: 700; color: #94A3B8;
    text-transform: uppercase; letter-spacing: 0.08em;
    border-bottom: 1px solid #1E3A5F;
    padding-bottom: 8px; margin: 28px 0 16px 0;
}

/* ── Timeline steps ── */
.step {
    display: flex; gap: 16px; align-items: flex-start;
    margin-bottom: 20px;
}
.step-num {
    min-width: 32px; height: 32px;
    background: linear-gradient(135deg, #2563EB, #4F46E5);
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-weight: 800; font-size: 0.85rem; color: white;
    flex-shrink: 0;
}
.step-content h4 { margin: 0 0 4px 0; color: #E2E8F0; font-size: 0.95rem; }
.step-content p  { margin: 0; color: #64748B; font-size: 0.85rem; }

/* ── Alert boxes ── */
.alert-info {
    background: rgba(59,130,246,0.08);
    border-left: 4px solid #3B82F6;
    border-radius: 8px; padding: 14px 16px; margin-bottom: 16px;
    color: #93C5FD; font-size: 0.9rem;
}
.alert-success {
    background: rgba(52,211,153,0.08);
    border-left: 4px solid #34D399;
    border-radius: 8px; padding: 14px 16px; margin-bottom: 16px;
    color: #6EE7B7; font-size: 0.9rem;
}
.alert-warn {
    background: rgba(251,191,36,0.08);
    border-left: 4px solid #FBB724;
    border-radius: 8px; padding: 14px 16px; margin-bottom: 16px;
    color: #FDE68A; font-size: 0.9rem;
}

/* ── Table styling ── */
[data-testid="stDataFrame"] {
    border: 1px solid #1E3A5F !important;
    border-radius: 12px !important;
    overflow: hidden;
}

/* ── Buttons ── */
.stButton > button {
    width: 100%; border-radius: 10px; border: none;
    font-weight: 700; font-size: 0.9rem; height: 46px;
    background: linear-gradient(135deg, #2563EB, #4F46E5);
    color: white; transition: opacity 0.2s, transform 0.15s;
}
.stButton > button:hover {
    opacity: 0.92; transform: translateY(-1px);
}

/* ── Sidebar nav radio ── */
[data-testid="stRadio"] label {
    font-size: 0.9rem !important;
    padding: 6px 0 !important;
}

/* ── Inputs ── */
[data-testid="stTextInput"] input,
[data-testid="stSelectbox"] > div > div {
    background: #0F1E35 !important;
    border: 1px solid #1E3A5F !important;
    border-radius: 8px !important;
    color: #E2E8F0 !important;
}

/* ── Hero banner ── */
.hero {
    background: linear-gradient(135deg, #0F1E35 0%, #1a1040 50%, #0F1E35 100%);
    border: 1px solid #1E3A5F;
    border-radius: 20px;
    padding: 44px 40px;
    margin-bottom: 28px;
    position: relative;
    overflow: hidden;
}
.hero::before {
    content: '';
    position: absolute; top: -50%; right: -10%;
    width: 400px; height: 400px;
    background: radial-gradient(circle, rgba(99,102,241,0.12) 0%, transparent 70%);
    pointer-events: none;
}
.hero h1 { font-size: 2.4rem; font-weight: 900; margin: 0 0 10px 0;
    background: linear-gradient(135deg, #60A5FA, #A78BFA, #F472B6);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.hero p { color: #94A3B8; font-size: 1.05rem; max-width: 620px; line-height: 1.7; margin: 0; }

/* ── Doc section ── */
.doc-block {
    background: #0A1628;
    border: 1px solid #1E3A5F;
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 14px;
}
.doc-block h3 { color: #60A5FA; margin: 0 0 8px 0; font-size: 1rem; }
.doc-block p  { color: #94A3B8; margin: 0; font-size: 0.87rem; line-height: 1.6; }

/* ── Tech stack pill ── */
.tech-pill {
    display: inline-block;
    background: rgba(99,102,241,0.12);
    border: 1px solid #4F46E5;
    border-radius: 999px;
    padding: 4px 14px;
    font-size: 0.78rem; font-weight: 600;
    color: #A78BFA;
    margin: 4px 4px 4px 0;
}

/* ── Score bar ── */
.score-bar-wrap { margin-bottom: 10px; }
.score-bar-label { display:flex; justify-content:space-between;
    font-size:0.8rem; color:#94A3B8; margin-bottom:4px; }
.score-bar-bg { background:#1E3A5F; border-radius:999px; height:8px; }
.score-bar-fill { height:8px; border-radius:999px;
    background: linear-gradient(90deg,#3B82F6,#8B5CF6); }

/* ── Candidate detail box ── */
.detail-row { display:flex; justify-content:space-between;
    padding: 10px 0; border-bottom: 1px solid #1E3A5F; font-size:0.88rem; }
.detail-row:last-child { border-bottom: none; }
.detail-key   { color: #64748B; }
.detail-value { color: #E2E8F0; font-weight: 600; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #050D1A; }
::-webkit-scrollbar-thumb { background: #1E3A5F; border-radius: 3px; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def api_get(path: str, timeout: int = 15) -> requests.Response | None:
    try:
        return requests.get(f"{BACKEND_URL}{path}", timeout=timeout)
    except Exception:
        return None


def api_post(path: str, **kwargs) -> requests.Response | None:
    try:
        return requests.post(f"{BACKEND_URL}{path}", **kwargs)
    except Exception:
        return None


def status_badge(status: str) -> str:
    styles = {
        "Hired":    "background:rgba(52,211,153,0.15);color:#34D399;border:1px solid #34D399;",
        "Rejected": "background:rgba(248,113,113,0.15);color:#F87171;border:1px solid #F87171;",
        "On Hold":  "background:rgba(251,191,36,0.15);color:#FBB724;border:1px solid #FBB724;",
        "Hold":     "background:rgba(251,191,36,0.15);color:#FBB724;border:1px solid #FBB724;",
        "Uploaded": "background:rgba(96,165,250,0.15);color:#60A5FA;border:1px solid #60A5FA;",
        "Interview Generated": "background:rgba(167,139,250,0.15);color:#A78BFA;border:1px solid #A78BFA;",
        "Interviewed": "background:rgba(52,211,153,0.1);color:#6EE7B7;border:1px solid #34D399;",
        "Evaluated":  "background:rgba(96,165,250,0.1);color:#93C5FD;border:1px solid #3B82F6;",
    }.get(status, "background:rgba(100,116,139,0.15);color:#94A3B8;border:1px solid #475569;")
    base = "display:inline-block;padding:3px 10px;border-radius:999px;font-size:0.75rem;font-weight:600;"
    return f'<span style="{base}{styles}">{status}</span>'


def score_bar(label: str, value: int) -> str:
    color = "#34D399" if value >= 75 else "#FBB724" if value >= 50 else "#F87171"
    return f"""
<div style="margin-bottom:10px;">
  <div style="display:flex;justify-content:space-between;font-size:0.8rem;color:#94A3B8;margin-bottom:4px;"><span>{label}</span><span style="color:{color};font-weight:700">{value}</span></div>
  <div style="background:#1E3A5F;border-radius:999px;height:8px;overflow:hidden;"><div style="width:{value}%;height:8px;border-radius:999px;background:linear-gradient(90deg,{color},{color}88);"></div></div>
</div>"""


def fmt_dt(raw: str | None) -> str:
    if not raw:
        return "—"
    try:
        return datetime.fromisoformat(raw).strftime("%d %b %Y, %H:%M")
    except Exception:
        return raw


# ─────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("""
    <div style="text-align:center; padding: 16px 0 8px 0;">
        <div style="font-size:2.4rem;">🎯</div>
        <div style="font-size:1.1rem; font-weight:800; color:#60A5FA;">AI HR Interviewer</div>
        <div style="font-size:0.72rem; color:#475569; letter-spacing:0.1em; text-transform:uppercase; margin-top:2px;">
            Enterprise Platform
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<hr style="border-color:#1E3A5F; margin:12px 0;">', unsafe_allow_html=True)

    page = st.radio(
        "Navigation",
        [
            "🏠 Overview & Docs",
            "📄 Upload Candidate",
            "🎙 Generate Interview",
            "📺 Live Interview",
            "📊 Analytics",
            "👥 Candidates",
            "⚙️  Infrastructure",
        ],
        label_visibility="collapsed",
    )

    st.markdown('<hr style="border-color:#1E3A5F; margin:12px 0;">', unsafe_allow_html=True)

    # Live backend pulse
    st.markdown('<div style="font-size:0.75rem;color:#475569;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px;">Backend Status</div>', unsafe_allow_html=True)
    r = api_get("/health", timeout=5)
    if r and r.status_code == 200:
        st.markdown('<div style="display:flex;align-items:center;gap:8px;"><div style="width:8px;height:8px;border-radius:50%;background:#34D399;"></div><span style="font-size:0.82rem;color:#34D399;font-weight:600;">CONNECTED</span></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div style="display:flex;align-items:center;gap:8px;"><div style="width:8px;height:8px;border-radius:50%;background:#F87171;"></div><span style="font-size:0.82rem;color:#F87171;font-weight:600;">OFFLINE</span></div>', unsafe_allow_html=True)

    st.markdown(f'<div style="font-size:0.72rem;color:#334155;margin-top:6px;word-break:break-all;">{BACKEND_URL}</div>', unsafe_allow_html=True)

    st.markdown('<hr style="border-color:#1E3A5F; margin:12px 0;">', unsafe_allow_html=True)

    # Session candidate
    if st.session_state.assistant_id:
        st.markdown(f"""
        <div style="background:#0F1E35;border:1px solid #1E3A5F;border-radius:10px;padding:12px;">
            <div style="font-size:0.7rem;color:#475569;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:6px;">Active Session</div>
            <div style="font-size:0.78rem;color:#60A5FA;font-weight:600;">Candidate #{st.session_state.last_candidate_id}</div>
            <div style="font-size:0.68rem;color:#334155;margin-top:4px;word-break:break-all;">
                {st.session_state.assistant_id[:28]}…
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<hr style="border-color:#1E3A5F; margin:12px 0;">', unsafe_allow_html=True)
    st.markdown(f'<div style="font-size:0.7rem;color:#334155;text-align:center;">v{APP_VERSION} · AI HR Interviewer</div>', unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════
# PAGE 1 — OVERVIEW & DOCUMENTATION
# ═════════════════════════════════════════════════════════════

if page == "🏠 Overview & Docs":

    st.markdown("""
    <div style="background:linear-gradient(135deg,#0F1E35 0%,#1a1040 50%,#0F1E35 100%);border:1px solid #1E3A5F;border-radius:20px;padding:44px 40px;margin-bottom:28px;">
        <h1>🎯 AI HR Interviewer</h1>
        <p>
            An enterprise-grade AI recruitment platform that automates the entire
            technical hiring pipeline — from resume upload to scored evaluation report —
            using a local LLM, real-time voice AI, and automated decision support.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # ── KPIs pulled live from backend ──────────────────────────────────
    r = api_get("/candidates?limit=500", timeout=8)
    candidates_live = r.json() if r and r.status_code == 200 else []

    total      = len(candidates_live)
    interviewed = sum(1 for c in candidates_live if c.get("status") in ("Interviewed","Evaluated","Hired","Rejected"))
    hired       = sum(1 for c in candidates_live if c.get("status") == "Hired")
    rejected    = sum(1 for c in candidates_live if c.get("status") == "Rejected")
    hire_rate   = f"{round(hired/interviewed*100)}%" if interviewed else "—"

    c1, c2, c3, c4, c5 = st.columns(5)
    for col, icon, value, label in [
        (c1, "👥", total,       "Total Candidates"),
        (c2, "🎤", interviewed, "Interviewed"),
        (c3, "✅", hired,       "Hired"),
        (c4, "❌", rejected,    "Rejected"),
        (c5, "📈", hire_rate,   "Hire Rate"),
    ]:
        col.markdown(f"""
        <div style="background:linear-gradient(145deg,#0F1E35,#0D1B30);border:1px solid #1E3A5F;border-radius:16px;padding:22px 20px;text-align:center;">
            <div style="font-size:2rem;margin-bottom:8px;">{icon}</div>
            <div style="font-size:2rem;font-weight:800;color:#60A5FA;">{value}</div>
            <div style="font-size:0.8rem;color:#64748B;text-transform:uppercase;letter-spacing:0.05em;">{label}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown('<div style="font-size:1rem;font-weight:700;color:#94A3B8;text-transform:uppercase;letter-spacing:0.08em;border-bottom:1px solid #1E3A5F;padding-bottom:8px;margin:24px 0 14px 0;">📖 What Is This Platform?</div>', unsafe_allow_html=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("""
        <div style="background:#0A1628;border:1px solid #1E3A5F;border-radius:12px;padding:20px 24px;margin-bottom:14px;">
            <h3>🧠 What the platform does</h3>
            <p>
                AI HR Interviewer replaces the manual screening stage of hiring.
                A recruiter uploads a candidate's resume PDF. The platform reads the
                CV with a local language model (Ollama), extracts skills, experience
                and projects, builds a personalised interview script, and launches a
                live voice interview via Vapi AI. Once the call ends, the transcript
                is automatically evaluated, scored across five dimensions, and written
                to both the database and a downloadable Excel report that HR can act on
                immediately — no human review of the raw call required.
            </p>
        </div>
        <div style="background:#0A1628;border:1px solid #1E3A5F;border-radius:12px;padding:20px 24px;margin-bottom:14px;">
            <h3>🎯 Who is it for?</h3>
            <p>
                HR teams and talent acquisition departments that screen large volumes
                of technical candidates. The platform supports 56 roles across
                engineering, data/AI, security, product, design, and management tracks.
                A typical company can screen 10× more candidates in the same time,
                with consistent and bias-reduced scoring.
            </p>
        </div>
        """, unsafe_allow_html=True)

    with col_b:
        st.markdown("""
        <div style="background:#0A1628;border:1px solid #1E3A5F;border-radius:12px;padding:20px 24px;margin-bottom:14px;">
            <h3>⚙️ How it works — end to end</h3>
            <p>
                <strong style="color:#60A5FA">1. Upload Resume →</strong>
                PDF is extracted, text is sent to Ollama which returns a structured
                profile (skills, years of experience, projects, education).<br><br>
                <strong style="color:#60A5FA">2. Generate Interview →</strong>
                The profile drives a custom system prompt injected into a Vapi voice
                assistant created specifically for that candidate.<br><br>
                <strong style="color:#60A5FA">3. Live Voice Interview →</strong>
                Candidate opens the Live Interview page. Vapi conducts a structured
                12-question interview in the browser — warm-up, technical, behavioural,
                closing — all grounded in the candidate's actual CV.<br><br>
                <strong style="color:#60A5FA">4. Automated Evaluation →</strong>
                When the call ends, Vapi fires a webhook. The transcript is sent to
                Ollama which returns scores for technical depth, communication, problem
                solving, experience alignment, and culture fit, plus a recruiter remarks
                summary and Hire/Reject/Hold decision.<br><br>
                <strong style="color:#60A5FA">5. Excel Report →</strong>
                All results are automatically written to a formatted, colour-coded Excel
                workbook with three sheets: All Candidates, Hire Shortlist, Rejected.
            </p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<div style="font-size:1rem;font-weight:700;color:#94A3B8;text-transform:uppercase;letter-spacing:0.08em;border-bottom:1px solid #1E3A5F;padding-bottom:8px;margin:24px 0 14px 0;">🚀 How To Use — Step by Step</div>', unsafe_allow_html=True)

    steps = [
        ("Upload Candidate",
         "Go to <strong>📄 Upload Candidate</strong>. Enter the candidate's full name, select their applied role, upload their resume PDF (max 10 MB, text-based). Click Upload. The system parses the CV and creates a candidate record. Note the Candidate ID shown in the response."),
        ("Generate Interview",
         "Go to <strong>🎙 Generate Interview</strong>. Enter the Candidate ID from Step 1. Click Generate Interview. The backend builds a personalised interview assistant on Vapi using the parsed CV. The Assistant ID is stored in the session automatically."),
        ("Conduct Live Interview",
         "Go to <strong>📺 Live Interview</strong>. You will see the assistant is connected. Share this page URL with the candidate, or conduct the interview yourself. Click Start Interview, allow microphone access, and speak naturally. The AI interviewer Alex will ask role-specific questions drawn from the candidate's CV."),
        ("View Evaluation",
         "After the call ends, Vapi sends a webhook to the backend which automatically triggers LLM evaluation. Results appear in <strong>👥 Candidates</strong> within 30–60 seconds. Click on a candidate row to see their full scores, remarks, and feedback."),
        ("Download Report",
         "Go to <strong>📊 Analytics</strong>. The Excel download button gives you the full formatted report with all candidates, scores, and the Hire Shortlist sheet pre-filtered for easy decision-making."),
    ]

    for i, (title, desc) in enumerate(steps, 1):
        st.markdown(f"""
        <div style="display:flex;gap:16px;align-items:flex-start;margin-bottom:20px;">
            <div style="min-width:32px;height:32px;background:linear-gradient(135deg,#2563EB,#4F46E5);border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:0.85rem;color:white;flex-shrink:0;">{i}</div>
            <div style="flex:1;">
                <h4>{title}</h4>
                <p>{desc}</p>
            </div>
        </div>""", unsafe_allow_html=True)

    st.markdown('<div style="font-size:1rem;font-weight:700;color:#94A3B8;text-transform:uppercase;letter-spacing:0.08em;border-bottom:1px solid #1E3A5F;padding-bottom:8px;margin:24px 0 14px 0;">🛠️ Technology Stack</div>', unsafe_allow_html=True)

    tech_col1, tech_col2 = st.columns(2)
    with tech_col1:
        st.markdown("""
        <div style="background:#0A1628;border:1px solid #1E3A5F;border-radius:12px;padding:20px 24px;margin-bottom:14px;">
            <h3>Backend Services</h3>
            <p>
                <span style="display:inline-block;background:rgba(99,102,241,0.12);border:1px solid #4F46E5;border-radius:999px;padding:4px 14px;font-size:0.78rem;font-weight:600;color:#A78BFA;margin:4px 4px 4px 0;">FastAPI</span>
                <span style="display:inline-block;background:rgba(99,102,241,0.12);border:1px solid #4F46E5;border-radius:999px;padding:4px 14px;font-size:0.78rem;font-weight:600;color:#A78BFA;margin:4px 4px 4px 0;">SQLAlchemy</span>
                <span style="display:inline-block;background:rgba(99,102,241,0.12);border:1px solid #4F46E5;border-radius:999px;padding:4px 14px;font-size:0.78rem;font-weight:600;color:#A78BFA;margin:4px 4px 4px 0;">SQLite / PostgreSQL</span>
                <span style="display:inline-block;background:rgba(99,102,241,0.12);border:1px solid #4F46E5;border-radius:999px;padding:4px 14px;font-size:0.78rem;font-weight:600;color:#A78BFA;margin:4px 4px 4px 0;">Pydantic v2</span>
                <span style="display:inline-block;background:rgba(99,102,241,0.12);border:1px solid #4F46E5;border-radius:999px;padding:4px 14px;font-size:0.78rem;font-weight:600;color:#A78BFA;margin:4px 4px 4px 0;">Uvicorn</span>
                <span style="display:inline-block;background:rgba(99,102,241,0.12);border:1px solid #4F46E5;border-radius:999px;padding:4px 14px;font-size:0.78rem;font-weight:600;color:#A78BFA;margin:4px 4px 4px 0;">OpenPyXL</span>
                <span style="display:inline-block;background:rgba(99,102,241,0.12);border:1px solid #4F46E5;border-radius:999px;padding:4px 14px;font-size:0.78rem;font-weight:600;color:#A78BFA;margin:4px 4px 4px 0;">pypdf</span>
                <span style="display:inline-block;background:rgba(99,102,241,0.12);border:1px solid #4F46E5;border-radius:999px;padding:4px 14px;font-size:0.78rem;font-weight:600;color:#A78BFA;margin:4px 4px 4px 0;">httpx</span>
            </p>
        </div>
        <div style="background:#0A1628;border:1px solid #1E3A5F;border-radius:12px;padding:20px 24px;margin-bottom:14px;">
            <h3>AI / LLM Layer</h3>
            <p>
                <span style="display:inline-block;background:rgba(99,102,241,0.12);border:1px solid #4F46E5;border-radius:999px;padding:4px 14px;font-size:0.78rem;font-weight:600;color:#A78BFA;margin:4px 4px 4px 0;">Ollama</span>
                <span style="display:inline-block;background:rgba(99,102,241,0.12);border:1px solid #4F46E5;border-radius:999px;padding:4px 14px;font-size:0.78rem;font-weight:600;color:#A78BFA;margin:4px 4px 4px 0;">LLaMA 3</span>
                <span style="display:inline-block;background:rgba(99,102,241,0.12);border:1px solid #4F46E5;border-radius:999px;padding:4px 14px;font-size:0.78rem;font-weight:600;color:#A78BFA;margin:4px 4px 4px 0;">Structured JSON extraction</span>
                <span style="display:inline-block;background:rgba(99,102,241,0.12);border:1px solid #4F46E5;border-radius:999px;padding:4px 14px;font-size:0.78rem;font-weight:600;color:#A78BFA;margin:4px 4px 4px 0;">CV profile parsing</span>
                <span style="display:inline-block;background:rgba(99,102,241,0.12);border:1px solid #4F46E5;border-radius:999px;padding:4px 14px;font-size:0.78rem;font-weight:600;color:#A78BFA;margin:4px 4px 4px 0;">Transcript evaluation</span>
            </p>
        </div>
        """, unsafe_allow_html=True)

    with tech_col2:
        st.markdown("""
        <div style="background:#0A1628;border:1px solid #1E3A5F;border-radius:12px;padding:20px 24px;margin-bottom:14px;">
            <h3>Voice Interview Layer</h3>
            <p>
                <span style="display:inline-block;background:rgba(99,102,241,0.12);border:1px solid #4F46E5;border-radius:999px;padding:4px 14px;font-size:0.78rem;font-weight:600;color:#A78BFA;margin:4px 4px 4px 0;">Vapi AI</span>
                <span style="display:inline-block;background:rgba(99,102,241,0.12);border:1px solid #4F46E5;border-radius:999px;padding:4px 14px;font-size:0.78rem;font-weight:600;color:#A78BFA;margin:4px 4px 4px 0;">Daily.co WebRTC</span>
                <span style="display:inline-block;background:rgba(99,102,241,0.12);border:1px solid #4F46E5;border-radius:999px;padding:4px 14px;font-size:0.78rem;font-weight:600;color:#A78BFA;margin:4px 4px 4px 0;">Deepgram STT</span>
                <span style="display:inline-block;background:rgba(99,102,241,0.12);border:1px solid #4F46E5;border-radius:999px;padding:4px 14px;font-size:0.78rem;font-weight:600;color:#A78BFA;margin:4px 4px 4px 0;">ElevenLabs TTS</span>
                <span style="display:inline-block;background:rgba(99,102,241,0.12);border:1px solid #4F46E5;border-radius:999px;padding:4px 14px;font-size:0.78rem;font-weight:600;color:#A78BFA;margin:4px 4px 4px 0;">GPT-4o</span>
                <span style="display:inline-block;background:rgba(99,102,241,0.12);border:1px solid #4F46E5;border-radius:999px;padding:4px 14px;font-size:0.78rem;font-weight:600;color:#A78BFA;margin:4px 4px 4px 0;">Webhooks</span>
            </p>
        </div>
        <div style="background:#0A1628;border:1px solid #1E3A5F;border-radius:12px;padding:20px 24px;margin-bottom:14px;">
            <h3>Frontend & Infrastructure</h3>
            <p>
                <span style="display:inline-block;background:rgba(99,102,241,0.12);border:1px solid #4F46E5;border-radius:999px;padding:4px 14px;font-size:0.78rem;font-weight:600;color:#A78BFA;margin:4px 4px 4px 0;">Streamlit</span>
                <span style="display:inline-block;background:rgba(99,102,241,0.12);border:1px solid #4F46E5;border-radius:999px;padding:4px 14px;font-size:0.78rem;font-weight:600;color:#A78BFA;margin:4px 4px 4px 0;">Python 3.11+</span>
                <span style="display:inline-block;background:rgba(99,102,241,0.12);border:1px solid #4F46E5;border-radius:999px;padding:4px 14px;font-size:0.78rem;font-weight:600;color:#A78BFA;margin:4px 4px 4px 0;">ngrok</span>
                <span style="display:inline-block;background:rgba(99,102,241,0.12);border:1px solid #4F46E5;border-radius:999px;padding:4px 14px;font-size:0.78rem;font-weight:600;color:#A78BFA;margin:4px 4px 4px 0;">Local HTTP server (iframe fix)</span>
                <span style="display:inline-block;background:rgba(99,102,241,0.12);border:1px solid #4F46E5;border-radius:999px;padding:4px 14px;font-size:0.78rem;font-weight:600;color:#A78BFA;margin:4px 4px 4px 0;">Pandas</span>
                <span style="display:inline-block;background:rgba(99,102,241,0.12);border:1px solid #4F46E5;border-radius:999px;padding:4px 14px;font-size:0.78rem;font-weight:600;color:#A78BFA;margin:4px 4px 4px 0;">openpyxl</span>
            </p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<div style="font-size:1rem;font-weight:700;color:#94A3B8;text-transform:uppercase;letter-spacing:0.08em;border-bottom:1px solid #1E3A5F;padding-bottom:8px;margin:24px 0 14px 0;">📋 Evaluation Scoring Dimensions</div>', unsafe_allow_html=True)

    dim_cols = st.columns(5)
    dims = [
        ("🔬", "Technical",       "Role-specific knowledge depth and accuracy"),
        ("💬", "Communication",   "Clarity, confidence, structure of answers"),
        ("🧩", "Problem Solving", "Reasoning quality on scenario questions"),
        ("📋", "Exp. Alignment",  "Do answers confirm the CV's claims?"),
        ("🤝", "Culture Fit",     "Professionalism and attitude during call"),
    ]
    for col, (icon, name, desc) in zip(dim_cols, dims):
        col.markdown(f"""
        <div style="background:linear-gradient(145deg,#0F1E35,#0D1B30);border:1px solid #1E3A5F;border-radius:16px;padding:22px 20px;text-align:center;">
            <div style="font-size:1.5rem;">{icon}</div>
            <div style="font-size:0.85rem;font-weight:700;color:#E2E8F0;margin:6px 0 4px;">{name}</div>
            <div style="font-size:0.75rem;color:#64748B;line-height:1.4;">{desc}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown('<div style="font-size:1rem;font-weight:700;color:#94A3B8;text-transform:uppercase;letter-spacing:0.08em;border-bottom:1px solid #1E3A5F;padding-bottom:8px;margin:24px 0 14px 0;">⚠️ Prerequisites</div>', unsafe_allow_html=True)
    st.markdown("""
    <div style="background:rgba(251,191,36,0.08);border-left:4px solid #FBB724;border-radius:8px;padding:14px 16px;margin-bottom:16px;color:#FDE68A;font-size:0.9rem;">
        <strong>Before using the platform, ensure:</strong><br>
        1. Ollama is running locally — <code>ollama serve</code> and <code>ollama pull llama3</code><br>
        2. FastAPI backend is running — <code>uvicorn app.main:app --reload --port 8000</code><br>
        3. ngrok is tunnelling the backend — <code>ngrok http 8000</code> — and BACKEND_URL in app.py is updated<br>
        4. Vapi webhook URL is set in the Vapi dashboard to: <code>https://YOUR_NGROK_URL/webhooks/vapi</code><br>
        5. VAPI_API_KEY and VAPI_PUBLIC_KEY are set in your <code>.env</code> file
    </div>
    """, unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════
# PAGE 2 — UPLOAD CANDIDATE
# ═════════════════════════════════════════════════════════════

elif page == "📄 Upload Candidate":

    st.markdown(
        '<div style="font-size:1.9rem;font-weight:800;background:linear-gradient(135deg,#60A5FA,#A78BFA);'
        '-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:4px;">📄 Upload Candidate</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div style="color:#64748B;font-size:0.92rem;margin-bottom:20px;">'
        'Upload a resume PDF — the system will parse the CV and create a candidate profile automatically.</div>',
        unsafe_allow_html=True,
    )
    st.markdown("""
    <div style="background:rgba(59,130,246,0.08);border-left:4px solid #3B82F6;border-radius:8px;
                padding:14px 16px;margin-bottom:16px;color:#93C5FD;font-size:0.9rem;">
        📌 Upload a <strong>text-based PDF</strong> (not a scanned image). The system extracts
        skills, experience, projects and email automatically. Supported roles: 56 tech tracks.
    </div>
    """, unsafe_allow_html=True)

    col_form, col_info = st.columns([2, 1])

    # ── LEFT COLUMN: upload form ──────────────────────────────
    with col_form:

        with st.form("upload_form", clear_on_submit=False):

            st.markdown(
                '<div style="font-size:1rem;font-weight:700;color:#94A3B8;text-transform:uppercase;'
                'letter-spacing:0.08em;border-bottom:1px solid #1E3A5F;padding-bottom:8px;margin-bottom:16px;">'
                'Candidate Details</div>',
                unsafe_allow_html=True,
            )

            c1, c2 = st.columns(2)
            with c1:
                candidate_name = st.text_input("👤 Full Name", placeholder="e.g. Ali Raza")
            with c2:
                role = st.selectbox("🎯 Applied Role", ROLES)

            uploaded_file = st.file_uploader("📎 Resume PDF (max 10 MB)", type=["pdf"])

            submitted = st.form_submit_button(
                "🚀 Upload & Parse Resume", use_container_width=True
            )

        if submitted:
            if not candidate_name.strip():
                st.error("❌ Candidate name is required.")
            elif not uploaded_file:
                st.error("❌ Please upload a PDF resume.")
            else:
                with st.spinner("⚙️ Parsing CV with AI — this may take 20–40 seconds…"):
                    resp = api_post(
                        "/candidates/upload",
                        files={"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")},
                        data={"name": candidate_name.strip(), "role": role},
                        timeout=180,
                    )

                if resp is None:
                    st.error("❌ Could not reach the backend. Check BACKEND_URL and ngrok.")
                elif resp.status_code in (200, 201):
                    result = resp.json()
                    st.session_state.last_candidate_id = result["id"]
                    st.session_state.candidate_data = result

                    st.markdown(f"""
                    <div style="background:rgba(52,211,153,0.08);border-left:4px solid #34D399;
                                border-radius:8px;padding:14px 16px;margin-bottom:16px;color:#6EE7B7;font-size:0.9rem;">
                        ✅ <strong>Candidate uploaded successfully!</strong>
                        Candidate ID: <strong>#{result['id']}</strong> — {result['name']}
                    </div>
                    """, unsafe_allow_html=True)

                    p1, p2, p3 = st.columns(3)
                    p1.metric("Candidate ID", f"#{result['id']}")
                    p2.metric("Years Experience", result.get("years_experience") or "—")
                    p3.metric("Skills Found", len(result.get("skills") or []))

                    if result.get("skills"):
                        st.markdown("**🛠️ Detected Skills:**")
                        pills = "".join(
                            f'<span style="display:inline-block;background:rgba(99,102,241,0.12);'
                            f'border:1px solid #4F46E5;border-radius:999px;padding:4px 14px;'
                            f'font-size:0.78rem;font-weight:600;color:#A78BFA;margin:4px 4px 4px 0;">{s}</span>'
                            for s in result["skills"]
                        )
                        st.markdown(pills, unsafe_allow_html=True)

                    if result.get("cv_summary"):
                        with st.expander("📋 AI-Generated CV Summary"):
                            st.markdown(result["cv_summary"])

                    st.info("✅ Next step → Go to **🎙 Generate Interview** to create the voice interview assistant.")
                else:
                    st.error(f"❌ Upload failed ({resp.status_code}): {resp.text}")

    # ── RIGHT COLUMN: guidelines card (plain Streamlit — no HTML wrapping) ──
    with col_info:

        st.markdown(
            '<div style="background:linear-gradient(145deg,#0F1E35,#0D1B30);border:1px solid #1E3A5F;'
            'border-radius:16px;padding:24px;">'
            '<div style="font-size:0.75rem;color:#475569;text-transform:uppercase;'
            'letter-spacing:0.08em;margin-bottom:16px;font-weight:700;">📋 Upload Guidelines</div>'

            '<div style="margin-bottom:16px;">'
            '<div style="color:#34D399;font-weight:700;font-size:0.85rem;margin-bottom:6px;">✅ Accepted</div>'
            '<div style="color:#94A3B8;font-size:0.82rem;line-height:1.9;">'
            '• Text-based PDF resumes<br>'
            '• Max 10 MB file size<br>'
            '• Max 30 pages<br>'
            '• English language CVs'
            '</div></div>'

            '<div style="margin-bottom:16px;">'
            '<div style="color:#F87171;font-weight:700;font-size:0.85rem;margin-bottom:6px;">❌ Not Accepted</div>'
            '<div style="color:#94A3B8;font-size:0.82rem;line-height:1.9;">'
            '• Scanned image PDFs<br>'
            '• Word (.docx) files<br>'
            '• Password-protected PDFs'
            '</div></div>'

            '<div style="margin-bottom:16px;">'
            '<div style="color:#FBB724;font-weight:700;font-size:0.85rem;margin-bottom:6px;">⏱️ Processing Time</div>'
            '<div style="color:#94A3B8;font-size:0.82rem;line-height:1.9;">'
            'CV parsing takes 20–60 seconds depending on Ollama model speed. '
            'The spinner will show while it runs.'
            '</div></div>'

            '<div>'
            '<div style="color:#A78BFA;font-weight:700;font-size:0.85rem;margin-bottom:6px;">💡 Tips</div>'
            '<div style="color:#94A3B8;font-size:0.82rem;line-height:1.9;">'
            '• Note the Candidate ID after upload<br>'
            '• Use it on the Generate Interview page<br>'
            '• CV summary is auto-generated'
            '</div></div>'

            '</div>',
            unsafe_allow_html=True,
        )

# ═════════════════════════════════════════════════════════════
# PAGE 3 — GENERATE INTERVIEW
# ═════════════════════════════════════════════════════════════

elif page == "🎙 Generate Interview":

    st.markdown('<div style="font-size:1.9rem;font-weight:800;background:linear-gradient(135deg,#60A5FA,#A78BFA);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:4px;">🎙 Generate Interview</div>', unsafe_allow_html=True)
    st.markdown('<div style="color:#64748B;font-size:0.92rem;margin-bottom:20px;">Build a personalised Vapi voice assistant grounded in the candidate\'s CV.</div>', unsafe_allow_html=True)

    col_gen, col_side = st.columns([2, 1])

    with col_gen:
        st.markdown('<div style="font-size:1rem;font-weight:700;color:#94A3B8;text-transform:uppercase;letter-spacing:0.08em;border-bottom:1px solid #1E3A5F;padding-bottom:8px;margin:24px 0 14px 0;">Select Candidate</div>', unsafe_allow_html=True)

        candidate_id = st.number_input(
            "Candidate ID",
            min_value=1,
            value=int(st.session_state.last_candidate_id),
            help="The ID shown after uploading a candidate resume.",
        )

        # Preview candidate if they exist
        preview = api_get(f"/candidates/{candidate_id}", timeout=8)
        if preview and preview.status_code == 200:
            c = preview.json()
            st.markdown(f"""
            <div style="background:#050D1A;border:1px solid #1E3A5F;border-radius:10px;padding:14px;margin-bottom:16px;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                    <span style="font-weight:700;color:#E2E8F0;">👤 {c['name']}</span>
                    {status_badge(c['status'])}
                </div>
                <div style="font-size:0.82rem;color:#64748B;">
                    🎯 {c['applied_role']} &nbsp;|&nbsp;
                    🗓️ {fmt_dt(c.get('created_at'))} &nbsp;|&nbsp;
                    📅 {c.get('years_experience') or '?'} yrs exp
                </div>
            </div>
            """, unsafe_allow_html=True)

        generate_btn = st.button("🚀 Generate AI Interview Assistant", use_container_width=True)

        if generate_btn:
            with st.spinner("🧠 Building CV-grounded interview prompt and creating Vapi assistant…"):
                resp = api_post(f"/vapi/generate/{candidate_id}", timeout=90)

            if resp is None:
                st.error("❌ Backend unreachable.")
            elif resp.status_code == 200:
                result = resp.json()
                asst_id = result["vapi"]["assistant_id"]
                st.session_state.assistant_id = asst_id
                st.session_state.last_candidate_id = candidate_id

                st.markdown(f"""
                <div style="background:rgba(52,211,153,0.08);border-left:4px solid #34D399;border-radius:8px;padding:14px 16px;margin-bottom:16px;color:#6EE7B7;font-size:0.9rem;">
                    ✅ <strong>Interview assistant created!</strong><br>
                    The assistant has been configured with questions tailored to
                    <strong>{result['candidate_name']}</strong>'s CV and
                    <strong>{result['applied_role']}</strong> role.
                </div>
                """, unsafe_allow_html=True)

                st.code(f"Assistant ID: {asst_id}", language=None)
                st.info("✅ Next step → Go to **📺 Live Interview** to start the voice session.")
            else:
                try:
                    err = resp.json().get("detail", resp.text)
                except Exception:
                    err = resp.text
                st.error(f"❌ Failed ({resp.status_code}): {err}")

    with col_side:
        st.markdown("""
        <div style="background:linear-gradient(145deg,#0F1E35,#0D1B30);border:1px solid #1E3A5F;border-radius:16px;padding:24px;margin-bottom:16px;">
            <div style="font-size:0.8rem;color:#475569;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:14px;">What Happens</div>
            <div style="display:flex;gap:16px;align-items:flex-start;margin-bottom:20px;">
                <div style="min-width:32px;height:32px;background:linear-gradient(135deg,#2563EB,#4F46E5);border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:0.85rem;color:white;flex-shrink:0;">1</div>
                <div style="flex:1;">
                    <h4>CV Profile Loaded</h4>
                    <p>Skills, projects and experience extracted at upload are retrieved.</p>
                </div>
            </div>
            <div style="display:flex;gap:16px;align-items:flex-start;margin-bottom:20px;">
                <div style="min-width:32px;height:32px;background:linear-gradient(135deg,#2563EB,#4F46E5);border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:0.85rem;color:white;flex-shrink:0;">2</div>
                <div style="flex:1;">
                    <h4>Custom Prompt Built</h4>
                    <p>Ollama generates a 12-question interview plan specific to this candidate's CV.</p>
                </div>
            </div>
            <div style="display:flex;gap:16px;align-items:flex-start;margin-bottom:20px;">
                <div style="min-width:32px;height:32px;background:linear-gradient(135deg,#2563EB,#4F46E5);border-radius:50%;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:0.85rem;color:white;flex-shrink:0;">3</div>
                <div style="flex:1;">
                    <h4>Vapi Assistant Created</h4>
                    <p>A dedicated assistant is created via Vapi API with the prompt injected — unique to this candidate.</p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════
# PAGE 4 — LIVE INTERVIEW
# ═════════════════════════════════════════════════════════════

elif page == "📺 Live Interview":

    st.markdown('<div style="font-size:1.9rem;font-weight:800;background:linear-gradient(135deg,#60A5FA,#A78BFA);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:4px;">📺 Live AI Voice Interview</div>', unsafe_allow_html=True)
    st.markdown('<div style="color:#64748B;font-size:0.92rem;margin-bottom:20px;">Conduct the real-time voice interview. The AI interviewer Alex will ask questions based on the candidate\'s CV.</div>', unsafe_allow_html=True)

    assistant_id = st.session_state.assistant_id

    if not assistant_id:
        st.markdown("""
        <div style="background:rgba(251,191,36,0.08);border-left:4px solid #FBB724;border-radius:8px;padding:14px 16px;margin-bottom:16px;color:#FDE68A;font-size:0.9rem;">
            ⚠️ No interview assistant found in this session.
            Go to <strong>🎙 Generate Interview</strong> first and generate an assistant for a candidate.
        </div>
        """, unsafe_allow_html=True)

    else:
        info_col, _ = st.columns([3, 1])
        with info_col:
            st.markdown(f"""
            <div style="background:rgba(52,211,153,0.08);border-left:4px solid #34D399;border-radius:8px;padding:14px 16px;margin-bottom:16px;color:#6EE7B7;font-size:0.9rem;">
                🎤 <strong>Assistant ready.</strong>
                Candidate #{st.session_state.last_candidate_id} —
                Assistant ID: <code>{assistant_id[:32]}…</code>
            </div>
            """, unsafe_allow_html=True)

        # Build widget HTML (f-string — all JS braces doubled)
        html_widget = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>AI HR Interview</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
html,body{{background:#020617;color:white;font-family:Inter,Arial,sans-serif;padding:20px;}}
.container{{background:linear-gradient(145deg,#0F172A,#111827);border:1px solid #1E293B;border-radius:24px;padding:28px;box-shadow:0 0 40px rgba(0,0,0,0.6),inset 0 1px 0 rgba(255,255,255,0.04);}}
.topbar{{display:flex;justify-content:space-between;align-items:center;margin-bottom:24px;gap:16px;flex-wrap:wrap;}}
.brand{{display:flex;align-items:center;gap:12px;}}
.brand-icon{{font-size:2rem;}}
.brand-text h2{{font-size:1.3rem;font-weight:800;margin:0;background:linear-gradient(135deg,#60A5FA,#A78BFA);-webkit-background-clip:text;-webkit-text-fill-color:transparent;}}
.brand-text p{{color:#475569;font-size:0.75rem;margin:0;}}
.live-badge{{display:flex;align-items:center;gap:8px;background:#111827;padding:8px 14px;border-radius:999px;border:1px solid #374151;font-size:0.8rem;}}
.indicator{{width:10px;height:10px;border-radius:50%;background:#6B7280;animation:pulse 1.5s infinite;}}
@keyframes pulse{{0%{{transform:scale(1);opacity:1;}}50%{{transform:scale(1.3);opacity:0.6;}}100%{{transform:scale(1);opacity:1;}}}}
.btn-row{{display:flex;gap:12px;margin-bottom:20px;}}
button{{flex:1;border:none;padding:16px;border-radius:12px;color:white;font-size:0.95rem;font-weight:700;cursor:pointer;transition:0.2s;}}
button:hover{{transform:translateY(-2px);opacity:0.9;}}
button:disabled{{opacity:0.4;cursor:not-allowed;transform:none;}}
.start-btn{{background:linear-gradient(135deg,#2563EB,#4F46E5);}}
.stop-btn{{background:linear-gradient(135deg,#DC2626,#B91C1C);}}
.status-box{{background:#0F172A;border:1px solid #1E293B;border-radius:14px;padding:18px;margin-bottom:18px;}}
#status{{font-size:1.1rem;font-weight:700;color:#10B981;}}
.metrics{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:18px;}}
.metric{{background:#0F172A;border:1px solid #1E293B;border-radius:14px;padding:14px;}}
.metric-label{{color:#475569;font-size:0.72rem;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:6px;}}
.metric-value{{font-size:1.1rem;font-weight:800;}}
.audio-wrap{{margin-bottom:18px;}}
.audio-label{{color:#475569;font-size:0.8rem;margin-bottom:6px;}}
.audio-bg{{width:100%;height:10px;background:#111827;border-radius:999px;overflow:hidden;border:1px solid #1E293B;}}
.audio-fill{{width:0%;height:100%;transition:width 0.08s;background:linear-gradient(90deg,#10B981,#3B82F6,#8B5CF6);}}
.logs{{background:#020617;border:1px solid #1E293B;border-radius:14px;padding:14px;height:240px;overflow-y:auto;}}
.log{{padding:8px 0;border-bottom:1px solid #0F172A;font-size:0.8rem;}}
.logs::-webkit-scrollbar{{width:4px;}}
.logs::-webkit-scrollbar-thumb{{background:#1E293B;border-radius:2px;}}
@media(max-width:600px){{.btn-row{{flex-direction:column;}}}}
</style>
</head>
<body>
<div style="background:linear-gradient(145deg,#0F172A,#111827);border:1px solid #1E293B;border-radius:24px;padding:28px;box-shadow:0 0 40px rgba(0,0,0,0.6);">

  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:24px;gap:16px;flex-wrap:wrap;">
    <div style="display:flex;align-items:center;gap:12px;">
      <div style="font-size:2rem;">🎤</div>
      <div style="">
        <h2>AI HR Interview</h2>
        <p>Enterprise Real-Time Voice Platform</p>
      </div>
    </div>
    <div style="display:flex;align-items:center;gap:8px;background:#111827;padding:8px 14px;border-radius:999px;border:1px solid #374151;font-size:0.8rem;">
      <div id="indicator" style="width:10px;height:10px;border-radius:50%;background:#6B7280;animation:pulse 1.5s infinite;"></div>
      <span id="liveStatus">READY</span>
    </div>
  </div>

  <div style="display:flex;gap:12px;margin-bottom:20px;">
    <button id="startBtn" style="flex:1;border:none;padding:16px;border-radius:12px;color:white;font-size:0.95rem;font-weight:700;cursor:pointer;background:linear-gradient(135deg,#2563EB,#4F46E5);" onclick="startVapiCall()">🚀 Start Interview</button>
    <button id="stopBtn" style="flex:1;border:none;padding:16px;border-radius:12px;color:white;font-size:0.95rem;font-weight:700;cursor:pointer;background:linear-gradient(135deg,#DC2626,#B91C1C);" onclick="stopVapiCall()" disabled>🛑 End Interview</button>
  </div>

  <div style="background:#0F172A;border:1px solid #1E293B;border-radius:14px;padding:18px;margin-bottom:18px;">
    <div id="status">🟢 System Ready — Click Start to begin</div>
  </div>

  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:18px;">
    <div style="background:#0F172A;border:1px solid #1E293B;border-radius:14px;padding:14px;">
      <div style="color:#475569;font-size:0.72rem;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:6px;">Session Timer</div>
      <div id="sessionTimer" style="font-size:1.1rem;font-weight:800;">0:00</div>
    </div>
    <div style="background:#0F172A;border:1px solid #1E293B;border-radius:14px;padding:14px;">
      <div style="color:#475569;font-size:0.72rem;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:6px;">Connection</div>
      <div id="connectionState" style="font-size:1.1rem;font-weight:800;">IDLE</div>
    </div>
    <div style="background:#0F172A;border:1px solid #1E293B;border-radius:14px;padding:14px;">
      <div style="color:#475569;font-size:0.72rem;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:6px;">Audio Input</div>
      <div id="audioState" style="font-size:1.1rem;font-weight:800;">STANDBY</div>
    </div>
    <div style="background:#0F172A;border:1px solid #1E293B;border-radius:14px;padding:14px;">
      <div style="color:#475569;font-size:0.72rem;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:6px;">AI Status</div>
      <div id="aiState" style="font-size:1.1rem;font-weight:800;">—</div>
    </div>
  </div>

  <div style="margin-bottom:18px;">
    <div style="color:#475569;font-size:0.8rem;margin-bottom:6px;">🎚 Audio Level</div>
    <div style="width:100%;height:10px;background:#111827;border-radius:999px;overflow:hidden;border:1px solid #1E293B;"><div id="volume-bar" style="width:0%;height:100%;transition:width 0.08s;background:linear-gradient(90deg,#10B981,#3B82F6,#8B5CF6);"></div></div>
  </div>

  <div style="background:#020617;border:1px solid #1E293B;border-radius:14px;padding:14px;height:240px;overflow-y:auto;" id="logs"></div>

</div>

<script type="module">
import Vapi from "https://esm.sh/@vapi-ai/web";

let vapi = null;
let isCallActive = false;
let isInitializing = false;
let callStartTime = null;
let timerInterval = null;
let eventsRegistered = false;

const $ = id => document.getElementById(id);

function log(msg, type="info") {{
  const logs = $("logs");
  const time = new Date().toLocaleTimeString();
  const colors = {{info:"#94A3B8",error:"#F87171",success:"#4ADE80",warning:"#FBB724"}};
  const el = document.createElement("div");
  el.className = "log";
  el.style.color = colors[type] || colors.info;
  el.textContent = `[${{time}}] ${{msg}}`;
  logs.appendChild(el);
  logs.scrollTop = logs.scrollHeight;
}}

function status(msg, color="#10B981") {{
  $("status").textContent = msg;
  $("status").style.color = color;
}}

function btns(running) {{
  $("startBtn").disabled = running;
  $("stopBtn").disabled = !running;
}}

function startTimer() {{
  callStartTime = Date.now();
  clearInterval(timerInterval);
  timerInterval = setInterval(() => {{
    if (!isCallActive) return;
    const s = Math.floor((Date.now() - callStartTime) / 1000);
    $("sessionTimer").textContent = `${{Math.floor(s/60)}}:${{String(s%60).padStart(2,"0")}}`;
  }}, 1000);
}}

async function cleanup() {{
  clearInterval(timerInterval);
  $("volume-bar").style.width = "0%";
  $("indicator").style.background = "#6B7280";
  $("liveStatus").textContent = "READY";
  $("connectionState").textContent = "IDLE";
  $("audioState").textContent = "STANDBY";
  $("aiState").textContent = "—";
  btns(false);
  isCallActive = false;
  isInitializing = false;
  if (vapi) {{ try {{ await vapi.stop(); }} catch(e) {{}} }}
  vapi = null;
}}

window.addEventListener("offline", () => {{ log("Network lost","error"); status("❌ Network Disconnected","#EF4444"); }});
window.addEventListener("online",  () => {{ log("Network restored","success"); }});

async function startVapiCall() {{
  if (isInitializing || isCallActive) {{ log("Session already active","warning"); return; }}
  isInitializing = true; btns(true);
  try {{
    log("Requesting microphone access…");
    status("🎤 Requesting microphone…","#F59E0B");
    const stream = await navigator.mediaDevices.getUserMedia({{ audio: true }});
    log("Microphone granted","success");
    $("audioState").textContent = "MIC READY";
    stream.getTracks().forEach(t => t.stop());

    status("⚙️ Initializing VAPI…","#3B82F6");
    vapi = new Vapi("{VAPI_PUBLIC_KEY}");
    window.vapiInstance = vapi;
    log("VAPI SDK initialized","success");

    if (!eventsRegistered) {{
      eventsRegistered = true;
      vapi.on("call-start", () => {{
        isCallActive = true;
        startTimer();
        status("✅ Interview Live","#10B981");
        $("indicator").style.background = "#10B981";
        $("liveStatus").textContent = "LIVE";
        $("connectionState").textContent = "CONNECTED";
        $("aiState").textContent = "ACTIVE";
        log("INTERVIEW STARTED","success");
      }});
      vapi.on("speech-start", () => {{
        status("🗣 AI Speaking…","#8B5CF6");
        $("audioState").textContent = "AI SPEAKING";
        $("aiState").textContent = "SPEAKING";
        log("AI speaking");
      }});
      vapi.on("speech-end", () => {{
        status("🎤 Your Turn","#10B981");
        $("audioState").textContent = "LISTENING";
        $("aiState").textContent = "LISTENING";
        log("Your turn to speak");
      }});
      vapi.on("volume-level", v => {{
        $("volume-bar").style.width = Math.min(v*100,100)+"%";
      }});
      vapi.on("error", e => {{
        log("ERROR: "+(e?.message||e?.errorMsg||JSON.stringify(e)),"error");
        status("❌ Connection Failed","#EF4444");
        $("connectionState").textContent = "FAILED";
      }});
      vapi.on("call-end", async () => {{
        log("Interview ended","warning");
        status("🔴 Interview Complete","#EF4444");
        $("liveStatus").textContent = "ENDED";
        $("aiState").textContent = "COMPLETE";
        await cleanup();
      }});
    }}

    status("🚀 Connecting…","#3B82F6");
    $("connectionState").textContent = "CONNECTING";
    log("Connecting to Vapi assistant…");
    await vapi.start("{assistant_id}");
    log("Assistant connected","success");

  }} catch(err) {{
    log("ERROR: "+(err?.message||JSON.stringify(err)),"error");
    status("❌ Failed to start","#EF4444");
    await cleanup();
  }} finally {{
    isInitializing = false;
  }}
}}

async function stopVapiCall() {{
  try {{
    status("🛑 Stopping…","#F59E0B");
    log("Stopping interview…");
    if (window.vapiInstance) await window.vapiInstance.stop();
    await cleanup();
    status("🛑 Interview Stopped","#EF4444");
    log("Interview stopped manually","success");
  }} catch(err) {{
    log("STOP ERROR: "+(err?.message||JSON.stringify(err)),"error");
  }}
}}

window.startVapiCall = startVapiCall;
window.stopVapiCall  = stopVapiCall;
window.addEventListener("beforeunload", async () => {{ await cleanup(); }});

log("Platform initialized — click Start Interview to begin","success");
status("🟢 System Ready");
</script>
</body>
</html>"""

        # Write to local server and embed via real origin
        import base64
        b64 = base64.b64encode(html_widget.encode()).decode()
        components.html(
            f'<iframe src="data:text/html;base64,{b64}" width="100%" height="940px" '
            f'allow="microphone" style="border:none;border-radius:16px;"></iframe>',
            height=960,
        )
        st.markdown("""
        <div style="background:rgba(59,130,246,0.08);border-left:4px solid #3B82F6;border-radius:8px;padding:14px 16px;margin-bottom:16px;color:#93C5FD;font-size:0.9rem;">
            🎤 <strong>Allow microphone access</strong> when the browser asks.
            The evaluation report will appear automatically in Analytics after the call ends (30–60 sec).
        </div>
        """, unsafe_allow_html=True)

        with st.expander("🌐 Remote / ngrok access issue?"):
            st.markdown(f"""
The widget is served from `{widget_url}` — a local address.
If you're accessing Streamlit via ngrok **from a different machine**, the browser
cannot reach `127.0.0.1` on your server. Fix options:

1. Run a second ngrok tunnel: `ngrok http {WIDGET_PORT}` and update `widget_url` in this file.
2. Serve the widget as a static file from your FastAPI backend (`{BACKEND_URL}/static/{fname}`)
   and point `components.iframe()` at that URL instead.
""")


# ═════════════════════════════════════════════════════════════
# PAGE 5 — ANALYTICS
# ═════════════════════════════════════════════════════════════

elif page == "📊 Analytics":

    st.markdown('<div style="font-size:1.9rem;font-weight:800;background:linear-gradient(135deg,#60A5FA,#A78BFA);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:4px;">📊 Recruitment Analytics</div>', unsafe_allow_html=True)
    st.markdown('<div style="color:#64748B;font-size:0.92rem;margin-bottom:20px;">Live data from the database — updated automatically after every evaluation.</div>', unsafe_allow_html=True)

    # Pull live candidates
    r = api_get("/candidates?limit=1000", timeout=15)
    if r is None or r.status_code != 200:
        st.error("❌ Cannot reach backend.")
        st.stop()

    raw = r.json()
    if not raw:
        st.info("No candidates yet. Upload and interview candidates to see analytics.")
        st.stop()

    df = pd.DataFrame(raw)

    # ── KPIs ──────────────────────────────────────────────────
    total      = len(df)
    interviewed = int(df["status"].isin(["Interviewed","Evaluated","Hired","Rejected"]).sum())
    hired       = int((df["status"] == "Hired").sum())
    rejected    = int((df["status"] == "Rejected").sum())
    on_hold     = int((df["status"] == "On Hold").sum())
    hire_rate   = f"{round(hired/interviewed*100)}%" if interviewed else "—"

    k1,k2,k3,k4,k5 = st.columns(5)
    for col, icon, val, lbl in [
        (k1,"👥",total,"Total"),
        (k2,"🎤",interviewed,"Interviewed"),
        (k3,"✅",hired,"Hired"),
        (k4,"❌",rejected,"Rejected"),
        (k5,"📈",hire_rate,"Hire Rate"),
    ]:
        col.markdown(f"""
        <div style="background:linear-gradient(145deg,#0F1E35,#0D1B30);border:1px solid #1E3A5F;border-radius:16px;padding:22px 20px;text-align:center;">
            <div style="font-size:2rem;margin-bottom:8px;">{icon}</div>
            <div style="font-size:2rem;font-weight:800;color:#60A5FA;">{val}</div>
            <div style="font-size:0.8rem;color:#64748B;text-transform:uppercase;letter-spacing:0.05em;">{lbl}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown('<div style="font-size:1rem;font-weight:700;color:#94A3B8;text-transform:uppercase;letter-spacing:0.08em;border-bottom:1px solid #1E3A5F;padding-bottom:8px;margin:24px 0 14px 0;">📈 Candidates by Role</div>', unsafe_allow_html=True)

    role_counts = df["applied_role"].value_counts().reset_index()
    role_counts.columns = ["Role", "Count"]

    ch1, ch2 = st.columns(2)
    with ch1:
        st.bar_chart(role_counts.set_index("Role"), use_container_width=True)

    with ch2:
        status_counts = df["status"].value_counts().reset_index()
        status_counts.columns = ["Status", "Count"]
        st.bar_chart(status_counts.set_index("Status"), use_container_width=True)

    st.markdown('<div style="font-size:1rem;font-weight:700;color:#94A3B8;text-transform:uppercase;letter-spacing:0.08em;border-bottom:1px solid #1E3A5F;padding-bottom:8px;margin:24px 0 14px 0;">📥 Download Report</div>', unsafe_allow_html=True)

    dl_col, _ = st.columns([1, 3])
    with dl_col:
        if st.button("⬇️ Download Excel Report", use_container_width=True):
            dl_r = api_get("/candidates/export/excel", timeout=30)
            if dl_r and dl_r.status_code == 200:
                st.download_button(
                    "📊 Save candidates.xlsx",
                    data=dl_r.content,
                    file_name="ai_hr_candidates.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
            else:
                st.error("Export failed.")

    st.markdown('<div style="font-size:1rem;font-weight:700;color:#94A3B8;text-transform:uppercase;letter-spacing:0.08em;border-bottom:1px solid #1E3A5F;padding-bottom:8px;margin:24px 0 14px 0;">📋 Recent Candidates</div>', unsafe_allow_html=True)

    display_cols = [c for c in ["id","name","applied_role","status","years_experience","created_at"] if c in df.columns]
    st.dataframe(df[display_cols].head(50), use_container_width=True, hide_index=True)


# ═════════════════════════════════════════════════════════════
# PAGE 6 — CANDIDATES
# ═════════════════════════════════════════════════════════════

elif page == "👥 Candidates":

    st.markdown('<div style="font-size:1.9rem;font-weight:800;background:linear-gradient(135deg,#60A5FA,#A78BFA);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:4px;">👥 Candidate Manager</div>', unsafe_allow_html=True)
    st.markdown('<div style="color:#64748B;font-size:0.92rem;margin-bottom:20px;">Browse, search and review full candidate profiles including evaluation scores.</div>', unsafe_allow_html=True)

    # Filters
    f1, f2, f3 = st.columns([2, 1, 1])
    with f1:
        search = st.text_input("🔍 Search by name", placeholder="Type to filter…")
    with f2:
        status_filter = st.selectbox("Status", ["All","Uploaded","Interview Generated","Interviewed","Evaluated","Hired","Rejected","On Hold"])
    with f3:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()

    r = api_get("/candidates?limit=1000", timeout=15)
    if r is None or r.status_code != 200:
        st.error("❌ Cannot reach backend.")
        st.stop()

    candidates = r.json()

    if search:
        candidates = [c for c in candidates if search.lower() in c.get("name","").lower()]
    if status_filter != "All":
        candidates = [c for c in candidates if c.get("status") == status_filter]

    if not candidates:
        st.info("No candidates match your filters.")
        st.stop()

    st.markdown(f"**{len(candidates)} candidate(s) found**")

    for c in candidates[:50]:
        with st.expander(f"#{c['id']}  •  {c['name']}  •  {c['applied_role']}  •  {c['status']}"):
            col_left, col_right = st.columns([1, 1])

            with col_left:
                st.markdown(f"""
                <div style="background:linear-gradient(145deg,#0F1E35,#0D1B30);border:1px solid #1E3A5F;border-radius:16px;padding:24px;margin-bottom:16px;">
                    <div style="font-size:1rem;font-weight:700;color:#94A3B8;text-transform:uppercase;letter-spacing:0.08em;border-bottom:1px solid #1E3A5F;padding-bottom:8px;margin:24px 0 14px 0;">Candidate Info</div>
                    <div style="display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid #1E3A5F;font-size:0.88rem;">
                        <span style="color:#64748B;">Name</span>
                        <span style="color:#E2E8F0;font-weight:600;">{c['name']}</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid #1E3A5F;font-size:0.88rem;">
                        <span style="color:#64748B;">Role</span>
                        <span style="color:#E2E8F0;font-weight:600;">{c['applied_role']}</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid #1E3A5F;font-size:0.88rem;">
                        <span style="color:#64748B;">Status</span>
                        <span style="color:#E2E8F0;font-weight:600;">{status_badge(c['status'])}</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid #1E3A5F;font-size:0.88rem;">
                        <span style="color:#64748B;">Email</span>
                        <span style="color:#E2E8F0;font-weight:600;">{c.get('email') or '—'}</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid #1E3A5F;font-size:0.88rem;">
                        <span style="color:#64748B;">Experience</span>
                        <span style="color:#E2E8F0;font-weight:600;">{c.get('years_experience') or '—'} yrs</span>
                    </div>
                    <div style="display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid #1E3A5F;font-size:0.88rem;">
                        <span style="color:#64748B;">Uploaded</span>
                        <span style="color:#E2E8F0;font-weight:600;">{fmt_dt(c.get('created_at'))}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                if c.get("skills"):
                    pills = "".join(f'<span style="display:inline-block;background:rgba(99,102,241,0.12);border:1px solid #4F46E5;border-radius:999px;padding:4px 14px;font-size:0.78rem;font-weight:600;color:#A78BFA;margin:4px 4px 4px 0;">{s}</span>' for s in c["skills"])
                    st.markdown(f"**Skills:**<br>{pills}", unsafe_allow_html=True)

            with col_right:
                # Fetch full candidate with evaluation
                full_r = api_get(f"/candidates/{c['id']}", timeout=8)
                if full_r and full_r.status_code == 200:
                    full = full_r.json()
                    ev = full.get("evaluation") if isinstance(full.get("evaluation"), dict) else None

                    if ev:
                        st.markdown(f"""
                        <div style="background:linear-gradient(145deg,#0F1E35,#0D1B30);border:1px solid #1E3A5F;border-radius:16px;padding:24px;margin-bottom:16px;">
                            <div style="font-size:1rem;font-weight:700;color:#94A3B8;text-transform:uppercase;letter-spacing:0.08em;border-bottom:1px solid #1E3A5F;padding-bottom:8px;margin:24px 0 14px 0;">Evaluation</div>
                            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
                                <div>
                                    <div style="font-size:1.8rem;font-weight:900;color:#60A5FA;">{ev.get('overall_score',0)}</div>
                                    <div style="font-size:0.72rem;color:#475569;">OVERALL SCORE</div>
                                </div>
                                {status_badge(ev.get('final_decision','—'))}
                            </div>
                            {score_bar("Technical", ev.get('technical_score',0))}
                            {score_bar("Communication", ev.get('communication_score',0))}
                            {score_bar("Problem Solving", ev.get('problem_solving_score',0))}
                            {score_bar("Exp. Alignment", ev.get('experience_alignment_score',0))}
                            {score_bar("Culture Fit", ev.get('culture_fit_score',0))}
                        </div>
                        """, unsafe_allow_html=True)

                        if ev.get("remarks"):
                            st.markdown(f"""
                            <div style="background:#0A1628;border:1px solid #1E3A5F;border-radius:12px;padding:20px 24px;margin-bottom:14px;">
                                <h3>💬 Recruiter Remarks</h3>
                                <p>{ev['remarks']}</p>
                            </div>
                            """, unsafe_allow_html=True)

                        if ev.get("strengths"):
                            st.markdown("**✅ Strengths:**")
                            for s in ev["strengths"]:
                                st.markdown(f"• {s}")

                        if ev.get("areas_for_improvement"):
                            st.markdown("**📌 Areas for Improvement:**")
                            for a in ev["areas_for_improvement"]:
                                st.markdown(f"• {a}")
                    else:
                        st.markdown("""
                        <div style="background:rgba(59,130,246,0.08);border-left:4px solid #3B82F6;border-radius:8px;padding:14px 16px;margin-bottom:16px;color:#93C5FD;font-size:0.9rem;">
                            No evaluation yet. Complete the voice interview to see scores here.
                        </div>
                        """, unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════
# PAGE 7 — INFRASTRUCTURE
# ═════════════════════════════════════════════════════════════

elif page == "⚙️  Infrastructure":

    st.markdown('<div style="font-size:1.9rem;font-weight:800;background:linear-gradient(135deg,#60A5FA,#A78BFA);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:4px;">⚙️ Infrastructure Status</div>', unsafe_allow_html=True)
    st.markdown('<div style="color:#64748B;font-size:0.92rem;margin-bottom:20px;">Live health checks and system configuration.</div>', unsafe_allow_html=True)

    st.markdown('<div style="font-size:1rem;font-weight:700;color:#94A3B8;text-transform:uppercase;letter-spacing:0.08em;border-bottom:1px solid #1E3A5F;padding-bottom:8px;margin:24px 0 14px 0;">🔗 Service Health</div>', unsafe_allow_html=True)

    def check(label, url, icon):
        r = api_get(url, timeout=6) if url.startswith("/") else None
        if url.startswith("/"):
            ok = r is not None and r.status_code == 200
        else:
            try:
                ok = requests.get(url, timeout=5).status_code == 200
            except Exception:
                ok = False
        dot   = "🟢" if ok else "🔴"
        state = "ONLINE" if ok else "OFFLINE"
        color = "#34D399" if ok else "#F87171"
        return f"""
        <div style="background:linear-gradient(145deg,#0F1E35,#0D1B30);border:1px solid #1E3A5F;border-radius:16px;padding:24px;margin-bottom:16px;transition:transform 0.2s;">
            <div style="display:flex;align-items:center;gap:12px;">
                <span style="font-size:1.3rem;">{icon}</span>
                <span style="font-weight:600;color:#E2E8F0;">{label}</span>
            </div>
            <div style="display:flex;align-items:center;gap:8px;">
                <span style="font-size:0.85rem;">{dot}</span>
                <span style="color:{color};font-weight:700;font-size:0.82rem;">{state}</span>
            </div>
        </div>"""

    st.markdown(check("FastAPI Backend",  "/health",                     "⚡"), unsafe_allow_html=True)
    st.markdown(check("Vapi Config",      "/vapi/config",                "🎙"), unsafe_allow_html=True)
    st.markdown(check("Database / ORM",   "/candidates?limit=1",         "🗄️"), unsafe_allow_html=True)
    st.markdown(check("Ollama LLM",       "http://localhost:11434",       "🧠"), unsafe_allow_html=True)

    st.markdown('<div style="font-size:1rem;font-weight:700;color:#94A3B8;text-transform:uppercase;letter-spacing:0.08em;border-bottom:1px solid #1E3A5F;padding-bottom:8px;margin:24px 0 14px 0;">🔧 Configuration</div>', unsafe_allow_html=True)

    cfg_col1, cfg_col2 = st.columns(2)
    with cfg_col1:
        st.markdown(f"""
        <div style="background:#0A1628;border:1px solid #1E3A5F;border-radius:12px;padding:20px 24px;margin-bottom:14px;">
            <h3>Backend</h3>
            <p>
                <strong>URL:</strong> <code>{BACKEND_URL}</code><br>
                <strong>Docs:</strong> <code>{BACKEND_URL}/docs</code><br>
                <strong>Webhooks:</strong> <code>{BACKEND_URL}/webhooks/vapi</code>
            </p>
        </div>
        <div style="background:#0A1628;border:1px solid #1E3A5F;border-radius:12px;padding:20px 24px;margin-bottom:14px;">
            <h3>Vapi Public Key</h3>
            <p><code>{VAPI_PUBLIC_KEY[:20]}…</code></p>
        </div>
        """, unsafe_allow_html=True)

    with cfg_col2:
        st.markdown(f"""
        <div style="background:#0A1628;border:1px solid #1E3A5F;border-radius:12px;padding:20px 24px;margin-bottom:14px;">
            <h3>Widget Server</h3>
            <p>
                <strong>Port:</strong> <code>{WIDGET_PORT}</code><br>
                <strong>Address:</strong> <code>http://127.0.0.1:{WIDGET_PORT}</code><br>
                <strong>Purpose:</strong> Serves the Vapi iframe from a real origin to fix
                Daily.co's postMessage null-origin error.
            </p>
        </div>
        <div style="background:#0A1628;border:1px solid #1E3A5F;border-radius:12px;padding:20px 24px;margin-bottom:14px;">
            <h3>Run Commands</h3>
            <p>
                <code>ollama serve</code><br>
                <code>uvicorn app.main:app --reload --port 8000</code><br>
                <code>ngrok http 8000</code><br>
                <code>streamlit run app.py</code>
            </p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<div style="font-size:1rem;font-weight:700;color:#94A3B8;text-transform:uppercase;letter-spacing:0.08em;border-bottom:1px solid #1E3A5F;padding-bottom:8px;margin:24px 0 14px 0;">📋 API Endpoints</div>', unsafe_allow_html=True)

    endpoints = [
        ("POST", "/candidates/upload",        "Upload candidate PDF and parse CV"),
        ("GET",  "/candidates",               "List all candidates"),
        ("GET",  "/candidates/{id}",          "Get single candidate with evaluation"),
        ("DELETE","/candidates/{id}",         "Delete candidate"),
        ("GET",  "/candidates/export/excel",  "Download Excel report"),
        ("POST", "/vapi/generate/{id}",       "Create Vapi interview assistant from CV"),
        ("GET",  "/vapi/assistant/{id}",      "Get existing assistant ID"),
        ("GET",  "/vapi/config",              "Get Vapi public config"),
        ("POST", "/webhooks/vapi",            "Receive Vapi call events"),
        ("GET",  "/health",                   "Backend health check"),
    ]

    rows_html = "".join(f"""
    <div style="display:flex;align-items:center;gap:12px;padding:9px 0;border-bottom:1px solid #1E3A5F;font-size:0.82rem;">
        <span style="background:{'rgba(52,211,153,0.12)' if m=='GET' else 'rgba(251,191,36,0.12)' if m=='POST' else 'rgba(248,113,113,0.12)'};
               color:{'#34D399' if m=='GET' else '#FBB724' if m=='POST' else '#F87171'};
               border-radius:5px;padding:2px 8px;font-weight:700;min-width:62px;text-align:center;">{m}</span>
        <code style="color:#60A5FA;">{path}</code>
        <span style="color:#64748B;flex:1;text-align:right;">{desc}</span>
    </div>""" for m, path, desc in endpoints)

    st.markdown(f'<div style="background:linear-gradient(145deg,#0F1E35,#0D1B30);border:1px solid #1E3A5F;border-radius:16px;padding:24px;margin-bottom:16px;">{rows_html}</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────────────────────

st.markdown(f"""
<div style="border-top:1px solid #1E3A5F;margin-top:40px;padding-top:16px;
     display:flex;justify-content:space-between;align-items:center;
     font-size:0.75rem;color:#334155;">
    <div>🎯 <strong style="color:#475569;">AI HR Interviewer Enterprise</strong> · v{APP_VERSION}</div>
    <div>{datetime.now().strftime("%d %b %Y · %H:%M")}</div>
</div>
""", unsafe_allow_html=True)