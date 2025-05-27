# ===== streamlit_ui.py =====
"""
Streamlit UI for Marketing Content Generator

Supports both local and Docker Compose environments:
- Local Dev: API at http://localhost:5000/generate
- Docker:    API at http://api:5000/generate
"""
import os
import socket
import difflib
import json
import streamlit as st
import requests
from typing import Dict, Any

# ─── Page & State Configuration ───────────────────────────────────────────────
st.set_page_config(page_title="Marketing Content Generator", layout="wide")

# initialize session state
if "history" not in st.session_state:
    st.session_state.history = []
if "last_payload" not in st.session_state:
    st.session_state.last_payload = None
if "feedback_history" not in st.session_state:
    st.session_state.feedback_history = []
if "content_diffs" not in st.session_state:
    st.session_state.content_diffs = []
if "translate_language" not in st.session_state:
    st.session_state.translate_language = "English"

# ─── Determine Default API URL ─────────────────────────────────────────────────
def default_api_url() -> str:
    try:
        socket.gethostbyname("api")
        return "http://api:5000/generate"
    except socket.gaierror:
        return os.getenv("API_URL", "http://localhost:5000/generate")

# ─── Campaign Types ───────────────────────────────────────────────────────────
CAMPAIGN_TYPES = [
    "social_media", "email_marketing", "ppc_ads", "content_marketing",
    "customer_retention", "seasonal_campaigns", "product_launch", "crisis_management"
]

# ─── Sidebar Inputs ──────────────────────────────────────────────────────────
st.sidebar.header("Configuration")
api_url = st.sidebar.text_input(
    "API URL", default_api_url(), help="Endpoint for the /generate POST API"
)

campaign_type = st.sidebar.selectbox("Campaign Type", CAMPAIGN_TYPES)

tone = st.sidebar.selectbox(
    "Tone", ["casual", "professional", "urgent", "friendly", "serious and bright"]
)

platform = ""
if campaign_type == "social_media":
    platform = st.sidebar.selectbox("Platform", ["LinkedIn", "Twitter", "Facebook"])

# Topic extended text area
topic = st.sidebar.text_area(
    "Topic", height=100, help="Enter the campaign topic or details (required)"
)
audience = st.sidebar.text_input("Audience (optional)")
system_prompt = st.sidebar.text_area(
    "Additional System Prompt", help="Extra instructions appended to the default system prompt"
)

generate = st.sidebar.button("Generate", disabled=not topic.strip())
st.title("Marketing Content Generator")

# ─── API Caller ────────────────────────────────────────────────────────────────
def call_api(payload: Dict[str, Any]) -> str:
    try:
        response = requests.post(api_url, json=payload, timeout=10)
        response.raise_for_status()
        return response.json().get("generated_content", "")
    except Exception as e:
        st.error(f"API error: {e}")
        return ""

# ─── Generate Handler ─────────────────────────────────────────────────────────
if generate:
    st.session_state.feedback_history = []
    st.session_state.content_diffs = []
    payload = {
        "campaign_type": campaign_type,
        "tone": tone,
        "platform": platform,
        "topic": topic,
        "audience": audience,
        "language": st.session_state.translate_language,
        "system_prompt": system_prompt or None
    }
    result = call_api(payload)
    if result:
        st.session_state.last_payload = payload
        st.session_state.history.insert(0, result)
        if len(st.session_state.history) > 5:
            st.session_state.history = st.session_state.history[:5]

# ─── Translate Callback ───────────────────────────────────────────────────────
def translate_callback():
    last = st.session_state.last_payload
    if not last:
        return
    payload = last.copy()
    if st.session_state.feedback_history:
        payload["feedback"] = " ".join(st.session_state.feedback_history)
    payload["language"] = st.session_state.translate_language
    st.session_state.last_payload = payload
    translated = call_api(payload)
    if translated:
        st.session_state.history[0] = translated

# ─── Improvement Callback ─────────────────────────────────────────────────────
def improve_callback(feedback_text: str):
    last = st.session_state.last_payload
    if not last or not feedback_text.strip():
        return
    st.session_state.feedback_history.insert(0, feedback_text)
    payload = last.copy()
    payload["feedback"] = " ".join(st.session_state.feedback_history)
    payload["language"] = st.session_state.translate_language
    st.session_state.last_payload = payload
    revised = call_api(payload)
    if revised:
        old = st.session_state.history[0].splitlines(keepends=True)
        new = revised.splitlines(keepends=True)
        diff = "".join(difflib.unified_diff(old, new, lineterm=""))
        st.session_state.content_diffs.insert(0, diff)
        st.session_state.history.insert(0, revised)
        if len(st.session_state.history) > 5:
            st.session_state.history = st.session_state.history[:5]
        st.session_state.feedback_input = ""

# ─── Display Generated & Feedback UI ──────────────────────────────────────────
if st.session_state.history:
    st.subheader("Generated Content")

    st.selectbox(
        "Language",
        ["English", "Spanish", "French", "German"],
        key="translate_language",
        on_change=translate_callback
    )

    latest = st.session_state.history[0]
    st.text_area("", latest, height=200, key="gen_content")
    st.download_button("Download Text", latest, file_name="generated_content.txt")

    feedback = st.text_area("Feedback (what to improve)", key="feedback_input")
    st.button(
        "Improve",
        disabled=not feedback.strip() or not st.session_state.last_payload,
        on_click=improve_callback,
        args=(feedback,)
    )

    if st.session_state.feedback_history:
        st.subheader("Feedback History")
        for idx, fb in enumerate(st.session_state.feedback_history, start=1):
            st.markdown(f"**#{idx}:** {fb}")

    # ─── Side-by-Side Before vs After ─────────────────────
    if st.session_state.content_diffs:
        before = st.session_state.history[1]
        after = st.session_state.history[0]

        st.subheader("Latest Improvement")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Before**")
            st.text_area("", before, height=200)
        with col2:
            st.markdown("**After**")
            st.text_area("", after, height=200)

    if len(st.session_state.history) > 1:
        st.subheader("History")
        for idx, past in enumerate(st.session_state.history[1:], start=2):
            st.markdown(f"**#{idx}:** {past}")