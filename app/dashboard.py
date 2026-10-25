"""
dashboard.py — Streamlit Money Manager Dashboard.
Apple "Liquid Glass" Cupertino design with translucent frosted materials,
SF typography, unified single date range, concurrent sync & live progress.
Run with: python -m streamlit run app/dashboard.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

# Fix Windows emoji encoding issue
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta
import urllib.parse
from dotenv import load_dotenv, set_key

# ── Load Environment Configuration (.env) ────────────────────────────────────
ENV_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
load_dotenv(ENV_PATH, override=True)


def parse_env_float(*keys: str, default: float = 0.0) -> float:
    """Helper to parse a float environment variable, removing currency symbols, commas, quotes."""
    for k in keys:
        raw_val = os.getenv(k)
        if raw_val is not None and str(raw_val).strip() != "":
            cleaned = (
                str(raw_val)
                .replace("₹", "")
                .replace("$", "")
                .replace(",", "")
                .replace("'", "")
                .replace('"', "")
                .strip()
            )
            try:
                return float(cleaned)
            except (ValueError, TypeError):
                continue
    return default


def parse_env_str(*keys: str, default: str = "") -> str:
    """Helper to parse a string environment variable."""
    for k in keys:
        raw_val = os.getenv(k)
        if raw_val is not None and str(raw_val).strip() != "":
            return str(raw_val).replace('"', '').replace("'", '').strip()
    return default


def get_portfolio_info() -> dict:
    """Parse offline savings and investments from .env."""
    load_dotenv(ENV_PATH, override=True)
    cash = parse_env_float("CASH_SAVINGS", "CASH_SAVINGS_AMOUNT", default=0.0)
    cash_notes = parse_env_str("CASH_SAVINGS_NOTES", default="")

    pf = parse_env_float("PF_AMOUNT", "PROVIDENT_FUND", "PF", default=0.0)
    pf_notes = parse_env_str("PF_NOTES", "PF_DESCRIPTION", default="")

    gold = parse_env_float("GOLD_INVESTMENTS", "GOLD_INVESTMENT", "GOLD", default=0.0)
    gold_notes = parse_env_str("GOLD_NOTES", "GOLD_DESCRIPTION", default="")

    mf = parse_env_float("MUTUAL_FUNDS_INVESTMENT", "MUTUAL_FUNDS", "MUTUAL_FUND_INVESTMENT", "MUTUAL_FUND", default=0.0)
    mf_notes = parse_env_str("MUTUAL_FUNDS_NOTES", "MUTUAL_FUND_NOTES", default="")

    total = cash + pf + gold + mf
    return {
        "cash": cash,
        "cash_notes": cash_notes,
        "pf": pf,
        "pf_notes": pf_notes,
        "gold": gold,
        "gold_notes": gold_notes,
        "mf": mf,
        "mf_notes": mf_notes,
        "total": total,
    }


def get_cash_savings_info() -> tuple[float, str]:
    """Parse CASH_SAVINGS and optional CASH_SAVINGS_NOTES from .env (backward compat)."""
    p = get_portfolio_info()
    return p["cash"], p["cash_notes"]


from database import (
    init_db,
    get_all_transactions,
    get_summary_stats,
    get_category_totals,
    get_daily_totals,
)
from categories import CATEGORIES
from sync import sync_emails

# ── Page Configuration ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Finances — Apple Liquid Glass",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Apple "Liquid Glass" Cupertino Design System ──────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=SF+Pro+Display:wght@300;400;500;600;700&display=swap');

    /* Global Typography & Background */
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text", "Helvetica Neue", sans-serif;
        color: #f5f5f7;
        -webkit-font-smoothing: antialiased;
    }

    .stApp {
        background: radial-gradient(circle at 15% 15%, rgba(10, 132, 255, 0.08) 0%, transparent 45%),
                    radial-gradient(circle at 85% 25%, rgba(191, 90, 242, 0.06) 0%, transparent 40%),
                    radial-gradient(circle at 50% 80%, rgba(48, 209, 88, 0.05) 0%, transparent 50%),
                    #0b0c10;
        background-attachment: fixed;
    }

    /* Glass Cards (Liquid Glass Material) */
    .glass-card {
        background: rgba(255, 255, 255, 0.04);
        backdrop-filter: blur(28px) saturate(190%);
        -webkit-backdrop-filter: blur(28px) saturate(190%);
        border: 1px solid rgba(255, 255, 255, 0.12);
        box-shadow: inset 0 1px 1px 0 rgba(255, 255, 255, 0.15),
                    0 16px 36px 0 rgba(0, 0, 0, 0.38);
        border-radius: 20px;
        padding: 24px 20px;
        text-align: left;
        position: relative;
        overflow: hidden;
        transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
    }
    .glass-card:hover {
        transform: translateY(-3px);
        border-color: rgba(255, 255, 255, 0.22);
        box-shadow: inset 0 1px 1px 0 rgba(255, 255, 255, 0.25),
                    0 20px 42px 0 rgba(0, 0, 0, 0.5);
    }

    /* Subtle Glass Specular Reflection Highlight */
    .glass-card::before {
        content: "";
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 40%;
        background: linear-gradient(180deg, rgba(255, 255, 255, 0.06) 0%, rgba(255, 255, 255, 0) 100%);
        pointer-events: none;
    }

    /* Metric Card Hierarchy */
    .metric-caption {
        font-size: 0.72rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: #86868b;
        margin-bottom: 8px;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .metric-number {
        font-size: 2.1rem;
        font-weight: 700;
        letter-spacing: -0.03em;
        line-height: 1.1;
        margin-bottom: 6px;
        font-feature-settings: "tnum" 1;
    }
    .metric-footnote {
        font-size: 0.75rem;
        color: #6e6e73;
        font-weight: 400;
    }

    /* Apple Pill Badges */
    .pill-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 5px 14px;
        background: rgba(255, 255, 255, 0.06);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 980px;
        font-size: 0.78rem;
        font-weight: 500;
        color: #a1a1a6;
        backdrop-filter: blur(16px);
    }

    /* Apple-style Segmented Control Bar */
    div[data-testid="stHorizontalBlock"] button {
        border-radius: 980px !important;
        font-weight: 500 !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        background: rgba(255, 255, 255, 0.05) !important;
        color: #f5f5f7 !important;
        transition: all 0.2s ease !important;
    }
    div[data-testid="stHorizontalBlock"] button:hover {
        background: rgba(255, 255, 255, 0.12) !important;
        border-color: rgba(255, 255, 255, 0.25) !important;
    }

    /* Primary Apple Sync Button */
    button[kind="primary"] {
        background: linear-gradient(180deg, #0A84FF 0%, #0066CC 100%) !important;
        border: 1px solid rgba(255, 255, 255, 0.25) !important;
        box-shadow: inset 0 1px 0 0 rgba(255, 255, 255, 0.35), 0 4px 14px rgba(10, 132, 255, 0.4) !important;
        border-radius: 980px !important;
        font-weight: 600 !important;
        letter-spacing: -0.01em !important;
        padding: 10px 24px !important;
        transition: all 0.25s ease !important;
    }
    button[kind="primary"]:hover {
        box-shadow: inset 0 1px 0 0 rgba(255, 255, 255, 0.45), 0 6px 20px rgba(10, 132, 255, 0.6) !important;
        transform: scale(1.01) !important;
    }

    /* Tab bar Apple Segmented design */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 6px;
        backdrop-filter: blur(20px);
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 12px;
        color: #86868b;
        font-size: 0.88rem;
        font-weight: 500;
        padding: 8px 18px;
        transition: all 0.2s ease;
    }
    .stTabs [aria-selected="true"] {
        background: rgba(255, 255, 255, 0.12) !important;
        color: #ffffff !important;
        font-weight: 600;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }

    /* Liquid Glass Category Overview Component */
    .glass-wheel-card {
        background: rgba(255, 255, 255, 0.035);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 20px;
        padding: 18px 20px 20px 20px;
        backdrop-filter: blur(28px) saturate(190%);
        -webkit-backdrop-filter: blur(28px) saturate(190%);
        box-shadow: inset 0 1px 1px 0 rgba(255, 255, 255, 0.16), 0 16px 36px 0 rgba(0, 0, 0, 0.35);
        margin-bottom: 12px;
    }
    .glass-wheel-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 6px;
    }
    .glass-wheel-title {
        color: #f5f5f7;
        font-size: 1.05rem;
        font-weight: 600;
        letter-spacing: -0.01em;
    }
    .glass-wheel-badge {
        font-size: 0.72rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #86868b;
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 3px 10px;
        border-radius: 980px;
    }
    /* Sidebar Glass Surface */
    [data-testid="stSidebar"] {
        background: rgba(18, 18, 22, 0.75) !important;
        backdrop-filter: blur(35px) saturate(200%) !important;
        -webkit-backdrop-filter: blur(35px) saturate(200%) !important;
        border-right: 1px solid rgba(255, 255, 255, 0.08) !important;
    }
</style>
""", unsafe_allow_html=True)

