"""
Strategy Monitor -- Live Monitoring for Pairs and Basket strategies.

Tabs:
  Pairs   -- z-scores, sparklines, risk controls, performance summary (FastAPI)
  Baskets -- active baskets, spread charts, open/closed trades (direct DB)
"""

import os
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from api_client import TradingSystemAPI  # noqa: E402
from utils import render_market_banner  # noqa: E402

from src.shared.database.base import db_readonly_session, db_transaction  # noqa: E402
from src.shared.database.models.strategy_models import (  # noqa: E402
    BasketRegistry,
    BasketSpread,
    BasketTrade,
    HarmonicTrade,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Strategy Monitor",
    page_icon="📡",
    layout="wide",
)

PLOTLY_CONFIG = {
    "displayModeBar": True,
    "displaylogo": False,
    "modeBarButtonsToRemove": ["pan2d", "lasso2d", "select2d"],
}

API_BASE = os.getenv("API_BASE_URL", "http://localhost:8001")
api = TradingSystemAPI(base_url=API_BASE)

COLOR_ENTRY = "rgba(255,60,60,0.7)"
COLOR_EXIT = "rgba(60,180,60,0.7)"
COLOR_ZERO = "rgba(150,150,150,0.4)"


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
# Pairs data fetchers
# ---------------------------------------------------------------------------


@st.cache_data(ttl=30)
def fetch_status():
    return api._make_request("GET", "/api/strategies/pairs/status")


@st.cache_data(ttl=30)
def fetch_active_pairs():
    data = api._make_request("GET", "/api/strategies/pairs/active")
    return data.get("pairs", [])


@st.cache_data(ttl=60)
def fetch_performance():
    return api._make_request("GET", "/api/strategies/pairs/performance")


@st.cache_data(ttl=30)
def fetch_pair_history(pair_id: int, days: int = 30):
    return api._make_request(
        "GET", f"/api/strategies/pairs/{pair_id}/history?days={days}"
    )


@st.cache_data(ttl=30)
def fetch_pair_details(pair_id: int):
    return api._make_request("GET", f"/api/strategies/pairs/{pair_id}/details")


@st.cache_data(ttl=30)
def fetch_risk_state():
    return api._make_request("GET", "/api/strategies/pairs/risk")


@st.cache_data(ttl=60)
def fetch_market_clock():
    return api._make_request("GET", "/clock")


@st.cache_data(ttl=60)
def fetch_pair_sparkline(pair_id: int, points: int = 48):
    return api._make_request(
        "GET", f"/api/strategies/pairs/{pair_id}/sparkline?points={points}"
    )


# ---------------------------------------------------------------------------
# Basket data helpers
# ---------------------------------------------------------------------------


@st.cache_data(ttl=30)
def load_all_baskets() -> List[dict]:
    try:
        with db_readonly_session() as session:
            baskets = (
                session.query(BasketRegistry)
                .order_by(BasketRegistry.rank_score.desc())
                .all()
            )
            result = []
            for b in baskets:
                latest = (
                    session.query(BasketSpread)
                    .filter(BasketSpread.basket_id == b.id)
                    .order_by(BasketSpread.timestamp.desc())
                    .first()
                )
                result.append(
                    {
                        "id": b.id,
                        "name": b.name or f"Basket-{b.id}",
                        "symbols": list(b.symbols or []),
                        "sector": b.sector or "--",
                        "half_life_hours": float(b.half_life_hours or 0),
                        "z_score_window": int(b.z_score_window or 30),
                        "entry_threshold": float(b.entry_threshold or 2.0),
                        "exit_threshold": float(b.exit_threshold or 0.5),
                        "rank_score": float(b.rank_score or 0),
                        "is_active": bool(b.is_active),
                        "current_z": (
                            float(latest.z_score)
                            if latest and latest.z_score is not None
                            else None
                        ),
                        "last_updated": (
                            latest.timestamp.isoformat() if latest else None
                        ),
                    }
                )
            return result
    except Exception as e:
        st.error(f"Failed to load baskets: {e}")
        return []


@st.cache_data(ttl=30)
def load_open_trades() -> List[dict]:
    try:
        with db_readonly_session() as session:
            trades = (
                session.query(BasketTrade)
                .filter(BasketTrade.status == "OPEN")
                .order_by(BasketTrade.entry_time.desc())
                .all()
            )
            result = []
            for t in trades:
                basket = session.get(BasketRegistry, t.basket_id)
                basket_name = (
                    basket.name if basket else None
                ) or f"Basket-{t.basket_id}"

                latest_spread = (
                    session.query(BasketSpread)
                    .filter(BasketSpread.basket_id == t.basket_id)
                    .order_by(BasketSpread.timestamp.desc())
                    .first()
                )
                unrealized_pnl = None
                if latest_spread and latest_spread.prices and t.legs:
                    pnl = 0.0
                    for leg in t.legs:
                        sym = leg.get("symbol")
                        ep = leg.get("entry_price") or 0.0
                        qty = leg.get("qty", 0)
                        side = leg.get("side", "buy")
                        cp = latest_spread.prices.get(sym)
                        if cp and ep:
                            sign = 1 if side == "buy" else -1
                            pnl += sign * qty * (float(cp) - float(ep))
                    unrealized_pnl = round(pnl, 2)

                hold_hours = None
                if t.entry_time:
                    entry = t.entry_time
                    if entry.tzinfo is None:
                        entry = entry.replace(tzinfo=timezone.utc)
                    hold_hours = round(
                        (datetime.now(timezone.utc) - entry).total_seconds() / 3600, 1
                    )

                result.append(
                    {
                        "id": t.id,
                        "basket_name": basket_name,
                        "side": t.side or "--",
                        "entry_time": (
                            t.entry_time.strftime("%Y-%m-%d %H:%M")
                            if t.entry_time
                            else "--"
                        ),
                        "entry_z": (
                            round(float(t.entry_z_score), 3)
                            if t.entry_z_score
                            else None
                        ),
                        "legs": t.legs or [],
                        "unrealized_pnl": unrealized_pnl,
                        "hold_hours": hold_hours,
                    }
                )
            return result
    except Exception as e:
        st.error(f"Failed to load open trades: {e}")
        return []


