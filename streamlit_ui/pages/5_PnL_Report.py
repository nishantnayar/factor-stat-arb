"""
P&L Report -- Realized performance across all pairs trades.

Sections:
  1. Summary KPIs (total P&L, win rate, profit factor, avg hold)
  2. Cumulative equity curve
  3. Daily P&L bar chart
  4. Monthly heatmap / table
  5. Per-pair attribution bar chart
  6. Full trade log table with filters
"""

import os
import sys
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from api_client import TradingSystemAPI
from utils import render_market_banner

st.set_page_config(
    page_title="P&L Report",
    page_icon="📊",
    layout="wide",
)

PLOTLY_CFG = {"displayModeBar": False}
PLOTLY_CFG_FULL = {
    "displayModeBar": True,
    "displaylogo": False,
    "modeBarButtonsToRemove": ["pan2d", "lasso2d", "select2d"],
}

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8001")
api = TradingSystemAPI(base_url=API_BASE)


def _load_css() -> None:
    css_file = os.path.join(os.path.dirname(__file__), "..", "styles.css")
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


# ---------------------------------------------------------------------------
# Data fetchers (cached)
# ---------------------------------------------------------------------------


@st.cache_data(ttl=60)
def fetch_summary():
    return api._make_request("GET", "/api/strategies/pairs/pnl/summary")


@st.cache_data(ttl=60)
def fetch_daily(days: int):
    return api._make_request("GET", f"/api/strategies/pairs/pnl/daily?days={days}")


@st.cache_data(ttl=60)
def fetch_monthly():
    return api._make_request("GET", "/api/strategies/pairs/pnl/monthly")


@st.cache_data(ttl=60)
def fetch_trades(days: int):
    return api._make_request("GET", f"/api/strategies/pairs/pnl/trades?days={days}")


@st.cache_data(ttl=60)
def fetch_clock():
    return api._make_request("GET", "/clock")


# ---------------------------------------------------------------------------
# Chart helpers
# ---------------------------------------------------------------------------