# Apple Liquid Glass Palette
APPLE_COLORS = [
    "#0A84FF",  # Cupertino Electric Blue
    "#5E5CE6",  # Deep Indigo
    "#BF5AF2",  # Vivid Violet / Purple
    "#FF375F",  # Neon Coral Rose
    "#FF9F0A",  # Bright Amber Orange
    "#30D158",  # Apple Mint
    "#64D2FF",  # Ice Cyan
    "#FFD60A",  # Radiant Gold
    "#FF6482",  # Flamingo Pink
    "#00E096",  # Emerald Teal
]

# ── Init DB on startup ─────────────────────────────────────────────────────────
init_db()

today = date.today()

# Setup Session State for Unified Single Date Range
if "start_date" not in st.session_state:
    st.session_state.start_date = today.replace(day=1)
if "end_date" not in st.session_state:
    st.session_state.end_date = today


def set_date_preset(start, end):
    st.session_state.start_date = start
    st.session_state.end_date = end


# ── Apple Sidebar ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### **Money Manager**")

    # Active AI Provider Indicator
    provider_name = os.getenv("AI_PROVIDER", "gemini").strip().lower()
    model_name = os.getenv("GROQ_MODEL" if provider_name == "groq" else "GEMINI_MODEL", "gemini-3.8-flash")
    st.markdown(
        f'<div class="pill-badge"><span>⚡</span> Engine: <b style="color:#ffffff;">{provider_name.title()}</b> · <span style="opacity:0.75;">{model_name}</span></div>',
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)
    st.markdown("---")

    # Unified Date Range Selection
    st.markdown("**Date Window**")
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("From", key="start_date")
    with col2:
        end_date = st.date_input("To", key="end_date")

    st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)

    # High-Performance Concurrently-Powered Sync Button
    sync_btn = st.button("📬 Sync Bank Alerts", type="primary", width='stretch')

    # Progress bar placeholder
    sync_status_box = st.empty()

    if sync_btn:
        progress_bar = st.progress(0.0)

        def on_sync_progress(fraction: float, message: str):
            progress_bar.progress(fraction)
            sync_status_box.caption(f"⚡ {message}")

        try:
            result = sync_emails(
                start_date=str(start_date),
                end_date=str(end_date),
                progress_callback=on_sync_progress,
                max_workers=6,
            )
            progress_bar.empty()
            sync_status_box.empty()
            if result and result.get("inserted", 0) > 0:
                st.success(f"Synced {result['inserted']} new transactions in seconds!")
            else:
                st.info("Everything is already up to date.")
            st.rerun()
        except Exception as e:
            progress_bar.empty()
            sync_status_box.empty()
            st.error(f"Sync error: {e}")

    st.markdown("---")

    # Initialize Category Filter in session state
    if "selected_category" not in st.session_state:
        st.session_state.selected_category = "All"
    selected_category = st.session_state.selected_category

    # Filter Data (Type only)
    st.markdown("**Filter Data**")
    selected_type = st.selectbox("Type", ["All", "debit", "credit"])

    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
    st.markdown("<div style='font-size:0.75rem; color:#86868b; text-transform:uppercase; letter-spacing:0.08em; font-weight:600; margin-bottom:8px;'>Click a category to view ledger & export:</div>", unsafe_allow_html=True)

    cat_totals = get_category_totals(str(start_date), str(end_date))

    if selected_category != "All":
        c_h1, c_h2 = st.columns([2.5, 1.2])
        with c_h1:
            st.markdown(f'<div class="pill-badge" style="margin-bottom:6px;"><span>✓</span> Cat: <b style="color:#ffffff;">{selected_category}</b></div>', unsafe_allow_html=True)
        with c_h2:
            if st.button("✕ Reset", key="sb_reset_cat", width='stretch'):
                st.session_state.selected_category = "All"
                st.rerun()

    if cat_totals:
        dot_css_rules = []
        for idx, row in enumerate(cat_totals):
            c_color = APPLE_COLORS[idx % len(APPLE_COLORS)]
            c_name = row["category"]
            dot_css_rules.append(f"""
            div[data-testid="stSidebar"] button[aria-label*="{c_name}"] p::before {{
                content: "\\25CF  " !important;
                color: {c_color} !important;
                font-size: 1.15em !important;
                filter: drop-shadow(0 0 7px {c_color}) !important;
            }}
            """)
        dot_css_rules.append("""
            div[data-testid="stSidebar"] button[kind="primary"] p::before {
                content: "\\2713  " !important;
                color: #ffffff !important;
                filter: drop-shadow(0 0 6px rgba(255,255,255,0.6)) !important;
            }
        """)
        st.html(f"<style>{''.join(dot_css_rules)}</style>")

        sb_cols = st.columns(2)
        for idx, row in enumerate(cat_totals):
            name = row["category"]
            is_active = (selected_category == name)
            target_col = sb_cols[idx % 2]
            with target_col:
                if st.button(name, key=f"sb_cat_btn_{name}", width='stretch', type="primary" if is_active else "secondary"):
                    if st.session_state.selected_category == name:
                        st.session_state.selected_category = "All"
                    else:
                        st.session_state.selected_category = name
                    st.rerun()