@st.cache_data(ttl=60)
def load_trade_history(limit: int = 50) -> List[dict]:
    try:
        with db_readonly_session() as session:
            trades = (
                session.query(BasketTrade)
                .filter(BasketTrade.status.in_(["CLOSED", "STOPPED"]))
                .order_by(BasketTrade.exit_time.desc())
                .limit(limit)
                .all()
            )
            result = []
            for t in trades:
                basket = session.get(BasketRegistry, t.basket_id)
                basket_name = (
                    basket.name if basket else None
                ) or f"Basket-{t.basket_id}"

                hold_hours = None
                if t.entry_time and t.exit_time:
                    entry = t.entry_time
                    ex = t.exit_time
                    if entry.tzinfo is None:
                        entry = entry.replace(tzinfo=timezone.utc)
                    if ex.tzinfo is None:
                        ex = ex.replace(tzinfo=timezone.utc)
                    hold_hours = round((ex - entry).total_seconds() / 3600, 1)

                result.append(
                    {
                        "basket_name": basket_name,
                        "side": t.side or "--",
                        "entry_z": (
                            round(float(t.entry_z_score), 3)
                            if t.entry_z_score
                            else None
                        ),
                        "exit_z": (
                            round(float(t.exit_z_score), 3) if t.exit_z_score else None
                        ),
                        "exit_reason": t.exit_reason or "--",
                        "hold_hours": hold_hours,
                        "pnl": round(float(t.pnl), 2) if t.pnl is not None else None,
                        "pnl_pct": (
                            round(float(t.pnl_pct) * 100, 3)
                            if t.pnl_pct is not None
                            else None
                        ),
                        "status": t.status,
                        "exit_time": (
                            t.exit_time.strftime("%Y-%m-%d %H:%M")
                            if t.exit_time
                            else "--"
                        ),
                    }
                )
            return result
    except Exception as e:
        st.error(f"Failed to load trade history: {e}")
        return []


@st.cache_data(ttl=30)
def load_spread_history(basket_id: int, limit: int = 200) -> List[dict]:
    try:
        with db_readonly_session() as session:
            rows = (
                session.query(BasketSpread)
                .filter(BasketSpread.basket_id == basket_id)
                .order_by(BasketSpread.timestamp.asc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "timestamp": r.timestamp,
                    "spread": float(r.spread) if r.spread is not None else None,
                    "z_score": float(r.z_score) if r.z_score is not None else None,
                }
                for r in rows
            ]
    except Exception as e:
        st.error(f"Failed to load spread history: {e}")
        return []


def set_basket_active(basket_id: int, active: bool) -> None:
    with db_transaction() as session:
        b = session.get(BasketRegistry, basket_id)
        if b:
            b.is_active = active


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fmt_time(ts_str) -> str:
    try:
        dt = datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
        return dt.strftime("%H:%M:%S")
    except Exception:
        return str(ts_str)[:19] if ts_str else "--"


def _z_color(z: Optional[float], entry_thr: float, exit_thr: float) -> str:
    if z is None:
        return "gray"
    if abs(z) > entry_thr:
        return "red"
    if abs(z) < exit_thr:
        return "green"
    return "orange"


def _fmt_z(z: Optional[float]) -> str:
    return f"{z:+.3f}" if z is not None else "--"


def _fmt_pnl(pnl: Optional[float]) -> str:
    if pnl is None:
        return "--"
    return f"${pnl:+,.2f}"


def _render_sparkline(z_values: list, entry_thr: float = 2.0) -> go.Figure:
    colours = [
        "red" if abs(z) > entry_thr else ("orange" if abs(z) > 1.5 else "#1f77b4")
        for z in z_values
    ]
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            y=z_values,
            mode="lines",
            line=dict(color="#1f77b4", width=1.5),
            showlegend=False,
            hovertemplate="z=%{y:.2f}<extra></extra>",
        )
    )
    if z_values:
        fig.add_trace(
            go.Scatter(
                x=[len(z_values) - 1],
                y=[z_values[-1]],
                mode="markers",
                marker=dict(color=colours[-1], size=6),
                showlegend=False,
                hoverinfo="skip",
            )
        )
    for level, color, dash in [
        (entry_thr, "rgba(255,60,60,0.5)", "dot"),
        (-entry_thr, "rgba(255,60,60,0.5)", "dot"),
        (0, "rgba(150,150,150,0.4)", "dot"),
    ]:
        fig.add_hline(y=level, line_color=color, line_dash=dash, line_width=1)
    fig.update_layout(
        height=70,
        margin=dict(l=0, r=0, t=4, b=4),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
    )
    return fig


