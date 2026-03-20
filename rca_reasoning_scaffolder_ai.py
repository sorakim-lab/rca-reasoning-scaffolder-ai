"""
PAC-Counter RCA Reasoning Scaffold
AI expands reasoning space instead of converging toward a single cause.
Design premise: conventional AI closes explanation. This scaffold opens it.

Run: streamlit run pac_scaffold.py
Optional: set ANTHROPIC_API_KEY for AI expansion mode
"""

import html
import json
import os
import re
from typing import Dict, List

import streamlit as st

st.set_page_config(
    page_title="RCA Reasoning Scaffold",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# =========================================================
# Constants
# =========================================================
INDIVIDUAL_BLAME_TERMS = [
    "operator error", "human error", "analyst error",
    "did not follow", "failed to follow", "careless",
    "negligence", "mistake by operator", "employee mistake",
    "technician mistake", "user error", "personnel error",
]

PROCEDURAL_TERMS = [
    "procedure", "sop", "instruction", "sequence", "step",
    "cross-reference", "ambiguous", "unclear", "fragmented", "documentation"
]

CONTEXT_TERMS = [
    "environment", "temperature", "humidity", "timing", "shift",
    "room", "workflow", "handoff", "context", "condition", "monitoring"
]

TRAINING_TERMS = [
    "training", "qualified", "qualification", "understanding", "interpretation"
]

EQUIPMENT_TERMS = [
    "equipment", "instrument", "machine", "device"
]

RECORD_TERMS = [
    "record", "documentation", "entry", "log"
]

# =========================================================
# Helpers
# =========================================================
def normalize(text: str) -> str:
    return text.strip().lower()

def esc(text: str) -> str:
    return html.escape(text or "").replace("\n", "<br>")

def contains_any(text: str, terms: List[str]) -> bool:
    return any(t in text for t in terms)

def render(raw_html: str):
    st.markdown(raw_html, unsafe_allow_html=True)

def overline(t: str) -> str:
    return (
        f'<div style="font-size:11px;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:.08em;color:#9ca3af;margin-bottom:8px;">{esc(t)}</div>'
    )

def heading(t: str, size="17px", mb="10px") -> str:
    return (
        f'<div style="font-size:{size};font-weight:700;color:#111827;'
        f'line-height:1.35;margin-bottom:{mb};">{esc(t)}</div>'
    )

def body(t: str) -> str:
    return f'<div style="font-size:14px;color:#4b5563;line-height:1.7;">{esc(t)}</div>'

def slabel(t: str, mt="14px") -> str:
    return (
        f'<div style="font-size:11px;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:.07em;color:#9ca3af;margin:{mt} 0 6px;">{esc(t)}</div>'
    )

CARD = (
    "background:#ffffff;border:1px solid #e5e7eb;border-radius:12px;"
    "padding:22px 24px;margin-bottom:12px;box-shadow:0 1px 3px rgba(0,0,0,.05);"
)

# =========================================================
# Rule-based logic
# =========================================================
def detect_pac_risk(hypothesis: str) -> Dict:
    h = normalize(hypothesis)
    matches = [t for t in INDIVIDUAL_BLAME_TERMS if t in h]

    if matches:
        return {
            "level": "High",
            "color": "#dc2626",
            "bg": "#fef2f2",
            "border": "#fca5a5",
            "label": "High convergence risk",
            "message": (
                "This hypothesis is converging early on an individual actor. "
                "Procedural, contextual, and organizational contributors may be closing off "
                "before they have been examined."
            ),
            "matched": matches,
        }

    if any(w in h for w in ["operator", "analyst", "personnel", "staff", "technician"]):
        return {
            "level": "Moderate",
            "color": "#d97706",
            "bg": "#fefce8",
            "border": "#fde68a",
            "label": "Moderate convergence risk",
            "message": (
                "The hypothesis foregrounds an individual actor. "
                "This does not necessarily indicate premature closure, "
                "but systemic contributors should remain explicitly visible."
            ),
            "matched": [],
        }

    return {
        "level": "Low",
        "color": "#16a34a",
        "bg": "#f0fdf4",
        "border": "#86efac",
        "label": "Low convergence risk",
        "message": (
            "No strong individual-blame language detected. "
            "Continue checking that multiple causal pathways remain open."
        ),
        "matched": [],
    }

def generate_pathways(summary: str, hypothesis: str) -> List[Dict]:
    text = normalize(summary + " " + hypothesis)
    paths = []

    # Always keep procedural path visible
    paths.append({
        "id": "procedural",
        "title": "Procedural / documentation pathway",
        "icon": "📄",
        "desc": (
            "The event may reflect ambiguity, fragmentation, or cross-reference burden "
            "in the procedure itself. Investigate whether the task required users to integrate "
            "instructions across multiple sections or documents."
        ),
        "prompt": "What would this event look like if the procedure — not the person — was the primary contributor?",
    })

    if contains_any(text, CONTEXT_TERMS) or "deviation" in text:
        paths.append({
            "id": "contextual",
            "title": "Contextual / workflow pathway",
            "icon": "🌡️",
            "desc": (
                "The deviation may have been shaped by task conditions, environmental instability, "
                "timing pressure, handoff issues, or surrounding workflow constraints."
            ),
            "prompt": "What contextual or environmental conditions were present that could have shaped the outcome?",
        })

    if contains_any(text, TRAINING_TERMS) or "understand" in text or "misunder" in text:
        paths.append({
            "id": "interpretation",
            "title": "Interpretation / training pathway",
            "icon": "🧩",
            "desc": (
                "The issue may involve differences in procedural interpretation, incomplete conceptual "
                "understanding, or a mismatch between formal training completion and practical interpretability."
            ),
            "prompt": "Could different investigators interpret the same procedure differently — and if so, why?",
        })

    if contains_any(text, EQUIPMENT_TERMS):
        paths.append({
            "id": "equipment",
            "title": "Equipment / interface pathway",
            "icon": "⚙️",
            "desc": (
                "The event may involve equipment condition, instrument behavior, or interface design "
                "that shaped how the task was carried out."
            ),
            "prompt": "How did the equipment or interface design constrain or shape the actor's available actions?",
        })

    if contains_any(text, RECORD_TERMS):
        paths.append({
            "id": "documentation",
            "title": "Documentation / recording pathway",
            "icon": "📝",
            "desc": (
                "The apparent issue may partly reflect how the event was documented, compressed, or "
                "later reconstructed, rather than the original action alone."
            ),
            "prompt": "How might the act of documenting this event have shaped how it is now being explained?",
        })

    seen, out = set(), []
    for p in paths:
        if p["id"] not in seen:
            out.append(p)
            seen.add(p["id"])
    return out[:5]

def generate_evidence(summary: str, hypothesis: str) -> List[str]:
    text = normalize(summary + " " + hypothesis)
    ev = [
        "Review the full SOP and all cross-referenced documents relevant to this task.",
        "Identify what evidence would specifically distinguish procedural ambiguity from individual noncompliance.",
        "Check whether alternative explanatory paths were raised and then prematurely narrowed.",
    ]

    if contains_any(text, CONTEXT_TERMS):
        ev.append("Review environmental logs and operating conditions during the event window.")
    if contains_any(text, TRAINING_TERMS) or "operator" in text or "analyst" in text:
        ev.append("Examine training records alongside how the procedure is actually interpreted in practice.")
    if contains_any(text, EQUIPMENT_TERMS):
        ev.append("Check equipment condition, interface usability, alarms, and maintenance history.")
    if contains_any(text, RECORD_TERMS):
        ev.append("Compare the original event with how it was later recorded in the deviation narrative.")

    seen, out = set(), []
    for item in ev:
        if item not in seen:
            out.append(item)
            seen.add(item)
    return out[:6]

def generate_questions() -> List[str]:
    return [
        "What would this event look like if individual blame were temporarily set aside?",
        "Which causal path is currently being treated as most obvious — and why?",
        "What relevant evidence has not yet been examined before narrowing toward closure?",
        "Could documentation structure or workflow conditions have shaped the actor's action?",
        "If a different person had been in the same situation, would the same outcome have occurred?",
    ]

# =========================================================
# Anthropic API
# =========================================================
def get_anthropic_key():
    secrets_obj = getattr(st, "secrets", {})
    try:
        secret_key = secrets_obj.get("ANTHROPIC_API_KEY", None)
    except Exception:
        secret_key = None
    return os.getenv("ANTHROPIC_API_KEY") or secret_key

def extract_json_object(raw: str) -> Dict:
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise

def run_claude_expansion(summary: str, hypothesis: str) -> Dict:
    import anthropic

    client = anthropic.Anthropic(api_key=get_anthropic_key())

    prompt = f"""You are a reasoning-space scaffold for Root Cause Analysis (RCA) in regulated environments.

Your job is NOT to determine the final root cause.
Do NOT give a final compliance decision.
Do NOT collapse the explanation into one neat answer.

Your role: preserve reasoning space, identify possible premature accountability convergence (PAC),
and suggest what additional evidence should be examined before closure.

Return ONLY valid JSON with this exact shape:
{{
  "alternative_pathways": [
    {{"title": "short title", "desc": "1-2 sentence description", "question": "one reopening question"}},
    {{"title": "short title", "desc": "1-2 sentence description", "question": "one reopening question"}},
    {{"title": "short title", "desc": "1-2 sentence description", "question": "one reopening question"}}
  ],
  "pac_warning": "2-3 sentence warning about whether responsibility may be converging too early",
  "next_evidence": ["item 1", "item 2", "item 3"],
  "reopening_questions": ["question 1", "question 2", "question 3"]
}}

Case summary:
{summary}

Current hypothesis:
{hypothesis}"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )

    content_blocks = getattr(message, "content", None)
    if not content_blocks:
        raise ValueError("Claude response did not include content.")

    raw = content_blocks[0].text.strip()
    return extract_json_object(raw)

# =========================================================
# CSS
# =========================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

html, body, [data-testid="stAppViewContainer"], .stApp {
    background: #f4f5f7 !important;
    font-family: 'Inter', sans-serif !important;
}
[data-testid="stHeader"],[data-testid="stDecoration"],
[data-testid="stToolbar"],footer { display:none !important; }

.block-container { max-width:1360px !important; padding:24px 32px 40px !important; }
[data-testid="stVerticalBlock"] > div:empty { display:none !important; }

div[data-testid="stVerticalBlockBorderWrapper"],
div[data-testid="stVerticalBlockBorderWrapper"] > div {
    border:none !important; background:transparent !important;
    box-shadow:none !important; padding:0 !important;
    border-radius:0 !important; margin:0 !important;
}

div[data-testid="stButton"] > button {
    font-family:'Inter',sans-serif !important;
    font-size:14px !important; font-weight:600 !important;
    color:#374151 !important; background:#ffffff !important;
    border:1.5px solid #d1d5db !important; border-radius:9px !important;
    padding:10px 18px !important; min-height:2.7rem !important;
    box-shadow:0 1px 2px rgba(0,0,0,.05) !important;
    transition:all .12s ease !important; width:100% !important;
}
div[data-testid="stButton"] > button:hover {
    background:#f9fafb !important; border-color:#9ca3af !important; color:#111827 !important;
}

.stTextArea label {
    font-size:14px !important; font-weight:600 !important; color:#374151 !important;
}
textarea {
    font-family:'Inter',sans-serif !important; font-size:14px !important;
    color:#1f2937 !important; background:#f9fafb !important;
    border:1.5px solid #d1d5db !important; border-radius:9px !important;
    padding:14px 16px !important; line-height:1.7 !important;
}
textarea:focus { border-color:#2563eb !important; outline:none !important; }

p, li { font-size:14px !important; color:#4b5563 !important; line-height:1.7 !important; }

@keyframes fill {
    from { width: 0%; }
    to   { width: var(--fill-w); }
}
.pac-bar-inner {
    animation: fill 0.8s ease-out forwards;
}
</style>
""", unsafe_allow_html=True)

