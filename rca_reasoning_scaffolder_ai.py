"""
RCA Reasoning Scaffolder — Combined
Merges step-by-step hypothesis workflow (rca_app.py)
with PAC detection + pathway expansion (pac_scaffold.py)

Run: streamlit run rca_combined.py
Requires: rca_reasoning_core.py in same directory
Optional: set ANTHROPIC_API_KEY for AI expansion
"""

import html
import json
import os
import re
from typing import Dict, List

import streamlit as st
import pandas as pd
from rca_reasoning_core import build_example_case

st.set_page_config(
    page_title="RCA Reasoning Scaffolder",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# =========================================================
# PAC detection terms
# =========================================================
INDIVIDUAL_BLAME_TERMS = [
    "operator error", "human error", "analyst error",
    "did not follow", "failed to follow", "careless",
    "negligence", "mistake by operator", "employee mistake",
    "technician mistake", "user error", "personnel error",
]
PROCEDURAL_TERMS = ["procedure", "sop", "instruction", "sequence", "step",
    "cross-reference", "ambiguous", "unclear", "fragmented", "documentation"]
CONTEXT_TERMS = ["environment", "temperature", "humidity", "timing", "shift",
    "room", "workflow", "handoff", "context", "condition", "monitoring"]
TRAINING_TERMS = ["training", "qualified", "qualification", "understanding", "interpretation"]
EQUIPMENT_TERMS = ["equipment", "instrument", "machine", "device"]
RECORD_TERMS = ["record", "documentation", "entry", "log"]

# =========================================================
# Session state
# =========================================================
STEPS = {
    1: ("Intake",        "Read the deviation and understand what happened before forming any explanation."),
    2: ("Hypotheses",    "Review all possible explanations. Do not narrow yet."),
    3: ("PAC Analysis",  "Check whether reasoning is converging too early on an individual actor."),
    4: ("Reasoning",     "Attach factors, evidence, and notes to each hypothesis."),
    5: ("Pre-Closure",   "Review what remains visible before committing to a final explanation."),
}

defaults = {
    "rca": None,
    "step": 1,
    "selected": "H1",
    "plausibility": {"H1": "Plausible", "H2": "Unclear", "H3": "Plausible"},
    "notes": {"H1": "", "H2": "", "H3": ""},
    "log": ["Session initialized.", "Investigation workspace ready."],
    "toast_msg": None,
    "ai_result": None,
    "pac_hypothesis": "",
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

if st.session_state.rca is None:
    st.session_state.rca = build_example_case()

rca = st.session_state.rca

# =========================================================
# Helpers
# =========================================================
def esc(t): return html.escape(str(t or "")).replace("\n", "<br>")
def render(h): st.markdown(h, unsafe_allow_html=True)
def log_event(msg): st.session_state.log.insert(0, msg)

def get_selected():
    for h in rca.hypotheses:
        if h.id == st.session_state.selected:
            return h
    return rca.hypotheses[0]

def set_status(hid, status):
    for h in rca.hypotheses:
        if h.id == hid:
            old = h.status
            h.status = status
            log_event(f"{hid}: {old} → {status}")
            break

def counts():
    a = sum(1 for h in rca.hypotheses if h.status == "active")
    n = sum(1 for h in rca.hypotheses if h.status == "narrowed")
    d = sum(1 for h in rca.hypotheses if h.status == "discarded")
    return a, n, d

def closure_info():
    a, _, _ = counts()
    total = len(rca.hypotheses)
    pct = round((1 - a / total) * 100)
    if a >= 3:   return "Open",      "#16a34a", "#f0fdf4", "#86efac", "Multiple paths still visible.", pct
    elif a == 2: return "Narrowing", "#d97706", "#fefce8", "#fde68a", "Two paths remain. Closure pressure building.", pct
    elif a == 1: return "At Risk",   "#dc2626", "#fef2f2", "#fca5a5", "Only one path left. Check before closing.", pct
    else:        return "Collapsed", "#6b7280", "#f9fafb", "#d1d5db", "No active paths.", pct

def contains_any(text, terms):
    return any(t in text for t in terms)

def normalize(text): return text.strip().lower()

# =========================================================
# PAC detection
# =========================================================
def detect_pac_risk(hypothesis: str) -> Dict:
    h = normalize(hypothesis)
    matches = [t for t in INDIVIDUAL_BLAME_TERMS if t in h]
    if matches:
        return {"level": "High", "color": "#dc2626", "bg": "#fef2f2", "border": "#fca5a5",
                "label": "High convergence risk", "matched": matches,
                "message": "This hypothesis is converging early on an individual actor. Procedural, contextual, and organizational contributors may be closing off before they have been examined."}
    if any(w in h for w in ["operator", "analyst", "personnel", "staff", "technician"]):
        return {"level": "Moderate", "color": "#d97706", "bg": "#fefce8", "border": "#fde68a",
                "label": "Moderate convergence risk", "matched": [],
                "message": "The hypothesis foregrounds an individual actor. Systemic contributors should remain explicitly visible."}
    return {"level": "Low", "color": "#16a34a", "bg": "#f0fdf4", "border": "#86efac",
            "label": "Low convergence risk", "matched": [],
            "message": "No strong individual-blame language detected. Continue checking that multiple causal pathways remain open."}

def generate_pathways(hypothesis: str) -> List[Dict]:
    text = normalize(rca.issue + " " + hypothesis)
    paths = []
    paths.append({"id": "procedural", "title": "Procedural / documentation", "icon": "📄",
        "desc": "The event may reflect ambiguity or cross-reference burden in the procedure itself.",
        "prompt": "What would this look like if the procedure — not the person — was the primary contributor?"})
    if contains_any(text, CONTEXT_TERMS) or "deviation" in text:
        paths.append({"id": "contextual", "title": "Contextual / workflow", "icon": "🌡️",
            "desc": "The deviation may have been shaped by task conditions, timing pressure, or workflow constraints.",
            "prompt": "What contextual conditions were present that could have shaped the outcome?"})
    if contains_any(text, TRAINING_TERMS) or "understand" in text or "misunder" in text:
        paths.append({"id": "interpretation", "title": "Interpretation / training", "icon": "🧩",
            "desc": "The issue may involve differences in procedural interpretation or incomplete understanding.",
            "prompt": "Could different investigators interpret the same procedure differently — and if so, why?"})
    if contains_any(text, EQUIPMENT_TERMS):
        paths.append({"id": "equipment", "title": "Equipment / interface", "icon": "⚙️",
            "desc": "The event may involve equipment condition or interface design that shaped how the task was carried out.",
            "prompt": "How did the equipment or interface constrain the actor's available actions?"})
    if contains_any(text, RECORD_TERMS):
        paths.append({"id": "documentation", "title": "Documentation / recording", "icon": "📝",
            "desc": "The apparent issue may partly reflect how the event was documented rather than the original action.",
            "prompt": "How might documenting this event have shaped how it is now being explained?"})
    return paths[:4]

# =========================================================
# AI expansion
# =========================================================
def get_anthropic_key():
    try:
        return st.secrets.get("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    except Exception:
        return os.getenv("ANTHROPIC_API_KEY")

def run_claude_expansion(hypothesis: str) -> Dict:
    import anthropic
    client = anthropic.Anthropic(api_key=get_anthropic_key())
    prompt = f"""You are a reasoning-space scaffold for Root Cause Analysis in regulated environments.
Do NOT give a final compliance decision. Do NOT collapse the explanation.
Your role: preserve reasoning space and surface premature accountability convergence (PAC).

Return ONLY valid JSON:
{{
  "alternative_pathways": [
    {{"title": "short title", "desc": "1-2 sentence description", "question": "one reopening question"}},
    {{"title": "short title", "desc": "1-2 sentence description", "question": "one reopening question"}},
    {{"title": "short title", "desc": "1-2 sentence description", "question": "one reopening question"}}
  ],
  "pac_warning": "2-3 sentence warning about premature convergence",
  "next_evidence": ["item 1", "item 2", "item 3"],
  "reopening_questions": ["question 1", "question 2", "question 3"]
}}

Case: {rca.issue}
Current hypothesis: {hypothesis}"""

    msg = client.messages.create(model="claude-sonnet-4-20250514", max_tokens=1200,
                                  messages=[{"role": "user", "content": prompt}])
    raw = msg.content[0].text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise

# =========================================================
# HTML primitives
# =========================================================
CARD = ("background:#ffffff;border:1px solid #e5e7eb;border-radius:12px;"
        "padding:22px 24px;margin-bottom:12px;box-shadow:0 1px 3px rgba(0,0,0,.05);")

def badge(status):
    cfg = {"active": ("Active","#1a56db","#e8f0fe","#c3d8fd"),
           "narrowed": ("Narrowed","#92400e","#fef3c7","#fde68a"),
           "discarded": ("Dropped","#374151","#f3f4f6","#d1d5db")}
    label, color, bg, bdr = cfg.get(status, cfg["discarded"])
    return (f'<span style="display:inline-block;padding:4px 10px;border-radius:5px;'
            f'font-size:12px;font-weight:700;background:{bg};color:{color};border:1px solid {bdr};">{label}</span>')

def plaus_badge(p):
    cfg = {"Plausible": ("#166534","#dcfce7","#86efac"),
           "Unclear": ("#92400e","#fef3c7","#fde68a"),
           "Weak": ("#374151","#f3f4f6","#d1d5db")}
    color, bg, bdr = cfg.get(p, cfg["Unclear"])
    return (f'<span style="display:inline-block;padding:4px 10px;border-radius:5px;'
            f'font-size:12px;font-weight:700;background:{bg};color:{color};border:1px solid {bdr};">{p}</span>')

def overline(t):
    return (f'<div style="font-size:11px;font-weight:700;text-transform:uppercase;'
            f'letter-spacing:.08em;color:#9ca3af;margin-bottom:8px;">{esc(t)}</div>')

def heading(t, size="17px", mb="10px"):
    return (f'<div style="font-size:{size};font-weight:700;color:#111827;'
            f'line-height:1.35;margin-bottom:{mb};">{esc(t)}</div>')

def body(t):
    return f'<div style="font-size:14px;color:#4b5563;line-height:1.7;">{t}</div>'

def slabel(t, mt="14px"):
    return (f'<div style="font-size:12px;font-weight:700;text-transform:uppercase;'
            f'letter-spacing:.07em;color:#9ca3af;margin:{mt} 0 6px;">{esc(t)}</div>')

def pill(t, bg="#f9fafb", bdr="#e5e7eb", color="#374151"):
    return (f'<div style="padding:10px 14px;background:{bg};border:1px solid {bdr};'
            f'border-radius:8px;margin-bottom:6px;font-size:14px;color:{color};">{esc(t)}</div>')

# =========================================================
# CSS
# =========================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [data-testid="stAppViewContainer"], .stApp {
    background:#eef0f4 !important; font-family:'Inter',sans-serif !important;
}
[data-testid="stHeader"],[data-testid="stDecoration"],[data-testid="stToolbar"],footer { display:none !important; }
.block-container { max-width:1480px !important; padding:20px 28px 32px !important; }
[data-testid="stVerticalBlock"] > div:empty { display:none !important; }
div[data-testid="stVerticalBlockBorderWrapper"],
div[data-testid="stVerticalBlockBorderWrapper"] > div {
    border:none !important; background:transparent !important;
    box-shadow:none !important; padding:0 !important;
    border-radius:0 !important; margin:0 !important;
}
div[data-testid="stButton"] > button {
    font-family:'Inter',sans-serif !important; font-size:14px !important;
    font-weight:600 !important; color:#374151 !important; background:#ffffff !important;
    border:1.5px solid #d1d5db !important; border-radius:9px !important;
    padding:10px 8px !important; min-height:2.7rem !important;
    box-shadow:0 1px 2px rgba(0,0,0,.05) !important; transition:all .12s ease !important;
    width:100% !important; white-space:nowrap !important;
}
div[data-testid="stButton"] > button:hover {
    background:#f3f4f6 !important; border-color:#9ca3af !important; color:#111827 !important;
}
[data-testid="stRadio"] { padding:8px 0 4px !important; }
[data-testid="stRadio"] label { font-size:15px !important; font-weight:500 !important; color:#374151 !important; padding:5px 10px !important; }
.stTextArea label { font-size:14px !important; font-weight:600 !important; color:#374151 !important; }
textarea {
    font-family:'Inter',sans-serif !important; font-size:14px !important;
    color:#1f2937 !important; background:#f9fafb !important;
    border:1.5px solid #d1d5db !important; border-radius:9px !important;
    padding:14px 16px !important; line-height:1.7 !important;
}
textarea:focus { border-color:#2563eb !important; outline:none !important; }
[data-testid="stExpander"] { border:1px solid #e5e7eb !important; border-radius:10px !important; background:#f9fafb !important; }
[data-testid="stExpander"] summary { font-size:15px !important; font-weight:600 !important; color:#374151 !important; }
@keyframes fill { from { width:0%; } to { width:var(--fill-w); } }
.pac-bar-inner { animation:fill 0.8s ease-out forwards; }
</style>
""", unsafe_allow_html=True)

# =========================================================
# Toast
# =========================================================
if st.session_state.toast_msg:
    st.toast(st.session_state.toast_msg)
    st.session_state.toast_msg = None

# =========================================================
# Derived state
# =========================================================
step = st.session_state.step
step_name, step_desc = STEPS[step]
sig_name, sig_color, sig_bg, sig_bdr, sig_msg, pressure_pct = closure_info()
active_c, narrowed_c, dropped_c = counts()
selected = get_selected()

# =========================================================
# Header
# =========================================================
render(f"""
<div style="{CARD}margin-bottom:10px;">
  <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:14px;">
    <div>
      {overline("GMP Investigation Tool · Prototype")}
      <div style="font-size:22px;font-weight:700;color:#111827;letter-spacing:-.02em;margin-bottom:4px;">
        RCA Reasoning Scaffolder
      </div>
      <div style="font-size:14px;color:#6b7280;">
        Keep multiple causal paths visible before committing to a final explanation.
        Detects premature accountability convergence (PAC) at each step.
      </div>
    </div>
    <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;">
      <div style="text-align:center;padding:10px 18px;background:#f0fdf4;border:1px solid #86efac;border-radius:10px;">
        <div style="font-size:24px;font-weight:700;color:#16a34a;">{active_c}</div>
        <div style="font-size:11px;font-weight:600;color:#16a34a;">Active</div>
      </div>
      <div style="text-align:center;padding:10px 18px;background:#fefce8;border:1px solid #fde68a;border-radius:10px;">
        <div style="font-size:24px;font-weight:700;color:#d97706;">{narrowed_c}</div>
        <div style="font-size:11px;font-weight:600;color:#d97706;">Narrowed</div>
      </div>
      <div style="text-align:center;padding:10px 18px;background:#f9fafb;border:1px solid #d1d5db;border-radius:10px;">
        <div style="font-size:24px;font-weight:700;color:#6b7280;">{dropped_c}</div>
        <div style="font-size:11px;font-weight:600;color:#6b7280;">Dropped</div>
      </div>
      <div style="text-align:center;padding:10px 18px;background:{sig_bg};border:1px solid {sig_bdr};border-radius:10px;">
        <div style="font-size:24px;font-weight:700;color:{sig_color};">{sig_name}</div>
        <div style="font-size:11px;font-weight:600;color:{sig_color};">Signal</div>
      </div>
    </div>
  </div>
</div>
""")

# =========================================================
# Step nav
# =========================================================
render('<div style="font-size:11px;font-weight:700;text-transform:uppercase;'
       'letter-spacing:.08em;color:#9ca3af;margin-bottom:8px;">Investigation Workflow</div>')

step_cols = st.columns(5)
for i, (n, (title, _)) in enumerate(STEPS.items()):
    with step_cols[i]:
        if step == n:
            render(f"""
            <div style="background:#eff6ff;border:2px solid #2563eb;border-radius:9px;
                padding:10px 14px;text-align:center;">
              <div style="font-size:11px;font-weight:700;color:#1d4ed8;">Step {n}</div>
              <div style="font-size:13px;font-weight:700;color:#1e40af;">{title}</div>
            </div>""")
        else:
            if st.button(f"Step {n}  {title}", key=f"step_{n}", use_container_width=True):
                st.session_state.step = n
                log_event(f"Moved to step {n}: {title}")
                st.session_state.toast_msg = f"→ Step {n}: {title}"
                st.rerun()

render(f"""
<div style="margin:10px 0 16px;padding:12px 16px;background:#eff6ff;
    border-radius:9px;border-left:4px solid #2563eb;">
  <span style="font-size:13px;font-weight:700;color:#1d4ed8;">Step {step} — {step_name}: </span>
  <span style="font-size:13px;color:#3b82f6;">{step_desc}</span>
</div>
""")

# =========================================================
# Main layout
# =========================================================
left, center, right = st.columns([1.1, 1.75, 1.1], gap="large")

# ─────────────────────────────────────────────────────────
# LEFT — Hypothesis list
# ─────────────────────────────────────────────────────────
with left:
    render('<div style="font-size:12px;font-weight:700;text-transform:uppercase;'
           'letter-spacing:.07em;color:#6b7280;margin-bottom:12px;">Hypotheses</div>')

    for h in rca.hypotheses:
        is_sel = h.id == st.session_state.selected
        card_bg = "#eff6ff" if is_sel else "#ffffff"
        card_bd = "#2563eb" if is_sel else "#e5e7eb"
        card_bw = "2px" if is_sel else "1px"

        # PAC badge per hypothesis
        risk = detect_pac_risk(h.description)
        pac_dot = f'<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:{risk["color"]};margin-left:6px;" title="PAC: {risk["level"]}"></span>'

        viewing_tag = '<div style="margin-top:6px;font-size:11px;color:#2563eb;font-weight:600;">▶ viewing</div>' if is_sel else ""

        render(f"""
        <div style="background:{card_bg};border:{card_bw} solid {card_bd};border-radius:12px;
            padding:16px 18px;margin-bottom:4px;box-shadow:0 1px 4px rgba(0,0,0,.05);">
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;">
            <div style="display:flex;align-items:center;">
              <span style="font-size:12px;font-weight:700;color:#9ca3af;">{h.id}</span>
              {pac_dot}
            </div>
            {badge(h.status)}
          </div>
          <div style="font-size:14px;font-weight:600;color:#111827;line-height:1.45;margin-bottom:8px;">
            {esc(h.description)}
          </div>
          <div style="font-size:12px;color:#6b7280;padding:6px 10px;background:rgba(0,0,0,.03);border-radius:6px;">
            {st.session_state.plausibility.get(h.id, "Unclear")}
          </div>
          {viewing_tag}
        </div>
        """)

        if st.button("✓ Viewing" if is_sel else f"View {h.id}",
                     key=f"sel_{h.id}", use_container_width=True,
                     type="primary" if is_sel else "secondary"):
            st.session_state.selected = h.id
            st.session_state.pac_hypothesis = h.description
            log_event(f"Viewing {h.id}")
            st.session_state.toast_msg = f"🔍 Now viewing {h.id}"
            st.rerun()

        b1, b2, b3 = st.columns(3)
        with b1:
            if st.button("✅" if h.status == "active" else "Active",
                         key=f"ba_{h.id}", use_container_width=True,
                         type="primary" if h.status == "active" else "secondary"):
                set_status(h.id, "active")
                st.session_state.selected = h.id
                st.session_state.toast_msg = f"✅ {h.id} → Active"
                st.rerun()
        with b2:
            if st.button("⚠️" if h.status == "narrowed" else "Narrow",
                         key=f"bn_{h.id}", use_container_width=True,
                         type="primary" if h.status == "narrowed" else "secondary"):
                set_status(h.id, "narrowed")
                st.session_state.selected = h.id
                st.session_state.toast_msg = f"⚠️ {h.id} → Narrowed"
                st.rerun()
        with b3:
            if st.button("❌" if h.status == "discarded" else "Drop",
                         key=f"bd_{h.id}", use_container_width=True,
                         type="primary" if h.status == "discarded" else "secondary"):
                set_status(h.id, "discarded")
                st.session_state.selected = h.id
                st.session_state.toast_msg = f"❌ {h.id} → Dropped"
                st.rerun()

        render('<div style="height:6px;"></div>')

# ─────────────────────────────────────────────────────────
# CENTER — Step content
# ─────────────────────────────────────────────────────────
with center:

    # ── Step 1: Intake ──
    if step == 1:
        render(f"""
        <div style="{CARD}">
          {overline("Deviation")}
          {heading(rca.issue, size="18px")}
          {body("Root cause analysis (RCA) identifies <strong>why something failed</strong> — "
                "not just the most visible cause, but the structural one.<br><br>"
                "Investigators often settle on the first plausible explanation, "
                "closing off other possibilities too early. "
                "This scaffold keeps multiple causal paths visible before you commit.")}
        </div>
        """)

        steps_rows = ""
        for n, (title, desc) in STEPS.items():
            act = n == step
            bg2 = "#eff6ff" if act else "#f9fafb"
            bl = "3px solid #2563eb" if act else "3px solid #e5e7eb"
            tc = "#1e40af" if act else "#374151"
            dc = "#3b82f6" if act else "#6b7280"
            steps_rows += (
                f'<div style="border-left:{bl};padding:10px 14px;border-radius:0 8px 8px 0;'
                f'background:{bg2};margin-bottom:6px;">'
                f'<div style="font-size:13px;font-weight:700;color:{tc};">Step {n} — {title}</div>'
                f'<div style="font-size:12px;color:{dc};margin-top:3px;">{desc}</div>'
                f'</div>'
            )
        render(f'<div style="{CARD}">{overline("What to do in each step")}{steps_rows}</div>')

        render(f"""
        <div style="background:#f0fdf4;border:1px solid #86efac;border-radius:12px;padding:16px 20px;">
          {overline("PAC framework")}
          {body("Premature Accountability Convergence (PAC) occurs when investigation reasoning "
                "narrows toward an individual actor before systemic, procedural, and contextual "
                "contributors have been examined. Each step in this scaffold is designed to "
                "resist that convergence.")}
        </div>
        """)

    # ── Step 2: Hypotheses ──
    elif step == 2:
        render(f"""
        <div style="{CARD}">
          {overline("Instructions")}
          {heading("Review each explanation — do not narrow yet")}
          {body("Use <strong>View</strong> to read each hypothesis in detail. "
                "Keep all paths open at this stage — narrowing comes later.")}
        </div>
        """)

        for h in rca.hypotheses:
            risk = detect_pac_risk(h.description)
            is_focused = h.id == st.session_state.selected
            render(f"""
            <div style="{CARD}margin-bottom:8px;border-left:4px solid {risk['color']};">
              <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
                <div style="display:flex;align-items:center;gap:8px;">
                  <span style="font-size:12px;font-weight:700;color:#9ca3af;">{h.id}</span>
                  {badge(h.status)}
                </div>
                <span style="font-size:11px;font-weight:700;padding:3px 8px;background:{risk['bg']};
                    color:{risk['color']};border:1px solid {risk['border']};border-radius:5px;">
                  PAC: {risk['level']}
                </span>
              </div>
              <div style="font-size:15px;font-weight:600;color:#111827;line-height:1.45;margin-bottom:6px;">
                {esc(h.description)}
              </div>
              <div style="font-size:13px;color:#6b7280;">{risk['message']}</div>
            </div>
            """)

            c1, c2, c3, c4 = st.columns(4)
            with c1:
                if st.button("✓ Viewing" if is_focused else f"View {h.id}",
                             key=f"v2_{h.id}", use_container_width=True,
                             type="primary" if is_focused else "secondary"):
                    st.session_state.selected = h.id
                    st.session_state.pac_hypothesis = h.description
                    st.session_state.toast_msg = f"🔍 Now viewing {h.id}"
                    st.rerun()
            with c2:
                if st.button("✅" if h.status == "active" else "Active",
                             key=f"a2_{h.id}", use_container_width=True,
                             type="primary" if h.status == "active" else "secondary"):
                    set_status(h.id, "active")
                    st.rerun()
            with c3:
                if st.button("⚠️" if h.status == "narrowed" else "Narrow",
                             key=f"n2_{h.id}", use_container_width=True,
                             type="primary" if h.status == "narrowed" else "secondary"):
                    set_status(h.id, "narrowed")
                    st.rerun()
            with c4:
                if st.button("❌" if h.status == "discarded" else "Drop",
                             key=f"d2_{h.id}", use_container_width=True,
                             type="primary" if h.status == "discarded" else "secondary"):
                    set_status(h.id, "discarded")
                    st.rerun()
            render('<div style="height:4px;"></div>')

    # ── Step 3: PAC Analysis ──
    elif step == 3:
        hyp_text = st.session_state.pac_hypothesis or selected.description
        risk = detect_pac_risk(hyp_text)
        pathways = generate_pathways(hyp_text)
        risk_pct = {"High": 85, "Moderate": 50, "Low": 15}[risk["level"]]

        matched_html = ""
        if risk["matched"]:
            terms = "".join(
                f'<span style="display:inline-block;padding:2px 8px;background:#fee2e2;'
                f'color:#991b1b;border-radius:4px;font-size:12px;font-weight:600;margin:2px 3px 2px 0;">'
                f'{esc(t)}</span>' for t in risk["matched"]
            )
            matched_html = f'<div style="margin-top:10px;">{slabel("Flagged language", mt="0")}{terms}</div>'

        render(f"""
        <div style="background:{risk['bg']};border:1px solid {risk['border']};border-radius:12px;padding:20px 22px;margin-bottom:12px;">
          {overline("PAC Risk — " + selected.id)}
          <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;margin-bottom:12px;">
            <div style="font-size:18px;font-weight:700;color:{risk['color']};">{esc(risk['label'])}</div>
            <div style="font-size:12px;color:{risk['color']};font-weight:600;padding:5px 12px;
                background:rgba(255,255,255,.7);border-radius:6px;border:1px solid {risk['border']};">
              Convergence pressure: {risk_pct}%
            </div>
          </div>
          <div style="background:rgba(255,255,255,.5);border-radius:5px;height:8px;overflow:hidden;margin-bottom:10px;">
            <div class="pac-bar-inner" style="--fill-w:{risk_pct}%;height:100%;background:{risk['color']};border-radius:5px;"></div>
          </div>
          <div style="font-size:13px;color:#374151;line-height:1.65;">{esc(risk['message'])}</div>
          {matched_html}
        </div>
        """)

        render(f'<div style="font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:#6b7280;margin-bottom:10px;">Alternative causal pathways — keep visible</div>')

        colors = ["#2563eb","#16a34a","#d97706","#7c3aed"]
        bgs    = ["#eff6ff","#f0fdf4","#fefce8","#f5f3ff"]
        bdrs   = ["#bfdbfe","#86efac","#fde68a","#ddd6fe"]

        for i, p in enumerate(pathways):
            c, bg, bdr = colors[i%4], bgs[i%4], bdrs[i%4]
            render(f"""
            <div style="background:{bg};border:1px solid {bdr};border-left:4px solid {c};border-radius:12px;padding:16px 18px;margin-bottom:8px;">
              <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
                <span style="font-size:16px;">{esc(p['icon'])}</span>
                <div style="font-size:13px;font-weight:700;color:#111827;">{esc(p['title'])}</div>
              </div>
              <div style="font-size:13px;color:#374151;line-height:1.6;margin-bottom:8px;">{esc(p['desc'])}</div>
              <div style="padding:8px 12px;background:rgba(255,255,255,.7);border-radius:6px;border:1px solid {bdr};">
                <span style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:{c};">Reopening question  </span>
                <span style="font-size:12px;color:#374151;font-style:italic;">{esc(p['prompt'])}</span>
              </div>
            </div>
            """)

        # AI expansion
        api_available = get_anthropic_key() is not None
        render('<div style="height:4px;"></div>')
        if st.button(
            "✨  Expand with AI" if api_available else "✨  AI expansion (set ANTHROPIC_API_KEY)",
            use_container_width=True,
            disabled=not api_available,
            key="ai_expand"
        ):
            with st.spinner("Generating AI reasoning expansion..."):
                try:
                    st.session_state.ai_result = run_claude_expansion(hyp_text)
                    st.session_state.toast_msg = "✨ AI expansion complete"
                    st.rerun()
                except Exception as e:
                    st.error(f"AI expansion failed: {e}")

        if st.session_state.ai_result:
            ai = st.session_state.ai_result
            render(f"""
            <div style="background:#faf5ff;border:1px solid #ddd6fe;border-left:4px solid #7c3aed;border-radius:12px;padding:18px 20px;margin-top:8px;">
              {overline("AI expansion · reasoning space mode")}
              {heading("AI-generated alternative pathways", size="15px")}
            """)
            if ai.get("pac_warning"):
                render(f'<div style="background:#fef2f2;border:1px solid #fca5a5;border-radius:8px;padding:12px 14px;margin-bottom:10px;font-size:13px;color:#374151;line-height:1.65;">{esc(ai["pac_warning"])}</div>')
            for path in ai.get("alternative_pathways", []):
                render(f"""
                <div style="padding:12px 14px;background:rgba(255,255,255,.7);border:1px solid #ddd6fe;border-radius:8px;margin-bottom:6px;">
                  <div style="font-size:13px;font-weight:700;color:#7c3aed;margin-bottom:4px;">✨ {esc(path.get('title',''))}</div>
                  <div style="font-size:13px;color:#374151;line-height:1.6;margin-bottom:6px;">{esc(path.get('desc',''))}</div>
                  <div style="font-size:12px;color:#6b7280;font-style:italic;">{esc(path.get('question',''))}</div>
                </div>
                """)
            render("</div>")

    # ── Step 4: Reasoning ──
    elif step == 4:
        factors_rows = "".join(pill(f) for f in selected.factors)
        evidence_rows = "".join(pill(e, bg="#f0fdf4", bdr="#86efac", color="#166534") for e in selected.evidence)

        render(f"""
        <div style="{CARD}">
          {overline("Selected Hypothesis — " + selected.id)}
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
            <span style="font-size:13px;font-weight:700;color:#9ca3af;">{selected.id}</span>
            {badge(selected.status)}
          </div>
          {heading(selected.description)}
          {body("Review the contributing factors and evidence below. "
                "Then rate plausibility and add your notes.")}
          {slabel("Contributing Factors")}
          {factors_rows}
          {slabel("Evidence")}
          {evidence_rows}
        </div>
        """)

        plaus_val = st.radio(
            "How plausible is this explanation?",
            ["Plausible", "Unclear", "Weak"], horizontal=True,
            index=["Plausible", "Unclear", "Weak"].index(
                st.session_state.plausibility.get(selected.id, "Unclear")),
            key=f"plaus_{selected.id}",
        )
        st.session_state.plausibility[selected.id] = plaus_val

        note = st.text_area("Your investigation note",
            value=st.session_state.notes.get(selected.id, ""),
            placeholder="Write down any ambiguity, missing information, or observations...",
            key=f"note_{selected.id}")
        st.session_state.notes[selected.id] = note

        if st.button("💾  Save Note", use_container_width=True, key="save_note"):
            log_event(f"Note saved for {selected.id}")
            st.session_state.toast_msg = f"💾 Note saved for {selected.id}"
            st.rerun()

    # ── Step 5: Pre-Closure ──
    elif step == 5:
        active_hs   = [h for h in rca.hypotheses if h.status == "active"]
        narrowed_hs = [h for h in rca.hypotheses if h.status == "narrowed"]
        dropped_hs  = [h for h in rca.hypotheses if h.status == "discarded"]

        render(f"""
        <div style="background:{sig_bg};border:1px solid {sig_bdr};border-radius:12px;padding:20px 22px;margin-bottom:12px;">
          {overline("Closure Signal")}
          <div style="font-size:24px;font-weight:800;color:{sig_color};margin-bottom:6px;">{sig_name}</div>
          {body(sig_msg)}
        </div>
        """)

        ca, cn, cd = st.columns(3)
        for col, label, items, color, bg2, bdr in [
            (ca, "Still Active",  active_hs,   "#16a34a","#f0fdf4","#86efac"),
            (cn, "Narrowed",      narrowed_hs, "#d97706","#fefce8","#fde68a"),
            (cd, "Dropped",       dropped_hs,  "#6b7280","#f9fafb","#d1d5db"),
        ]:
            with col:
                items_html = "".join(
                    f'<div style="font-size:13px;color:#374151;padding:5px 0;border-bottom:1px solid #f3f4f6;">'
                    f'<strong>{h.id}</strong> — {esc(h.description)}</div>'
                    for h in items
                ) or '<div style="font-size:13px;color:#9ca3af;">None</div>'
                render(f"""
                <div style="background:{bg2};border:1px solid {bdr};border-radius:12px;padding:16px 18px;margin-bottom:8px;">
                  <div style="font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:{color};margin-bottom:8px;">{label}</div>
                  {items_html}
                </div>""")

        prompts = "".join(
            f'<div style="display:flex;gap:10px;padding:10px 0;border-bottom:1px solid #f3f4f6;">'
            f'<span style="color:#d97706;font-weight:700;font-size:15px;flex-shrink:0;">?</span>'
            f'<span style="font-size:13px;color:#374151;line-height:1.6;">{esc(q)}</span></div>'
            for q in [
                "Did the investigation become cleaner by becoming narrower?",
                "Which explanations lost visibility before closure?",
                "Is the final reasoning state genuinely stronger, or just neater?",
            ]
        )
        render(f'<div style="{CARD}">{overline("Before You Close")}{prompts}</div>')

        with st.expander("Full investigation summary"):
            rows = [{"ID": h.id, "Description": h.description, "Status": h.status,
                     "Plausibility": st.session_state.plausibility.get(h.id,""),
                     "Note": st.session_state.notes.get(h.id,""),
                     "Factors": " | ".join(h.factors), "Evidence": " | ".join(h.evidence)}
                    for h in rca.hypotheses]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# ─────────────────────────────────────────────────────────
# RIGHT — Inspector panel
# ─────────────────────────────────────────────────────────
with right:
    render(f"""
    <div style="{CARD}">
      {overline("Closure Signal")}
      <div style="font-size:26px;font-weight:800;color:{sig_color};margin-bottom:4px;">{sig_name}</div>
      <div style="font-size:13px;color:#4b5563;margin-bottom:14px;line-height:1.6;">{sig_msg}</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;">
        <div style="text-align:center;padding:8px;background:#f0fdf4;border:1px solid #86efac;border-radius:8px;">
          <div style="font-size:20px;font-weight:700;color:#16a34a;">{active_c}</div>
          <div style="font-size:11px;font-weight:600;color:#16a34a;">Active</div>
        </div>
        <div style="text-align:center;padding:8px;background:#fefce8;border:1px solid #fde68a;border-radius:8px;">
          <div style="font-size:20px;font-weight:700;color:#d97706;">{narrowed_c}</div>
          <div style="font-size:11px;font-weight:600;color:#d97706;">Narrowed</div>
        </div>
        <div style="text-align:center;padding:8px;background:#f9fafb;border:1px solid #d1d5db;border-radius:8px;">
          <div style="font-size:20px;font-weight:700;color:#6b7280;">{dropped_c}</div>
          <div style="font-size:11px;font-weight:600;color:#6b7280;">Dropped</div>
        </div>
        <div style="text-align:center;padding:8px;background:{sig_bg};border:1px solid {sig_bdr};border-radius:8px;">
          <div style="font-size:20px;font-weight:700;color:{sig_color};">{pressure_pct}%</div>
          <div style="font-size:11px;font-weight:600;color:{sig_color};">Pressure</div>
        </div>
      </div>
    </div>
    """)

    render(f"""
    <div style="{CARD}">
      {overline("Currently Viewing")}
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
        <span style="font-size:12px;font-weight:700;color:#9ca3af;">{selected.id}</span>
        {badge(selected.status)}
      </div>
      <div style="font-size:14px;font-weight:600;color:#111827;line-height:1.4;margin-bottom:12px;">
        {esc(selected.description)}
      </div>
      {slabel("Plausibility", mt="0")}
      <div style="margin-bottom:10px;">{plaus_badge(st.session_state.plausibility.get(selected.id, "Unclear"))}</div>
      {slabel("Note", mt="0")}
      <div style="font-size:13px;color:#4b5563;line-height:1.6;font-style:italic;">
        {esc(st.session_state.notes.get(selected.id, "") or "No note yet.")}
      </div>
    </div>
    """)

    render(f"""
    <div style="{CARD}">
      {overline("About This Tool")}
      <div style="font-size:13px;color:#6b7280;line-height:1.65;">
        This tool does not find the correct root cause for you.
        It makes <strong>reasoning compression visible</strong> before
        the investigation locks in — so you can ask:
        is this explanation strong, or just neat?
      </div>
    </div>
    """)

# =========================================================
# Bottom — log + nav
# =========================================================
render('<div style="height:10px;"></div>')
bot_l, bot_r = st.columns([2.5, 1], gap="large")

with bot_l:
    log_rows = "".join(
        f'<div style="display:flex;gap:10px;padding:6px 0;border-bottom:1px solid #f3f4f6;">'
        f'<span style="color:#9ca3af;flex-shrink:0;">›</span>'
        f'<span style="font-size:13px;color:#4b5563;">{esc(line)}</span></div>'
        for line in st.session_state.log[:6]
    )
    render(f'<div style="{CARD}margin-bottom:0;">{overline("Event Log")}{log_rows}</div>')

with bot_r:
    render('<div style="font-size:11px;font-weight:700;text-transform:uppercase;'
           'letter-spacing:.08em;color:#9ca3af;margin-bottom:8px;">Navigation</div>')
    nav1, nav2 = st.columns(2)
    with nav1:
        if st.button("← Back", use_container_width=True, key="nav_back"):
            if st.session_state.step > 1:
                st.session_state.step -= 1
                log_event(f"Step {st.session_state.step}: {STEPS[st.session_state.step][0]}")
                st.session_state.toast_msg = f"← Step {st.session_state.step}"
                st.rerun()
    with nav2:
        if st.button("Next →", use_container_width=True, key="nav_next"):
            if st.session_state.step < 5:
                st.session_state.step += 1
                log_event(f"Step {st.session_state.step}: {STEPS[st.session_state.step][0]}")
                st.session_state.toast_msg = f"→ Step {st.session_state.step}"
                st.rerun()
