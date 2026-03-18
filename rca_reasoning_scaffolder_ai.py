import json
import os
from typing import Dict, List, Tuple

import streamlit as st

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


st.set_page_config(
    page_title="RCA Reasoning Scaffolder",
    page_icon="🧠",
    layout="wide"
)

# -----------------------------
# Constants
# -----------------------------
INDIVIDUAL_BLAME_TERMS = [
    "operator error",
    "human error",
    "analyst error",
    "did not follow",
    "failed to follow",
    "careless",
    "negligence",
    "mistake by operator",
    "employee mistake",
    "technician mistake",
]

PROCEDURAL_TERMS = [
    "procedure", "sop", "instruction", "sequence", "step", "cross-reference",
    "ambiguous", "unclear", "fragmented", "documentation"
]

CONTEXT_TERMS = [
    "environment", "temperature", "humidity", "timing", "shift", "room", "equipment",
    "workflow", "handoff", "context", "condition", "monitoring"
]

TRAINING_TERMS = [
    "training", "qualified", "qualification", "understanding", "interpretation"
]

DEFAULT_MODEL = "gpt-5.4-mini"


# -----------------------------
# Helper logic
# -----------------------------
def normalize_text(text: str) -> str:
    return text.strip().lower()


def detect_compression_risk(hypothesis: str) -> Dict[str, str]:
    h = normalize_text(hypothesis)
    matches = [term for term in INDIVIDUAL_BLAME_TERMS if term in h]

    if matches:
        return {
            "level": "High",
            "message": (
                "Current reasoning appears to converge early on an individual actor. "
                "Before closure, examine whether procedural, contextual, or organizational contributors remain underexplored."
            )
        }

    if any(word in h for word in ["operator", "analyst", "personnel", "staff"]):
        return {
            "level": "Moderate",
            "message": (
                "The current hypothesis foregrounds an individual actor. "
                "This does not necessarily mean premature accountability convergence is occurring, "
                "but alternative systemic contributors should remain visible."
            )
        }

    return {
        "level": "Low",
        "message": (
            "The current hypothesis does not appear strongly compressed around individual blame. "
            "Continue checking whether multiple causal pathways remain open."
        )
    }


def generate_alternative_paths(summary: str, hypothesis: str) -> List[Dict[str, str]]:
    text = normalize_text(summary + " " + hypothesis)
    paths: List[Dict[str, str]] = []

    paths.append({
        "title": "Procedural / documentation pathway",
        "desc": (
            "The event may reflect ambiguity, fragmentation, or cross-reference burden in the procedure itself. "
            "Investigate whether the task required users to integrate instructions across multiple sections or documents."
        )
    })

    if any(term in text for term in CONTEXT_TERMS) or "deviation" in text:
        paths.append({
            "title": "Contextual / workflow pathway",
            "desc": (
                "The deviation may have been shaped by task conditions, environmental instability, timing pressure, "
                "handoff issues, or surrounding workflow constraints rather than by a single isolated action."
            )
        })

    if any(term in text for term in TRAINING_TERMS) or "understand" in text or "misunder" in text:
        paths.append({
            "title": "Interpretation / training pathway",
            "desc": (
                "The issue may involve differences in procedural interpretation, incomplete conceptual understanding, "
                "or a mismatch between formal training completion and practical interpretability."
            )
        })

    if "equipment" in text or "instrument" in text or "machine" in text or "device" in text:
        paths.append({
            "title": "Equipment / interface pathway",
            "desc": (
                "The event may also involve equipment condition, instrument behavior, or interface design that shaped how the task was carried out."
            )
        })

    if "record" in text or "documentation" in text or "entry" in text or "log" in text:
        paths.append({
            "title": "Documentation / recording pathway",
            "desc": (
                "The apparent issue may partly reflect how the event was documented, compressed, or later reconstructed, "
                "rather than the original action alone."
            )
        })

    seen = set()
    deduped = []
    for path in paths:
        if path["title"] not in seen:
            deduped.append(path)
            seen.add(path["title"])

    return deduped[:5]