# ---------------------------------------------------------------------------
# Tab renderers
# ---------------------------------------------------------------------------


def _render_pairs_tab() -> None:
    clock = fetch_market_clock()
    if "error" not in clock:
        render_market_banner(clock)

    status = fetch_status()
    if "error" not in status:
        is_active = status.get("is_active", False)
        last_update = status.get("last_update", "--")

        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Strategy", "Active" if is_active else "Inactive")
        col2.metric("Total Pairs", status.get("total_pairs", 0))
        col3.metric("Active Pairs", status.get("active_pairs", 0))
        col4.metric("Total P&L", f"${status.get('total_pnl', 0):,.2f}")
        col5.metric("Last Update", _fmt_time(last_update))

        bcol1, bcol2, bcol3, _ = st.columns([1, 1, 1, 5])
        with bcol1:
            if st.button("Start Strategy", type="primary"):
                r = api._make_request("POST", "/api/strategies/pairs/start")
                st.success(r.get("message", "Started"))
                st.cache_data.clear()
        with bcol2:
            if st.button("Stop Strategy"):
                r = api._make_request("POST", "/api/strategies/pairs/stop")
                st.info(r.get("message", "Stopped"))
                st.cache_data.clear()
        with bcol3:
            if st.button("Emergency Stop", type="secondary"):
                if st.session_state.get("confirm_estop"):
                    r = api._make_request(
                        "POST", "/api/strategies/pairs/emergency-stop"
                    )
                    st.error(r.get("message", "Emergency stop sent"))
                    st.session_state["confirm_estop"] = False
                    st.cache_data.clear()
                else:
                    st.session_state["confirm_estop"] = True
                    st.warning("Click again to confirm emergency stop")
    else:
        st.error("Could not reach API server. Is FastAPI running on port 8001?")

    risk = fetch_risk_state()
    if "error" not in risk:
        cb_active = risk.get("circuit_breaker_active", False)
        peak = risk.get("peak_equity")
        threshold = risk.get("drawdown_threshold", 0.05)
        triggered_at = risk.get("circuit_breaker_triggered_at")

        if cb_active:
            st.error(
                f"Circuit Breaker ACTIVE -- all new entries blocked. "
                f"Triggered: {triggered_at or 'unknown'}"
            )

        with st.expander("Risk Controls", expanded=cb_active):
            rc1, rc2, rc3, rc4 = st.columns(4)
            rc1.metric("Circuit Breaker", "ACTIVE" if cb_active else "CLEAR")
            rc2.metric("Peak Equity", f"${peak:,.2f}" if peak else "--")
            rc3.metric("Drawdown Threshold", f"{threshold * 100:.1f}%")
            with rc4:
                if cb_active:
                    if st.button("Reset Circuit Breaker", type="primary"):
                        api._make_request(
                            "POST",
                            "/api/strategies/pairs/risk/reset-circuit-breaker",
                        )
                        st.success("Circuit breaker reset")
                        st.cache_data.clear()
                new_threshold = st.number_input(
                    "Update threshold (%)",
                    min_value=1.0,
                    max_value=50.0,
                    value=float(threshold * 100),
                    step=0.5,
                    key="risk_threshold_input",
                )
                if st.button("Save Threshold"):
                    api._make_request(
                        "PUT",
                        "/api/strategies/pairs/risk/threshold",
                        json={"threshold": new_threshold / 100},
                    )
                    st.success(f"Threshold updated to {new_threshold:.1f}%")
                    st.cache_data.clear()

    st.divider()

    st.subheader("Active Pairs")
    pairs = fetch_active_pairs()

    if not pairs:
        st.info(
            "No active pairs found. Run `scripts/discover_pairs.py` and register pairs."
        )
        return

    h1, h2, h3, h4, h5 = st.columns([2, 1, 1, 1, 3])
    h1.markdown("**Pair**")
    h2.markdown("**Status**")
    h3.markdown("**Z-Score**")
    h4.markdown("**Unrealized P&L**")
    h5.markdown("**Z-Score (last 48 pts)**")
    st.divider()

    for p in pairs:
        pair_id = int(p["id"])
        z = p.get("z_score")
        pnl = p.get("pnl", 0.0)

        prev_key = f"prev_pnl_{pair_id}"
        prev_pnl = st.session_state.get(prev_key)
        pnl_delta = pnl - prev_pnl if prev_pnl is not None else None
        st.session_state[prev_key] = pnl

        if z is None:
            z_label = "--"
        elif abs(z) > 2.0:
            z_label = f"**:red[{z:.3f}]**"
        elif abs(z) > 1.5:
            z_label = f"**:orange[{z:.3f}]**"
        else:
            z_label = f"{z:.3f}"

        c1, c2, c3, c4, c5 = st.columns([2, 1, 1, 1, 3])
        c1.markdown(
            f"**{p['name']}**  \n<small>corr {p.get('correlation', 0):.3f} "
            f"· {p.get('days_held') or 0}d held</small>",
            unsafe_allow_html=True,
        )
        with c2:
            if p["status"] == "in_trade":
                st.badge("in_trade", color="blue")
            else:
                st.badge(p["status"], color="gray")
        c3.markdown(z_label)
        c4.metric(
            label="P&L",
            value=f"${pnl:,.2f}",
            delta=f"${pnl_delta:+,.2f}" if pnl_delta is not None else None,
            delta_color="normal",
        )

        spark_data = fetch_pair_sparkline(pair_id)
        if "error" not in spark_data:
            pts = spark_data.get("data", [])
            if pts:
                z_vals = [d["z"] for d in pts]
                c5.plotly_chart(
                    _render_sparkline(z_vals),
                    config={"displayModeBar": False},
                )
            else:
                c5.caption("No spread data yet")
        else:
            c5.caption("--")

    st.divider()

    st.subheader("Z-Score Chart")
    pair_names = [p["name"] for p in pairs]
    selected_name = st.selectbox("Select pair", pair_names)
    selected = next(p for p in pairs if p["name"] == selected_name)
    pair_id = int(selected["id"])

    days = st.slider("History (days)", 7, 90, 30)
    history_data = fetch_pair_history(pair_id, days)

    if "error" not in history_data:
        history = history_data.get("history", [])
        entry_thr = history_data.get("entry_threshold", 2.0)
        exit_thr = history_data.get("exit_threshold", 0.5)

        if history:
            hist_df = pd.DataFrame(history)
            hist_df["timestamp"] = pd.to_datetime(hist_df["timestamp"], unit="ms")
            hist_df = hist_df.dropna(subset=["z_score"])

            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=hist_df["timestamp"],
                    y=hist_df["z_score"],
                    mode="lines",
                    name="Z-Score",
                    line=dict(color="#1f77b4", width=1.5),
                )
            )
            for level, color, dash, label in [
                (entry_thr, "red", "dash", f"+{entry_thr} Entry"),
                (-entry_thr, "red", "dash", f"-{entry_thr} Entry"),
                (exit_thr, "green", "dot", f"+{exit_thr} Exit"),
                (-exit_thr, "green", "dot", f"-{exit_thr} Exit"),
                (0, "gray", "dot", "Zero"),
            ]:
                fig.add_hline(
                    y=level,
                    line_color=color,
                    line_dash=dash,
                    annotation_text=label,
                    annotation_position="right",
                )
            fig.update_layout(
                xaxis_title="Date",
                yaxis_title="Z-Score",
                height=360,
                template="none",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=0, r=60, t=30, b=0),
                legend=dict(orientation="h"),
            )
            st.plotly_chart(fig, config=PLOTLY_CONFIG)
        else:
            st.info("No spread history yet. Strategy must run at least one cycle.")

    st.divider()

    st.subheader("Performance Summary")
    perf = fetch_performance()
    if "error" not in perf:
        pc1, pc2, pc3, pc4, pc5 = st.columns(5)
        pc1.metric("Total P&L", f"${perf.get('total_pnl', 0):,.2f}")
        pc2.metric("Sharpe Ratio", f"{perf.get('sharpe_ratio', 0):.3f}")
        pc3.metric("Max Drawdown", f"{perf.get('max_drawdown', 0):.2f}%")
        pc4.metric("Win Rate", f"{perf.get('win_rate', 0)*100:.1f}%")
        pc5.metric("Avg Hold Time", f"{perf.get('avg_hold_time', 0):.1f}h")

    st.divider()

    with st.expander(f"Pair Details -- {selected_name}"):
        details = fetch_pair_details(pair_id)
        if "error" not in details:
            dc1, dc2, dc3, dc4 = st.columns(4)
            dc1.metric("Hedge Ratio", f"{details.get('hedge_ratio', 0):.4f}")
            dc2.metric("Half-Life", f"{details.get('half_life', '--')}h")
            dc3.metric(
                "Cointegration p", f"{details.get('cointegration_pvalue', 0):.4f}"
            )
            dc4.metric("Correlation", f"{details.get('correlation', 0):.3f}")

            open_trade = details.get("open_trade")
            if open_trade:
                st.markdown("**Open Trade**")
                st.json(open_trade)

            last_sig = details.get("last_signal")
            if last_sig:
                st.markdown(
                    f"**Last Signal:** `{last_sig.get('type')}` "
                    f"z={last_sig.get('z_score', 0):.3f}  "
                    f"@ {last_sig.get('timestamp', '')}"
                )