# ── Data Retrieval ────────────────────────────────────────────────────────────
# Fetch all categories for overall stats & wheel, filtering by selected_type
txns = get_all_transactions(
    start_date=str(start_date),
    end_date=str(end_date),
    category="All",
    txn_type=selected_type,
)
df = pd.DataFrame(txns) if txns else pd.DataFrame()

daily_totals = get_daily_totals(str(start_date), str(end_date))

# ── Summary Calculations ──────────────────────────────────────────────────────
if not df.empty:
    filter_spent = df[df["type"] == "debit"]["amount"].sum()
    filter_income = df[df["type"] == "credit"]["amount"].sum()
    filter_count = len(df)
else:
    filter_spent = filter_income = filter_count = 0

net_savings = filter_income - filter_spent
net_color = "#30D158" if net_savings >= 0 else "#FF453A"

# ── Dashboard Title & Header ──────────────────────────────────────────────────
top_l, top_r = st.columns([3, 1])
with top_l:
    st.markdown(
        f"<h2 style='font-weight:700; letter-spacing:-0.03em; margin-bottom:2px;'>Financial Dashboard</h2>"
        f"<span style='color:#86868b; font-size:0.9rem;'>{start_date.strftime('%d %b %Y')} &nbsp;→&nbsp; {end_date.strftime('%d %b %Y')}</span>",
        unsafe_allow_html=True,
    )