# =========================================================
# Session state
# =========================================================
defaults = {
    "summary": "",
    "hypothesis": "",
    "ai_result": None,
    "show_analysis": False,
    "toast_msg": None,
    "last_summary": "",
    "last_hypothesis": "",
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

if st.session_state.toast_msg:
    st.toast(st.session_state.toast_msg)
    st.session_state.toast_msg = None

# =========================================================
# Header
# =========================================================
render(f"""
<div style="{CARD}margin-bottom:16px;">
  <div style="display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:16px;">
    <div style="max-width:680px;">
      {overline("RCA Reasoning Scaffold · PAC-Counter Design")}
      <div style="font-size:24px;font-weight:700;color:#111827;letter-spacing:-.02em;margin-bottom:6px;">
        Reasoning Space Expander
      </div>
      <div style="font-size:15px;color:#4b5563;line-height:1.7;">
        Conventional AI closes explanation — it converges toward a single neat cause.
        This scaffold is designed to do the opposite:
        <strong>keep multiple causal paths visible</strong> and surface premature
        accountability convergence (PAC) before reasoning locks in.
      </div>
    </div>
    <div style="background:#fafafa;border:1px solid #e5e7eb;border-radius:10px;padding:14px 18px;min-width:220px;">
      <div style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:#9ca3af;margin-bottom:8px;">Design premise</div>
      <div style="font-size:13px;color:#374151;line-height:1.6;">
        AI that <em>expands</em> reasoning space,<br>
        not AI that <em>replaces</em> human judgment.<br><br>
        Based on PAC framework — premature accountability convergence in regulated environments.
      </div>
    </div>
  </div>
</div>
""")

# =========================================================
# Input section
# =========================================================
render(
    f'<div style="{CARD}margin-bottom:12px;">'
    f'{overline("Step 1 — Enter the case")}'
    f'{heading("Describe the deviation and the current working hypothesis")}'
    f'{body("Be specific about what happened. The scaffold will analyse whether reasoning is closing too quickly around an individual actor.")}'
    f'</div>'
)

col1, col2 = st.columns(2, gap="large")
with col1:
    summary_input = st.text_area(
        "Deviation summary",
        value=st.session_state.summary,
        placeholder=(
            "Example: During environmental monitoring review, a deviation was identified "
            "involving possible sampling sequence issues. Initial discussion emphasized operator behavior, "
            "but the procedure required repeated cross-checking across sections."
        ),
        height=160,
        key="input_summary",
    )

with col2:
    hypothesis_input = st.text_area(
        "Current working hypothesis",
        value=st.session_state.hypothesis,
        placeholder="Example: Operator did not follow the sampling sequence correctly.",
        height=160,
        key="input_hypothesis",
    )

# Reset stale AI result when input changes
if (
    summary_input != st.session_state.last_summary
    or hypothesis_input != st.session_state.last_hypothesis
):
    st.session_state.ai_result = None

st.session_state.summary = summary_input
st.session_state.hypothesis = hypothesis_input
st.session_state.last_summary = summary_input
st.session_state.last_hypothesis = hypothesis_input

b1, b2, b3 = st.columns([1, 1, 1.4], gap="small")
with b1:
    expand_clicked = st.button("🔍  Expand reasoning space", use_container_width=True, type="primary")
with b2:
    sample_clicked = st.button("Load sample case", use_container_width=True)
with b3:
    ai_clicked = st.button(
        "✨  Expand with AI  (set ANTHROPIC_API_KEY)",
        use_container_width=True,
        disabled=(get_anthropic_key() is None),
    )

if sample_clicked:
    st.session_state.summary = (
        "During environmental monitoring review, a deviation was identified involving possible "
        "sampling sequence issues. Initial discussion emphasized operator behavior, but the procedure "
        "required repeated cross-checking across sections, and surrounding room conditions may also "
        "have shifted during the event window."
    )
    st.session_state.hypothesis = "Operator did not follow the sampling sequence correctly."
    st.session_state.last_summary = st.session_state.summary
    st.session_state.last_hypothesis = st.session_state.hypothesis
    st.session_state.ai_result = None
    st.session_state.show_analysis = False
    st.session_state.toast_msg = "📋 Sample case loaded — click Expand to analyse"
    st.rerun()

summary = st.session_state.summary
hypothesis = st.session_state.hypothesis

if expand_clicked:
    if summary.strip() and hypothesis.strip():
        st.session_state.show_analysis = True
    else:
        st.warning("Please enter both the deviation summary and the current working hypothesis.")

if ai_clicked:
    if not summary.strip() or not hypothesis.strip():
        st.warning("Please enter both the deviation summary and the current working hypothesis.")
    else:
        st.session_state.show_analysis = True
        st.session_state.ai_result = None
        with st.spinner("Generating reasoning expansion — this may take a moment..."):
            try:
                result = run_claude_expansion(summary, hypothesis)
                st.session_state.ai_result = result
                st.session_state.toast_msg = "✨ AI expansion complete"
                st.rerun()
            except Exception as e:
                st.error(f"AI expansion failed: {e}")

# =========================================================
# Analysis output
# =========================================================
if not st.session_state.show_analysis:
    render(f"""
    <div style="{CARD}margin-top:8px;background:#fafafa;border-color:#e5e7eb;">
      {overline("How this works")}
      {heading("Enter a case above to begin")}
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px;margin-top:14px;">
        <div style="padding:14px 16px;background:#eff6ff;border:1px solid #bfdbfe;border-radius:9px;">
          <div style="font-size:13px;font-weight:700;color:#1d4ed8;margin-bottom:4px;">1. PAC detection</div>
          <div style="font-size:13px;color:#3b82f6;line-height:1.55;">
            Identifies language that converges too early on individual blame.
          </div>
        </div>
        <div style="padding:14px 16px;background:#f0fdf4;border:1px solid #86efac;border-radius:9px;">
          <div style="font-size:13px;font-weight:700;color:#16a34a;margin-bottom:4px;">2. Pathway expansion</div>
          <div style="font-size:13px;color:#15803d;line-height:1.55;">
            Surfaces alternative causal pathways before reasoning closes.
          </div>
        </div>
        <div style="padding:14px 16px;background:#fefce8;border:1px solid #fde68a;border-radius:9px;">
          <div style="font-size:13px;font-weight:700;color:#d97706;margin-bottom:4px;">3. Evidence prompts</div>
          <div style="font-size:13px;color:#b45309;line-height:1.55;">
            Suggests what to examine before committing to a final explanation.
          </div>
        </div>
      </div>
    </div>
    """)
else:
    risk = detect_pac_risk(hypothesis)
    pathways = generate_pathways(summary, hypothesis)
    evidence = generate_evidence(summary, hypothesis)
    questions = generate_questions()

    render('<div style="height:8px;"></div>')

    risk_pct = {"High": 85, "Moderate": 50, "Low": 15}[risk["level"]]

    matched_html = ""
    if risk["matched"]:
        terms = "".join(
            f'<span style="display:inline-block;padding:2px 8px;background:#fee2e2;'
            f'color:#991b1b;border-radius:4px;font-size:12px;font-weight:600;margin:2px 3px 2px 0;">'
            f'{esc(t)}</span>'
            for t in risk["matched"]
        )
        matched_html = f'<div style="margin-top:10px;">{slabel("Flagged language", mt="0")}{terms}</div>'

    render(f"""
    <div style="background:{risk['bg']};border:1px solid {risk['border']};border-radius:12px;padding:22px 24px;margin-bottom:12px;">
      <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;margin-bottom:14px;">
        <div>
          {overline("PAC Risk Assessment")}
          <div style="font-size:20px;font-weight:700;color:{risk['color']};">{esc(risk['label'])}</div>
        </div>
        <div style="font-size:13px;color:{risk['color']};font-weight:600;padding:6px 14px;background:rgba(255,255,255,.7);border-radius:7px;border:1px solid {risk['border']};">
          Convergence pressure: {risk_pct}%
        </div>
      </div>
      <div style="background:rgba(255,255,255,.5);border-radius:6px;height:10px;overflow:hidden;margin-bottom:12px;">
        <div class="pac-bar-inner" style="--fill-w:{risk_pct}%;height:100%;background:{risk['color']};border-radius:6px;"></div>
      </div>
      <div style="font-size:14px;color:#374151;line-height:1.65;">{esc(risk['message'])}</div>
      {matched_html}
    </div>
    """)

    main_l, main_r = st.columns([1.55, 1], gap="large")

    with main_l:
        hyp_display = hypothesis.strip()
        hyp_html = (
            f'<div style="font-size:16px;font-weight:600;color:#111827;line-height:1.5;font-style:italic;">"{esc(hyp_display)}"</div>'
            if hyp_display else
            '<div style="font-size:14px;color:#9ca3af;font-style:italic;">No hypothesis entered yet — analysis based on deviation summary only.</div>'
        )

        render(f"""
        <div style="{CARD}border-left:4px solid #6b7280;">
          {overline("Current working hypothesis")}
          {hyp_html}
          <div style="margin-top:10px;font-size:13px;color:#6b7280;">
            The scaffold examines whether this explanation is closing too early —
            and what pathways may be losing visibility as a result.
          </div>
        </div>
        """)

        render("""
        <div style="font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:#6b7280;margin-bottom:10px;">
          Alternative causal pathways — keep these visible
        </div>
        """)

        for i, p in enumerate(pathways):
            accent = ["#2563eb", "#16a34a", "#d97706", "#7c3aed", "#db2777"][i % 5]
            accent_bg = ["#eff6ff", "#f0fdf4", "#fefce8", "#f5f3ff", "#fdf2f8"][i % 5]
            accent_bdr = ["#bfdbfe", "#86efac", "#fde68a", "#ddd6fe", "#fbcfe8"][i % 5]

            render(f"""
            <div style="background:{accent_bg};border:1px solid {accent_bdr};border-left:4px solid {accent};border-radius:12px;padding:18px 20px;margin-bottom:8px;">
              <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
                <span style="font-size:18px;">{esc(p['icon'])}</span>
                <div style="font-size:14px;font-weight:700;color:#111827;">{esc(p['title'])}</div>
              </div>
              <div style="font-size:14px;color:#374151;line-height:1.65;margin-bottom:10px;">
                {esc(p['desc'])}
              </div>
              <div style="padding:10px 12px;background:rgba(255,255,255,.7);border-radius:7px;border:1px solid {accent_bdr};">
                <span style="font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:{accent};">Reopening question  </span>
                <span style="font-size:13px;color:#374151;font-style:italic;">
                  {esc(p['prompt'])}
                </span>
              </div>
            </div>
            """)

        render(f'<div style="height:4px;"></div>')
        render(f"""
        <div style="{CARD}">
          {overline("Questions to reopen reasoning space")}
          {heading("Before narrowing, ask:")}
        """)

        for q in questions:
            render(f"""
            <div style="display:flex;gap:10px;padding:10px 0;border-bottom:1px solid #f3f4f6;">
              <span style="color:#d97706;font-weight:700;font-size:15px;flex-shrink:0;">?</span>
              <span style="font-size:14px;color:#374151;line-height:1.6;">{esc(q)}</span>
            </div>
            """)

        render("</div>")

    with main_r:
        render(f"""
        <div style="{CARD}">
          {overline("Evidence to examine first")}
          {heading("Do not narrow until you have checked:")}
        """)

        for item in evidence:
            render(f"""
            <div style="display:flex;gap:10px;padding:9px 0;border-bottom:1px solid #f3f4f6;">
              <span style="color:#2563eb;font-weight:700;flex-shrink:0;">→</span>
              <span style="font-size:14px;color:#374151;line-height:1.6;">{esc(item)}</span>
            </div>
            """)

        render("</div>")

        render(f"""
        <div style="{CARD}">
          {overline("Reasoning space snapshot")}
          {heading("What should remain open")}
          <div style="margin-top:4px;">
        """)

        for p in pathways:
            render(f"""
            <div style="display:flex;align-items:center;gap:8px;padding:8px 10px;background:#f9fafb;border-radius:7px;margin-bottom:5px;">
              <span style="font-size:14px;">{esc(p['icon'])}</span>
              <span style="font-size:13px;color:#374151;font-weight:500;">{esc(p['title'])}</span>
              <span style="margin-left:auto;font-size:11px;font-weight:700;padding:2px 7px;background:#f0fdf4;color:#16a34a;border:1px solid #86efac;border-radius:4px;">OPEN</span>
            </div>
            """)

        render("</div></div>")

        render(f"""
        <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:18px 20px;">
          {overline("Design note")}
          <div style="font-size:13px;color:#64748b;line-height:1.65;">
            This scaffold does not determine the root cause.
            It is intentionally designed to <strong>resist premature closure</strong> —
            the opposite of how most AI systems handle explanation tasks.<br><br>
            Based on the PAC framework: AI systems that generate single-cause explanations
            accelerate accountability convergence. This prototype explores the counter-design.
          </div>
        </div>
        """)

    if st.session_state.ai_result:
        ai = st.session_state.ai_result
        render('<div style="height:8px;"></div>')
        render(f"""
        <div style="background:#faf5ff;border:1px solid #ddd6fe;border-radius:12px;padding:22px 24px;margin-bottom:12px;">
          {overline("AI Expansion · Claude — reasoning space mode")}
          {heading("AI-generated alternative pathways", size="18px")}
          <div style="font-size:14px;color:#7c3aed;margin-bottom:16px;">
            This AI is configured to expand reasoning, not conclude it.
            It will not give you the answer — it will give you more questions.
          </div>
        </div>
        """)

        ai_l, ai_r = st.columns([1.55, 1], gap="large")

        with ai_l:
            if ai.get("pac_warning"):
                render(f"""
                <div style="background:#fef2f2;border:1px solid #fca5a5;border-left:4px solid #dc2626;border-radius:12px;padding:18px 20px;margin-bottom:12px;">
                  {overline("AI PAC warning")}
                  <div style="font-size:14px;color:#374151;line-height:1.65;">{esc(ai['pac_warning'])}</div>
                </div>
                """)

            for i, path in enumerate(ai.get("alternative_pathways", [])):
                colors = ["#7c3aed", "#0891b2", "#059669"]
                bgs = ["#f5f3ff", "#ecfeff", "#ecfdf5"]
                bdrs = ["#ddd6fe", "#a5f3fc", "#a7f3d0"]
                c = colors[i % 3]
                bg = bgs[i % 3]
                bdr = bdrs[i % 3]

                title = esc(path.get("title", ""))
                desc = esc(path.get("desc", ""))
                question = esc(path.get("question", ""))

                question_html = (
                    f'<div style="padding:10px 12px;background:rgba(255,255,255,.7);border-radius:7px;border:1px solid {bdr};font-size:13px;color:#374151;font-style:italic;">{question}</div>'
                    if question else ""
                )

                render(f"""
                <div style="background:{bg};border:1px solid {bdr};border-left:4px solid {c};border-radius:12px;padding:18px 20px;margin-bottom:8px;">
                  <div style="font-size:14px;font-weight:700;color:#111827;margin-bottom:6px;">
                    ✨ {title}
                  </div>
                  <div style="font-size:14px;color:#374151;line-height:1.65;margin-bottom:10px;">
                    {desc}
                  </div>
                  {question_html}
                </div>
                """)

        with ai_r:
            if ai.get("next_evidence"):
                render(f"""
                <div style="{CARD}">
                  {overline("AI — evidence to examine")}
                """)
                for item in ai["next_evidence"]:
                    render(f"""
                    <div style="display:flex;gap:10px;padding:9px 0;border-bottom:1px solid #f3f4f6;">
                      <span style="color:#7c3aed;font-weight:700;flex-shrink:0;">→</span>
                      <span style="font-size:14px;color:#374151;line-height:1.6;">{esc(item)}</span>
                    </div>
                    """)
                render("</div>")

            if ai.get("reopening_questions"):
                render(f"""
                <div style="{CARD}">
                  {overline("AI — reopening questions")}
                """)
                for q in ai["reopening_questions"]:
                    render(f"""
                    <div style="display:flex;gap:10px;padding:9px 0;border-bottom:1px solid #f3f4f6;">
                      <span style="color:#d97706;font-weight:700;flex-shrink:0;">?</span>
                      <span style="font-size:14px;color:#374151;line-height:1.6;">{esc(q)}</span>
                    </div>
                    """)
                render("</div>")
