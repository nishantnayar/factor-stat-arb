"""
Ops -- System configuration, connection status, and data quality monitoring.

Tabs:
  Connections & Preferences -- API status, Alpaca status, analysis defaults
  Data Quality              -- ingestion timestamps, stale data alerts
"""

import json
import os
import sys
from datetime import datetime

import pandas as pd
import streamlit as st

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from api_client import get_api_client  # noqa: E402

_PREFS_FILE = os.path.join(
    os.path.dirname(__file__), "..", "..", "config", "analysis_prefs.json"
)
_PREFS_DEFAULTS = {"symbol": "AAPL", "timeframe": "1M"}


def _load_prefs() -> dict:
    try:
        with open(_PREFS_FILE) as f:
            data = json.load(f)
        return {**_PREFS_DEFAULTS, **data}
    except Exception:
        return dict(_PREFS_DEFAULTS)


def _save_prefs(symbol: str, timeframe: str) -> None:
    try:
        os.makedirs(os.path.dirname(_PREFS_FILE), exist_ok=True)
        with open(_PREFS_FILE, "w") as f:
            json.dump({"symbol": symbol, "timeframe": timeframe}, f)
    except Exception:
        pass


st.set_page_config(
    page_title="Ops",
    page_icon="⚙️",
    layout="wide",
)


def load_css() -> None:
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


def _status_badge(ok: bool, ok_label: str, fail_label: str) -> str:
    if ok:
        return (
            f'<span style=\'color:#2A7A4B;font-family:"DM Sans",sans-serif;'
            f"font-weight:500;'>{ok_label}</span>"
        )
    return (
        f'<span style=\'color:#C0392B;font-family:"DM Sans",sans-serif;'
        f"font-weight:500;'>{fail_label}</span>"
    )


def _metric_card(label: str, value: str, sub: str = "", color: str = "#1a1a1a") -> str:
    return (
        f"<div class='metric-container'>"
        f'<div style=\'font-family:"DM Sans",sans-serif;font-size:0.72rem;'
        f"text-transform:uppercase;letter-spacing:0.07em;color:#6b6b6b;"
        f"margin-bottom:0.3rem;'>{label}</div>"
        f'<div style=\'font-family:"DM Sans",sans-serif;font-size:1.5rem;'
        f"font-weight:600;color:{color};'>{value}</div>"
        + (
            f'<div style=\'font-family:"DM Mono",monospace;font-size:0.72rem;'
            f"color:#9e9e9e;margin-top:0.2rem;'>{sub}</div>"
            if sub
            else ""
        )
        + "</div>"
    )