with top_r:
    st.markdown(
        f"<div style='text-align:right; padding-top:8px;'>"
        f"<span class='pill-badge'><b>{filter_count}</b> Transactions</span>"
        f"</div>",
        unsafe_allow_html=True,
    )

st.markdown("<div style='height: 18px;'></div>", unsafe_allow_html=True)

# ── Apple Liquid Glass Metric Cards ───────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)

with c1:
    st.markdown(f"""
    <div class="glass-card">
        <div class="metric-caption"><span style="color:#FF453A;">●</span> Total Spent</div>
        <div class="metric-number" style="color: #FF453A;">₹{filter_spent:,.2f}</div>
        <div class="metric-footnote">Outflows & debits</div>
    </div>
    """, unsafe_allow_html=True)

with c2:
    st.markdown(f"""
    <div class="glass-card">
        <div class="metric-caption"><span style="color:#30D158;">●</span> Total Income</div>
        <div class="metric-number" style="color: #30D158;">₹{filter_income:,.2f}</div>
        <div class="metric-footnote">Salary & credits</div>
    </div>
    """, unsafe_allow_html=True)

with c3:
    st.markdown(f"""
    <div class="glass-card">
        <div class="metric-caption"><span style="color:{net_color};">●</span> Net Cashflow</div>
        <div class="metric-number" style="color: {net_color};">₹{net_savings:,.2f}</div>
        <div class="metric-footnote">Income minus expenses</div>
    </div>
    """, unsafe_allow_html=True)