def generate_next_evidence(summary: str, hypothesis: str) -> List[str]:
    text = normalize_text(summary + " " + hypothesis)
    evidence = [
        "Review adjacent SOP sections and cross-referenced documents.",
        "Check whether alternative pathways were considered and then prematurely narrowed.",
        "Examine what evidence would distinguish procedural ambiguity from individual noncompliance."
    ]

    if "environment" in text or "monitoring" in text or "room" in text:
        evidence.append("Review environmental logs and surrounding operating conditions near the event time.")

    if "training" in text or "understand" in text or "operator" in text or "analyst" in text:
        evidence.append("Examine training records together with how the procedure is actually interpreted in practice.")

    if "equipment" in text or "instrument" in text:
        evidence.append("Check equipment condition, interface usability, alarms, and maintenance history.")

    if "entry" in text or "record" in text or "documentation" in text:
        evidence.append("Compare the original event with how it was later recorded in the deviation narrative.")

    deduped = []
    seen = set()
    for item in evidence:
        if item not in seen:
            deduped.append(item)
            seen.add(item)

    return deduped[:6]


def generate_unexplored_questions(summary: str, hypothesis: str) -> List[str]:
    return [
        "What would this event look like if the procedure itself contributed to the deviation?",
        "Which causal path is currently being treated as most obvious, and why?",
        "What relevant evidence has not yet been examined before narrowing toward closure?",
        "Could documentation structure or workflow conditions have shaped the actor’s action?",
        "What explanation would remain plausible if individual blame were temporarily set aside?"
    ]


def build_reasoning_map(summary: str, hypothesis: str) -> Tuple[str, List[Dict[str, str]], List[str], List[str]]:
    current = hypothesis.strip() if hypothesis.strip() else "No current hypothesis entered."

    active_paths = generate_alternative_paths(summary, hypothesis)
    narrowed: List[str] = []
    risk = detect_compression_risk(hypothesis)

    if risk["level"] in ["High", "Moderate"]:
        narrowed.append("Individual-actor explanation may be narrowing faster than surrounding system factors.")

    if "operator error" in hypothesis.lower() or "human error" in hypothesis.lower():
        narrowed.append("Responsibility may be converging before procedural ambiguity is ruled out.")

    unexplored = [
        "Procedural structure",
        "Cross-document dependency",
        "Workflow context",
        "Interpretive burden",
        "Evidence needed before closure"
    ]

    return current, active_paths, narrowed, unexplored


# -----------------------------
# LLM helper
# -----------------------------
def get_openai_client():
    api_key = os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY", None)
    if not api_key:
        return None
    if OpenAI is None:
        return None
    return OpenAI(api_key=api_key)


def build_llm_prompt(summary: str, hypothesis: str) -> str:
    return f"""
You are assisting with an RCA reasoning scaffold in a regulated environment.

Your job is NOT to determine the final root cause.
Do NOT give a final compliance decision.
Do NOT collapse the explanation into one neat answer.
Your role is to preserve reasoning space, identify possible premature accountability convergence, and suggest what additional evidence should be examined before closure.

Return strict JSON with the following shape:
{{
  "alternative_pathways": [
    {{"title": "short title", "desc": "1-2 sentence description"}},
    {{"title": "short title", "desc": "1-2 sentence description"}},
    {{"title": "short title", "desc": "1-2 sentence description"}}
  ],
  "pac_warning": "2-3 sentence warning about whether responsibility may be converging too early",
  "next_evidence": [
    "evidence item 1",
    "evidence item 2",
    "evidence item 3"
  ],
  "reopening_questions": [
    "question 1",
    "question 2",
    "question 3"
  ]
}}

Case summary:
{summary}

Current hypothesis:
{hypothesis}
""".strip()


def parse_llm_json(raw_text: str) -> Dict[str, object]:
    text = raw_text.strip()

    if text.startswith("```"):
        parts = text.split("```")
        cleaned = []
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if part.lower() == "json":
                continue
            if part.lower().startswith("json\n"):
                part = part[5:]
            cleaned.append(part)
        if cleaned:
            text = cleaned[0].strip()

    return json.loads(text)


