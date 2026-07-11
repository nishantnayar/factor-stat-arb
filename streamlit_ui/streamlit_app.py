"""
Trading System - Home Dashboard
Real-time account overview, market status, and positions summary.
"""

import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import streamlit as st  # noqa: E402
from utils import render_market_banner  # noqa: E402

from src.shared.logging import setup_logging  # noqa: E402

setup_logging(service_name="streamlit_ui")

st.set_page_config(
    page_title="Trading System",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)


# --- CSS ---


def load_css() -> None:
    css_file = os.path.join(os.path.dirname(__file__), "styles.css")
    try:
        with open(css_file) as f:
            css = f.read()
        from css_config import generate_css_variables, get_theme_css

        st.markdown(
            f"<style>{generate_css_variables()}{css}{get_theme_css()}</style>",
            unsafe_allow_html=True,
        )
    except Exception:
        pass


# --- Helpers ---


def _fmt_dollar(v) -> str:
    try:
        v = float(v)
        return f"${v:,.2f}"
    except Exception:
        return "-"


def _fmt_pct(v) -> str:
    try:
        v = float(v)
        sign = "+" if v >= 0 else ""
        return f"{sign}{v:.2f}%"
    except Exception:
        return "-"


def _pnl_color(v) -> str:
    try:
        return "#2A7A4B" if float(v) >= 0 else "#C0392B"
    except Exception:
        return "#6b6b6b"


# --- Sidebar ---


def render_sidebar(account: dict, positions: list) -> None:
    st.sidebar.markdown(
        '<h2 style=\'font-family:"Playfair Display",Georgia,serif;'
        "font-size:1.15rem;font-weight:500;color:#1a1a1a;"
        "border-bottom:1px solid rgba(26,26,26,0.1);padding-bottom:0.4rem;"
        "margin-bottom:0.8rem;'>Trading System</h2>",
        unsafe_allow_html=True,
    )

    if "error" not in account:
        equity = float(account.get("equity", 0))
        last_equity = float(account.get("last_equity", equity))
        day_pnl = equity - last_equity
        day_pct = (day_pnl / last_equity * 100) if last_equity else 0

        st.sidebar.metric("Portfolio Value", _fmt_dollar(equity))
        color = _pnl_color(day_pnl)
        sign = "+" if day_pnl >= 0 else ""
        st.sidebar.markdown(
            f'<div style=\'font-family:"DM Mono",monospace;font-size:0.85rem;'
            f"color:{color};margin:-0.4rem 0 0.6rem 0;'>"
            f"{sign}{_fmt_dollar(abs(day_pnl))} ({sign}{day_pct:.2f}%) today</div>",
            unsafe_allow_html=True,
        )
        st.sidebar.metric("Buying Power", _fmt_dollar(account.get("buying_power", 0)))
        st.sidebar.metric("Cash", _fmt_dollar(account.get("cash", 0)))
    else:
        st.sidebar.warning("API unavailable")

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        f'<p style=\'font-family:"DM Sans",sans-serif;font-size:0.78rem;'
        f"color:#9e9e9e;margin:0;'>Open positions: {len(positions)}</p>",
        unsafe_allow_html=True,
    )


# --- Main ---


