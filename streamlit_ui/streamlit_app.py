"""factor-stat-arb dashboard (bare-bones skeleton).

A minimal tabbed shell to grow the Factor Lab into. The Overview tab is wired to
the real database so it doubles as a smoke test of the UI -> backend path; the
other tabs are placeholders for the milestones still to be built.

Run via the project entry point:  uv run main.py up streamlit
or directly:                      uv run streamlit run streamlit_ui/streamlit_app.py
"""

import sys
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402

from src.services.strategy_engine.factor_stat_arb.confidence_model import (  # noqa: E402
    ConfidenceModel,
)

st.set_page_config(
    page_title="Factor Statistical Arbitrage",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Single-hue sequential ramp (light -> dark) for magnitude encodings, and one
# fixed accent for single-series lines. Keeps every chart on one axis/one hue.
SEQUENTIAL_HUE = "#4C6FFF"
LINE_COLOR = "#4C6FFF"
BAND_COLOR = "rgba(76, 111, 255, 0.15)"
MUTED_INK = "#6B7280"


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


@st.cache_data(ttl=600)
def _factor_structure(var_threshold: float, lookback_bars: Optional[int]) -> dict:
    """Fit the PCA factor model live (not persisted anywhere) and summarize it."""
    from src.services.strategy_engine.factor_stat_arb.data import load_return_matrix
    from src.services.strategy_engine.factor_stat_arb.factor_model import FactorModel
    from src.services.strategy_engine.factor_stat_arb.proxies import (
        load_universe_symbols,
    )

    universe = load_universe_symbols()
    returns = load_return_matrix(symbols=universe, lookback_bars=lookback_bars)
    if returns.empty:
        return {}

    fm = FactorModel(var_threshold=var_threshold).fit(returns)
    assert fm.loadings_ is not None and fm.symbols_ is not None
    loadings = fm.loadings_
    top_loadings = {
        pc: loadings[pc].abs().sort_values(ascending=False).head(10)
        for pc in loadings.columns[:5]
    }
    return {
        "k": fm.k_,
        "total_variance": fm.total_variance_explained(),
        "explained_variance_ratio": fm.explained_variance_ratio_,
        "n_symbols": len(fm.symbols_),
        "n_bars": len(returns),
        "top_loadings": top_loadings,
    }


def render_factor_structure() -> None:
    st.subheader("Factor Structure")
    st.caption(
        "PCA is fit live from the current universe on each load (not cached in "
        "the DB) - results shift as the data window and universe roll forward."
    )

    c1, c2 = st.columns(2)
    var_threshold = c1.slider("Target variance explained", 0.3, 0.9, 0.6, 0.05)
    lookback_bars = c2.number_input(
        "Lookback (hourly bars, 0 = all)", min_value=0, value=0, step=500
    )

    try:
        s = _factor_structure(var_threshold, lookback_bars or None)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not fit factor model: {exc}")
        return
    if not s:
        st.warning("No return data available for the current universe.")
        return

    m1, m2, m3 = st.columns(3)
    m1.metric("Components retained", s["k"])
    m2.metric("Variance explained", f"{s['total_variance']:.0%}")
    m3.metric("Universe", f"{s['n_symbols']} symbols, {s['n_bars']} bars")

    evr = s["explained_variance_ratio"]
    cumulative = evr.cumsum()
    pcs = [f"PC{i + 1}" for i in range(len(evr))]

    fig = go.Figure()
    fig.add_bar(x=pcs, y=evr, marker_color=SEQUENTIAL_HUE, name="Per-component")
    fig.add_trace(
        go.Scatter(
            x=pcs,
            y=cumulative,
            mode="lines+markers",
            line=dict(color=MUTED_INK, width=2),
            marker=dict(size=6),
            name="Cumulative",
            yaxis="y2",
        )
    )
    fig.update_layout(
        yaxis=dict(title="Variance explained (per component)", tickformat=".0%"),
        yaxis2=dict(
            title="Cumulative",
            tickformat=".0%",
            overlaying="y",
            side="right",
            range=[0, 1],
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(t=40, b=20),
        height=380,
    )
    st.plotly_chart(fig, width="stretch")

    st.markdown("**Top loadings by component**")
    pc_choice = st.selectbox("Component", list(s["top_loadings"].keys()))
    loadings = s["top_loadings"][pc_choice]
    st.bar_chart(loadings)


@st.cache_data(ttl=30)
def _basket_registry() -> pd.DataFrame:
    from sqlalchemy import text

    from src.config.database import get_engine

    eng = get_engine("trading")
    with eng.connect() as conn:
        df = pd.read_sql(
            text(
                "SELECT id, name, sector, symbols, hedge_weights, half_life_hours, "
                "min_correlation AS proxy_r2, z_score_abs_mean, rank_score, "
                "is_active, last_validated, notes "
                "FROM strategy_engine.basket_registry "
                "ORDER BY rank_score DESC"
            ),
            conn,
        )
    return df


@st.cache_data(ttl=60)
def _basket_spread_series(
    symbols: tuple, hedge_weights: dict, lookback_bars: int
) -> pd.DataFrame:
    """Recompute the spread + rolling z-score live (basket_spread table isn't populated)."""
    from src.services.strategy_engine.factor_stat_arb.data import load_price_matrix
    from src.services.strategy_engine.factor_stat_arb.residual_ou import (
        build_log_spread,
        fit_ou,
    )

    prices = load_price_matrix(symbols=list(symbols))
    if prices.empty:
        return pd.DataFrame()
    if lookback_bars:
        prices = prices.iloc[-lookback_bars:]

    spread = build_log_spread(prices, hedge_weights)
    ou = fit_ou(spread)
    window = (
        min(max(int(round(ou.half_life)), 10), len(spread) - 1)
        if ou.mean_reverting
        else 60
    )
    window = max(window, 10)
    roll_mean = spread.rolling(window, min_periods=window // 2).mean()
    roll_std = spread.rolling(window, min_periods=window // 2).std()
    z = (spread - roll_mean) / roll_std

    return pd.DataFrame(
        {
            "spread": spread,
            "z_score": z,
            "ou_mu": ou.mu,
            "ou_half_life": ou.half_life,
            "ou_sigma_eq": ou.sigma_eq,
        }
    )


def render_basket_registry() -> None:
    st.subheader("Basket Registry")
    st.caption(
        "Discovered factor-residual baskets (strategy_engine.basket_registry). "
        "New candidates land with is_active=false pending manual review."
    )

    try:
        df = _basket_registry()
    except Exception as exc:  # noqa: BLE001
        st.error(f"Database not reachable: {exc}")
        return
    if df.empty:
        st.info("No baskets discovered yet. Run scripts/discover_factor_baskets.py.")
        return

    c1, c2 = st.columns(2)
    status_choice = c1.selectbox("Status", ["All", "Active", "Pending"])
    sectors = ["All"] + sorted(df["sector"].dropna().unique().tolist())
    sector_choice = c2.selectbox("Sector", sectors)

    view = df.copy()
    if status_choice == "Active":
        view = view[view["is_active"]]
    elif status_choice == "Pending":
        view = view[~view["is_active"]]
    if sector_choice != "All":
        view = view[view["sector"] == sector_choice]

    st.dataframe(
        view[
            [
                "name",
                "sector",
                "proxy_r2",
                "half_life_hours",
                "z_score_abs_mean",
                "rank_score",
                "is_active",
                "last_validated",
            ]
        ],
        width="stretch",
        hide_index=True,
    )

    st.markdown("**Basket detail**")
    basket_name = st.selectbox("Select a basket", view["name"].tolist())
    row = view[view["name"] == basket_name].iloc[0]

    weights = row["hedge_weights"]
    betas_str = " + ".join(
        f"{v:+.2f} {k}" for k, v in weights.items() if k != row["symbols"][0]
    )
    st.markdown(
        f"`{row['symbols'][0]}` trades like `{betas_str.lstrip('+ ')}` "
        f"(proxy R2 = {row['proxy_r2']:.2f}, half-life = {row['half_life_hours']:.0f}h)"
    )

    lookback_bars = st.number_input(
        "Lookback for spread chart (bars, 0 = all)", min_value=0, value=2000, step=500
    )
    try:
        series = _basket_spread_series(
            tuple(row["symbols"]), weights, lookback_bars or 0
        )
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not compute spread series: {exc}")
        return
    if series.empty:
        st.warning("No price history available for this basket's symbols.")
        return

    mu = float(series["ou_mu"].iloc[0])
    sigma_eq = float(series["ou_sigma_eq"].iloc[0])

    fig = go.Figure()
    if pd.notna(sigma_eq):
        fig.add_hrect(
            y0=mu - sigma_eq, y1=mu + sigma_eq, fillcolor=BAND_COLOR, line_width=0
        )
    fig.add_trace(
        go.Scatter(
            x=series.index,
            y=series["spread"],
            mode="lines",
            line=dict(color=LINE_COLOR, width=1.5),
            name="Residual spread",
        )
    )
    fig.add_hline(y=mu, line=dict(color=MUTED_INK, width=1, dash="dash"))
    fig.update_layout(
        title="Log-price spread with OU mean +/- equilibrium std",
        margin=dict(t=40, b=20),
        height=320,
        showlegend=False,
    )
    st.plotly_chart(fig, width="stretch")

    fig_z = go.Figure()
    fig_z.add_trace(
        go.Scatter(
            x=series.index,
            y=series["z_score"],
            mode="lines",
            line=dict(color=LINE_COLOR, width=1.5),
            name="Z-score",
        )
    )
    for level, dash in ((2.0, "dash"), (-2.0, "dash"), (0.0, "dot")):
        fig_z.add_hline(y=level, line=dict(color=MUTED_INK, width=1, dash=dash))
    fig_z.update_layout(
        title="Rolling z-score (entry threshold +/- 2.0 shown)",
        margin=dict(t=40, b=20),
        height=280,
        showlegend=False,
    )
    st.plotly_chart(fig_z, width="stretch")


def render_placeholder(name: str, milestone: str) -> None:
    st.subheader(name)
    st.info(f"Not built yet - {milestone}. See docs/PROJECT_SPEC.md.")


@st.cache_resource
def _load_confidence_model() -> Optional["ConfidenceModel"]:
    import joblib

    path = PROJECT_ROOT / "models" / "confidence_model.joblib"
    if not path.exists():
        return None
    model: ConfidenceModel = joblib.load(path)
    return model


def render_signals() -> None:
    from src.services.strategy_engine.factor_stat_arb.confidence_model import (
        FEATURE_COLUMNS,
        volume_regime,
    )

    st.subheader("Signals")
    st.caption(
        "Confidence model (LightGBM) + SHAP explanation per candidate basket. "
        "Trained on simulated backtest trades via scripts/train_confidence_model.py."
    )

    model = _load_confidence_model()
    if model is None:
        st.info(
            "No trained confidence model found. Run "
            "`uv run scripts/train_confidence_model.py` after backtesting "
            "discovered baskets."
        )
        return

    try:
        df = _basket_registry()
    except Exception as exc:  # noqa: BLE001
        st.error(f"Database not reachable: {exc}")
        return
    if df.empty:
        st.info("No baskets discovered yet. Run scripts/discover_factor_baskets.py.")
        return

    basket_name = st.selectbox("Select a basket", df["name"].tolist())
    row = df[df["name"] == basket_name].iloc[0]

    with st.spinner("Computing volume regime..."):
        vol_regime = volume_regime(list(row["symbols"]))

    features = pd.DataFrame(
        [
            {
                "half_life_hours": row["half_life_hours"],
                "proxy_r2": row["proxy_r2"],
                "z_score_abs_mean": row["z_score_abs_mean"],
                "rank_score": row["rank_score"],
                "sector": row["sector"],
                "volume_regime": vol_regime,
            }
        ]
    )[FEATURE_COLUMNS]

    try:
        proba = model.predict_proba(features)[0]
        shap_values = model.explain(features)[0]
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not score basket: {exc}")
        return

    st.metric("Confidence (P profitable)", f"{proba:.0%}")

    contrib = pd.Series(shap_values, index=FEATURE_COLUMNS).sort_values()
    st.markdown("**SHAP contribution per feature**")
    st.bar_chart(contrib)


def main() -> None:
    st.title("Factor Statistical Arbitrage")
    st.caption(
        "Explainable factor-residual statistical arbitrage - paper trading only."
    )

    tab_overview, tab_factors, tab_registry, tab_signals, tab_backtest = st.tabs(
        ["Overview", "Factor Structure", "Basket Registry", "Signals", "Backtest"]
    )
    with tab_overview:
        render_overview()
    with tab_factors:
        render_factor_structure()
    with tab_registry:
        render_basket_registry()
    with tab_signals:
        render_signals()
    with tab_backtest:
        render_placeholder("Backtest", "Milestone 3 (factor backtest engine)")


main()