def _render_baskets_tab() -> None:
    st.caption("N-stock cointegrated baskets using Johansen weights. Direct DB access.")

    try:
        with db_readonly_session() as session:
            total_active = (
                session.query(BasketRegistry)
                .filter(BasketRegistry.is_active.is_(True))
                .count()
            )
            total_open = (
                session.query(BasketTrade).filter(BasketTrade.status == "OPEN").count()
            )
            closed_trades = (
                session.query(BasketTrade)
                .filter(BasketTrade.status.in_(["CLOSED", "STOPPED"]))
                .all()
            )
            closed_pnl = sum(float(t.pnl) for t in closed_trades if t.pnl is not None)
            open_trades_raw = (
                session.query(BasketTrade).filter(BasketTrade.status == "OPEN").all()
            )
            total_unrealized = 0.0
            for t in open_trades_raw:
                latest_spread = (
                    session.query(BasketSpread)
                    .filter(BasketSpread.basket_id == t.basket_id)
                    .order_by(BasketSpread.timestamp.desc())
                    .first()
                )
                if latest_spread and latest_spread.prices and t.legs:
                    for leg in t.legs:
                        sym = leg.get("symbol")
                        ep = leg.get("entry_price") or 0.0
                        qty = leg.get("qty", 0)
                        side = leg.get("side", "buy")
                        cp = latest_spread.prices.get(sym)
                        if cp and ep:
                            sign = 1 if side == "buy" else -1
                            total_unrealized += sign * qty * (float(cp) - float(ep))
    except Exception:
        total_active = total_open = 0
        closed_pnl = total_unrealized = 0.0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Active Baskets", total_active)
    m2.metric("Open Trades", total_open)
    m3.metric("Unrealized P&L", f"${total_unrealized:+,.2f}")
    m4.metric("Closed P&L (All Time)", f"${closed_pnl:+,.2f}")

    st.divider()

    st.subheader("Active Baskets")
    all_baskets = load_all_baskets()
    active_baskets = [b for b in all_baskets if b["is_active"]]

    if not all_baskets:
        st.info("No baskets registered. Run `scripts/discover_baskets.py` first.")
    else:
        show_inactive = st.checkbox("Show inactive baskets", value=False)
        display_baskets = all_baskets if show_inactive else active_baskets

        if not display_baskets:
            st.info("No active baskets. Activate one below or run discover_baskets.py.")
        else:
            hcols = st.columns([2.5, 3.0, 1.5, 1.2, 1.0, 1.2, 1.5, 1.5])
            for col, h in zip(
                hcols,
                [
                    "Name",
                    "Symbols",
                    "Sector",
                    "Half-life (h)",
                    "Z-win",
                    "Last Z",
                    "Status",
                    "Action",
                ],
            ):
                col.markdown(f"**{h}**")
            st.divider()

            for b in display_baskets:
                cols = st.columns([2.5, 3.0, 1.5, 1.2, 1.0, 1.2, 1.5, 1.5])
                z = b["current_z"]
                entry_thr = b["entry_threshold"]
                exit_thr = b["exit_threshold"]
                z_color = _z_color(z, entry_thr, exit_thr)
                z_str = _fmt_z(z)

                cols[0].markdown(f"**{b['name']}**")
                cols[1].write(", ".join(b["symbols"]))
                cols[2].write(b["sector"])
                cols[3].write(f"{b['half_life_hours']:.1f}")
                cols[4].write(b["z_score_window"])
                cols[5].markdown(f"**:{z_color}[{z_str}]**")
                with cols[6]:
                    if b["is_active"]:
                        st.badge("Active", color="green")
                    else:
                        st.badge("Inactive", color="gray")
                if b["is_active"]:
                    if cols[7].button("Deactivate", key=f"b_deact_{b['id']}"):
                        set_basket_active(b["id"], False)
                        st.cache_data.clear()
                        st.rerun()
                else:
                    if cols[7].button(
                        "Activate", key=f"b_act_{b['id']}", type="primary"
                    ):
                        set_basket_active(b["id"], True)
                        st.cache_data.clear()
                        st.rerun()

        st.divider()
        st.caption(
            "Z-score color: red = |z| > entry threshold, "
            "green = |z| < exit threshold, orange = between"
        )

    st.divider()

    st.subheader("Spread Charts")
    chart_baskets = active_baskets if active_baskets else all_baskets
    if not chart_baskets:
        st.info("No baskets to chart.")
    else:
        for b in chart_baskets:
            with st.expander(
                f"{b['name']}  ({', '.join(b['symbols'])})", expanded=False
            ):
                history = load_spread_history(b["id"], limit=200)
                if not history:
                    st.info("No spread data yet. Wait for the next flow cycle.")
                    continue

                ts = [r["timestamp"] for r in history]
                spreads = [r["spread"] for r in history]
                zscores = [r["z_score"] for r in history]

                fig = go.Figure()
                fig.add_trace(
                    go.Scatter(
                        x=ts,
                        y=spreads,
                        name="Spread",
                        line=dict(color="#1f77b4", width=1.5),
                        yaxis="y1",
                    )
                )
                fig.add_trace(
                    go.Scatter(
                        x=ts,
                        y=zscores,
                        name="Z-score",
                        line=dict(color="#ff7f0e", width=1.5, dash="dot"),
                        yaxis="y2",
                    )
                )
                entry_thr = b["entry_threshold"]
                for level, color, dash in [
                    (entry_thr, COLOR_ENTRY, "dot"),
                    (-entry_thr, COLOR_ENTRY, "dot"),
                    (0, COLOR_ZERO, "dot"),
                ]:
                    fig.add_hline(
                        y=level,
                        line_color=color,
                        line_dash=dash,
                        line_width=1,
                        yref="y2",
                    )
                fig.update_layout(
                    height=300,
                    margin=dict(l=0, r=0, t=20, b=20),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    legend=dict(orientation="h", y=1.0),
                    yaxis=dict(title="Spread"),
                    yaxis2=dict(
                        title="Z-score", overlaying="y", side="right", showgrid=False
                    ),
                    xaxis=dict(title=""),
                )
                st.plotly_chart(fig, width="stretch", config=PLOTLY_CONFIG)

    st.divider()

    st.subheader("Open Trades")
    open_trades = load_open_trades()
    if not open_trades:
        st.info("No open basket trades.")
    else:
        hcols = st.columns([2.0, 1.2, 1.5, 1.0, 1.0, 3.0, 1.5])
        for col, h in zip(
            hcols,
            [
                "Basket",
                "Side",
                "Entry Time",
                "Entry Z",
                "Hold (h)",
                "Legs",
                "Unreal. P&L",
            ],
        ):
            col.markdown(f"**{h}**")
        st.divider()
        for t in open_trades:
            cols = st.columns([2.0, 1.2, 1.5, 1.0, 1.0, 3.0, 1.5])
            legs_str = ", ".join(
                f"{l.get('symbol')} {l.get('side','?').upper()} x{l.get('qty',0)}"
                for l in t["legs"]
            )
            pnl = t["unrealized_pnl"]
            pnl_color = (
                "green" if pnl and pnl > 0 else ("red" if pnl and pnl < 0 else "")
            )
            cols[0].markdown(f"**{t['basket_name']}**")
            cols[1].write(t["side"])
            cols[2].write(t["entry_time"])
            cols[3].write(_fmt_z(t["entry_z"]))
            cols[4].write(f"{t['hold_hours']}h" if t["hold_hours"] else "--")
            cols[5].write(legs_str)
            if pnl_color:
                cols[6].markdown(f"**:{pnl_color}[{_fmt_pnl(pnl)}]**")
            else:
                cols[6].write(_fmt_pnl(pnl))
        st.divider()

    st.divider()

    st.subheader("Trade History (Last 50)")
    history = load_trade_history(limit=50)
    if not history:
        st.info("No closed basket trades yet.")
    else:
        hcols = st.columns([2.0, 1.2, 1.0, 1.0, 1.5, 1.0, 1.2, 1.2, 1.5])
        for col, h in zip(
            hcols,
            [
                "Basket",
                "Side",
                "Entry Z",
                "Exit Z",
                "Exit Reason",
                "Hold (h)",
                "P&L",
                "P&L %",
                "Exit Time",
            ],
        ):
            col.markdown(f"**{h}**")
        st.divider()
        for t in history:
            cols = st.columns([2.0, 1.2, 1.0, 1.0, 1.5, 1.0, 1.2, 1.2, 1.5])
            pnl = t["pnl"]
            pnl_color = (
                "green" if pnl and pnl > 0 else ("red" if pnl and pnl < 0 else "")
            )
            cols[0].write(t["basket_name"])
            cols[1].write(t["side"])
            cols[2].write(_fmt_z(t["entry_z"]))
            cols[3].write(_fmt_z(t["exit_z"]))
            cols[4].write(t["exit_reason"])
            cols[5].write(f"{t['hold_hours']}h" if t["hold_hours"] else "--")
            pnl_str = _fmt_pnl(pnl)
            pnl_pct_str = f"{t['pnl_pct']:+.3f}%" if t["pnl_pct"] is not None else "--"
            if pnl_color:
                cols[6].markdown(f"**:{pnl_color}[{pnl_str}]**")
                cols[7].markdown(f":{pnl_color}[{pnl_pct_str}]")
            else:
                cols[6].write(pnl_str)
                cols[7].write(pnl_pct_str)
            cols[8].write(t["exit_time"])
        st.divider()

    if st.button("Refresh Data"):
        st.cache_data.clear()
        st.rerun()


