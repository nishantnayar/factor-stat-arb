"""factor-stat-arb dashboard (bare-bones skeleton).

A minimal tabbed shell to grow the Factor Lab into. The Overview tab is wired to
the real database so it doubles as a smoke test of the UI -> backend path; the
other tabs are placeholders for the milestones still to be built.

Run via the project entry point:  uv run main.py up streamlit
or directly:                      uv run streamlit run streamlit_ui/streamlit_app.py
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import streamlit as st  # noqa: E402

st.set_page_config(
    page_title="Factor Stat Arb",
    layout="wide",
    initial_sidebar_state="collapsed",
)


@st.cache_data(ttl=30)
def _db_status() -> dict:
    """Live universe/data counts from the app DB layer. Cached briefly."""
    from sqlalchemy import text

    from src.config.database import get_engine

    eng = get_engine("trading")
    with eng.connect() as conn:
        db = conn.execute(text("select current_database()")).scalar()
        symbols = conn.execute(
            text("select count(*) from data_ingestion.symbols")
        ).scalar()
        bars = conn.execute(
            text(
                "select count(*) from data_ingestion.market_data "
                "where data_source = 'yahoo_adjusted'"
            )
        ).scalar()
        latest = conn.execute(
            text(
                "select max(timestamp) from data_ingestion.market_data "
                "where data_source = 'yahoo_adjusted'"
            )
        ).scalar()
    return {"db": db, "symbols": symbols, "bars": bars, "latest": latest}


def render_overview() -> None:
    st.subheader("Overview")
    try:
        s = _db_status()
    except Exception as exc:  # noqa: BLE001
        st.error(f"Database not reachable: {exc}")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("Database", s["db"])
    c2.metric("Universe (symbols)", f"{s['symbols']:,}")
    c3.metric("Hourly bars", f"{s['bars']:,}")
    st.caption(f"Latest bar: {s['latest']}")


def render_placeholder(name: str, milestone: str) -> None:
    st.subheader(name)
    st.info(f"Not built yet - {milestone}. See docs/PROJECT_SPEC.md.")


def main() -> None:
    st.title("Factor Statistical Arbitrage")
    st.caption("Explainable factor-residual statistical arbitrage - paper trading only.")

    tab_overview, tab_factors, tab_signals, tab_backtest = st.tabs(
        ["Overview", "Factor Structure", "Signals", "Backtest"]
    )
    with tab_overview:
        render_overview()
    with tab_factors:
        render_placeholder("Factor Structure", "Milestone 1-2 (PCA + proxy mapping)")
    with tab_signals:
        render_placeholder("Signals", "Milestone 5 (confidence model + SHAP)")
    with tab_backtest:
        render_placeholder("Backtest", "Milestone 3 (factor backtest engine)")


main()
