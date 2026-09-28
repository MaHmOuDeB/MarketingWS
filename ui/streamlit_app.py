"""Streamlit UI for the Marketing Content Generator.

Talks to the API at API_URL (default http://localhost:8000). If APP_API_KEY is set, it is sent as
the X-API-Key header, so the key never reaches the browser.
"""

from __future__ import annotations

import difflib
import html
import os
from typing import Any, Dict, Optional

import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")
HEADERS = {"X-API-Key": os.environ["APP_API_KEY"]} if os.getenv("APP_API_KEY") else {}

st.set_page_config(page_title="Marketing Content Generator", page_icon="✍️", layout="wide")


# ─── API ──────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_options() -> Dict[str, Any]:
    r = requests.get(f"{API_URL}/options", timeout=10)
    r.raise_for_status()
    return r.json()


def call(path: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        r = requests.post(f"{API_URL}{path}", json=payload, headers=HEADERS, timeout=90)
    except requests.RequestException:
        st.error(f"Can't reach the API at {API_URL}. Is it running?")
        return None
    if r.ok:
        return r.json()
    detail = r.json().get("detail") if r.headers.get("content-type", "").startswith("application/json") else r.text
    if isinstance(detail, list):  # pydantic validation errors
        detail = "; ".join(f"{'.'.join(map(str, d.get('loc', [])[1:]))}: {d.get('msg')}" for d in detail)
    st.error(f"{r.status_code}: {detail}")
    return None


def diff_html(before: str, after: str) -> str:
    """Word-level diff: removed words struck through in red, added words in green."""
    a, b = before.split(), after.split()
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b).get_opcodes():
        if op in ("replace", "delete"):
            out.append(f"<del style='color:#b42318'>{html.escape(' '.join(a[i1:i2]))}</del>")
        if op in ("replace", "insert"):
            out.append(
                f"<ins style='color:#067647;text-decoration:none;font-weight:600'>"
                f"{html.escape(' '.join(b[j1:j2]))}</ins>"
            )
        if op == "equal":
            out.append(html.escape(" ".join(a[i1:i2])))
    return " ".join(out)


# ─── state ────────────────────────────────────────────────────────────────────
ss = st.session_state
ss.setdefault("versions", [])  # list of {"text", "label"}; last = current
ss.setdefault("brief", None)
ss.setdefault("backend", "")

try:
    opts = load_options()
except requests.RequestException:
    st.error(f"Can't reach the API at {API_URL}. Start it first (see the README).")
    st.stop()

campaigns = opts["campaigns"]

# ─── sidebar: the brief ───────────────────────────────────────────────────────
with st.sidebar:
    st.header("Brief")
    ctype = st.selectbox("Campaign type", list(campaigns), format_func=lambda k: campaigns[k]["label"])
    platforms = campaigns[ctype]["platforms"]
    platform = st.selectbox("Platform", platforms) if platforms else None
    tone = st.selectbox("Tone", opts["tones"])
    language = st.selectbox("Language", opts["languages"])
    topic = st.text_area("Topic", height=110, placeholder="What is the campaign about? Offer, product, key facts…")
    audience = st.text_input("Audience (optional)", placeholder="e.g. university students in Berlin")
    extra = st.text_area(
        "Extra instructions (optional)", height=80, placeholder="e.g. mention the 14-day free trial; no emojis"
    )
    go = st.button("Generate", type="primary", use_container_width=True, disabled=len(topic.strip()) < 3)

st.title("Marketing Content Generator")
st.caption("Generate a first draft, refine it with feedback, translate it — then download.")

brief = {
    "campaign_type": ctype,
    "tone": tone,
    "topic": topic,
    "audience": audience or None,
    "platform": platform,
    "language": language,
    "extra_instructions": extra or None,
}

if go:
    res = call("/generate", brief)
    if res:
        ss.brief, ss.backend = brief, res["backend"]
        ss.versions = [{"text": res["content"], "label": "First draft"}]

if not ss.versions:
    st.info("Fill in the brief on the left and press **Generate**.")
    st.stop()

current = ss.versions[-1]["text"]
if ss.backend == "demo":
    st.warning(
        "Demo mode: no OpenAI key is configured, so this copy is a placeholder. "
        "Set OPENAI_API_KEY to generate real copy."
    )

left, right = st.columns([3, 2], gap="large")
with left:
    st.subheader(ss.versions[-1]["label"])
    with st.container(border=True):
        # readable copy (a disabled text area renders greyed out); line breaks kept
        st.markdown(html.escape(current).replace("\n", "  \n"))
    st.caption(f"{len(current)} characters" + (f" · via {ss.backend}" if ss.backend else ""))
    st.download_button("Download .txt", current, file_name="marketing_copy.txt", use_container_width=True)

with right:
    st.subheader("Refine")
    with st.form("refine", clear_on_submit=True, border=False):
        feedback = st.text_area(
            "What should change?", height=100, placeholder="e.g. shorter, warmer, mention the free trial"
        )
        improve = st.form_submit_button("Improve draft", use_container_width=True)
    if improve and len(feedback.strip()) >= 2:
        res = call("/refine", {**ss.brief, "draft": current, "feedback": feedback})
        if res:
            ss.versions.append({"text": res["content"], "label": f"Revision {len(ss.versions)}", "feedback": feedback})
            st.rerun()
    elif improve:
        st.warning("Write what should change first.")

    st.subheader("Translate")
    target = st.selectbox("Into", [lang for lang in opts["languages"]], key="translate_to")
    if st.button("Translate current copy", use_container_width=True):
        res = call("/translate", {"text": current, "language": target, "platform": ss.brief.get("platform")})
        if res:
            ss.versions.append({"text": res["content"], "label": f"Translation ({target})"})
            st.rerun()

if len(ss.versions) > 1:
    if ss.versions[-1].get("feedback"):  # a word diff only makes sense for revisions
        st.subheader("What changed")
        st.caption(f"Feedback: {ss.versions[-1]['feedback']}")
        prev = ss.versions[-2]["text"]
        st.markdown(f"<div style='line-height:1.7'>{diff_html(prev, current)}</div>", unsafe_allow_html=True)
    with st.expander(f"All versions ({len(ss.versions)})"):
        for v in reversed(ss.versions):
            st.markdown(f"**{v['label']}**")
            st.text(v["text"])