def run_llm_expansion(summary: str, hypothesis: str, model: str = DEFAULT_MODEL) -> Dict[str, object]:
    client = get_openai_client()
    if client is None:
        raise RuntimeError(
            "OpenAI client is not available. Set OPENAI_API_KEY and install the openai package."
        )

    prompt = build_llm_prompt(summary, hypothesis)

    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "You are a reasoning-space scaffold for RCA. "
                            "You expand possibilities and slow premature accountability convergence."
                        )
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt}
                ],
            },
        ],
    )

    raw_text = response.output_text
    parsed = parse_llm_json(raw_text)
    return parsed


# -----------------------------
# UI
# -----------------------------
st.title("🧠 RCA Reasoning Scaffolder")
st.caption(
    "A prototype for keeping reasoning space open during deviation investigations. "
    "This tool does not determine the final cause. It is designed to slow premature accountability convergence."
)

with st.sidebar:
    st.subheader("Prototype framing")
    st.write(
        "Conventional RCA tools often compress explanation toward a single neat cause. "
        "This scaffold explores the opposite design direction: support logic that expands reasoning space instead of closing it too early."
    )
    st.info("Design principle: not decision replacement, but reasoning support.")

    st.subheader("Experimental LLM mode")
    st.write(
        "The LLM button is optional. The main scaffold remains rule-based and stable. "
        "The experimental mode generates richer alternative pathways and evidence prompts."
    )

st.markdown("---")

if "deviation_summary" not in st.session_state:
    st.session_state.deviation_summary = ""
if "current_hypothesis" not in st.session_state:
    st.session_state.current_hypothesis = ""

col1, col2 = st.columns([1.25, 1])

with col1:
    st.session_state.deviation_summary = st.text_area(
        "Deviation summary",
        value=st.session_state.deviation_summary,
        placeholder=(
            "Example: During environmental monitoring review, sampling sequence may not have been followed correctly. "
            "The initial discussion quickly focused on operator error."
        ),
        height=180
    )

with col2:
    st.session_state.current_hypothesis = st.text_area(
        "Investigator's current hypothesis",
        value=st.session_state.current_hypothesis,
        placeholder="Example: Operator did not follow the sampling sequence correctly.",
        height=180
    )

button_col1, button_col2, button_col3 = st.columns([1, 1, 1.3])

with button_col1:
    expand_clicked = st.button("Expand reasoning space", use_container_width=True)

with button_col2:
    load_sample_clicked = st.button("Load sample case", use_container_width=True)

with button_col3:
    llm_clicked = st.button("Expand with LLM (experimental)", use_container_width=True)

if load_sample_clicked:
    st.session_state.deviation_summary = (
        "During environmental monitoring review, a deviation was identified involving possible sampling sequence issues. "
        "Initial discussion emphasized operator behavior, but the procedure required repeated cross-checking across sections, "
        "and surrounding room conditions may also have shifted during the event window."
    )
    st.session_state.current_hypothesis = "Operator did not follow the sampling sequence correctly."
    st.rerun()

deviation_summary = st.session_state.deviation_summary
current_hypothesis = st.session_state.current_hypothesis

if not deviation_summary and not current_hypothesis:
    st.markdown("### What this prototype does")
    st.write("Enter a deviation summary and a current hypothesis. The scaffold will:")
    st.markdown(
        """
- surface alternative contributing pathways
- warn when reasoning seems to close too quickly around individual blame
- suggest next evidence to examine
- preserve a visible map of active and narrowed reasoning paths
- optionally generate richer exploratory prompts with an LLM
        """
    )

show_base = expand_clicked or llm_clicked or (deviation_summary and current_hypothesis)

