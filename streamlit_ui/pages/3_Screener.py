"""
Stock Screener Page with Local LLM Integration
Filter stocks by technical and fundamental criteria with AI-powered analysis
"""

import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st
from loguru import logger
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode

# Add parent directory to path
parent_dir = os.path.dirname(os.path.dirname(__file__))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from streamlit_ui.api_client import get_api_client  # noqa: E402
from streamlit_ui.services.llm_service import LLMService, get_llm_service  # noqa: E402
from streamlit_ui.utils import (  # noqa: E402
    format_number,
    get_real_market_data,
    show_loading_spinner,
)

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

SECTOR_VARIATIONS: Dict[str, List[str]] = {
    "finance": ["financial", "finance", "banking", "bank", "financial services"],
    "technology": ["tech", "technology", "software", "information technology"],
    "healthcare": ["health", "healthcare", "medical", "pharmaceutical"],
    "energy": ["energy", "oil", "gas", "petroleum"],
    "consumer": ["consumer", "retail", "consumer goods"],
}

SORT_OPTIONS = [
    "None",
    "RSI (highest first)",
    "RSI (lowest first)",
    "Price Change 30d (best first)",
    "Price Change 30d (worst first)",
    "Market Cap (largest first)",
    "Price (highest first)",
    "Volatility (highest first)",
]

SORT_KEY_MAP = {
    "RSI (highest first)": ("rsi", True),
    "RSI (lowest first)": ("rsi", False),
    "Price Change 30d (best first)": ("price_change_30d", True),
    "Price Change 30d (worst first)": ("price_change_30d", False),
    "Market Cap (largest first)": ("market_cap", True),
    "Price (highest first)": ("current_price", True),
    "Volatility (highest first)": ("volatility", True),
}

# sort_by values returned by LLM → (field, descending)
LLM_SORT_MAP = {
    "rsi_desc": ("rsi", True),
    "rsi_asc": ("rsi", False),
    "price_change_desc": ("price_change_30d", True),
    "price_change_asc": ("price_change_30d", False),
    "market_cap_desc": ("market_cap", True),
    "price_desc": ("current_price", True),
}

# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------

if "screener_results" not in st.session_state:
    st.session_state.screener_results = []
if "screener_query" not in st.session_state:
    st.session_state.screener_query = ""
if "screener_chat_history" not in st.session_state:
    st.session_state.screener_chat_history = []


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------


def load_custom_css():
    css_file = os.path.join(os.path.dirname(__file__), "..", "styles.css")
    try:
        with open(css_file, "r") as f:
            css_content = f.read()
        from streamlit_ui.css_config import generate_css_variables, get_theme_css

        full_css = generate_css_variables() + css_content + get_theme_css()
        st.markdown(f"<style>{full_css}</style>", unsafe_allow_html=True)
    except Exception as e:
        st.warning(f"Error loading CSS: {e}")


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------


