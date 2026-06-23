from __future__ import annotations

import html
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from assistant.agent import DealerAssistant


st.set_page_config(page_title="VIKMO Dealer Assistant", page_icon="V", layout="wide")

st.markdown(
    """
    <style>
    :root {
        --bg: #f3f6f8;
        --panel: #ffffff;
        --ink: #17212b;
        --muted: #596776;
        --line: #d7e0e8;
        --accent: #0f766e;
        --accent-soft: #e6f5f2;
        --warn: #b45309;
        --warn-soft: #fff4df;
        --danger: #b42318;
        --danger-soft: #fff0ee;
    }

    .stApp {
        background: var(--bg);
        color: var(--ink);
    }

    .block-container {
        max-width: 1180px;
        padding: 1.15rem 1.25rem 6rem;
    }

    [data-testid="stSidebar"] {
        background: var(--panel);
        border-right: 1px solid var(--line);
    }

    [data-testid="stSidebar"] * {
        color: var(--ink) !important;
    }

    .vikmo-logo {
        display: flex;
        align-items: center;
        gap: .65rem;
        margin: .25rem 0 1.25rem;
    }

    .logo-mark {
        width: 38px;
        height: 38px;
        border-radius: 8px;
        display: grid;
        place-items: center;
        background: #111827;
        color: #ffffff;
        font-weight: 800;
        letter-spacing: 0;
    }

    .logo-copy strong {
        display: block;
        font-size: 1.05rem;
        line-height: 1.1;
        color: var(--ink);
    }

    .logo-copy span {
        display: block;
        font-size: .8rem;
        color: var(--muted);
        margin-top: .1rem;
    }

    .sidebar-label {
        color: var(--muted);
        font-size: .78rem;
        font-weight: 700;
        text-transform: uppercase;
        margin: 1.1rem 0 .45rem;
    }

    .stButton > button {
        border-radius: 8px;
        border: 1px solid var(--line);
        background: #ffffff;
        color: var(--ink) !important;
        font-weight: 600;
        text-align: left;
        min-height: 42px;
        white-space: normal;
    }

    .stButton > button:hover {
        border-color: var(--accent);
        color: var(--accent) !important;
        background: var(--accent-soft);
    }

    .chat-shell {
        background: var(--panel);
        border: 1px solid var(--line);
        border-radius: 8px;
        min-height: calc(100vh - 8rem);
        padding: 1.1rem;
        box-shadow: 0 16px 36px rgba(19, 33, 48, .07);
    }

    .chat-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        border-bottom: 1px solid var(--line);
        padding-bottom: .9rem;
        margin-bottom: 1rem;
    }

    .chat-title {
        font-size: 1.2rem;
        font-weight: 800;
        color: var(--ink);
    }

    .chat-subtitle {
        font-size: .86rem;
        color: var(--muted);
        margin-top: .15rem;
    }

    .status-pill {
        border-radius: 999px;
        padding: .35rem .65rem;
        background: var(--accent-soft);
        color: var(--accent);
        font-size: .78rem;
        font-weight: 800;
        border: 1px solid #bde4dc;
    }

    [data-testid="stChatMessage"] {
        background: transparent;
        padding: .35rem 0;
    }

    [data-testid="stChatMessage"] p,
    [data-testid="stChatMessage"] li,
    [data-testid="stChatMessage"] span {
        color: var(--ink) !important;
    }

    [data-testid="stChatMessageContent"] {
        border-radius: 8px;
        padding: .85rem 1rem;
        border: 1px solid var(--line);
        color: var(--ink) !important;
    }

    [data-testid="stChatMessage"]:has([aria-label="Chat message from user"]) [data-testid="stChatMessageContent"] {
        background: #eaf3ff;
        border-color: #c9def8;
    }

    [data-testid="stChatMessage"]:has([aria-label="Chat message from assistant"]) [data-testid="stChatMessageContent"] {
        background: #ffffff;
    }

    .product-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
        gap: .75rem;
        margin: .5rem 0 1rem 3.25rem;
    }

    .product-card, .order-card {
        border: 1px solid var(--line);
        border-radius: 8px;
        background: #ffffff;
        padding: .85rem;
        color: var(--ink);
    }

    .product-name {
        font-weight: 800;
        color: var(--ink);
        line-height: 1.25;
        margin-bottom: .35rem;
    }

    .product-meta {
        display: flex;
        flex-wrap: wrap;
        gap: .35rem;
        margin: .45rem 0;
    }

    .chip, .stock-badge {
        display: inline-flex;
        align-items: center;
        border-radius: 999px;
        font-size: .76rem;
        font-weight: 800;
        padding: .22rem .5rem;
        border: 1px solid var(--line);
        color: var(--ink);
        background: #f7fafc;
    }

    .stock-ok {
        color: #066b4d;
        background: #e8f7ef;
        border-color: #b9e7cc;
    }

    .stock-low {
        color: var(--warn);
        background: var(--warn-soft);
        border-color: #fed7aa;
    }

    .stock-out {
        color: var(--danger);
        background: var(--danger-soft);
        border-color: #fecaca;
    }

    .price-row {
        display: flex;
        align-items: end;
        justify-content: space-between;
        gap: 1rem;
        margin-top: .65rem;
        color: var(--ink);
    }

    .price {
        font-size: 1.05rem;
        font-weight: 900;
        color: var(--ink);
    }

    .fitment {
        color: var(--muted);
        font-size: .82rem;
        line-height: 1.35;
    }

    .order-wrap {
        margin: .5rem 0 1rem 3.25rem;
    }

    .order-card {
        border-color: #bde4dc;
        background: #fbfffe;
    }

    .order-title {
        color: var(--accent);
        font-weight: 900;
        margin-bottom: .55rem;
    }

    .order-line {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        padding: .45rem 0;
        border-top: 1px solid #dcece8;
        color: var(--ink);
    }

    .order-total {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        padding-top: .65rem;
        margin-top: .35rem;
        border-top: 2px solid #bde4dc;
        font-weight: 900;
        color: var(--ink);
    }

    .empty-state {
        border: 1px dashed var(--line);
        border-radius: 8px;
        padding: 1.1rem;
        color: var(--muted);
        background: #fbfcfd;
        margin: 1rem 0;
    }

    .stChatInput textarea {
        color: var(--ink) !important;
        background: #ffffff !important;
        border-color: var(--line) !important;
    }

    .stSpinner, .stSpinner * {
        color: var(--ink) !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def assistant() -> DealerAssistant:
    return DealerAssistant()


def stock_class(stock: int) -> str:
    if stock <= 0:
        return "stock-out"
    if stock < 10:
        return "stock-low"
    return "stock-ok"


def stock_label(stock: int) -> str:
    if stock <= 0:
        return "Out of stock"
    if stock < 10:
        return f"Low stock: {stock}"
    return f"In stock: {stock}"


def render_product_cards(docs: list[dict]) -> None:
    if not docs:
        return
    cards = ['<div class="product-grid">']
    for doc in docs:
        stock = int(doc["stock"])
        cards.append(
            f"""
            <div class="product-card">
                <div class="product-name">{html.escape(str(doc["name"]))}</div>
                <div class="fitment">{html.escape(str(doc["vehicle_fitment"]))}</div>
                <div class="product-meta">
                    <span class="chip">{html.escape(str(doc["sku"]))}</span>
                    <span class="chip">{html.escape(str(doc["brand"]))}</span>
                    <span class="stock-badge {stock_class(stock)}">{stock_label(stock)}</span>
                </div>
                <div class="price-row">
                    <div class="price">INR {int(doc["price_inr"]):,}</div>
                    <div class="fitment">{html.escape(str(doc["category"]))}</div>
                </div>
            </div>
            """
        )
    cards.append("</div>")
    st.markdown("".join(cards), unsafe_allow_html=True)


def render_order_card(order: dict | None) -> None:
    if not order:
        return
    if order.get("status") != "ready_for_confirmation":
        errors = "; ".join(order.get("errors", [])) or "Order details need attention."
        st.error(errors)
        return

    lines = ['<div class="order-wrap"><div class="order-card">']
    lines.append(f'<div class="order-title">Order created for {html.escape(str(order["dealer"]))}</div>')
    for item in order.get("items", []):
        lines.append(
            f"""
            <div class="order-line">
                <div>{int(item["quantity"])} x {html.escape(str(item["name"]))}<br><span class="fitment">{html.escape(str(item["sku"]))}</span></div>
                <div>INR {int(item["line_total_inr"]):,}</div>
            </div>
            """
        )
    lines.append(
        f"""
        <div class="order-total">
            <div>Total</div>
            <div>INR {int(order["total_inr"]):,}</div>
        </div>
        </div></div>
        """
    )
    st.markdown("".join(lines), unsafe_allow_html=True)


def spinner_text(prompt: str) -> str:
    text = prompt.lower()
    if "order" in text or "buy" in text or "purchase" in text:
        return "Creating order..."
    if "stock" in text or "available" in text:
        return "Checking stock..."
    return "Searching compatible parts..."


bot = assistant()

if "messages" not in st.session_state:
    st.session_state.messages = []

if toast := st.session_state.pop("toast", None):
    st.toast(toast)

with st.sidebar:
    st.markdown(
        """
        <div class="vikmo-logo">
            <div class="logo-mark">V</div>
            <div class="logo-copy">
                <strong>VIKMO</strong>
                <span>Dealer Assistant</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<div class="sidebar-label">Suggestions</div>', unsafe_allow_html=True)
    examples = [
        "Need brake pads",
        "For Bajaj Pulsar 150",
        "Check stock for BRK-1042",
        "Order 10 brake pads for Bajaj Pulsar 150 for ABC Motors",
        "Show parts for Yamaha FZ",
    ]
    for example in examples:
        if st.button(example, use_container_width=True):
            st.session_state.pending_prompt = example

    st.markdown('<div class="sidebar-label">Session</div>', unsafe_allow_html=True)
    if st.button("Reset chat", use_container_width=True):
        bot.reset()
        st.session_state.messages = []
        st.rerun()

st.markdown('<div class="chat-shell">', unsafe_allow_html=True)
st.markdown(
    """
    <div class="chat-header">
        <div>
            <div class="chat-title">VIKMO Dealer Assistant</div>
            <div class="chat-subtitle">Search parts, check stock, and create dealer orders.</div>
        </div>
        <div class="status-pill">Live catalogue</div>
    </div>
    """,
    unsafe_allow_html=True,
)

if not st.session_state.messages:
    st.markdown(
        '<div class="empty-state">Ask for a part, vehicle fitment, stock availability, or order creation.</div>',
        unsafe_allow_html=True,
    )

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
    if message["role"] == "assistant":
        state = message.get("state") or {}
        render_product_cards(state.get("retrieved_docs", []))
        render_order_card(state.get("order_summary"))

prompt = st.chat_input("Ask for parts, stock, fitment or orders")
if st.session_state.get("pending_prompt"):
    prompt = st.session_state.pop("pending_prompt")

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.spinner(spinner_text(prompt)):
        state = bot.chat(prompt)
    if state.get("order_summary", {}).get("status") == "ready_for_confirmation":
        st.session_state.toast = "Order created successfully"
    st.session_state.messages.append(
        {"role": "assistant", "content": state["final_answer"], "state": state}
    )
    st.rerun()

st.markdown("</div>", unsafe_allow_html=True)
