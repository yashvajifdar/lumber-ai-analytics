"""
Lumber AI Analytics — Chat interface.
Run: streamlit run app/main.py
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
from app.engine_factory import build_engine
from app.chart_builder import build_chart

# ── cold-start: generate DB if it doesn't exist (Streamlit Cloud / fresh clone) ──
if not os.path.exists("data/lumber.db"):
    with st.spinner("Setting up data warehouse for first run..."):
        from etl.generate_data import generate
        from etl.loader import run as run_etl
        generate()
        run_etl()

st.set_page_config(
    page_title="Lumber AI Analytics",
    page_icon="🪵",
    layout="wide",
)

# ── global styles ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Suggestion cards */
div[data-testid="stButton"] > button {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
    padding: 14px 16px;
    text-align: left;
    font-size: 13px;
    font-weight: 500;
    color: #374151;
    width: 100%;
    line-height: 1.4;
    transition: border-color 0.15s ease, box-shadow 0.15s ease, transform 0.15s ease;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
div[data-testid="stButton"] > button:hover {
    border-color: #2563EB;
    box-shadow: 0 4px 14px rgba(37,99,235,0.12);
    transform: translateY(-1px);
    color: #2563EB;
}
div[data-testid="stButton"] > button:focus {
    outline: none;
    border-color: #2563EB;
    box-shadow: 0 0 0 3px rgba(37,99,235,0.1);
}

/* Hide default Streamlit header padding */
.block-container { padding-top: 2rem; }
</style>
""", unsafe_allow_html=True)

st.sidebar.title("🪵 Lumber AI Analytics")

# ── engine init (once per session) ───────────────────────────────────────────
if "engine" not in st.session_state:
    st.session_state.engine = build_engine()

engine = st.session_state.engine

if engine is None:
    st.warning(
        "**API key not configured.** "
        "Create a `.env` file with `ANTHROPIC_API_KEY=your_key_here` "
        "and restart the app."
    )
    st.stop()

if "messages" not in st.session_state:
    st.session_state.messages = []

# ── empty state: greeting + suggestion cards ──────────────────────────────────
# Each suggestion: (icon, short label shown on card, full question sent to engine)
SUGGESTIONS = [
    ("💰", "Sales this year",       "What were total sales this year?"),
    ("📈", "Margin by product",     "Which products have the highest margin?"),
    ("🏪", "Revenue by location",   "Show me revenue by location"),
    ("👷", "Top contractors",       "Which customers spend the most?"),
    ("📦", "Low inventory",         "What inventory is running low?"),
    ("🐌", "Slow-moving stock",     "Show me slow-moving stock"),
    ("🔄", "Repeat customers",      "What is our repeat customer rate?"),
    ("🗂️", "Category breakdown",    "Which category drives the most revenue?"),
]

if not st.session_state.messages:
    st.markdown("""
    <div style="text-align:center; padding: 56px 0 44px;">
        <div style="font-size:52px; margin-bottom:16px;">🪵</div>
        <h1 style="font-size:2.2rem; font-weight:700; color:#111827; margin:0 0 10px;">
            What's happening in the business?
        </h1>
        <p style="color:#6b7280; font-size:1.05rem; margin:0;">
            Ask about revenue, margins, inventory, or customers — plain English, real numbers.
        </p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)
    cols = [col1, col2, col3, col4]
    for i, (icon, label, question) in enumerate(SUGGESTIONS):
        if cols[i % 4].button(f"{icon}  {label}", key=f"sug_{i}"):
            st.session_state["prefill"] = question

# ── render conversation history ───────────────────────────────────────────────
for idx, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        safe_content = msg["content"].replace("$", r"\$") if msg["role"] == "assistant" else msg["content"]
        st.markdown(safe_content)
        if "chart" in msg:
            st.plotly_chart(msg["chart"], use_container_width=True, key=f"chart_hist_{idx}")

# ── follow-up chips (rendered every run so clicks are captured) ───────────────
# Stored in session state after each response — always present in widget tree,
# not buried inside the "if question:" block where Streamlit can't register clicks.
last_follow_ups = st.session_state.get("last_follow_ups", [])
if last_follow_ups:
    st.markdown("""
    <style>
    div[data-testid="stHorizontalBlock"] div[data-testid="stButton"] > button {
        background: #f9fafb;
        border: 1px solid #e5e7eb;
        border-radius: 999px;
        padding: 8px 16px;
        font-size: 12px;
        font-weight: 500;
        color: #6b7280;
        box-shadow: none;
    }
    div[data-testid="stHorizontalBlock"] div[data-testid="stButton"] > button:hover {
        background: #eff6ff;
        border-color: #2563EB;
        color: #2563EB;
        transform: none;
        box-shadow: none;
    }
    </style>
    <p style='color:#9ca3af; font-size:12px; margin: 16px 0 6px;'>You might also ask</p>
    """, unsafe_allow_html=True)
    fu_cols = st.columns(len(last_follow_ups))
    for i, item in enumerate(last_follow_ups):
        # Guard against stale session state that stored plain strings (old format)
        label, question = item if isinstance(item, tuple) else (item, item)
        if fu_cols[i].button(label, key=f"fu_{i}"):
            st.session_state["prefill"] = question

question = st.chat_input("Ask about your business...")

if "prefill" in st.session_state and st.session_state["prefill"]:
    question = st.session_state.pop("prefill")

# ── process question ──────────────────────────────────────────────────────────
if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Analyzing..."):
            # Pass up to 3 prior exchanges as context so short replies like
            # "Sure" or "Yes" resolve against the preceding conversation.
            prior = st.session_state.messages[:-1][-6:]
            result = engine.ask(question, history=prior or None)

        if result.error:
            st.error(f"Something went wrong: {result.error}")
            st.session_state["last_follow_ups"] = []
        else:
            safe_text = result.text.replace("$", r"\$")
            st.markdown(safe_text)

            fig = None
            if result.df is not None and result.chart_spec is not None:
                fig = build_chart(result.df, result.chart_spec)
                if fig is not None:
                    # Unique key prevents duplicate-ID error when the same
                    # question is asked more than once in a session.
                    st.plotly_chart(fig, use_container_width=True,
                                    key=f"chart_live_{len(st.session_state.messages)}")

            st.session_state["last_follow_ups"] = result.follow_ups

    # persist for history replay
    msg: dict = {"role": "assistant", "content": result.text}
    if fig is not None:
        msg["chart"] = fig
    st.session_state.messages.append(msg)
    # Rerun so follow-up buttons render in the correct position above the input.
    st.rerun()