# ---------------------------------------------------------------------------
# Harmonic data helpers
# ---------------------------------------------------------------------------


@st.cache_data(ttl=30)
def load_harmonic_open_trades() -> List[dict]:
    try:
        with db_readonly_session() as session:
            trades = (
                session.query(HarmonicTrade)
                .filter(HarmonicTrade.status == "OPEN")
                .order_by(HarmonicTrade.entry_time.desc())
                .all()
            )
            result = []
            for t in trades:
                entry = t.entry_time
                if entry and entry.tzinfo is None:
                    entry = entry.replace(tzinfo=timezone.utc)
                hold_hours = (
                    round(
                        (datetime.now(timezone.utc) - entry).total_seconds() / 3600, 1
                    )
                    if entry
                    else None
                )
                result.append(
                    {
                        "id": t.id,
                        "symbol": t.symbol,
                        "pattern": t.pattern,
                        "direction": t.direction,
                        "side": t.side,
                        "qty": t.qty,
                        "entry_price": float(t.entry_price) if t.entry_price else None,
                        "entry_time": (
                            entry.strftime("%Y-%m-%d %H:%M") if entry else "--"
                        ),
                        "stop_loss": float(t.stop_loss) if t.stop_loss else None,
                        "target_1": float(t.target_1) if t.target_1 else None,
                        "target_2": float(t.target_2) if t.target_2 else None,
                        "x_price": float(t.x_price) if t.x_price else None,
                        "a_price": float(t.a_price) if t.a_price else None,
                        "b_price": float(t.b_price) if t.b_price else None,
                        "c_price": float(t.c_price) if t.c_price else None,
                        "d_price": float(t.d_price) if t.d_price else None,
                        "hold_hours": hold_hours,
                        "status": t.status,
                    }
                )
            return result
    except Exception as e:
        st.error(f"Failed to load harmonic trades: {e}")
        return []