def _format_dt(iso_str) -> str:
    if not iso_str:
        return "--"
    try:
        dt = datetime.fromisoformat(str(iso_str).replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return str(iso_str)


# ---------------------------------------------------------------------------
# Tab renderers
# ---------------------------------------------------------------------------


def _render_connections_tab(api) -> None:
    st.subheader("Connection Status")

    c1, c2, c3 = st.columns(3)

    with c1:
        health = api.health_check()
        api_ok = "error" not in health
        st.markdown(
            f"<div class='metric-container'>"
            f'<div style=\'font-family:"DM Sans",sans-serif;font-size:0.72rem;'
            f"text-transform:uppercase;letter-spacing:0.07em;color:#6b6b6b;"
            f"margin-bottom:0.3rem;'>API Server</div>"
            f"{_status_badge(api_ok, '● Connected', '● Unreachable')}"
            f'<div style=\'font-family:"DM Mono",monospace;font-size:0.75rem;'
            f"color:#9e9e9e;margin-top:0.2rem;'>"
            f"{os.getenv('API_BASE_URL', 'http://localhost:8001')}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    with c2:
        account = api.get_alpaca_account()
        alpaca_ok = "error" not in account
        acct_num = account.get("account_number", "") if alpaca_ok else ""
        mode = "Paper Trading" if alpaca_ok else "--"
        st.markdown(
            f"<div class='metric-container'>"
            f'<div style=\'font-family:"DM Sans",sans-serif;font-size:0.72rem;'
            f"text-transform:uppercase;letter-spacing:0.07em;color:#6b6b6b;"
            f"margin-bottom:0.3rem;'>Alpaca</div>"
            f"{_status_badge(alpaca_ok, '● Connected', '● Unreachable')}"
            f'<div style=\'font-family:"DM Mono",monospace;font-size:0.75rem;'
            f"color:#9e9e9e;margin-top:0.2rem;'>"
            f"{acct_num or '--'} · {mode}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    with c3:
        clock = api.get_market_clock()
        clock_ok = "error" not in clock
        is_open = clock.get("is_open", False) if clock_ok else False
        st.markdown(
            f"<div class='metric-container'>"
            f'<div style=\'font-family:"DM Sans",sans-serif;font-size:0.72rem;'
            f"text-transform:uppercase;letter-spacing:0.07em;color:#6b6b6b;"
            f"margin-bottom:0.3rem;'>Market</div>"
            f"{_status_badge(is_open, '● Open', '● Closed')}"
            f'<div style=\'font-family:"DM Mono",monospace;font-size:0.75rem;'
            f"color:#9e9e9e;margin-top:0.2rem;'>"
            f"{'Real-time via Alpaca' if clock_ok else 'Clock unavailable'}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    if st.button("Recheck connections", key="recheck_btn"):
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")

    st.subheader("Analysis Preferences")
    st.markdown(
        "<p style='color:#6b6b6b;font-size:0.88rem;margin-bottom:1rem;'>"
        "These defaults pre-fill the Analysis page each session.</p>",
        unsafe_allow_html=True,
    )

    prefs = _load_prefs()
    if "selected_symbol" not in st.session_state:
        st.session_state.selected_symbol = prefs["symbol"]
    if "selected_timeframe" not in st.session_state:
        st.session_state.selected_timeframe = prefs["timeframe"]

    p1, p2 = st.columns(2)
    with p1:
        new_sym = (
            st.text_input(
                "Default Symbol",
                value=st.session_state.selected_symbol,
                help="Pre-filled symbol in the Analysis page",
            )
            .upper()
            .strip()
        )
        if new_sym and new_sym != st.session_state.selected_symbol:
            st.session_state.selected_symbol = new_sym
            _save_prefs(new_sym, st.session_state.selected_timeframe)
            st.success(f"Default symbol saved as {new_sym}")

    with p2:
        timeframes = ["1D", "1W", "1M", "3M", "6M", "1Y"]
        current_idx = (
            timeframes.index(st.session_state.selected_timeframe)
            if st.session_state.selected_timeframe in timeframes
            else 2
        )
        new_tf = st.selectbox(
            "Default Timeframe",
            timeframes,
            index=current_idx,
            help="Pre-filled timeframe in the Analysis page",
        )
        if new_tf != st.session_state.selected_timeframe:
            st.session_state.selected_timeframe = new_tf
            _save_prefs(st.session_state.selected_symbol, new_tf)
            st.success(f"Default timeframe saved as {new_tf}")

    st.markdown("---")

    st.subheader("System Info")
    s1, s2 = st.columns(2)
    with s1:
        api_url = os.getenv("API_BASE_URL", "http://localhost:8001")
        st.markdown(
            f'<div style=\'font-family:"DM Sans",sans-serif;font-size:0.88rem;'
            f"line-height:1.9;color:#1a1a1a;'>"
            f"<span style='color:#6b6b6b;'>API URL&emsp;</span>"
            f"<span style='font-family:\"DM Mono\",monospace;'>{api_url}</span><br>"
            f"<span style='color:#6b6b6b;'>Session started&emsp;</span>"
            f"<span style='font-family:\"DM Mono\",monospace;'>"
            f"{datetime.now().strftime('%Y-%m-%d %H:%M')}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )
    with s2:
        import streamlit as _st

        st.markdown(
            f'<div style=\'font-family:"DM Sans",sans-serif;font-size:0.88rem;'
            f"line-height:1.9;color:#1a1a1a;'>"
            f"<span style='color:#6b6b6b;'>Streamlit&emsp;</span>"
            f"<span style='font-family:\"DM Mono\",monospace;'>"
            f"{_st.__version__}</span><br>"
            f"<span style='color:#6b6b6b;'>Python&emsp;</span>"
            f"<span style='font-family:\"DM Mono\",monospace;'>"
            f"{sys.version.split()[0]}</span>"
            f"</div>",
            unsafe_allow_html=True,
        )


def _render_data_quality_tab(api) -> None:
    if st.button("Refresh", key="refresh_btn"):
        st.cache_data.clear()
        st.rerun()

    summary = api.get_data_quality_summary()

    if "error" in summary:
        st.error("Could not load data quality summary. Is the API running?")
        return

    total = summary.get("total_symbols", 0)
    stale = summary.get("stale_symbols", 0)
    ok = summary.get("ok_symbols", 0)
    last_ingest = _format_dt(summary.get("last_ingestion_at"))

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(_metric_card("Tracked Symbols", str(total)), unsafe_allow_html=True)
    with c2:
        st.markdown(
            _metric_card("Up to Date", str(ok), color="#2A7A4B"), unsafe_allow_html=True
        )
    with c3:
        color = "#C0392B" if stale > 0 else "#6b6b6b"
        st.markdown(
            _metric_card("Stale", str(stale), color=color), unsafe_allow_html=True
        )
    with c4:
        st.markdown(
            _metric_card(
                "Last Ingestion",
                last_ingest[:10] if last_ingest != "--" else "--",
                sub=last_ingest[11:] if last_ingest != "--" else "",
            ),
            unsafe_allow_html=True,
        )

    st.markdown("---")

    alerts = api.get_data_quality_alerts()
    if alerts:
        st.markdown(
            f"<h2>Alerts <span style='color:#C0392B;font-size:1rem;font-weight:500'>"
            f"({len(alerts)} issue{'s' if len(alerts) != 1 else ''})</span></h2>",
            unsafe_allow_html=True,
        )
        alert_df = (
            pd.DataFrame(alerts)[
                ["symbol", "last_date", "days_since_last_bar", "record_count"]
            ]
            .rename(
                columns={
                    "symbol": "Symbol",
                    "last_date": "Last Bar",
                    "days_since_last_bar": "Days Stale",
                    "record_count": "Records",
                }
            )
            .sort_values("Days Stale", ascending=False)
        )
        st.dataframe(
            alert_df,
            hide_index=True,
            column_config={
                "Days Stale": st.column_config.NumberColumn(format="%d days"),
                "Records": st.column_config.NumberColumn(format="%d"),
            },
        )
        st.markdown("---")
    else:
        st.success("All symbols are up to date.")
        st.markdown("---")

    st.subheader("All Ingestion Series")
    statuses = api.get_ingestion_status()

    if not statuses:
        st.info("No market data found. Trigger a data ingestion flow first.")
        return

    df = pd.DataFrame(statuses)
    stale_filter = st.selectbox("Freshness", ["All", "Stale only", "Fresh only"])
    if stale_filter == "Stale only":
        filtered = df[df["is_stale"]]
    elif stale_filter == "Fresh only":
        filtered = df[~df["is_stale"]]
    else:
        filtered = df

    display = (
        filtered[
            ["symbol", "last_date", "days_since_last_bar", "record_count", "is_stale"]
        ]
        .rename(
            columns={
                "symbol": "Symbol",
                "last_date": "Last Bar",
                "days_since_last_bar": "Days Stale",
                "record_count": "Records",
                "is_stale": "Stale?",
            }
        )
        .sort_values(["Days Stale", "Symbol"], ascending=[False, True])
    )

    st.dataframe(
        display,
        hide_index=True,
        column_config={
            "Days Stale": st.column_config.NumberColumn(format="%d days"),
            "Records": st.column_config.NumberColumn(format="%d"),
            "Stale?": st.column_config.CheckboxColumn(),
        },
    )

    st.markdown(
        f'<div style=\'font-family:"DM Mono",monospace;font-size:0.72rem;color:#9e9e9e;'
        f"margin-top:0.5rem;'>Showing {len(display)} of {len(df)} series . "
        f"Stale threshold: >2 days since last successful load</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    load_css()
    st.title("Ops")

    api = get_api_client()

    tab_conn, tab_dq = st.tabs(["Connections & Preferences", "Data Quality"])

    with tab_conn:
        _render_connections_tab(api)

    with tab_dq:
        _render_data_quality_tab(api)


if __name__ == "__main__":
    main()