def _equity_curve(series: list) -> go.Figure:
    df = pd.DataFrame(series)
    if df.empty:
        return go.Figure()
    df["date"] = pd.to_datetime(df["date"])
    pos = df["cumulative_pnl"] >= 0
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["cumulative_pnl"],
            mode="lines",
            fill="tozeroy",
            fillcolor="rgba(0,200,100,0.15)",
            line=dict(color="#00c864", width=2),
            name="Cumulative P&L",
            hovertemplate="%{x|%Y-%m-%d}<br>$%{y:,.2f}<extra></extra>",
        )
    )
    fig.add_hline(y=0, line_color="rgba(150,150,150,0.5)", line_dash="dot")
    fig.update_layout(
        height=280,
        margin=dict(l=0, r=0, t=30, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis_title=None,
        yaxis_title="Cumulative P&L ($)",
        yaxis=dict(tickprefix="$", tickformat=",.0f"),
        template="none",
        showlegend=False,
        title="Cumulative Realized P&L",
    )
    return fig


def _daily_bar(series: list) -> go.Figure:
    df = pd.DataFrame(series)
    if df.empty:
        return go.Figure()
    df["date"] = pd.to_datetime(df["date"])
    colors = ["#00c864" if v >= 0 else "#e05252" for v in df["daily_pnl"]]
    fig = go.Figure(
        go.Bar(
            x=df["date"],
            y=df["daily_pnl"],
            marker_color=colors,
            hovertemplate="%{x|%Y-%m-%d}<br>$%{y:,.2f}<extra></extra>",
        )
    )
    fig.add_hline(y=0, line_color="rgba(150,150,150,0.5)", line_dash="dot")
    fig.update_layout(
        height=220,
        margin=dict(l=0, r=0, t=30, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis_title=None,
        yaxis=dict(tickprefix="$", tickformat=",.0f"),
        template="none",
        title="Daily Realized P&L",
    )
    return fig


def _pair_attribution(per_pair: list) -> go.Figure:
    if not per_pair:
        return go.Figure()
    df = pd.DataFrame(per_pair).sort_values("total_pnl")
    colors = ["#00c864" if v >= 0 else "#e05252" for v in df["total_pnl"]]
    fig = go.Figure(
        go.Bar(
            x=df["total_pnl"],
            y=df["pair"],
            orientation="h",
            marker_color=colors,
            hovertemplate="%{y}<br>$%{x:,.2f}<extra></extra>",
        )
    )
    fig.add_vline(x=0, line_color="rgba(150,150,150,0.5)", line_dash="dot")
    fig.update_layout(
        height=max(200, len(df) * 50),
        margin=dict(l=0, r=0, t=30, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(tickprefix="$", tickformat=",.0f"),
        yaxis_title=None,
        template="none",
        title="P&L by Pair (all-time)",
    )
    return fig


def _monthly_table(monthly: list) -> pd.DataFrame:
    if not monthly:
        return pd.DataFrame()
    rows = []
    for m in monthly:
        rows.append(
            {
                "Month": m["month"],
                "P&L ($)": m["total_pnl"],
                "Trades": m["trade_count"],
                "Win Rate": f"{m['win_rate'] * 100:.1f}%",
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    _load_css()
    st.title("P&L Report")

    clock = fetch_clock()
    if "error" not in clock:
        render_market_banner(clock)

    # ---- Sidebar filters ----
    with st.sidebar:
        st.header("Filters")
        days = st.selectbox("Lookback period", [30, 60, 90, 180, 365], index=2)
        st.caption("Affects trade log and daily chart.")

    # ---- Summary ----
    summary = fetch_summary()
    if "error" in summary:
        st.error("Could not reach API server. Is FastAPI running on port 8001?")
        return

    total_pnl = summary.get("total_pnl", 0.0)
    total_trades = summary.get("total_trades", 0)
    win_rate = summary.get("win_rate", 0.0)
    avg_pnl_pct = summary.get("avg_pnl_pct", 0.0)
    profit_factor = summary.get("profit_factor")
    per_pair = summary.get("per_pair", [])

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Total Realized P&L", f"${total_pnl:,.2f}", border=True)
    k2.metric("Total Trades", total_trades, border=True)
    k3.metric("Win Rate", f"{win_rate * 100:.1f}%", border=True)
    k4.metric("Avg Trade Return", f"{avg_pnl_pct * 100:.2f}%", border=True)
    k5.metric(
        "Profit Factor",
        f"{profit_factor:.2f}" if profit_factor is not None else "--",
        border=True,
    )

    if total_trades == 0:
        st.info(
            "No closed trades yet. The P&L report will populate once trades complete."
        )
        return

    st.divider()

    # ---- Equity curve + daily bar ----
    daily_data = fetch_daily(days)
    series = daily_data.get("series", []) if "error" not in daily_data else []

    col_left, col_right = st.columns([3, 2])
    with col_left:
        if series:
            st.plotly_chart(
                _equity_curve(series), config=PLOTLY_CFG_FULL, width="stretch"
            )
        else:
            st.info("No daily P&L data for the selected period.")
    with col_right:
        if series:
            st.plotly_chart(_daily_bar(series), config=PLOTLY_CFG, width="stretch")

    st.divider()

    # ---- Per-pair attribution + monthly table ----
    col_attr, col_month = st.columns([2, 3])
    with col_attr:
        if per_pair:
            st.plotly_chart(
                _pair_attribution(per_pair), config=PLOTLY_CFG, width="stretch"
            )

    with col_month:
        monthly_data = fetch_monthly()
        monthly = monthly_data.get("monthly", []) if "error" not in monthly_data else []
        if monthly:
            st.subheader("Monthly Breakdown")
            mdf = _monthly_table(monthly)

            # colour P&L column
            def _pnl_style(val):
                color = "#00c864" if val >= 0 else "#e05252"
                return f"color: {color}; font-weight: bold"

            styled = mdf.style.map(_pnl_style, subset=["P&L ($)"]).format(
                {"P&L ($)": "${:,.2f}"}
            )
            st.dataframe(styled, width="stretch", hide_index=True)
        else:
            st.info("No monthly data yet.")

    st.divider()

    # ---- Per-pair stats table ----
    if per_pair:
        st.subheader("Per-Pair Statistics")
        pp_df = pd.DataFrame(per_pair)
        pp_df = pp_df.rename(
            columns={
                "pair": "Pair",
                "total_pnl": "Total P&L ($)",
                "trade_count": "Trades",
                "win_rate": "Win Rate",
                "avg_pnl_pct": "Avg Return (%)",
                "avg_hold_hours": "Avg Hold (h)",
                "stop_losses": "Stop Losses",
            }
        )
        pp_df["Win Rate"] = pp_df["Win Rate"].apply(lambda x: f"{x * 100:.1f}%")
        pp_df["Avg Return (%)"] = pp_df["Avg Return (%)"].apply(
            lambda x: f"{x * 100:.2f}%" if x is not None else "--"
        )

        def _pnl_row_style(val):
            color = "#00c864" if val >= 0 else "#e05252"
            return f"color: {color}; font-weight: bold"

        pp_styled = pp_df.style.map(_pnl_row_style, subset=["Total P&L ($)"]).format(
            {"Total P&L ($)": "${:,.2f}"}
        )
        st.dataframe(pp_styled, width="stretch", hide_index=True)

    st.divider()

    # ---- Trade log ----
    st.subheader("Trade Log")
    trades_data = fetch_trades(days)
    trades = trades_data.get("trades", []) if "error" not in trades_data else []

    if not trades:
        st.info(f"No closed trades in the last {days} days.")
        return

    tdf = pd.DataFrame(trades)

    # Sidebar pair filter (applied client-side)
    pair_options = ["All"] + sorted(tdf["pair_name"].unique().tolist())
    with st.sidebar:
        pair_filter = st.selectbox("Filter by pair", pair_options)
    if pair_filter != "All":
        tdf = tdf[tdf["pair_name"] == pair_filter]

    # Sidebar exit reason filter
    with st.sidebar:
        reason_options = ["All"] + sorted(tdf["exit_reason"].dropna().unique().tolist())
        reason_filter = st.selectbox("Exit reason", reason_options)
    if reason_filter != "All":
        tdf = tdf[tdf["exit_reason"] == reason_filter]

    # Format for display
    display_cols = [
        "pair_name",
        "side",
        "status",
        "entry_time",
        "exit_time",
        "hold_hours",
        "entry_z_score",
        "exit_z_score",
        "pnl",
        "pnl_pct",
        "exit_reason",
    ]
    tdf_disp = tdf[display_cols].copy()
    tdf_disp = tdf_disp.rename(
        columns={
            "pair_name": "Pair",
            "side": "Side",
            "status": "Status",
            "entry_time": "Entry",
            "exit_time": "Exit",
            "hold_hours": "Hold (h)",
            "entry_z_score": "Entry Z",
            "exit_z_score": "Exit Z",
            "pnl": "P&L ($)",
            "pnl_pct": "Return (%)",
            "exit_reason": "Reason",
        }
    )
    tdf_disp["Entry"] = pd.to_datetime(tdf_disp["Entry"]).dt.strftime("%Y-%m-%d %H:%M")
    tdf_disp["Exit"] = pd.to_datetime(tdf_disp["Exit"]).dt.strftime("%Y-%m-%d %H:%M")
    tdf_disp["Return (%)"] = tdf_disp["Return (%)"].apply(
        lambda x: f"{x * 100:.2f}%" if x is not None else "--"
    )

    def _pnl_cell(val):
        if val is None:
            return ""
        color = "#00c864" if val >= 0 else "#e05252"
        return f"color: {color}; font-weight: bold"

    trade_styled = tdf_disp.style.map(_pnl_cell, subset=["P&L ($)"]).format(
        {"P&L ($)": lambda x: f"${x:,.2f}" if x is not None else "--"}
    )
    st.dataframe(trade_styled, width="stretch", hide_index=True)
    st.caption(f"Showing {len(tdf_disp)} trades | Last {days} days")


if __name__ == "__main__" or True:
    main()