@st.cache_data(ttl=60)
def load_harmonic_closed_trades(limit: int = 50) -> List[dict]:
    try:
        with db_readonly_session() as session:
            trades = (
                session.query(HarmonicTrade)
                .filter(HarmonicTrade.status.in_(["CLOSED", "STOPPED"]))
                .order_by(HarmonicTrade.exit_time.desc())
                .limit(limit)
                .all()
            )
            result = []
            for t in trades:
                entry = t.entry_time
                ex = t.exit_time
                if entry and entry.tzinfo is None:
                    entry = entry.replace(tzinfo=timezone.utc)
                if ex and ex.tzinfo is None:
                    ex = ex.replace(tzinfo=timezone.utc)
                hold_hours = (
                    round((ex - entry).total_seconds() / 3600, 1)
                    if entry and ex
                    else None
                )
                result.append(
                    {
                        "symbol": t.symbol,
                        "pattern": t.pattern,
                        "direction": t.direction,
                        "side": t.side,
                        "qty": t.qty,
                        "entry_price": float(t.entry_price) if t.entry_price else None,
                        "exit_price": float(t.exit_price) if t.exit_price else None,
                        "exit_reason": t.exit_reason or "--",
                        "hold_hours": hold_hours,
                        "pnl": float(t.pnl) if t.pnl is not None else None,
                        "pnl_pct": float(t.pnl_pct) if t.pnl_pct is not None else None,
                        "status": t.status,
                        "exit_time": (ex.strftime("%Y-%m-%d %H:%M") if ex else "--"),
                    }
                )
            return result
    except Exception as e:
        st.error(f"Failed to load harmonic trade history: {e}")
        return []