with c4:
    st.markdown(f"""
    <div class="glass-card">
        <div class="metric-caption"><span style="color:#0A84FF;">●</span> Volume</div>
        <div class="metric-number" style="color: #0A84FF;">{filter_count}</div>
        <div class="metric-footnote">Processed bank alerts</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='height: 26px;'></div>", unsafe_allow_html=True)

# ── Cupertino Tabs ────────────────────────────────────────────────────────────
tab_overview, tab_daily, tab_categories, tab_table, tab_cash = st.tabs([
    "Overview",
    "Day-by-Day Timeline",
    "Category Analysis",
    "Ledger & Export",
    "Savings & Investments",
])

PLOT_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="-apple-system, SF Pro Display, sans-serif", color="#86868b", size=12),
    margin=dict(t=30, b=30, l=30, r=30),
)

# ── Tab 1: Overview ───────────────────────────────────────────────────────────
with tab_overview:
    if not df.empty:
        col_pie, col_bar = st.columns([1, 1.2])

        with col_pie:
            if cat_totals:
                cat_df = pd.DataFrame(cat_totals)
                total_cat_spent = cat_df["total"].sum()

                # Header
                st.html("""<div class="glass-wheel-header"><span class="glass-wheel-title">Category Overview</span><span class="glass-wheel-badge">Distribution</span></div>""")

                # Apple Liquid Glass Donut Wheel
                fig_pie = px.pie(
                    cat_df,
                    values="total",
                    names="category",
                    hole=0.72,
                    color_discrete_sequence=APPLE_COLORS,
                )
                fig_pie.update_traces(
                    textposition="inside",
                    textinfo="percent",
                    textfont=dict(size=11, color="#ffffff", family="-apple-system, SF Pro Display, sans-serif"),
                    hovertemplate="<b style='color:#ffffff; font-size:13px;'>%{label}</b><br><span style='color:#86868b;'>Spent:</span> <b style='color:#ffffff;'>₹%{value:,.2f}</b><br><span style='color:#86868b;'>Share:</span> <b style='color:#ffffff;'>%{percent}</b><extra></extra>",
                    marker=dict(
                        line=dict(color="#0c0d12", width=2.5),
                    ),
                    pull=[0] * len(cat_df),
                )
                fig_pie.update_layout(
                    **{**PLOT_LAYOUT, "margin": dict(t=6, b=6, l=6, r=6)},
                    height=360,
                    showlegend=False,
                )
                st.plotly_chart(fig_pie, width='stretch')
            else:
                st.info("No debit transactions recorded.")

        with col_bar:
            st.markdown("<b style='color:#f5f5f7; font-size:1.05rem;'>Daily Spending Trend</b>", unsafe_allow_html=True)
            if daily_totals:
                day_df = pd.DataFrame(daily_totals)
                fig_trend = px.bar(
                    day_df,
                    x="date",
                    y="total",
                    color_discrete_sequence=["#0A84FF"],
                    labels={"date": "Date", "total": "Debited (₹)"},
                )
                fig_trend.update_traces(
                    marker=dict(cornerradius=6),
                    hovertemplate="<b>%{x}</b><br>Spent: ₹%{y:,.2f}<extra></extra>",
                )
                fig_trend.update_layout(
                    **PLOT_LAYOUT,
                    height=360,
                    xaxis=dict(showgrid=False, tickangle=-45, color="#6e6e73"),
                    yaxis=dict(gridcolor="rgba(255,255,255,0.06)", zerolinecolor="rgba(255,255,255,0.1)"),
                )
                st.plotly_chart(fig_trend, width='stretch')
            else:
                st.info("No spending trends available.")

        # ── Category-Filtered Ledger & Export Display ───────────────────────────
        if selected_category != "All":
            cat_txns = df[df["category"] == selected_category] if not df.empty else pd.DataFrame()
            st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
            st.markdown(
                f"<div class='glass-card' style='padding: 20px 24px;'>"
                f"<div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;'>"
                f"  <span style='font-size:1.15rem; font-weight:700; color:#f5f5f7;'>📋 Ledger & Export: <span style='color:#0A84FF;'>{selected_category}</span> ({len(cat_txns)} records)</span>"
                f"  <span class='pill-badge'>Category Filter</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
            
            if not cat_txns.empty:
                t_cols = cat_txns[["date", "time", "type", "amount", "merchant", "category", "balance", "description"]].copy()
                t_cols.columns = ["Date", "Time", "Type", "Amount (₹)", "Merchant", "Category", "Balance (₹)", "Description"]
                t_cols["Amount (₹)"] = t_cols["Amount (₹)"].map(lambda x: f"₹{x:,.2f}")
                t_cols["Balance (₹)"] = t_cols["Balance (₹)"].map(lambda x: f"₹{x:,.2f}" if pd.notnull(x) and x != "" else "—")
                
                def color_badge(val):
                    if val == "debit":
                        return "color: #FF453A; font-weight: 600;"
                    elif val == "credit":
                        return "color: #30D158; font-weight: 600;"
                    return ""
                
                styled_cat_ledger = t_cols.style.map(color_badge, subset=["Type"])
                st.dataframe(styled_cat_ledger, width='stretch', height=320)
                
                cat_csv = cat_txns.to_csv(index=False).encode("utf-8")
                st.download_button(
                    f"📥 Download {selected_category} Statement (CSV)",
                    data=cat_csv,
                    file_name=f"{selected_category.lower().replace(' ', '_')}_{start_date}_{end_date}.csv",
                    mime="text/csv",
                    key=f"export_cat_btn_{selected_category}",
                )
            else:
                st.info(f"No transactions found for {selected_category}.")
            st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("📭 No transactions found for this date range. Click **'📬 Sync Bank Alerts'** in the sidebar!")

# ── Tab 2: Day-by-Day Timeline ────────────────────────────────────────────────
with tab_daily:
    st.markdown("<b style='color:#f5f5f7; font-size:1.05rem;'>Daily Cashflow & Activity</b>", unsafe_allow_html=True)
    if not df.empty:
        daily_summary = df.groupby("date").apply(
            lambda g: pd.Series({
                "Debited (₹)": g[g["type"] == "debit"]["amount"].sum(),
                "Credited (₹)": g[g["type"] == "credit"]["amount"].sum(),
                "Net Flow (₹)": g[g["type"] == "credit"]["amount"].sum() - g[g["type"] == "debit"]["amount"].sum(),
                "Alerts": len(g),
            }),
            include_groups=False,
        ).reset_index().sort_values(by="date", ascending=False)

        fig_daily = go.Figure()
        fig_daily.add_trace(go.Bar(
            x=daily_summary["date"],
            y=daily_summary["Debited (₹)"],
            name="Spent (Debit)",
            marker_color="#FF453A",
            marker=dict(cornerradius=5),
            hovertemplate="<b>%{x}</b><br>Spent: ₹%{y:,.2f}<extra></extra>",
        ))
        fig_daily.add_trace(go.Bar(
            x=daily_summary["date"],
            y=daily_summary["Credited (₹)"],
            name="Income (Credit)",
            marker_color="#30D158",
            marker=dict(cornerradius=5),
            hovertemplate="<b>%{x}</b><br>Credited: ₹%{y:,.2f}<extra></extra>",
        ))
        fig_daily.update_layout(
            **PLOT_LAYOUT,
            barmode="group",
            height=380,
            xaxis=dict(showgrid=False, tickangle=-45),
            yaxis=dict(gridcolor="rgba(255,255,255,0.06)"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig_daily, width='stretch')

        d_table = daily_summary.copy()
        d_table["Debited (₹)"] = d_table["Debited (₹)"].map(lambda x: f"₹{x:,.2f}")
        d_table["Credited (₹)"] = d_table["Credited (₹)"].map(lambda x: f"₹{x:,.2f}")
        d_table["Net Flow (₹)"] = d_table["Net Flow (₹)"].map(lambda x: f"₹{x:,.2f}")
        st.dataframe(d_table, width='stretch', height=340)
    else:
        st.info("No daily data recorded.")

# ── Tab 3: Category Analysis ──────────────────────────────────────────────────
with tab_categories:
    st.markdown("<b style='color:#f5f5f7; font-size:1.05rem;'>Expense Distribution by Category</b>", unsafe_allow_html=True)
    if cat_totals:
        c_df = pd.DataFrame(cat_totals)
        tot_debit = c_df["total"].sum()
        c_df["Share"] = (c_df["total"] / tot_debit * 100).map(lambda x: f"{x:.1f}%")

        c_chart, c_tbl = st.columns([1.1, 1])
        with c_chart:
            fig_hbar = px.bar(
                c_df.sort_values(by="total", ascending=True),
                x="total",
                y="category",
                orientation="h",
                color="total",
                color_continuous_scale=["#0A84FF", "#BF5AF2"],
                labels={"total": "Amount (₹)", "category": "Category"},
            )
            fig_hbar.update_traces(
                marker=dict(cornerradius=6),
                hovertemplate="<b>%{y}</b><br>Total: ₹%{x:,.2f}<extra></extra>",
            )
            fig_hbar.update_layout(
                **PLOT_LAYOUT,
                coloraxis_showscale=False,
                height=400,
                xaxis=dict(gridcolor="rgba(255,255,255,0.06)"),
                yaxis=dict(showgrid=False),
            )
            st.plotly_chart(fig_hbar, width='stretch')

        with c_tbl:
            c_show = c_df.copy()
            c_show["Total Spent"] = c_show["total"].map(lambda x: f"₹{x:,.2f}")
            c_show = c_show[["category", "Total Spent", "Share"]]
            c_show.columns = ["Category", "Total Spent (₹)", "Share %"]
            st.dataframe(c_show, width='stretch', height=380)
    else:
        st.info("No expense categories found in this period.")

# ── Tab 4: Ledger & Export ────────────────────────────────────────────────────
with tab_table:
    ledger_df = df.copy()
    if selected_category != "All":
        ledger_df = ledger_df[ledger_df["category"] == selected_category]
        ledger_title = f"Transaction Ledger for {selected_category} ({len(ledger_df)})"
        st.markdown(f"<div style='display:flex; justify-content:space-between; align-items:center;'><b style='color:#f5f5f7; font-size:1.05rem;'>{ledger_title}</b><span class='pill-badge'>Filtered: {selected_category}</span></div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<b style='color:#f5f5f7; font-size:1.05rem;'>Transaction Ledger ({filter_count})</b>", unsafe_allow_html=True)
    if not ledger_df.empty:
        search_query = st.text_input("Search Ledger", placeholder="Filter by merchant name or note (e.g. Swiggy, Amazon, EPAM)...", label_visibility="collapsed")
        if search_query:
            mask = (
                ledger_df["merchant"].str.contains(search_query, case=False, na=False) |
                ledger_df["description"].str.contains(search_query, case=False, na=False)
            )
            ledger_df = ledger_df[mask]

        table_cols = ledger_df[["date", "time", "type", "amount", "merchant", "category", "balance", "description"]].copy()
        table_cols.columns = ["Date", "Time", "Type", "Amount (₹)", "Merchant", "Category", "Balance (₹)", "Description"]
        table_cols["Amount (₹)"] = table_cols["Amount (₹)"].map(lambda x: f"₹{x:,.2f}")
        table_cols["Balance (₹)"] = table_cols["Balance (₹)"].map(lambda x: f"₹{x:,.2f}" if pd.notnull(x) and x != "" else "—")

        def color_badge(val):
            if val == "debit":
                return "color: #FF453A; font-weight: 600;"
            elif val == "credit":
                return "color: #30D158; font-weight: 600;"
            return ""

        styled_ledger = table_cols.style.map(color_badge, subset=["Type"])
        st.dataframe(styled_ledger, width='stretch', height=450)

        csv_bytes = ledger_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "📥 Download Statement (CSV)",
            data=csv_bytes,
            file_name=f"statement_{start_date}_{end_date}.csv",
            mime="text/csv",
        )
    else:
        st.info("No transaction ledger items to display.")

# ── Tab 5: Savings & Investments ──────────────────────────────────────────────
with tab_cash:
    portfolio = get_portfolio_info()
    cash_val = portfolio["cash"]
    pf_val = portfolio["pf"]
    gold_val = portfolio["gold"]
    mf_val = portfolio["mf"]
    total_assets = portfolio["total"]

    st.markdown(
        f"<div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:18px;'>"
        f"  <div>"
        f"    <b style='color:#f5f5f7; font-size:1.25rem; letter-spacing:-0.02em;'>Savings & Investments Portfolio</b>"
        f"    <div style='color:#86868b; font-size:0.88rem; margin-top:3px;'>Offline reserves & investments configured in <code>.env</code></div>"
        f"  </div>"
        f"  <div style='text-align:right;'>"
        f"    <div style='font-size:0.74rem; color:#86868b; text-transform:uppercase; letter-spacing:0.08em; font-weight:600;'>Total Portfolio Worth</div>"
        f"    <div style='font-size:1.45rem; font-weight:700; color:#30D158; letter-spacing:-0.02em;'>₹{total_assets:,.2f}</div>"
        f"  </div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # 4 Portfolio Asset Cards (Cash, PF, Gold, Mutual Funds)
    k1, k2, k3, k4 = st.columns(4)

    with k1:
        st.markdown(f"""
        <div class="glass-card">
            <div class="metric-caption"><span style="color:#30D158;">●</span> Cash Savings</div>
            <div class="metric-number" style="color: #30D158;">₹{cash_val:,.2f}</div>
            <div class="metric-footnote">{portfolio['cash_notes'] or 'CASH_SAVINGS in .env'}</div>
        </div>
        """, unsafe_allow_html=True)

    with k2:
        st.markdown(f"""
        <div class="glass-card">
            <div class="metric-caption"><span style="color:#0A84FF;">●</span> PF Amount</div>
            <div class="metric-number" style="color: #0A84FF;">₹{pf_val:,.2f}</div>
            <div class="metric-footnote">{portfolio['pf_notes'] or 'PF_AMOUNT in .env'}</div>
        </div>
        """, unsafe_allow_html=True)

    with k3:
        st.markdown(f"""
        <div class="glass-card">
            <div class="metric-caption"><span style="color:#FFD60A;">●</span> Gold Investments</div>
            <div class="metric-number" style="color: #FFD60A;">₹{gold_val:,.2f}</div>
            <div class="metric-footnote">{portfolio['gold_notes'] or 'GOLD_INVESTMENTS in .env'}</div>
        </div>
        """, unsafe_allow_html=True)

    with k4:
        st.markdown(f"""
        <div class="glass-card">
            <div class="metric-caption"><span style="color:#BF5AF2;">●</span> Mutual Funds</div>
            <div class="metric-number" style="color: #BF5AF2;">₹{mf_val:,.2f}</div>
            <div class="metric-footnote">{portfolio['mf_notes'] or 'MUTUAL_FUNDS in .env'}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)

    # Charts & Breakdown
    chart_col, env_col = st.columns([1.1, 0.9])

    with chart_col:
        st.markdown("<b style='color:#f5f5f7; font-size:1.05rem;'>Portfolio Asset Allocation</b>", unsafe_allow_html=True)

        alloc_data = []
        if cash_val > 0:
            alloc_data.append({"Asset": "Cash Savings", "Amount": cash_val, "Color": "#30D158"})
        if pf_val > 0:
            alloc_data.append({"Asset": "PF Amount", "Amount": pf_val, "Color": "#0A84FF"})
        if gold_val > 0:
            alloc_data.append({"Asset": "Gold Investments", "Amount": gold_val, "Color": "#FFD60A"})
        if mf_val > 0:
            alloc_data.append({"Asset": "Mutual Funds", "Amount": mf_val, "Color": "#BF5AF2"})
        if not alloc_data:
            alloc_data.append({"Asset": "No Assets Configured", "Amount": 1.0, "Color": "#3a3a3c"})

        alloc_df = pd.DataFrame(alloc_data)
        fig_alloc = px.pie(
            alloc_df,
            values="Amount",
            names="Asset",
            hole=0.68,
            color="Asset",
            color_discrete_map={row["Asset"]: row["Color"] for row in alloc_data},
        )
        fig_alloc.update_traces(
            textposition="inside",
            textinfo="percent+label",
            textfont=dict(size=11, color="#ffffff", family="-apple-system, SF Pro Display, sans-serif"),
            hovertemplate="<b style='color:#ffffff; font-size:13px;'>%{label}</b><br><span style='color:#86868b;'>Amount:</span> <b style='color:#ffffff;'>₹%{value:,.2f}</b><extra></extra>",
            marker=dict(line=dict(color="#0c0d12", width=2.5)),
        )
        fig_alloc.update_layout(
            **{**PLOT_LAYOUT, "margin": dict(t=10, b=10, l=10, r=10)},
            height=340,
            showlegend=False,
        )
        st.plotly_chart(fig_alloc, width='stretch')

    with env_col:
        st.markdown("<b style='color:#f5f5f7; font-size:1.05rem;'>Environment (.env) Configuration</b>", unsafe_allow_html=True)
        st.markdown(f"""
        <div class="glass-card" style="padding: 16px 20px; margin-bottom: 14px;">
            <div style="font-size:0.8rem; color:#86868b; text-transform:uppercase; letter-spacing:0.06em; font-weight:600; margin-bottom:6px;">Current Configuration in <code>.env</code></div>
            <div style="font-family:monospace; font-size:0.90rem; color:#f5f5f7; background:rgba(0,0,0,0.3); padding:10px 14px; border-radius:10px; border:1px solid rgba(255,255,255,0.08); line-height:1.7;">
                <span style="color:#64D2FF;">CASH_SAVINGS</span> = <span style="color:#30D158; font-weight:700;">₹{cash_val:,.2f}</span><br>
                <span style="color:#64D2FF;">PF_AMOUNT</span> = <span style="color:#0A84FF; font-weight:700;">₹{pf_val:,.2f}</span><br>
                <span style="color:#64D2FF;">GOLD_INVESTMENTS</span> = <span style="color:#FFD60A; font-weight:700;">₹{gold_val:,.2f}</span><br>
                <span style="color:#64D2FF;">MUTUAL_FUNDS</span> = <span style="color:#BF5AF2; font-weight:700;">₹{mf_val:,.2f}</span>
            </div>
            <div style="font-size:0.8rem; color:#86868b; margin-top:8px;">
                File: <code style="color:#f5f5f7;">{ENV_PATH}</code>
            </div>
        </div>
        """, unsafe_allow_html=True)

        e_sub1, e_sub2 = st.columns([1, 1])
        with e_sub1:
            if st.button("🔄 Reload from .env", key="btn_reload_env", width='stretch'):
                load_dotenv(ENV_PATH, override=True)
                st.rerun()

        st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
        with st.expander("✏️ Quick Update .env from Dashboard"):
            c_input = st.number_input("Cash Savings (₹)", min_value=0.0, value=float(cash_val), step=1000.0, format="%.2f", key="inp_cash")
            pf_input = st.number_input("PF Amount (₹)", min_value=0.0, value=float(pf_val), step=1000.0, format="%.2f", key="inp_pf")
            gold_input = st.number_input("Gold Investments (₹)", min_value=0.0, value=float(gold_val), step=1000.0, format="%.2f", key="inp_gold")
            mf_input = st.number_input("Mutual Funds (₹)", min_value=0.0, value=float(mf_val), step=1000.0, format="%.2f", key="inp_mf")
            if st.button("💾 Save All to .env", type="primary", key="btn_save_all_env", width='stretch'):
                try:
                    set_key(ENV_PATH, "CASH_SAVINGS", str(int(c_input) if c_input.is_integer() else c_input))
                    set_key(ENV_PATH, "PF_AMOUNT", str(int(pf_input) if pf_input.is_integer() else pf_input))
                    set_key(ENV_PATH, "GOLD_INVESTMENTS", str(int(gold_input) if gold_input.is_integer() else gold_input))
                    set_key(ENV_PATH, "MUTUAL_FUNDS", str(int(mf_input) if mf_input.is_integer() else mf_input))
                    load_dotenv(ENV_PATH, override=True)
                    st.success("Successfully updated .env!")
                    st.rerun()
                except Exception as ex:
                    st.error(f"Error saving to .env: {ex}")


# ── Minimal Apple Footer ──────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    f"<div style='text-align: center; color: #6e6e73; font-size: 0.78rem; padding: 12px 0;'>"
    f"Money Manager &nbsp;•&nbsp; Powered by <b>{provider_name.title()} ({model_name})</b> & Gmail API"
    f"</div>",
    unsafe_allow_html=True,
)