def get_indicators_for_symbol_from_db(
    symbol: str,
    ohlc_data: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Get all technical indicators for a symbol from the database."""
    from utils import get_latest_technical_indicators

    if not ohlc_data:
        return {}

    latest_indicators = get_latest_technical_indicators(symbol)

    closing_prices = [item["close"] for item in ohlc_data]
    volumes = [item.get("volume", 0) for item in ohlc_data]

    if not latest_indicators:
        return {
            "symbol": symbol,
            "current_price": closing_prices[-1] if closing_prices else None,
            "current_volume": volumes[-1] if volumes else 0,
        }

    return {
        "symbol": symbol,
        "current_price": closing_prices[-1] if closing_prices else None,
        "sma_20": latest_indicators.get("sma_20"),
        "sma_50": latest_indicators.get("sma_50"),
        "rsi": (latest_indicators.get("rsi_14") or latest_indicators.get("rsi")),
        "price_change_1d": latest_indicators.get("price_change_1d"),
        "price_change_5d": latest_indicators.get("price_change_5d"),
        "price_change_30d": latest_indicators.get("price_change_30d"),
        "volatility": latest_indicators.get("volatility_20"),
        "macd": latest_indicators.get("macd_line"),
        "macd_signal": latest_indicators.get("macd_signal"),
        "macd_histogram": latest_indicators.get("macd_histogram"),
        "bb_position": latest_indicators.get("bb_position"),
        "avg_volume": latest_indicators.get("avg_volume_20"),
        "current_volume": (
            volumes[-1] if volumes else latest_indicators.get("current_volume")
        ),
    }


def _sector_matches(sector_criteria: str, stock_sector: str) -> bool:
    """Case-insensitive sector match with common alias expansion."""
    sc = sector_criteria.lower()
    ss = stock_sector.lower()
    if sc in ss or ss == sc:
        return True
    for key, variations in SECTOR_VARIATIONS.items():
        if sc in key or key in sc:
            if any(var in ss for var in variations):
                return True
    return False


def _compute_signal(stock: Dict[str, Any]) -> str:
    """Derive a human-readable signal badge from indicator values."""
    rsi = stock.get("rsi")
    macd_h = stock.get("macd_histogram")

    if rsi is not None and rsi < 30:
        return "Oversold"
    if rsi is not None and rsi > 70:
        return "Overbought"
    if macd_h is not None and macd_h > 0 and rsi is not None and rsi < 50:
        return "Bullish"
    if macd_h is not None and macd_h < 0 and rsi is not None and rsi > 50:
        return "Bearish"
    return "Neutral"


def _format_criteria_readable(criteria: Dict[str, Any]) -> str:
    """Convert a criteria dict into a human-readable summary string."""
    parts = []
    if criteria.get("sector"):
        parts.append(f"**{criteria['sector']}** sector")
    if criteria.get("industry"):
        parts.append(f"industry: *{criteria['industry']}*")
    if criteria.get("min_price") or criteria.get("max_price"):
        lo = f"${criteria['min_price']:.0f}" if criteria.get("min_price") else "$0"
        hi = f"${criteria['max_price']:.0f}" if criteria.get("max_price") else "any"
        parts.append(f"price {lo}–{hi}")
    if criteria.get("rsi_min") or criteria.get("rsi_max"):
        lo = criteria.get("rsi_min", 0)
        hi = criteria.get("rsi_max", 100)
        parts.append(f"RSI {lo:.0f}–{hi:.0f}")
    if criteria.get("min_volume"):
        parts.append(f"min vol {format_number(criteria['min_volume'])}")
    if criteria.get("min_market_cap"):
        parts.append(f"mkt cap ≥ ${criteria['min_market_cap']:.1f}B")
    sort_by = criteria.get("sort_by")
    if sort_by and sort_by in LLM_SORT_MAP:
        field, desc = LLM_SORT_MAP[sort_by]
        direction = "highest" if desc else "lowest"
        parts.append(f"sorted by {direction} {field.replace('_', ' ')}")
    if criteria.get("keywords"):
        parts.append(f"keywords: {', '.join(criteria['keywords'])}")
    if not parts:
        return "No filters applied — showing all stocks."
    return "Searching for " + " · ".join(parts)


# ---------------------------------------------------------------------------
# Core screening logic
# ---------------------------------------------------------------------------


def screen_stocks(
    api_client,
    llm_service: Optional[LLMService],  # noqa: F841
    criteria: Dict[str, Any],
    symbols: List[str],
    query: str = "",
) -> List[Dict[str, Any]]:
    """
    Screen stocks based on criteria dict.

    sort_by and limit are handled here; the caller does not need to sort
    the results. The query parameter is used only for logging.
    """
    results = []
    total = len(symbols)
    status = st.status(f"Screening {total} symbols...", expanded=True)

    for idx, symbol in enumerate(symbols):
        try:
            status.update(label=f"Processing {symbol} ({idx + 1}/{total})...")

            ohlc_data = get_real_market_data(
                _api_client=api_client,
                symbol=symbol,
                data_source="yahoo",
            )
            if not ohlc_data:
                logger.debug(f"Skipping {symbol}: no market data")
                continue

            indicators = get_indicators_for_symbol_from_db(symbol, ohlc_data)

            company_info = api_client.get_company_info(symbol)
            if "error" not in company_info:
                indicators.update(
                    {
                        "name": company_info.get("name", symbol),
                        "sector": company_info.get("sector"),
                        "industry": company_info.get("industry"),
                        "market_cap": (
                            company_info.get("marketCap")
                            or company_info.get("market_cap")
                        ),
                    }
                )

            if not criteria:
                results.append(indicators)
                continue

            matches = True

            # Sector
            if matches and criteria.get("sector"):
                stock_sector = indicators.get("sector") or ""
                if not _sector_matches(criteria["sector"], stock_sector):
                    matches = False

            # Industry
            if matches and criteria.get("industry"):
                ind_c = criteria["industry"].lower()
                ind_s = (indicators.get("industry") or "").lower()
                if ind_c not in ind_s and ind_s != ind_c:
                    matches = False

            # Price
            if matches and indicators.get("current_price"):
                p = indicators["current_price"]
                if criteria.get("min_price") and p < criteria["min_price"]:
                    matches = False
                if criteria.get("max_price") and p > criteria["max_price"]:
                    matches = False

            # Volume
            if matches and criteria.get("min_volume"):
                if (indicators.get("avg_volume") or 0) < criteria["min_volume"]:
                    matches = False

            # Market cap
            if matches and criteria.get("min_market_cap"):
                mc = indicators.get("market_cap") or 0
                mc_b = mc / 1_000_000_000
                if mc_b < criteria["min_market_cap"]:
                    matches = False

            # RSI (skip range filter when sort_by is rsi-based)
            sort_by = criteria.get("sort_by", "")
            rsi_sort = sort_by in ("rsi_desc", "rsi_asc")
            if matches and not rsi_sort and indicators.get("rsi") is not None:
                rsi = indicators["rsi"]
                if criteria.get("rsi_min") and rsi < criteria["rsi_min"]:
                    matches = False
                if criteria.get("rsi_max") and rsi > criteria["rsi_max"]:
                    matches = False

            # 30d price change
            if matches:
                chg = indicators.get("price_change_30d")
                if chg is not None:
                    if (
                        criteria.get("min_price_change_pct") is not None
                        and chg < criteria["min_price_change_pct"]
                    ):
                        matches = False
                    if (
                        criteria.get("max_price_change_pct") is not None
                        and chg > criteria["max_price_change_pct"]
                    ):
                        matches = False

            # 1d price change
            if matches and criteria.get("min_price_change_1d") is not None:
                chg1d = indicators.get("price_change_1d")
                if chg1d is not None and chg1d < criteria["min_price_change_1d"]:
                    matches = False

            # 5d price change
            if matches and criteria.get("min_price_change_5d") is not None:
                chg5d = indicators.get("price_change_5d")
                if chg5d is not None and chg5d < criteria["min_price_change_5d"]:
                    matches = False

            # Volatility
            if matches and criteria.get("max_volatility") is not None:
                vol = indicators.get("volatility")
                if vol is not None and vol > criteria["max_volatility"]:
                    matches = False

            # MACD signal
            if matches and criteria.get("macd_signal"):
                macd_h = indicators.get("macd_histogram")
                if macd_h is not None:
                    if criteria["macd_signal"] == "bullish" and macd_h <= 0:
                        matches = False
                    elif criteria["macd_signal"] == "bearish" and macd_h >= 0:
                        matches = False

            # Bollinger Band position
            if matches:
                bb = indicators.get("bb_position")
                if bb is not None:
                    if criteria.get("bb_min") is not None and bb < criteria["bb_min"]:
                        matches = False
                    if criteria.get("bb_max") is not None and bb > criteria["bb_max"]:
                        matches = False

            # SMA crossover
            if matches and criteria.get("sma_crossover"):
                sma20 = indicators.get("sma_20")
                sma50 = indicators.get("sma_50")
                price = indicators.get("current_price")
                xover = criteria["sma_crossover"]
                if xover == "above_sma20" and (
                    price is None or sma20 is None or price <= sma20
                ):
                    matches = False
                elif xover == "below_sma20" and (
                    price is None or sma20 is None or price >= sma20
                ):
                    matches = False
                elif xover == "golden_cross" and (
                    sma20 is None or sma50 is None or sma20 <= sma50
                ):
                    matches = False
                elif xover == "death_cross" and (
                    sma20 is None or sma50 is None or sma20 >= sma50
                ):
                    matches = False

            # Keywords (company name / symbol)
            if matches and criteria.get("keywords"):
                search_text = " ".join(
                    str(indicators.get(f, "") or "")
                    for f in ("symbol", "name", "sector", "industry")
                ).lower()
                kw_matched = False
                for kw in criteria["keywords"]:
                    kw_lower = kw.lower()
                    if kw_lower in search_text:
                        kw_matched = True
                        break
                    # Also try sector alias expansion
                    for key, variations in SECTOR_VARIATIONS.items():
                        if kw_lower in key or key in kw_lower:
                            stock_sector = (indicators.get("sector") or "").lower()
                            if any(v in stock_sector for v in variations):
                                kw_matched = True
                                break
                    if kw_matched:
                        break
                if not kw_matched:
                    matches = False

            if matches:
                results.append(indicators)
                logger.debug(f"Match: {symbol} - {indicators.get('name', 'N/A')}")

        except Exception as e:
            logger.error(f"Error processing {symbol}: {e}")
            status.write(f":warning: Error processing {symbol}: {e}")
            continue

    status.update(
        label=f"Screened {total} symbols - {len(results)} matches",
        state="complete",
        expanded=False,
    )

    # Sort results
    sort_by = criteria.get("sort_by") if criteria else None
    manual_sort = criteria.get("manual_sort") if criteria else None

    if sort_by and sort_by in LLM_SORT_MAP:
        field, descending = LLM_SORT_MAP[sort_by]
        default = -1 if descending else float("inf")
        results.sort(
            key=lambda x: (x.get(field) or default),
            reverse=descending,
        )
        if len(results) > 10:
            results = results[:10]
    elif manual_sort and manual_sort in SORT_KEY_MAP:
        field, descending = SORT_KEY_MAP[manual_sort]
        default = -1 if descending else float("inf")
        results.sort(
            key=lambda x: (x.get(field) or default),
            reverse=descending,
        )

    return results


# ---------------------------------------------------------------------------
# Results display
# ---------------------------------------------------------------------------


def _build_results_df(results: List[Dict[str, Any]]) -> pd.DataFrame:
    """Build a DataFrame with numeric columns for proper AgGrid sorting."""
    rows = []
    for s in results:
        macd_h = s.get("macd_histogram")
        signal = _compute_signal(s)
        rows.append(
            {
                "Symbol": s.get("symbol", "N/A"),
                "Name": s.get("name", "N/A"),
                "Sector": s.get("sector", "N/A"),
                "Signal": signal,
                "Price": s.get("current_price"),
                "RSI": s.get("rsi"),
                "1d %": s.get("price_change_1d"),
                "5d %": s.get("price_change_5d"),
                "30d %": s.get("price_change_30d"),
                "Volatility": s.get("volatility"),
                "MACD Hist": macd_h,
                "BB Pos": s.get("bb_position"),
                "SMA 20": s.get("sma_20"),
                "Avg Vol": s.get("avg_volume"),
                "Mkt Cap": s.get("market_cap"),
            }
        )
    return pd.DataFrame(rows)


def _configure_aggrid(df: pd.DataFrame):
    """Build AgGrid options with cell styling and value formatters."""
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_pagination(paginationAutoPageSize=True)
    gb.configure_side_bar()
    gb.configure_default_column(
        groupable=True, sortable=True, filterable=True, resizable=True
    )

    # RSI colour coding
    rsi_style = JsCode("""
    function(params) {
        if (params.value == null) return {};
        if (params.value < 30)
            return {'backgroundColor': '#1a4731', 'color': '#4ade80'};
        if (params.value > 70)
            return {'backgroundColor': '#4b1a1a', 'color': '#f87171'};
        return {};
    }
    """)
    rsi_fmt = JsCode("function(p){return p.value==null?'N/A':p.value.toFixed(1);}")
    gb.configure_column("RSI", cellStyle=rsi_style, valueFormatter=rsi_fmt, width=80)

    # Signal badge colours
    signal_style = JsCode("""
    function(params) {
        const v = params.value;
        if (v === 'Oversold')  return {color:'#4ade80', fontWeight:'bold'};
        if (v === 'Overbought') return {color:'#f87171', fontWeight:'bold'};
        if (v === 'Bullish')   return {color:'#60a5fa', fontWeight:'bold'};
        if (v === 'Bearish')   return {color:'#fb923c', fontWeight:'bold'};
        return {color:'#9ca3af'};
    }
    """)
    gb.configure_column("Signal", cellStyle=signal_style, width=110)

    # Numeric formatters (keep values numeric so sorting works)
    price_fmt = JsCode(
        "function(p){return p.value==null?'N/A':'$'+p.value.toFixed(2);}"
    )
    pct_fmt = JsCode(
        "function(p){return p.value==null?'N/A':"
        "(p.value>=0?'+':'')+p.value.toFixed(1)+'%';}"
    )
    mc_fmt = JsCode("""
    function(p) {
        if (p.value == null) return 'N/A';
        const b = p.value / 1e9;
        return b >= 1 ? '$'+b.toFixed(1)+'B' : '$'+(p.value/1e6).toFixed(0)+'M';
    }
    """)
    vol_fmt = JsCode("""
    function(p) {
        if (p.value == null) return 'N/A';
        if (p.value >= 1e6) return (p.value/1e6).toFixed(1)+'M';
        if (p.value >= 1e3) return (p.value/1e3).toFixed(0)+'K';
        return p.value.toFixed(0);
    }
    """)
    f2_fmt = JsCode("function(p){return p.value==null?'N/A':p.value.toFixed(2);}")

    gb.configure_column("Price", valueFormatter=price_fmt, width=90)
    gb.configure_column("1d %", valueFormatter=pct_fmt, width=80)
    gb.configure_column("5d %", valueFormatter=pct_fmt, width=80)
    gb.configure_column("30d %", valueFormatter=pct_fmt, width=85)
    gb.configure_column(
        "Volatility",
        valueFormatter=JsCode(
            "function(p){return p.value==null?'N/A':p.value.toFixed(1)+'%';}"
        ),
        width=95,
    )
    gb.configure_column("MACD Hist", valueFormatter=f2_fmt, width=100)
    gb.configure_column("BB Pos", valueFormatter=f2_fmt, width=85)
    gb.configure_column("SMA 20", valueFormatter=price_fmt, width=90)
    gb.configure_column("Avg Vol", valueFormatter=vol_fmt, width=95)
    gb.configure_column("Mkt Cap", valueFormatter=mc_fmt, width=100)

    return gb.build()


def display_results(
    results: List[Dict[str, Any]],
    llm_service: Optional[LLMService],
    query: str,
):
    """Render the AI analysis, results table, chat panel, and CSV download."""
    st.markdown("---")
    st.subheader("Screening Results")

    # AI Analysis
    if llm_service and query:
        with st.expander("AI Analysis", expanded=True):
            with show_loading_spinner("Generating AI analysis..."):
                analysis = llm_service.analyze_screened_results(results, query=query)
                st.write(analysis)

    # Results table
    df = _build_results_df(results)
    grid_opts = _configure_aggrid(df)
    AgGrid(
        df,
        gridOptions=grid_opts,
        theme="streamlit",
        height=420,
        allow_unsafe_jscode=True,
    )

    # CSV export
    export_df = df.copy()
    csv = export_df.to_csv(index=False)
    st.download_button(
        label="Download Results as CSV",
        data=csv,
        file_name=(f"screener_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"),
        mime="text/csv",
    )

    # Chat panel
    if llm_service:
        with st.expander("Ask a follow-up question about these results"):
            chat_history = st.session_state.screener_chat_history
            # Render prior exchanges
            for msg in chat_history:
                role = msg["role"]
                with st.chat_message(role):
                    st.write(msg["content"])
            # New question input
            col_q, col_btn = st.columns([5, 1])
            with col_q:
                follow_up = st.text_input(
                    "Your question:",
                    key="screener_chat_input",
                    label_visibility="collapsed",
                    placeholder="e.g. Which of these has the best risk/reward?",
                )
            with col_btn:
                ask_btn = st.button("Ask", key="screener_ask_btn")

            if ask_btn and follow_up:
                with show_loading_spinner("Thinking..."):
                    answer = llm_service.chat_about_results(
                        results=results,
                        history=chat_history,
                        question=follow_up,
                    )
                chat_history.append({"role": "user", "content": follow_up})
                chat_history.append({"role": "assistant", "content": answer})
                # Trim to last 6 turns
                if len(chat_history) > 6:
                    st.session_state.screener_chat_history = chat_history[-6:]
                st.rerun()


# ---------------------------------------------------------------------------
# Main page
# ---------------------------------------------------------------------------


def screener_page():
    st.set_page_config(layout="wide", page_title="Stock Screener - AI Powered")
    load_custom_css()

    st.title("Stock Screener with AI Analysis")
    st.write(
        "Filter stocks using natural language or traditional filters, "
        "powered by your local LLM."
    )

    api_client = get_api_client()

    with show_loading_spinner("Connecting to API..."):
        health = api_client.health_check()
        if "error" in health:
            st.error("Failed to connect to API. Please check your connection.")
            return

    # ---- Sidebar ----
    with st.sidebar:
        st.header("Screener Settings")
        symbol_limit = st.slider(
            "Symbols to screen", min_value=10, max_value=200, value=50, step=10
        )

        st.subheader("LLM Settings")
        llm_service: Optional[LLMService] = None
        try:
            # Use a temporary service to discover available models
            temp_svc = LLMService(model="phi3")
            model_info = temp_svc.get_model_info()
            available = [m["name"] for m in model_info["available_models"]]
        except Exception:
            available = []

        if available:
            default_model = "phi3" if "phi3" in available else available[0]
            selected_model = st.selectbox(
                "Ollama model",
                available,
                index=(
                    available.index(default_model) if default_model in available else 0
                ),
            )
        else:
            selected_model = st.text_input("Ollama model (manual)", value="phi3")

        try:
            with show_loading_spinner("Initialising LLM..."):
                llm_service = get_llm_service(model=selected_model)
            st.success(f"LLM ready ({selected_model})")
        except Exception as e:
            st.warning(f"LLM not available: {e}. Traditional filters still work.")

    # ---- Tabs ----
    tab1, tab2 = st.tabs(["Natural Language Query", "Traditional Filters"])

    # ------------------------------------------------------------------ Tab 1
    with tab1:
        st.subheader("Ask in Natural Language")
        st.caption("Example: 'Find oversold tech stocks with RSI < 30 and high volume'")

        query = st.text_input(
            "Enter your screening query:",
            value=st.session_state.screener_query,
            placeholder="e.g., Find undervalued tech stocks with RSI < 30",
        )

        col1, col2, _ = st.columns([1, 1, 3])
        with col1:
            search_button = st.button("Search", type="primary", width="stretch")
        with col2:
            clear_button = st.button("Clear", type="secondary", width="stretch")

        if clear_button:
            st.session_state.screener_results = []
            st.session_state.screener_query = ""
            st.session_state.screener_chat_history = []
            st.rerun()

        if search_button and query:
            st.session_state.screener_query = query
            st.session_state.screener_chat_history = []

            criteria: Dict[str, Any] = {}
            if llm_service:
                with show_loading_spinner("Interpreting query..."):
                    try:
                        criteria = llm_service.interpret_screening_query(query)
                    except Exception as e:
                        st.error(f"Error interpreting query: {e}")
                        criteria = {}
                # Human-readable interpretation
                readable = _format_criteria_readable(criteria)
                st.info(readable)
            else:
                st.warning("LLM not available. Please use the Traditional Filters tab.")

            with show_loading_spinner("Loading symbols..."):
                try:
                    all_syms = api_client.get_all_symbols()
                    if "error" not in all_syms and all_syms:
                        symbols = [
                            s.get("symbol", "") for s in all_syms if s.get("symbol")
                        ]
                    else:
                        symbols = _fallback_symbols()
                except Exception:
                    symbols = _fallback_symbols()
                st.info(f"Screening {min(len(symbols), symbol_limit)} symbols...")

            with show_loading_spinner("Screening stocks..."):
                try:
                    results = screen_stocks(
                        api_client,
                        llm_service,
                        criteria,
                        symbols[:symbol_limit],
                        query=query,
                    )
                    st.session_state.screener_results = results
                except Exception as e:
                    st.error(f"Error during screening: {e}")
                    import traceback as tb

                    st.code(tb.format_exc())
                    results = []

            if results:
                st.success(f"Found {len(results)} matching stocks")
            else:
                _show_no_results_tips()

    # ------------------------------------------------------------------ Tab 2
    with tab2:
        st.subheader("Traditional Filter Options")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.write("**Sector & Industry**")
            sectors = api_client.get_sectors() if "error" not in health else []
            selected_sector = st.selectbox("Sector", ["All"] + sectors)
            if selected_sector != "All":
                industries = (
                    api_client.get_industries(sector=selected_sector)
                    if "error" not in health
                    else []
                )
            else:
                industries = (
                    api_client.get_industries() if "error" not in health else []
                )
            selected_industry = st.selectbox("Industry", ["All"] + industries)

        with col2:
            st.write("**Price & Volume**")
            min_price = st.number_input(
                "Min Price ($)", min_value=0.0, value=0.0, step=1.0
            )
            max_price = st.number_input(
                "Max Price ($)", min_value=0.0, value=0.0, step=1.0
            )
            min_volume = st.number_input(
                "Min Avg Volume", min_value=0, value=0, step=10_000
            )
            min_market_cap = st.number_input(
                "Min Market Cap (B)", min_value=0.0, value=0.0, step=0.1
            )

        with col3:
            st.write("**Technical Indicators**")
            rsi_min = st.slider("RSI Min", 0, 100, 0)
            rsi_max = st.slider("RSI Max", 0, 100, 100)
            min_price_change = st.number_input(
                "Min 30d Change %", min_value=-100.0, value=0.0, step=1.0
            )
            max_price_change = st.number_input(
                "Max 30d Change %", min_value=-100.0, value=100.0, step=1.0
            )
            max_volatility = st.number_input(
                "Max Volatility %", min_value=0.0, value=0.0, step=1.0
            )

        with col4:
            st.write("**Advanced Filters**")
            macd_signal_opt = st.selectbox("MACD Signal", ["Any", "Bullish", "Bearish"])
            sma_crossover_opt = st.selectbox(
                "SMA Crossover",
                [
                    "Any",
                    "Price above SMA20",
                    "Price below SMA20",
                    "Golden Cross (SMA20>SMA50)",
                    "Death Cross (SMA20<SMA50)",
                ],
            )
            bb_min = st.slider("BB Position Min", 0.0, 1.0, 0.0, step=0.05)
            bb_max = st.slider("BB Position Max", 0.0, 1.0, 1.0, step=0.05)
            sort_opt = st.selectbox("Sort Results By", SORT_OPTIONS)

        filter_button = st.button("Apply Filters", type="primary", width="stretch")

        if filter_button:
            criteria = {}
            if selected_sector != "All":
                criteria["sector"] = selected_sector
            if selected_industry != "All":
                criteria["industry"] = selected_industry
            if min_price > 0:
                criteria["min_price"] = min_price
            if max_price > 0:
                criteria["max_price"] = max_price
            if min_volume > 0:
                criteria["min_volume"] = min_volume
            if min_market_cap > 0:
                criteria["min_market_cap"] = min_market_cap
            if rsi_min > 0:
                criteria["rsi_min"] = rsi_min
            if rsi_max < 100:
                criteria["rsi_max"] = rsi_max
            if min_price_change != 0:
                criteria["min_price_change_pct"] = min_price_change
            if max_price_change != 100:
                criteria["max_price_change_pct"] = max_price_change
            if max_volatility > 0:
                criteria["max_volatility"] = max_volatility
            if macd_signal_opt != "Any":
                criteria["macd_signal"] = macd_signal_opt.lower()
            if bb_min > 0:
                criteria["bb_min"] = bb_min
            if bb_max < 1.0:
                criteria["bb_max"] = bb_max
            if sma_crossover_opt != "Any":
                xover_map = {
                    "Price above SMA20": "above_sma20",
                    "Price below SMA20": "below_sma20",
                    "Golden Cross (SMA20>SMA50)": "golden_cross",
                    "Death Cross (SMA20<SMA50)": "death_cross",
                }
                criteria["sma_crossover"] = xover_map[sma_crossover_opt]
            if sort_opt != "None":
                criteria["manual_sort"] = sort_opt

            with show_loading_spinner("Loading symbols..."):
                if selected_sector != "All" or selected_industry != "All":
                    syms_data = api_client.get_symbols_by_filter(
                        sector=(selected_sector if selected_sector != "All" else None),
                        industry=(
                            selected_industry if selected_industry != "All" else None
                        ),
                    )
                else:
                    syms_data = api_client.get_all_symbols()

                if "error" not in syms_data:
                    symbols = [
                        s.get("symbol", "") for s in syms_data if s.get("symbol")
                    ]
                else:
                    symbols = _fallback_symbols()

            with show_loading_spinner("Screening stocks..."):
                try:
                    results = screen_stocks(
                        api_client,
                        llm_service,
                        criteria,
                        symbols[:symbol_limit],
                        query="",
                    )
                    st.session_state.screener_results = results
                    st.session_state.screener_query = ""
                    st.session_state.screener_chat_history = []
                except Exception as e:
                    st.error(f"Error during screening: {e}")
                    import traceback as tb

                    st.code(tb.format_exc())
                    results = []

            if results:
                st.success(f"Found {len(results)} matching stocks")
            else:
                _show_no_results_tips()

    # ---- Results (shared between tabs) ----
    if st.session_state.screener_results:
        display_results(
            results=st.session_state.screener_results,
            llm_service=llm_service,
            query=st.session_state.screener_query,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fallback_symbols() -> List[str]:
    return ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "NFLX"]


def _show_no_results_tips():
    st.warning("No stocks matched your criteria.")
    st.info(
        "**Tips:** Relax your filters · Check market data availability "
        "· Try Traditional Filters for more control"
    )


def main():
    screener_page()


if __name__ == "__main__":
    main()