@st.cache_data(ttl=60)
def load_harmonic_summary() -> dict:
    try:
        with db_readonly_session() as session:
            open_count = (
                session.query(HarmonicTrade)
                .filter(HarmonicTrade.status == "OPEN")
                .count()
            )
            closed = (
                session.query(HarmonicTrade)
                .filter(HarmonicTrade.status.in_(["CLOSED", "STOPPED"]))
                .all()
            )
            closed_pnl = sum(float(t.pnl) for t in closed if t.pnl is not None)
            wins = sum(1 for t in closed if t.pnl is not None and float(t.pnl) > 0)
            win_rate = wins / len(closed) if closed else 0.0
            return {
                "open_trades": open_count,
                "closed_trades": len(closed),
                "closed_pnl": closed_pnl,
                "win_rate": win_rate,
            }
    except Exception as e:
        st.error(f"Failed to load harmonic summary: {e}")
        return {
            "open_trades": 0,
            "closed_trades": 0,
            "closed_pnl": 0.0,
            "win_rate": 0.0,
        }


def _render_xabcd_chart(trade: dict) -> go.Figure:
    """Mini XABCD price-level chart for a single harmonic trade row."""
    labels = ["X", "A", "B", "C", "D"]
    prices = [
        trade.get("x_price"),
        trade.get("a_price"),
        trade.get("b_price"),
        trade.get("c_price"),
        trade.get("d_price"),
    ]

    fig = go.Figure()

    if all(p is not None for p in prices):
        fig.add_trace(
            go.Scatter(
                x=labels,
                y=prices,
                mode="lines+markers+text",
                text=[f"{p:.2f}" for p in prices],
                textposition="top center",
                line=dict(color="#1f77b4", width=1.5),
                marker=dict(size=6, color="#1f77b4"),
                showlegend=False,
            )
        )

    d = trade["d_price"] or 0
    sl = trade["stop_loss"] or 0
    t1 = trade["target_1"] or 0
    t2 = trade["target_2"] or 0

    for y, color, label in [
        (t2, "#2A7A4B", "T2"),
        (t1, "#58A87A", "T1"),
        (d, "#1f77b4", "D (entry)"),
        (sl, "#C0392B", "SL"),
    ]:
        fig.add_hline(
            y=y,
            line_color=color,
            line_dash="dot",
            line_width=1.5,
            annotation_text=f"{label} {y:.2f}",
            annotation_position="right",
        )
    fig.update_layout(
        height=140,
        margin=dict(l=0, r=70, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=all(p is not None for p in prices)),
        yaxis=dict(visible=False),
        showlegend=False,
    )
    return fig