def main() -> None:
    load_css()

    from api_client import get_api_client

    api = get_api_client()

    # Fetch live data
    clock = api.get_market_clock()
    account = api.get_alpaca_account()
    positions = api.get_alpaca_positions()
    orders = api.get_alpaca_orders(status="open", limit=20)

    render_sidebar(account, positions)

    # --- Greeting + title ---
    from datetime import datetime as _dt

    hour = _dt.now().hour
    greeting = (
        "Good morning"
        if hour < 12
        else ("Good afternoon" if hour < 17 else "Good evening")
    )

    st.markdown(
        f'<div style=\'margin-bottom:0.2rem;font-family:"DM Sans",sans-serif;'
        f"font-size:0.85rem;color:#4a4a4a;'>{greeting}, Nishant</div>"
        f"<h1 style='margin-top:0;'>Dashboard</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='color:#6b6b6b;font-size:0.88rem;margin-top:-0.8rem;"
        "margin-bottom:1.2rem;'>"
        "Here's what's happening in your paper trading account today.</p>",
        unsafe_allow_html=True,
    )

    # --- Market clock ---
    if "error" not in clock:
        render_market_banner(clock)

    # --- Account metrics ---
    if "error" not in account:
        equity = float(account.get("equity", 0))
        last_equity = float(account.get("last_equity", equity))
        day_pnl = equity - last_equity
        day_pct = (day_pnl / last_equity * 100) if last_equity else 0
        buying_power = float(account.get("buying_power", 0))

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Portfolio Value", _fmt_dollar(equity))
        sign = "+" if day_pnl >= 0 else ""
        c2.metric(
            "Today's P&L",
            _fmt_dollar(day_pnl),
            f"{sign}{day_pct:.2f}%",
        )
        c3.metric("Buying Power", _fmt_dollar(buying_power))
        c4.metric("Open Positions", len(positions))
    else:
        st.error(
            "Could not load account data - is the API running on port 8001?"
        )

    st.markdown("---")

    # --- Positions ---
    col_left, col_right = st.columns([3, 1])

    with col_left:
        st.markdown("<h2>Positions</h2>", unsafe_allow_html=True)

        if positions:
            rows = []
            for p in positions:
                unrl = float(p.get("unrealized_pl", 0))
                unrl_pct = float(p.get("unrealized_plpc", 0)) * 100
                intraday_pct = float(p.get("unrealized_intraday_plpc", 0)) * 100
                sign_u = "+" if unrl >= 0 else ""
                sign_i = "+" if intraday_pct >= 0 else ""
                rows.append(
                    {
                        "Symbol": p.get("symbol", ""),
                        "Side": p.get("side", "").upper(),
                        "Qty": int(float(p.get("qty", 0))),
                        "Avg Entry": _fmt_dollar(p.get("avg_entry_price", 0)),
                        "Price": _fmt_dollar(p.get("current_price", 0)),
                        "Mkt Value": _fmt_dollar(p.get("market_value", 0)),
                        "Unrlzd P&L": (
                            f"{sign_u}{_fmt_dollar(unrl)} ({sign_u}{unrl_pct:.2f}%)"
                        ),
                        "Today %": f"{sign_i}{intraday_pct:.2f}%",
                    }
                )

            import pandas as pd

            df = pd.DataFrame(rows)
            st.dataframe(df, width="stretch", hide_index=True)
        else:
            st.markdown(
                '<p style=\'color:#9e9e9e;font-family:"DM Sans",sans-serif;'
                "font-size:0.9rem;padding:1rem 0;'>No open positions.</p>",
                unsafe_allow_html=True,
            )

    with col_right:
        st.markdown("<h2>Open Orders</h2>", unsafe_allow_html=True)

        if orders:
            for o in orders[:8]:
                sym = o.get("symbol", "")
                side = o.get("side", "").upper()
                qty = o.get("qty", "")
                otype = o.get("order_type") or o.get("type", "")
                color = "#2A7A4B" if side == "BUY" else "#C0392B"
                st.markdown(
                    f"<div style='border:1px solid rgba(26,26,26,0.08);"
                    f"border-radius:4px;padding:0.55rem 0.8rem;margin-bottom:0.4rem;"
                    f"background:#fff;'>"
                    f'<span style=\'font-family:"DM Mono",monospace;font-weight:500;'
                    f"color:#1a1a1a;'>{sym}</span>"
                    f"&nbsp;<span style='color:{color};font-size:0.78rem;"
                    f'font-family:"DM Sans",sans-serif;font-weight:500;'
                    f"text-transform:uppercase;'>{side}</span><br>"
                    f'<span style=\'font-family:"DM Mono",monospace;font-size:0.78rem;'
                    f"color:#6b6b6b;'>{qty} shares | {otype}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
            if len(orders) > 8:
                st.caption(f"+{len(orders) - 8} more - see Portfolio page")
        else:
            st.markdown(
                '<p style=\'color:#9e9e9e;font-family:"DM Sans",sans-serif;'
                "font-size:0.85rem;padding:0.6rem 0;'>No open orders.</p>",
                unsafe_allow_html=True,
            )

    # --- Refresh ---
    st.markdown("---")
    st.markdown(
        '<p style=\'font-family:"DM Sans",sans-serif;font-size:0.75rem;'
        "color:#9e9e9e;'>Data refreshes on page reload.</p>",
        unsafe_allow_html=True,
    )
    if st.button("Refresh", key="home_refresh"):
        st.cache_data.clear()
        st.rerun()


if __name__ == "__main__":
    main()
