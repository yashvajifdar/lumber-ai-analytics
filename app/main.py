"""
Lumber AI Analytics — MVP Streamlit app.
Run: streamlit run app/main.py
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from metrics import kpis
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

# ── sidebar nav ─────────────────────────────────────────────────────────────
st.sidebar.title("🪵 Lumber AI Analytics")
page = st.sidebar.radio("Navigate", ["Dashboard", "Products", "Customers", "Inventory", "Chat"])

# ── helpers ──────────────────────────────────────────────────────────────────

def metric_card(label: str, value: str, delta: str = ""):
    st.metric(label=label, value=value, delta=delta)


def fmt_currency(v: float) -> str:
    if v >= 1_000_000:
        return f"${v/1_000_000:.2f}M"
    if v >= 1_000:
        return f"${v/1_000:.1f}K"
    return f"${v:.2f}"


# ═══════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════
if page == "Dashboard":
    st.title("Business Overview")

    period = st.selectbox("Period", ["month", "week", "day"], index=0)
    df = kpis.revenue_over_time(period)

    # KPI row
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        metric_card("Total Revenue", fmt_currency(df["revenue"].sum()))
    with col2:
        metric_card("Gross Profit", fmt_currency(df["gross_profit"].sum()))
    with col3:
        avg_margin = (df["gross_profit"].sum() / df["revenue"].sum() * 100)
        metric_card("Avg Margin", f"{avg_margin:.1f}%")
    with col4:
        metric_card("Total Orders", f"{int(df['orders'].sum()):,}")

    st.divider()

    col_l, col_r = st.columns(2)

    with col_l:
        st.subheader("Revenue Over Time")
        fig = px.bar(df, x="period", y="revenue",
                     color_discrete_sequence=["#2563EB"],
                     labels={"period": "", "revenue": "Revenue ($)"})
        fig.update_layout(margin=dict(t=10))
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.subheader("Gross Margin % Over Time")
        fig = px.line(df, x="period", y="margin_pct",
                      color_discrete_sequence=["#16A34A"],
                      labels={"period": "", "margin_pct": "Margin %"})
        fig.update_layout(margin=dict(t=10))
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Revenue by Location")
    loc_df = kpis.revenue_by_location("month")
    fig = px.line(loc_df, x="period", y="revenue", color="location",
                  labels={"period": "", "revenue": "Revenue ($)"})
    st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════
# PRODUCTS
# ═══════════════════════════════════════════════════════════════════════════
elif page == "Products":
    st.title("Product Performance")

    col_l, col_r = st.columns(2)

    with col_l:
        st.subheader("Top 10 Products by Revenue")
        df = kpis.top_products(10, "revenue")
        fig = px.bar(df, x="revenue", y="name", orientation="h",
                     color="margin_pct", color_continuous_scale="RdYlGn",
                     labels={"name": "", "revenue": "Revenue ($)", "margin_pct": "Margin %"})
        fig.update_layout(yaxis={"categoryorder": "total ascending"}, margin=dict(t=10))
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.subheader("Revenue by Category")
        cat_df = kpis.revenue_by_category()
        fig = px.pie(cat_df, names="category", values="revenue",
                     color_discrete_sequence=px.colors.qualitative.Pastel)
        fig.update_layout(margin=dict(t=10))
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Lowest Margin Products (min $5K revenue)")
    bm = kpis.bottom_margin_products(10)
    fig = px.bar(bm, x="margin_pct", y="name", orientation="h",
                 color="margin_pct", color_continuous_scale="RdYlGn",
                 labels={"name": "", "margin_pct": "Margin %"})
    fig.update_layout(yaxis={"categoryorder": "total ascending"}, margin=dict(t=10))
    st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════
# CUSTOMERS
# ═══════════════════════════════════════════════════════════════════════════
elif page == "Customers":
    st.title("Customer Intelligence")

    split = kpis.customer_type_split()
    ret   = kpis.repeat_customer_rate()

    col1, col2, col3, col4 = st.columns(4)
    contractor_row = split[split["type"] == "Contractor"].iloc[0]
    retail_row     = split[split["type"] == "Retail"].iloc[0]

    with col1:
        metric_card("Contractor Revenue", fmt_currency(contractor_row["revenue"]))
    with col2:
        metric_card("Retail Revenue", fmt_currency(retail_row["revenue"]))

    ret_c = ret[ret["type"] == "Contractor"]
    ret_r = ret[ret["type"] == "Retail"]
    with col3:
        if not ret_c.empty:
            metric_card("Contractor Repeat Rate", f"{ret_c.iloc[0]['repeat_rate_pct']}%")
    with col4:
        if not ret_r.empty:
            metric_card("Retail Repeat Rate", f"{ret_r.iloc[0]['repeat_rate_pct']}%")

    st.divider()
    col_l, col_r = st.columns(2)

    with col_l:
        st.subheader("Revenue Split: Contractor vs Retail")
        fig = px.pie(split, names="type", values="revenue",
                     color_discrete_sequence=["#2563EB", "#F59E0B"])
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.subheader("Top 10 Customers by Revenue")
        top = kpis.top_customers(10)
        fig = px.bar(top, x="revenue", y="customer_id", orientation="h",
                     color="type",
                     color_discrete_map={"Contractor": "#2563EB", "Retail": "#F59E0B"},
                     labels={"customer_id": "", "revenue": "Revenue ($)"})
        fig.update_layout(yaxis={"categoryorder": "total ascending"}, margin=dict(t=10))
        st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════
# INVENTORY
# ═══════════════════════════════════════════════════════════════════════════
elif page == "Inventory":
    st.title("Inventory Health")

    inv = kpis.inventory_health()
    below = inv[inv["below_reorder"] == 1]

    col1, col2, col3 = st.columns(3)
    with col1:
        metric_card("Total Inventory Value", fmt_currency(inv["inventory_value"].sum()))
    with col2:
        metric_card("SKUs Below Reorder Point", str(len(below)))
    with col3:
        metric_card("Total SKU-Locations", str(len(inv)))

    st.divider()

    if not below.empty:
        st.subheader("⚠️  Items Below Reorder Point")
        st.dataframe(below[["name", "category", "location",
                             "stock_level", "reorder_point", "inventory_value"]],
                     use_container_width=True, hide_index=True)

    st.subheader("Slow-Moving Inventory (last 90 days)")
    slow = kpis.slow_moving_inventory()
    fig = px.scatter(slow, x="units_sold_90d", y="total_stock",
                     size="inventory_value", color="category",
                     hover_name="name",
                     labels={"units_sold_90d": "Units Sold (90d)",
                             "total_stock": "Stock Level"})
    st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════
# CHAT
# ═══════════════════════════════════════════════════════════════════════════
elif page == "Chat":
    st.title("Ask Your Business")
    st.caption("AI-powered analytics. Ask anything about revenue, margin, products, customers, or inventory.")

    # ── engine init (once per session) ───────────────────────────────────────
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

    # ── render conversation history ───────────────────────────────────────────
    for idx, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            safe_content = msg["content"].replace("$", r"\$") if msg["role"] == "assistant" else msg["content"]
            st.markdown(safe_content)
            if "chart" in msg:
                st.plotly_chart(msg["chart"], use_container_width=True, key=f"chart_hist_{idx}")

    # ── suggestion buttons ────────────────────────────────────────────────────
    SUGGESTIONS = [
        "What were total sales this year?",
        "Which products have the highest margin?",
        "Show me revenue by location",
        "Which customers spend the most?",
        "What inventory is running low?",
        "Show me slow-moving stock",
        "What is our repeat customer rate?",
        "Which category drives the most revenue?",
    ]

    if not st.session_state.messages:
        st.markdown("**Try asking:**")
        cols = st.columns(4)
        for i, s in enumerate(SUGGESTIONS):
            if cols[i % 4].button(s, key=f"sug_{i}"):
                st.session_state["prefill"] = s

    # ── follow-up buttons (rendered every run so clicks are captured) ─────────
    # Follow-ups are stored in session state after each response so these
    # buttons are always present in the widget tree, not buried inside the
    # "if question:" block where Streamlit can't register clicks on reruns.
    last_follow_ups = st.session_state.get("last_follow_ups", [])
    if last_follow_ups:
        st.markdown("**You might also ask:**")
        fu_cols = st.columns(len(last_follow_ups))
        for i, q in enumerate(last_follow_ups):
            if fu_cols[i].button(q, key=f"fu_{i}"):
                st.session_state["prefill"] = q

    question = st.chat_input("Ask a business question...")

    if "prefill" in st.session_state and st.session_state["prefill"]:
        question = st.session_state.pop("prefill")

    # ── process question ──────────────────────────────────────────────────────
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
        # Rerun so the follow-up buttons render in the correct position
        # (they render before the chat input, but last_follow_ups is only
        # set during this block — rerun ensures a clean layout).
        st.rerun()