def _render_harmonic_tab() -> None:
    st.caption(
        "Gartley harmonic pattern trades. "
        "Patterns detected daily from EOD price data (yahoo_adjusted)."
    )

    summary = load_harmonic_summary()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Open Trades", summary["open_trades"])
    m2.metric("Closed Trades", summary["closed_trades"])
    m3.metric(
        "Closed P&L",
        f"${summary['closed_pnl']:+,.2f}",
    )
    m4.metric("Win Rate", f"{summary['win_rate'] * 100:.1f}%")

    st.divider()

    # ---- Open trades ----
    st.subheader("Open Trades")
    open_trades = load_harmonic_open_trades()

    if not open_trades:
        st.info(
            "No open harmonic trades. "
            "Run the harmonic flow or wait for the next scheduled scan."
        )
    else:
        hcols = st.columns([1.2, 1.2, 1.0, 1.0, 1.2, 1.0, 1.2, 1.2, 1.0, 3.0])
        for col, h in zip(
            hcols,
            [
                "Symbol",
                "Pattern",
                "Direction",
                "Side",
                "Entry Price",
                "Qty",
                "Stop Loss",
                "Target 1",
                "Hold (h)",
                "Levels",
            ],
        ):
            col.markdown(f"**{h}**")
        st.divider()

        for t in open_trades:
            cols = st.columns([1.2, 1.2, 1.0, 1.0, 1.2, 1.0, 1.2, 1.2, 1.0, 3.0])
            dir_color = "green" if t["direction"] == "bullish" else "red"
            cols[0].markdown(f"**{t['symbol']}**")
            cols[1].write(t["pattern"].capitalize())
            cols[2].markdown(f"**:{dir_color}[{t['direction'].capitalize()}]**")
            cols[3].write(t["side"].upper())
            cols[4].write(f"${t['entry_price']:.4f}" if t["entry_price"] else "--")
            cols[5].write(t["qty"])
            cols[6].markdown(f":red[${t['stop_loss']:.4f}]" if t["stop_loss"] else "--")
            cols[7].markdown(f":green[${t['target_1']:.4f}]" if t["target_1"] else "--")
            cols[8].write(f"{t['hold_hours']}h" if t["hold_hours"] else "--")
            if t["d_price"]:
                cols[9].plotly_chart(
                    _render_xabcd_chart(t),
                    config={"displayModeBar": False},
                    width="stretch",
                )
            else:
                cols[9].write("--")
        st.divider()

    st.divider()

    # ---- Trade history ----
    st.subheader("Trade History (Last 50)")
    history = load_harmonic_closed_trades(limit=50)

    if not history:
        st.info("No closed harmonic trades yet.")
    else:
        hcols = st.columns([1.2, 1.2, 1.0, 1.2, 1.2, 1.5, 1.0, 1.2, 1.2, 1.5])
        for col, h in zip(
            hcols,
            [
                "Symbol",
                "Pattern",
                "Direction",
                "Entry Price",
                "Exit Price",
                "Exit Reason",
                "Hold (h)",
                "P&L",
                "P&L %",
                "Exit Time",
            ],
        ):
            col.markdown(f"**{h}**")
        st.divider()

        for t in history:
            cols = st.columns([1.2, 1.2, 1.0, 1.2, 1.2, 1.5, 1.0, 1.2, 1.2, 1.5])
            pnl = t["pnl"]
            pnl_color = (
                "green" if pnl and pnl > 0 else ("red" if pnl and pnl < 0 else "")
            )
            dir_color = "green" if t["direction"] == "bullish" else "red"
            pnl_str = _fmt_pnl(pnl)
            pnl_pct_str = f"{t['pnl_pct']:+.3f}%" if t["pnl_pct"] is not None else "--"
            cols[0].markdown(f"**{t['symbol']}**")
            cols[1].write(t["pattern"].capitalize())
            cols[2].markdown(f":{dir_color}[{t['direction'].capitalize()}]")
            cols[3].write(f"${t['entry_price']:.4f}" if t["entry_price"] else "--")
            cols[4].write(f"${t['exit_price']:.4f}" if t["exit_price"] else "--")
            cols[5].write(t["exit_reason"])
            cols[6].write(f"{t['hold_hours']}h" if t["hold_hours"] else "--")
            if pnl_color:
                cols[7].markdown(f"**:{pnl_color}[{pnl_str}]**")
                cols[8].markdown(f":{pnl_color}[{pnl_pct_str}]")
            else:
                cols[7].write(pnl_str)
                cols[8].write(pnl_pct_str)
            cols[9].write(t["exit_time"])
        st.divider()

    if st.button("Refresh Harmonic Data"):
        st.cache_data.clear()
        st.rerun()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    _load_css()
    st.title("Strategy Monitor")

    tab_pairs, tab_baskets, tab_harmonic = st.tabs(["Pairs", "Baskets", "Harmonic"])

    with tab_pairs:
        _render_pairs_tab()

    with tab_baskets:
        _render_baskets_tab()

    with tab_harmonic:
        _render_harmonic_tab()


if __name__ == "__main__" or True:
    main()