if show_base:
    st.markdown("---")

    risk = detect_compression_risk(current_hypothesis)
    alt_paths = generate_alternative_paths(deviation_summary, current_hypothesis)
    next_evidence = generate_next_evidence(deviation_summary, current_hypothesis)
    questions = generate_unexplored_questions(deviation_summary, current_hypothesis)
    current, active_paths, narrowed, unexplored = build_reasoning_map(deviation_summary, current_hypothesis)

    risk_col, note_col = st.columns([0.9, 2.1])

    with risk_col:
        if risk["level"] == "High":
            st.error(f"PAC risk: {risk['level']}")
        elif risk["level"] == "Moderate":
            st.warning(f"PAC risk: {risk['level']}")
        else:
            st.success(f"PAC risk: {risk['level']}")

    with note_col:
        st.markdown("### Accountability compression warning")
        st.write(risk["message"])

    st.markdown("### Alternative contributing pathways")
    for i, path in enumerate(alt_paths, start=1):
        with st.container(border=True):
            st.markdown(f"#### {i}. {path['title']}")
            st.write(path["desc"])

    lower_left, lower_right = st.columns(2)

    with lower_left:
        st.markdown("### What may be prematurely closed?")
        if narrowed:
            for item in narrowed:
                st.write(f"- {item}")
        else:
            st.write("- No strong narrowing signal detected yet.")

        st.markdown("### Questions to reopen reasoning space")
        for q in questions:
            st.write(f"- {q}")

    with lower_right:
        st.markdown("### Next evidence to examine")
        for item in next_evidence:
            st.write(f"- {item}")

        st.markdown("### Design note")
        st.caption(
            "This scaffold does not select the final root cause. "
            "It is intentionally designed to preserve multiple explanations before closure."
        )

    st.markdown("---")
    st.markdown("### Reasoning space snapshot")

    snap_col1, snap_col2, snap_col3 = st.columns(3)

    with snap_col1:
        with st.container(border=True):
            st.markdown("#### Current hypothesis")
            st.write(current)

    with snap_col2:
        with st.container(border=True):
            st.markdown("#### Active pathways")
            for path in active_paths:
                st.write(f"- {path['title']}")

    with snap_col3:
        with st.container(border=True):
            st.markdown("#### Still unexplored")
            for item in unexplored:
                st.write(f"- {item}")

    st.markdown("---")
    st.markdown("### Why this matters")
    st.write(
        "In many RCA workflows, explanation pressure pushes investigators toward a single neat cause. "
        "This prototype explores the opposite direction: a support layer that keeps causal space open long enough "
        "to reduce premature accountability convergence."
    )

if llm_clicked:
    st.markdown("---")
    st.markdown("### ✨ Experimental LLM expansion")

    if not deviation_summary.strip() or not current_hypothesis.strip():
        st.warning("Enter both a deviation summary and a current hypothesis first.")
    else:
        with st.spinner("Generating exploratory reasoning support..."):
            try:
                llm_result = run_llm_expansion(
                    summary=deviation_summary,
                    hypothesis=current_hypothesis,
                    model=DEFAULT_MODEL
                )

                llm_alt = llm_result.get("alternative_pathways", [])
                llm_warning = llm_result.get("pac_warning", "")
                llm_evidence = llm_result.get("next_evidence", [])
                llm_questions = llm_result.get("reopening_questions", [])

                st.caption(
                    "Experimental mode uses an LLM to generate richer scaffolding. "
                    "This is not a final RCA answer and should not be used as closure."
                )

                if llm_warning:
                    st.markdown("#### LLM PAC warning")
                    st.info(llm_warning)

                if llm_alt:
                    st.markdown("#### LLM-generated alternative pathways")
                    for i, path in enumerate(llm_alt, start=1):
                        with st.container(border=True):
                            st.markdown(f"##### {i}. {path.get('title', 'Untitled pathway')}")
                            st.write(path.get("desc", ""))

                llm_col1, llm_col2 = st.columns(2)

                with llm_col1:
                    st.markdown("#### LLM evidence prompts")
                    if llm_evidence:
                        for item in llm_evidence:
                            st.write(f"- {item}")
                    else:
                        st.write("- No additional evidence prompts returned.")

                with llm_col2:
                    st.markdown("#### LLM reopening questions")
                    if llm_questions:
                        for item in llm_questions:
                            st.write(f"- {item}")
                    else:
                        st.write("- No additional reopening questions returned.")

            except Exception as e:
                st.error("LLM expansion failed.")
                st.code(str(e))
                st.caption(
                    "Check that OPENAI_API_KEY is set and that the openai package is installed."
                )
