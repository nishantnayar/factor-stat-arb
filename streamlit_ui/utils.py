"""
Common utilities for the Trading System Streamlit UI
"""

import os
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Union

if TYPE_CHECKING:
    from st_aggrid import GridOptionsBuilder

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ============================================================================
# FORMATTING UTILITIES
# ============================================================================


def format_currency(value: float, currency: str = "$", decimals: int = 2) -> str:
    """
    Format a number as currency

    Args:
        value: The numeric value to format
        currency: Currency symbol (default: "$")
        decimals: Number of decimal places (default: 2)

    Returns:
        Formatted currency string
    """
    if value is None or np.isnan(value):
        return f"{currency}0.00"

    if abs(value) >= 1_000_000_000:
        return f"{currency}{value/1_000_000_000:.{decimals}f}B"
    elif abs(value) >= 1_000_000:
        return f"{currency}{value/1_000_000:.{decimals}f}M"
    elif abs(value) >= 1_000:
        return f"{currency}{value/1_000:.{decimals}f}K"
    else:
        return f"{currency}{value:,.{decimals}f}"


def format_percentage(value: float, decimals: int = 2, show_sign: bool = True) -> str:
    """
    Format a number as percentage

    Args:
        value: The numeric value to format (as decimal, not percentage)
        decimals: Number of decimal places (default: 2)
        show_sign: Whether to show + sign for positive values

    Returns:
        Formatted percentage string
    """
    if value is None or np.isnan(value):
        return "0.00%"

    percentage = value * 100
    if show_sign and percentage > 0:
        return f"+{percentage:.{decimals}f}%"
    else:
        return f"{percentage:.{decimals}f}%"


def format_number(value: float, decimals: int = 2) -> str:
    """
    Format a number with appropriate scaling

    Args:
        value: The numeric value to format
        decimals: Number of decimal places

    Returns:
        Formatted number string
    """
    if value is None or np.isnan(value):
        return "0"

    if abs(value) >= 1_000_000_000:
        return f"{value/1_000_000_000:.{decimals}f}B"
    elif abs(value) >= 1_000_000:
        return f"{value/1_000_000:.{decimals}f}M"
    elif abs(value) >= 1_000:
        return f"{value/1_000:.{decimals}f}K"
    else:
        return f"{value:,.{decimals}f}"


def format_date(date: Union[str, datetime], format_str: str = "%Y-%m-%d") -> str:
    """
    Format a date string or datetime object

    Args:
        date: Date string or datetime object
        format_str: Output format string

    Returns:
        Formatted date string
    """
    if isinstance(date, str):
        try:
            date = datetime.fromisoformat(date.replace("Z", "+00:00"))
        except ValueError:
            return date

    return date.strftime(format_str)


# ============================================================================
# DATA PROCESSING UTILITIES
# ============================================================================


def get_timeframe_days(timeframe: str) -> int:
    """
    Convert timeframe string to days

    Args:
        timeframe: Timeframe string (1D, 1W, 1M, 3M, 6M, 1Y)

    Returns:
        Number of days
    """
    timeframe_map = {"1D": 1, "1W": 7, "1M": 30, "3M": 90, "6M": 180, "1Y": 365}
    return timeframe_map.get(timeframe, 30)


def get_date_range(
    timeframe: str, end_date: Optional[datetime] = None
) -> Tuple[str, str]:
    """
    Get start and end dates for a timeframe

    Args:
        timeframe: Timeframe string
        end_date: End date (defaults to now)

    Returns:
        Tuple of (start_date, end_date) as ISO strings
    """
    if end_date is None:
        end_date = datetime.now()

    days = get_timeframe_days(timeframe)
    start_date = end_date - timedelta(days=days)

    return start_date.isoformat(), end_date.isoformat()


def calculate_returns(prices: pd.Series) -> pd.Series:
    """
    Calculate returns from price series

    Args:
        prices: Series of prices

    Returns:
        Series of returns
    """
    return prices.pct_change().dropna()


def calculate_volatility(returns: pd.Series, window: int = 30) -> pd.Series:
    """
    Calculate rolling volatility

    Args:
        returns: Series of returns
        window: Rolling window size

    Returns:
        Series of rolling volatility
    """
    return returns.rolling(window=window).std() * np.sqrt(252)


def calculate_sharpe_ratio(returns: pd.Series, risk_free_rate: float = 0.02) -> float:
    """
    Calculate Sharpe ratio

    Args:
        returns: Series of returns
        risk_free_rate: Risk-free rate (annual)

    Returns:
        Sharpe ratio
    """
    if len(returns) == 0:
        return 0.0

    excess_returns = returns - (risk_free_rate / 252)
    return excess_returns.mean() / returns.std() * np.sqrt(252)


def calculate_max_drawdown(prices: pd.Series) -> float:
    """
    Calculate maximum drawdown

    Args:
        prices: Series of prices

    Returns:
        Maximum drawdown as percentage
    """
    if len(prices) == 0:
        return 0.0

    peak = prices.expanding().max()
    drawdown = (prices - peak) / peak
    return drawdown.min()


# ============================================================================
# CHART UTILITIES
# ============================================================================


def create_price_chart(
    dates: pd.Series,
    prices: pd.Series,
    title: str = "Price Chart",
    symbol: str = "",
    color: str = "#2E8B57",
) -> go.Figure:
    """
    Create a price line chart

    Args:
        dates: Series of dates
        prices: Series of prices
        title: Chart title
        symbol: Symbol name
        color: Line color

    Returns:
        Plotly figure
    """
    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=dates,
            y=prices,
            mode="lines",
            name=f"{symbol} Price" if symbol else "Price",
            line=dict(color=color, width=2),
            hovertemplate="<b>%{fullData.name}</b><br>"
            + "Date: %{x}<br>"
            + "Price: $%{y:.2f}<br>"
            + "<extra></extra>",
        )
    )

    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title="Price ($)",
        height=400,
        hovermode="x unified",
        showlegend=True,
    )

    return fig


def ohlc_data_to_dataframe(ohlc_data: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Convert OHLC data list to pandas DataFrame with datetime index

    Args:
        ohlc_data: List of OHLC data dictionaries with 'time' (Unix timestamp) and OHLCV fields

    Returns:
        DataFrame with datetime index and OHLCV columns
    """
    from datetime import datetime

    df_data = []
    for item in ohlc_data:
        # Convert Unix timestamp to datetime
        dt = datetime.fromtimestamp(item["time"])
        df_data.append(
            {
                "date": dt,
                "open": item["open"],
                "high": item["high"],
                "low": item["low"],
                "close": item["close"],
                "volume": item.get("volume", 0),
            }
        )

    df = pd.DataFrame(df_data)
    df.set_index("date", inplace=True)
    df.sort_index(inplace=True)

    return df


def create_candlestick_chart(
    dates: pd.Series,
    open_prices: pd.Series,
    high_prices: pd.Series,
    low_prices: pd.Series,
    close_prices: pd.Series,
    title: str = "Candlestick Chart",
    symbol: str = "",
) -> go.Figure:
    """
    Create a candlestick chart

    Args:
        dates: Series of dates
        open_prices: Series of open prices
        high_prices: Series of high prices
        low_prices: Series of low prices
        close_prices: Series of close prices
        title: Chart title
        symbol: Symbol name

    Returns:
        Plotly figure
    """
    fig = go.Figure(
        data=go.Candlestick(
            x=dates,
            open=open_prices,
            high=high_prices,
            low=low_prices,
            close=close_prices,
            name=f"{symbol} OHLC" if symbol else "OHLC",
        )
    )

    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title="Price ($)",
        height=400,
        hovermode="x unified",
    )

    return fig


def create_candlestick_chart_with_overlays(
    ohlc_data: List[Dict[str, Any]],
    symbol: str,
    title: str = "",
    show_sma: bool = False,
    sma_period: int = 20,
    show_ema: bool = False,
    ema_period: int = 50,
    show_bollinger: bool = False,
    bb_period: int = 20,
    bb_std: float = 2.0,
    height: int = 500,
) -> go.Figure:
    """
    Create a candlestick chart with optional technical indicator overlays

    Args:
        ohlc_data: List of OHLC data dictionaries
        symbol: Stock symbol
        title: Chart title (defaults to symbol name)
        show_sma: Show Simple Moving Average overlay
        sma_period: SMA period (default: 20)
        show_ema: Show Exponential Moving Average overlay
        ema_period: EMA period (default: 50)
        show_bollinger: Show Bollinger Bands overlay
        bb_period: Bollinger Bands period (default: 20)
        bb_std: Bollinger Bands standard deviation (default: 2.0)
        height: Chart height in pixels

    Returns:
        Plotly figure
    """
    # Convert OHLC data to DataFrame
    df = ohlc_data_to_dataframe(ohlc_data)

    if len(df) == 0:
        # Return empty figure if no data
        fig = go.Figure()
        fig.update_layout(title="No Data Available", height=height)
        return fig

    # Create figure with candlestick
    fig = go.Figure()

    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name=f"{symbol} OHLC",
            increasing_line_color="#26a69a",
            decreasing_line_color="#ef5350",
        )
    )

    # Get technical indicators from database for overlays
    timestamps = [item["time"] for item in ohlc_data]
    start_timestamp = min(timestamps)
    end_timestamp = max(timestamps)
    start_date = datetime.fromtimestamp(start_timestamp)
    end_date = datetime.fromtimestamp(end_timestamp)

    indicators = get_technical_indicators_from_db(
        symbol=symbol, start_date=start_date, end_date=end_date
    )

    # Create mapping from date to indicator values
    indicator_map = {}
    if indicators:
        for ind in indicators:
            try:
                ind_date = datetime.fromisoformat(ind["date"]).date()
                indicator_map[ind_date] = ind
            except Exception:
                continue

    # Add SMA overlay from database
    if show_sma:
        sma_values = []
        sma_dates = []
        for idx, row in df.iterrows():
            date_key = idx.date() if hasattr(idx, "date") else idx
            if date_key in indicator_map:
                # Use sma_20, sma_50, or sma_200 based on period
                if sma_period == 20:
                    sma_val = indicator_map[date_key].get("sma_20")
                elif sma_period == 50:
                    sma_val = indicator_map[date_key].get("sma_50")
                elif sma_period == 200:
                    sma_val = indicator_map[date_key].get("sma_200")
                else:
                    sma_val = None

                if sma_val is not None:
                    sma_values.append(sma_val)
                    sma_dates.append(idx)

        if sma_values:
            # Create a Series aligned with df.index
            sma_series = pd.Series(index=sma_dates, data=sma_values)
            sma_series = sma_series.reindex(df.index, method="ffill")

            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=sma_series,
                    mode="lines",
                    name=f"SMA {sma_period}",
                    line=dict(color="#2196F3", width=2, dash="solid"),
                    hovertemplate=f"<b>SMA {sma_period}</b><br>Date: %{{x}}<br>Price: $%{{y:.2f}}<extra></extra>",
                )
            )

    # Add EMA overlay from database
    if show_ema:
        ema_values = []
        ema_dates = []
        for idx, row in df.iterrows():
            date_key = idx.date() if hasattr(idx, "date") else idx
            if date_key in indicator_map:
                # Use ema_12, ema_26, or ema_50 based on period
                if ema_period == 12:
                    ema_val = indicator_map[date_key].get("ema_12")
                elif ema_period == 26:
                    ema_val = indicator_map[date_key].get("ema_26")
                elif ema_period == 50:
                    ema_val = indicator_map[date_key].get("ema_50")
                else:
                    ema_val = None

                if ema_val is not None:
                    ema_values.append(ema_val)
                    ema_dates.append(idx)

        if ema_values:
            # Create a Series aligned with df.index
            ema_series = pd.Series(index=ema_dates, data=ema_values)
            ema_series = ema_series.reindex(df.index, method="ffill")

            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=ema_series,
                    mode="lines",
                    name=f"EMA {ema_period}",
                    line=dict(color="#FF9800", width=2, dash="dash"),
                    hovertemplate=f"<b>EMA {ema_period}</b><br>Date: %{{x}}<br>Price: $%{{y:.2f}}<extra></extra>",
                )
            )

    # Add Bollinger Bands overlay from database
    if show_bollinger:
        bb_upper_values = []
        bb_middle_values = []
        bb_lower_values = []
        bb_dates = []

        for idx, row in df.iterrows():
            date_key = idx.date() if hasattr(idx, "date") else idx
            if date_key in indicator_map:
                ind = indicator_map[date_key]
                bb_upper = ind.get("bb_upper")
                bb_middle = ind.get("bb_middle")
                bb_lower = ind.get("bb_lower")

                if (
                    bb_upper is not None
                    and bb_middle is not None
                    and bb_lower is not None
                ):
                    bb_upper_values.append(bb_upper)
                    bb_middle_values.append(bb_middle)
                    bb_lower_values.append(bb_lower)
                    bb_dates.append(idx)

        if bb_upper_values:
            # Create Series aligned with df.index
            upper_series = pd.Series(index=bb_dates, data=bb_upper_values).reindex(
                df.index, method="ffill"
            )
            middle_series = pd.Series(index=bb_dates, data=bb_middle_values).reindex(
                df.index, method="ffill"
            )
            lower_series = pd.Series(index=bb_dates, data=bb_lower_values).reindex(
                df.index, method="ffill"
            )

            # Upper band
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=upper_series,
                    mode="lines",
                    name=f"BB Upper ({bb_period}, {bb_std}sigma)",
                    line=dict(color="rgba(33, 150, 243, 0.3)", width=1, dash="dot"),
                    hovertemplate=f"<b>BB Upper</b><br>Date: %{{x}}<br>Price: $%{{y:.2f}}<extra></extra>",
                    showlegend=True,
                )
            )

            # Middle band (SMA)
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=middle_series,
                    mode="lines",
                    name=f"BB Middle ({bb_period})",
                    line=dict(color="rgba(33, 150, 243, 0.5)", width=1, dash="dashdot"),
                    hovertemplate=f"<b>BB Middle</b><br>Date: %{{x}}<br>Price: $%{{y:.2f}}<extra></extra>",
                    showlegend=True,
                )
            )

            # Lower band
            fig.add_trace(
                go.Scatter(
                    x=df.index,
                    y=lower_series,
                    mode="lines",
                    name=f"BB Lower ({bb_period}, {bb_std}sigma)",
                    line=dict(color="rgba(33, 150, 243, 0.3)", width=1, dash="dot"),
                    hovertemplate=f"<b>BB Lower</b><br>Date: %{{x}}<br>Price: $%{{y:.2f}}<extra></extra>",
                    showlegend=True,
                    fill="tonexty",
                    fillcolor="rgba(33, 150, 243, 0.1)",
                )
            )

    # Update layout (no title in chart since subheader is shown above)
    fig.update_layout(
        title="",  # No title - subheader is shown above the chart
        xaxis_title="Date",
        yaxis_title="Price ($)",
        height=height,
        hovermode="x unified",
        xaxis_rangeslider_visible=False,
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01,
            bgcolor="rgba(255, 255, 255, 0.8)",
        ),
    )

    return fig


def create_volume_chart(
    dates: pd.Series,
    volumes: pd.Series,
    title: str = "Volume Chart",
    color: str = "lightblue",
) -> go.Figure:
    """
    Create a volume bar chart

    Args:
        dates: Series of dates
        volumes: Series of volumes
        title: Chart title
        color: Bar color

    Returns:
        Plotly figure
    """
    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=dates,
            y=volumes,
            name="Volume",
            marker_color=color,
            hovertemplate="<b>Volume</b><br>"
            + "Date: %{x}<br>"
            + "Volume: %{y:,.0f}<br>"
            + "<extra></extra>",
        )
    )

    fig.update_layout(
        title=title,
        xaxis_title="Date",
        yaxis_title="Volume",
        height=300,
        hovermode="x unified",
    )

    return fig


def create_pie_chart(
    labels: List[str],
    values: List[float],
    title: str = "Pie Chart",
    colors: Optional[List[str]] = None,
) -> go.Figure:
    """
    Create a pie chart

    Args:
        labels: List of labels
        values: List of values
        title: Chart title
        colors: Optional list of colors

    Returns:
        Plotly figure
    """
    fig = go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=values,
                hovertemplate="<b>%{label}</b><br>"
                + "Value: %{value:,.0f}<br>"
                + "Percentage: %{percent}<br>"
                + "<extra></extra>",
            )
        ]
    )

    if colors:
        fig.update_traces(marker=dict(colors=colors))

    fig.update_layout(title=title, height=400, showlegend=True)

    return fig


def create_rsi_chart(
    ohlc_data: List[Dict[str, Any]], symbol: str, period: int = 14, height: int = 200
) -> go.Figure:
    """
    Create an RSI (Relative Strength Index) chart

    Args:
        ohlc_data: List of OHLC data dictionaries
        symbol: Stock symbol
        period: RSI period (default: 14)
        height: Chart height in pixels

    Returns:
        Plotly figure
    """
    from streamlit_ui.utils.technical_indicators import calculate_rsi

    # Convert OHLC data to DataFrame
    df = ohlc_data_to_dataframe(ohlc_data)

    if len(df) == 0:
        fig = go.Figure()
        fig.update_layout(title="RSI - No Data Available", height=height)
        return fig

    # Calculate RSI for each point
    closing_prices = df["close"].tolist()
    rsi_values = []

    for i in range(len(closing_prices)):
        window_prices = closing_prices[max(0, i - period + 1) : i + 1]
        rsi = calculate_rsi(window_prices, period=min(period, len(window_prices)))
        rsi_values.append(rsi if rsi is not None else np.nan)

    fig = go.Figure()

    # Add RSI line
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=rsi_values,
            mode="lines",
            name=f"RSI {period}",
            line=dict(color="#9C27B0", width=2),
            hovertemplate=f"<b>RSI {period}</b><br>Date: %{{x}}<br>RSI: %{{y:.2f}}<extra></extra>",
        )
    )

    # Add overbought line (70)
    fig.add_hline(
        y=70,
        line_dash="dash",
        line_color="red",
        annotation_text="Overbought (70)",
        annotation_position="right",
    )

    # Add oversold line (30)
    fig.add_hline(
        y=30,
        line_dash="dash",
        line_color="green",
        annotation_text="Oversold (30)",
        annotation_position="right",
    )

    # Add neutral line (50)
    fig.add_hline(y=50, line_dash="dot", line_color="gray", opacity=0.5)

    fig.update_layout(
        title="",  # No title - subheader is shown above the chart
        xaxis_title="Date",
        yaxis_title="RSI",
        height=height,
        yaxis=dict(range=[0, 100]),
        hovermode="x unified",
        showlegend=True,
        margin=dict(l=40, r=40, t=10, b=40),  # Consistent margins
    )

    return fig


def create_macd_chart(
    ohlc_data: List[Dict[str, Any]],
    symbol: str,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
    height: int = 200,
) -> go.Figure:
    """
    Create a MACD (Moving Average Convergence Divergence) chart

    Args:
        ohlc_data: List of OHLC data dictionaries
        symbol: Stock symbol
        fast_period: Fast EMA period (default: 12)
        slow_period: Slow EMA period (default: 26)
        signal_period: Signal line EMA period (default: 9)
        height: Chart height in pixels

    Returns:
        Plotly figure
    """
    from streamlit_ui.utils.technical_indicators import calculate_macd

    # Convert OHLC data to DataFrame
    df = ohlc_data_to_dataframe(ohlc_data)

    if len(df) == 0:
        fig = go.Figure()
        fig.update_layout(title="MACD - No Data Available", height=height)
        return fig

    # Calculate MACD for each point
    closing_prices = df["close"].tolist()
    macd_values = []
    signal_values = []
    histogram_values = []

    for i in range(len(closing_prices)):
        window_prices = closing_prices[
            max(0, i - slow_period - signal_period + 1) : i + 1
        ]
        macd_result = calculate_macd(
            window_prices,
            fast_period=min(fast_period, len(window_prices)),
            slow_period=min(slow_period, len(window_prices)),
            signal_period=min(signal_period, len(window_prices)),
        )

        if macd_result is not None:
            macd_values.append(macd_result["macd"])
            signal_values.append(macd_result["signal"])
            histogram_values.append(macd_result["histogram"])
        else:
            macd_values.append(np.nan)
            signal_values.append(np.nan)
            histogram_values.append(np.nan)

    fig = go.Figure()

    # Add MACD line
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=macd_values,
            mode="lines",
            name="MACD",
            line=dict(color="#2196F3", width=2),
            hovertemplate="<b>MACD</b><br>Date: %{x}<br>Value: %{y:.3f}<extra></extra>",
        )
    )

    # Add Signal line
    fig.add_trace(
        go.Scatter(
            x=df.index,
            y=signal_values,
            mode="lines",
            name="Signal",
            line=dict(color="#FF9800", width=2, dash="dash"),
            hovertemplate="<b>Signal</b><br>Date: %{x}<br>Value: %{y:.3f}<extra></extra>",
        )
    )

    # Add Histogram (bar chart)
    colors = ["green" if h >= 0 else "red" for h in histogram_values]
    fig.add_trace(
        go.Bar(
            x=df.index,
            y=histogram_values,
            name="Histogram",
            marker_color=colors,
            opacity=0.6,
            hovertemplate="<b>Histogram</b><br>Date: %{x}<br>Value: %{y:.3f}<extra></extra>",
        )
    )

    # Add zero line
    fig.add_hline(y=0, line_dash="dot", line_color="gray", opacity=0.5)

    fig.update_layout(
        title="",  # No title - subheader is shown above the chart
        xaxis_title="Date",
        yaxis_title="MACD",
        height=height,
        hovermode="x unified",
        showlegend=True,
        barmode="overlay",
        margin=dict(l=40, r=40, t=10, b=40),  # Consistent margins
    )

    return fig


# ============================================================================
# SESSION STATE UTILITIES
# ============================================================================


def initialize_session_state() -> None:
    """
    Initialize default session state values
    """
    defaults = {
        "portfolio_value": 125000,
        "total_return": 15.2,
        "active_positions": 8,
        "win_rate": 68,
        "selected_symbol": "AAPL",
        "selected_timeframe": "1M",
        "user_preferences": {
            "theme": "light",
            "notifications": True,
            "auto_refresh": False,
        },
        "trading_data": {
            "last_update": datetime.now(),
            "market_status": "open",
            "positions": [],
            "orders": [],
        },
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def update_session_state(key: str, value: Any) -> None:
    """
    Update a session state variable

    Args:
        key: Session state key
        value: New value
    """
    st.session_state[key] = value


def get_session_state(key: str, default: Any = None) -> Any:
    """
    Get a session state variable with default

    Args:
        key: Session state key
        default: Default value if key doesn't exist

    Returns:
        Session state value or default
    """
    return st.session_state.get(key, default)


def reset_session_state() -> None:
    """
    Reset all session state to defaults
    """
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    initialize_session_state()


# ============================================================================
# UI UTILITIES
# ============================================================================


def load_custom_css() -> None:
    """
    Load custom CSS from file
    """
    css_file = os.path.join(os.path.dirname(__file__), "styles.css")
    try:
        with open(css_file, "r") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.warning("Custom CSS file not found. Using default styling.")
    except Exception as e:
        st.error(f"Error loading custom CSS: {e}")


def create_metric_card(
    title: str, value: str, delta: str = None, delta_color: str = "normal"
) -> None:
    """
    Create a styled metric card

    Args:
        title: Metric title
        value: Metric value
        delta: Delta value (optional)
        delta_color: Delta color (normal, inverse, off)
    """
    st.markdown('<div class="metric-container">', unsafe_allow_html=True)
    st.metric(title, value, delta)
    st.markdown("</div>", unsafe_allow_html=True)


def create_info_card(title: str, content: str) -> None:
    """
    Create an info card

    Args:
        title: Card title
        content: Card content
    """
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown(f"**{title}**")
    st.write(content)
    st.markdown("</div>", unsafe_allow_html=True)


def create_expandable_section(title: str, content: str, expanded: bool = False) -> None:
    """
    Create an expandable section

    Args:
        title: Section title
        content: Section content
        expanded: Whether to expand by default
    """
    with st.expander(title, expanded=expanded):
        st.write(content)


# ============================================================================
# DATA VALIDATION UTILITIES
# ============================================================================


def validate_symbol(symbol: str) -> bool:
    """
    Validate stock symbol format

    Args:
        symbol: Stock symbol to validate

    Returns:
        True if valid, False otherwise
    """
    if not symbol or not isinstance(symbol, str):
        return False

    # Basic validation: 1-5 characters, alphanumeric
    return len(symbol) <= 5 and symbol.isalnum()


def validate_date_range(start_date: str, end_date: str) -> bool:
    """
    Validate date range

    Args:
        start_date: Start date string
        end_date: End date string

    Returns:
        True if valid, False otherwise
    """
    try:
        start = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        end = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        return start < end
    except (ValueError, TypeError):
        return False


def validate_numeric_input(
    value: Any, min_val: float = None, max_val: float = None
) -> bool:
    """
    Validate numeric input

    Args:
        value: Value to validate
        min_val: Minimum value (optional)
        max_val: Maximum value (optional)

    Returns:
        True if valid, False otherwise
    """
    try:
        num_val = float(value)
        if min_val is not None and num_val < min_val:
            return False
        if max_val is not None and num_val > max_val:
            return False
        return True
    except (ValueError, TypeError):
        return False


# ============================================================================
# ERROR HANDLING UTILITIES
# ============================================================================


def handle_api_error(error: Exception, context: str = "") -> None:
    """
    Handle API errors with user-friendly messages

    Args:
        error: Exception object
        context: Additional context for the error
    """
    error_msg = str(error)

    if "ConnectionError" in error_msg:
        st.error(
            "[Error] Cannot connect to API server. "
            "Please ensure the API is running on port 8001."
        )
    elif "TimeoutError" in error_msg:
        st.error("[Error] Request timed out. Please try again.")
    elif "HTTPError" in error_msg:
        st.error(f"[Error] API Error: {error_msg}")
    else:
        st.error(f"[Error] Unexpected error: {error_msg}")

    if context:
        st.info(f"Context: {context}")


def show_loading_spinner(message: str = "Loading..."):
    """
    Context manager for showing loading spinner

    Args:
        message: Loading message
    """
    return st.spinner(message)


def show_success_message(message: str) -> None:
    """
    Show success message

    Args:
        message: Success message
    """
    st.success(message)


def show_warning_message(message: str) -> None:
    """
    Show warning message

    Args:
        message: Warning message
    """
    st.warning(message)


def show_error_message(message: str) -> None:
    """
    Show error message

    Args:
        message: Error message
    """
    st.error(message)


def show_info_message(message: str) -> None:
    """
    Show info message

    Args:
        message: Info message
    """
    st.info(message)


# ============================================================================
# LIGHTWEIGHT CHARTS UTILITIES
# ============================================================================


def generate_ohlc_data(
    symbol: str, days: int = 365, base_price: float = 150.0, volatility: float = 2.0
) -> List[Dict[str, Any]]:
    """
    Generates realistic OHLC data for lightweight charts.

    Args:
        symbol: Stock symbol
        days: Number of days of data to generate
        base_price: Starting price
        volatility: Daily price volatility

    Returns:
        List of OHLC data dictionaries
    """
    from datetime import datetime, timedelta

    import numpy as np

    # Generate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    dates = pd.date_range(start=start_date, end=end_date, freq="D")

    ohlc_data = []
    current_price = base_price

    for i, date in enumerate(dates):
        # Generate daily price movement
        daily_change = np.random.normal(0, volatility)
        open_price = current_price
        close_price = open_price + daily_change

        # Generate high and low prices
        high_price = max(open_price, close_price) + abs(
            np.random.normal(0, volatility * 0.5)
        )
        low_price = min(open_price, close_price) - abs(
            np.random.normal(0, volatility * 0.5)
        )

        # Generate volume (higher volume on larger price movements)
        volume_multiplier = 1 + abs(daily_change) / volatility
        volume = int(np.random.randint(1000000, 5000000) * volume_multiplier)

        ohlc_data.append(
            {
                "time": int(date.timestamp()),
                "open": round(open_price, 2),
                "high": round(high_price, 2),
                "low": round(low_price, 2),
                "close": round(close_price, 2),
                "volume": volume,
            }
        )

        current_price = close_price

    return ohlc_data


def create_lightweight_ohlc_chart(
    ohlc_data: List[Dict[str, Any]], symbol: str, height: int = 400
) -> None:
    """
    Creates a lightweight OHLC candlestick chart.

    Args:
        ohlc_data: List of OHLC data dictionaries
        symbol: Stock symbol for display
        height: Chart height in pixels
    """
    from streamlit_lightweight_charts import Chart, renderLightweightCharts

    # Prepare data for lightweight chart
    chart_data = {
        "chart": {"height": height},
        "series": [
            {
                "type": "Candlestick",
                "data": ohlc_data,
                "options": {
                    "upColor": "#26a69a",
                    "downColor": "#ef5350",
                    "borderVisible": False,
                    "wickUpColor": "#26a69a",
                    "wickDownColor": "#ef5350",
                },
            }
        ],
    }

    # Render the lightweight chart
    renderLightweightCharts([chart_data], key=f"ohlc_chart_{symbol}")


def create_lightweight_volume_chart(
    ohlc_data: List[Dict[str, Any]], symbol: str, height: int = 200
) -> None:
    """
    Creates a lightweight volume chart.

    Args:
        ohlc_data: List of OHLC data dictionaries
        symbol: Stock symbol for display
        height: Chart height in pixels
    """
    from streamlit_lightweight_charts import Chart, renderLightweightCharts

    # Prepare volume data
    volume_data = {
        "chart": {"height": height},
        "series": [
            {
                "type": "Histogram",
                "data": [
                    {"time": item["time"], "value": item["volume"]}
                    for item in ohlc_data
                ],
                "options": {
                    "color": "#26a69a",
                    "priceFormat": {
                        "type": "volume",
                    },
                    "priceScaleId": "",
                },
            }
        ],
    }

    # Render the lightweight chart
    renderLightweightCharts([volume_data], key=f"volume_chart_{symbol}")


def get_technical_indicators_from_db(
    symbol: str,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """
    Fetch technical indicators from database for a symbol within a date range.

    Args:
        symbol: Stock symbol
        start_date: Start date (datetime object)
        end_date: End date (datetime object)

    Returns:
        List of technical indicator dictionaries with date, rsi, macd_line, macd_signal, macd_histogram, etc.
    """
    try:
        from datetime import date

        from sqlalchemy import select

        from src.shared.database.base import db_transaction
        from src.shared.database.models.technical_indicators import TechnicalIndicators

        symbol = symbol.upper()

        # Convert datetime to date if needed
        start_dt = (
            start_date.date()
            if isinstance(start_date, datetime)
            else (start_date if isinstance(start_date, date) else None)
        )
        end_dt = (
            end_date.date()
            if isinstance(end_date, datetime)
            else (end_date if isinstance(end_date, date) else None)
        )

        with db_transaction() as session:
            stmt = select(TechnicalIndicators).where(
                TechnicalIndicators.symbol == symbol
            )

            if start_dt:
                stmt = stmt.where(TechnicalIndicators.date >= start_dt)
            if end_dt:
                stmt = stmt.where(TechnicalIndicators.date <= end_dt)

            stmt = stmt.order_by(TechnicalIndicators.date.asc())

            result = session.execute(stmt)
            records = result.scalars().all()

            # Convert to list of dictionaries
            indicators = []
            for record in records:
                indicators.append(record.to_dict())

            return indicators

    except Exception as e:
        st.warning(f"Error fetching technical indicators from database: {str(e)}")
        return []


def get_latest_technical_indicators(symbol: str) -> Optional[Dict[str, Any]]:
    """
    Fetch latest technical indicators from database for a symbol.

    Args:
        symbol: Stock symbol

    Returns:
        Dictionary with latest indicator values, or None if not found
    """
    try:
        from sqlalchemy import select

        from src.shared.database.base import db_transaction
        from src.shared.database.models.technical_indicators import (
            TechnicalIndicatorsLatest,
        )

        symbol = symbol.upper()

        with db_transaction() as session:
            stmt = select(TechnicalIndicatorsLatest).where(
                TechnicalIndicatorsLatest.symbol == symbol
            )

            result = session.execute(stmt)
            record = result.scalar_one_or_none()

            if record:
                return record.to_dict()
            return None

    except Exception as e:
        st.warning(
            f"Error fetching latest technical indicators from database: {str(e)}"
        )
        return None


def create_lightweight_rsi_chart(
    ohlc_data: List[Dict[str, Any]], symbol: str, period: int = 14, height: int = 200
) -> None:
    """
    Creates a lightweight RSI chart with reference lines using data from database.

    Args:
        ohlc_data: List of OHLC data dictionaries (used to determine date range)
        symbol: Stock symbol for display
        period: RSI period (default: 14, but uses rsi_14 from database)
        height: Chart height in pixels
    """
    from datetime import date, datetime

    from streamlit_lightweight_charts import Chart, renderLightweightCharts

    if not ohlc_data:
        st.warning("No OHLC data available to determine date range for RSI chart")
        return

    # Get date range from OHLC data
    timestamps = [item["time"] for item in ohlc_data]
    start_timestamp = min(timestamps)
    end_timestamp = max(timestamps)

    start_date = datetime.fromtimestamp(start_timestamp)
    end_date = datetime.fromtimestamp(end_timestamp)

    # Fetch technical indicators from database
    indicators = get_technical_indicators_from_db(
        symbol=symbol, start_date=start_date, end_date=end_date
    )

    if not indicators:
        st.warning(
            f"No technical indicators found in database for {symbol}. Please ensure indicators are calculated and stored."
        )
        return

    # Create a mapping from date to timestamp for matching
    date_to_timestamp = {}
    for item in ohlc_data:
        dt = datetime.fromtimestamp(item["time"])
        date_key = dt.date()
        date_to_timestamp[date_key] = item["time"]

    # Prepare RSI data points from database
    rsi_data = []
    for indicator in indicators:
        # Use rsi_14 if available, otherwise fall back to rsi
        rsi_value = indicator.get("rsi_14") or indicator.get("rsi")

        if rsi_value is not None:
            # Parse the date from the indicator
            indicator_date = datetime.fromisoformat(indicator["date"]).date()

            # Find matching timestamp from OHLC data
            if indicator_date in date_to_timestamp:
                rsi_data.append(
                    {
                        "time": date_to_timestamp[indicator_date],
                        "value": round(float(rsi_value), 2),
                    }
                )

    if not rsi_data:
        st.warning(
            f"No RSI data found in database for {symbol} in the selected date range"
        )
        return

    # Prepare chart data with RSI line and reference lines
    rsi_chart_data = {
        "chart": {
            "height": height,
            "rightPriceScale": {
                "visible": True,
                "scaleMargins": {"top": 0.1, "bottom": 0.1},
            },
        },
        "series": [
            {
                "type": "Line",
                "data": rsi_data,
                "options": {
                    "color": "#9C27B0",
                    "lineWidth": 2,
                    "priceLineVisible": False,
                    "lastValueVisible": True,
                    "crosshairMarkerVisible": True,
                },
            },
            # Overbought line (70) - use same timestamps as RSI data
            {
                "type": "Line",
                "data": [{"time": item["time"], "value": 70} for item in rsi_data],
                "options": {
                    "color": "#ef5350",
                    "lineWidth": 1,
                    "lineStyle": 2,  # Dashed
                    "priceLineVisible": False,
                    "lastValueVisible": False,
                    "crosshairMarkerVisible": False,
                },
            },
            # Oversold line (30) - use same timestamps as RSI data
            {
                "type": "Line",
                "data": [{"time": item["time"], "value": 30} for item in rsi_data],
                "options": {
                    "color": "#26a69a",
                    "lineWidth": 1,
                    "lineStyle": 2,  # Dashed
                    "priceLineVisible": False,
                    "lastValueVisible": False,
                    "crosshairMarkerVisible": False,
                },
            },
            # Neutral line (50) - use same timestamps as RSI data
            {
                "type": "Line",
                "data": [{"time": item["time"], "value": 50} for item in rsi_data],
                "options": {
                    "color": "#999999",
                    "lineWidth": 1,
                    "lineStyle": 0,  # Dotted
                    "priceLineVisible": False,
                    "lastValueVisible": False,
                    "crosshairMarkerVisible": False,
                },
            },
        ],
    }

    # Render the lightweight chart
    renderLightweightCharts([rsi_chart_data], key=f"rsi_chart_{symbol}_{period}")


def create_lightweight_macd_chart(
    ohlc_data: List[Dict[str, Any]],
    symbol: str,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
    height: int = 200,
) -> None:
    """
    Creates a lightweight MACD chart with MACD line, signal line, and histogram using data from database.

    Args:
        ohlc_data: List of OHLC data dictionaries (used to determine date range)
        symbol: Stock symbol for display
        fast_period: Fast EMA period (default: 12, but uses stored MACD from database)
        slow_period: Slow EMA period (default: 26, but uses stored MACD from database)
        signal_period: Signal line EMA period (default: 9, but uses stored MACD from database)
        height: Chart height in pixels
    """
    from datetime import date, datetime

    from streamlit_lightweight_charts import Chart, renderLightweightCharts

    if not ohlc_data:
        st.warning("No OHLC data available to determine date range for MACD chart")
        return

    # Get date range from OHLC data
    timestamps = [item["time"] for item in ohlc_data]
    start_timestamp = min(timestamps)
    end_timestamp = max(timestamps)

    start_date = datetime.fromtimestamp(start_timestamp)
    end_date = datetime.fromtimestamp(end_timestamp)

    # Fetch technical indicators from database
    indicators = get_technical_indicators_from_db(
        symbol=symbol, start_date=start_date, end_date=end_date
    )

    if not indicators:
        st.warning(
            f"No technical indicators found in database for {symbol}. Please ensure indicators are calculated and stored."
        )
        return

    # Create a mapping from date to timestamp for matching
    date_to_timestamp = {}
    for item in ohlc_data:
        dt = datetime.fromtimestamp(item["time"])
        date_key = dt.date()
        date_to_timestamp[date_key] = item["time"]

    # Prepare MACD data points from database
    macd_data = []
    signal_data = []
    histogram_data = []

    for indicator in indicators:
        macd_line = indicator.get("macd_line")
        macd_signal = indicator.get("macd_signal")
        macd_histogram = indicator.get("macd_histogram")

        if (
            macd_line is not None
            and macd_signal is not None
            and macd_histogram is not None
        ):
            # Parse the date from the indicator
            indicator_date = datetime.fromisoformat(indicator["date"]).date()

            # Find matching timestamp from OHLC data
            if indicator_date in date_to_timestamp:
                timestamp = date_to_timestamp[indicator_date]
                macd_data.append(
                    {"time": timestamp, "value": round(float(macd_line), 4)}
                )
                signal_data.append(
                    {"time": timestamp, "value": round(float(macd_signal), 4)}
                )
                histogram_data.append(
                    {
                        "time": timestamp,
                        "value": round(float(macd_histogram), 4),
                        "color": "#26a69a" if macd_histogram >= 0 else "#ef5350",
                    }
                )

    if not macd_data:
        st.warning(
            f"No MACD data found in database for {symbol} in the selected date range"
        )
        return

    # Prepare chart data with MACD line, signal line, and histogram
    macd_chart_data = {
        "chart": {
            "height": height,
            "rightPriceScale": {
                "visible": True,
                "scaleMargins": {"top": 0.1, "bottom": 0.1},
            },
        },
        "series": [
            # Histogram (bars)
            {
                "type": "Histogram",
                "data": histogram_data,
                "options": {
                    "priceFormat": {
                        "type": "price",
                        "precision": 4,
                    },
                    "priceScaleId": "",
                    "scaleMargins": {
                        "top": 0.7,
                        "bottom": 0.0,
                    },
                },
            },
            # MACD line
            {
                "type": "Line",
                "data": macd_data,
                "options": {
                    "color": "#2196F3",
                    "lineWidth": 2,
                    "priceLineVisible": False,
                    "lastValueVisible": True,
                    "crosshairMarkerVisible": True,
                    "priceScaleId": "left",
                },
            },
            # Signal line
            {
                "type": "Line",
                "data": signal_data,
                "options": {
                    "color": "#FF9800",
                    "lineWidth": 2,
                    "lineStyle": 2,  # Dashed
                    "priceLineVisible": False,
                    "lastValueVisible": True,
                    "crosshairMarkerVisible": True,
                    "priceScaleId": "left",
                },
            },
            # Zero line
            {
                "type": "Line",
                "data": [
                    {"time": item["time"], "value": 0}
                    for item in ohlc_data[: len(macd_data)]
                ],
                "options": {
                    "color": "#999999",
                    "lineWidth": 1,
                    "lineStyle": 0,  # Dotted
                    "priceLineVisible": False,
                    "lastValueVisible": False,
                    "crosshairMarkerVisible": False,
                    "priceScaleId": "left",
                },
            },
        ],
    }

    # Render the lightweight chart
    renderLightweightCharts(
        [macd_chart_data],
        key=f"macd_chart_{symbol}_{fast_period}_{slow_period}_{signal_period}",
    )


def convert_api_data_to_ohlc(api_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert API market data to OHLC format for lightweight charts.

    Args:
        api_data: List of market data from API

    Returns:
        List of OHLC data dictionaries
    """
    ohlc_data = []

    for item in api_data:
        # Convert timestamp to Unix timestamp
        if isinstance(item["timestamp"], str):
            from datetime import datetime

            dt = datetime.fromisoformat(item["timestamp"].replace("Z", "+00:00"))
            timestamp = int(dt.timestamp())
        else:
            timestamp = int(item["timestamp"].timestamp())

        ohlc_data.append(
            {
                "time": timestamp,
                "open": float(item["open"]) if item["open"] else 0.0,
                "high": float(item["high"]) if item["high"] else 0.0,
                "low": float(item["low"]) if item["low"] else 0.0,
                "close": float(item["close"]) if item["close"] else 0.0,
                "volume": int(item["volume"]) if item["volume"] else 0,
            }
        )

    return ohlc_data


def filter_ohlc_data_by_timeframe(
    ohlc_data: List[Dict[str, Any]], timeframe: str
) -> List[Dict[str, Any]]:
    """
    Filter OHLC data by timeframe, keeping only data within the specified period.

    Args:
        ohlc_data: List of OHLC data dictionaries with 'time' (Unix timestamp)
        timeframe: Timeframe string (1D, 1W, 1M, 3M, 6M, 1Y, ALL)

    Returns:
        Filtered list of OHLC data dictionaries
    """
    if not ohlc_data:
        return []

    if timeframe == "ALL":
        return ohlc_data

    # Get number of days for timeframe
    days = get_timeframe_days(timeframe)

    # Get the latest timestamp (most recent data point)
    latest_time = max(item["time"] for item in ohlc_data)

    # Calculate cutoff time (days ago from latest)
    cutoff_time = latest_time - (days * 24 * 60 * 60)  # Convert days to seconds

    # Filter data to include only points within the timeframe
    filtered_data = [item for item in ohlc_data if item["time"] >= cutoff_time]

    # Sort by time (oldest first) to ensure proper ordering
    filtered_data.sort(key=lambda x: x["time"])

    return filtered_data


def get_real_market_data(
    _api_client, symbol: str, data_source: str = "yahoo"
) -> List[Dict[str, Any]]:
    """
    Fetch real market data from API and convert to OHLC format.

    Args:
        api_client: API client instance
        symbol: Stock symbol
        days: Number of days to fetch
        data_source: Data source (yahoo, polygon, alpaca)

    Returns:
        List of OHLC data dictionaries
    """
    try:
        # Fetch data from API (no date filtering to get all available data)
        api_data = _api_client.get_market_data(symbol=symbol, data_source=data_source)

        if "error" in api_data:
            return []

        # Convert to OHLC format
        ohlc_data = convert_api_data_to_ohlc(api_data)

        # Sort by time (oldest first)
        ohlc_data.sort(key=lambda x: x["time"])

        return ohlc_data

    except Exception as e:
        print(f"Error fetching real market data: {e}")
        return []


# ============================================================================
# ESG SCORES, KEY STATISTICS, AND INSTITUTIONAL HOLDERS UTILITIES
# ============================================================================


def get_latest_esg_scores(symbol: str) -> Optional[Dict[str, Any]]:
    """
    Get latest ESG scores for a symbol from the database

    Args:
        symbol: Stock symbol

    Returns:
        Dictionary with ESG scores data, or None if not available
    """
    try:
        from sqlalchemy import desc, select

        from src.shared.database.base import db_transaction
        from src.shared.database.models.esg_scores import ESGScore

        symbol = symbol.upper()

        with db_transaction() as session:
            query = (
                select(ESGScore)
                .where(ESGScore.symbol == symbol)
                .order_by(desc(ESGScore.date))
                .limit(1)
            )

            result = session.execute(query).scalar_one_or_none()

            if result:
                return {
                    "symbol": result.symbol,
                    "date": result.date.isoformat() if result.date else None,
                    "total_esg": float(result.total_esg) if result.total_esg else None,
                    "environment_score": (
                        float(result.environment_score)
                        if result.environment_score
                        else None
                    ),
                    "social_score": (
                        float(result.social_score) if result.social_score else None
                    ),
                    "governance_score": (
                        float(result.governance_score)
                        if result.governance_score
                        else None
                    ),
                    "controversy_level": result.controversy_level,
                    "esg_performance": result.esg_performance,
                    "peer_group": result.peer_group,
                    "peer_count": result.peer_count,
                    "percentile": (
                        float(result.percentile) if result.percentile else None
                    ),
                }

            return None
    except Exception as e:
        print(f"Error fetching ESG scores: {e}")
        return None


def get_latest_key_statistics(symbol: str) -> Optional[Dict[str, Any]]:
    """
    Get latest key statistics for a symbol from the API

    Args:
        symbol: Stock symbol

    Returns:
        Dictionary with key statistics data, or None if not available
    """
    try:
        from api_client import get_api_client

        api_client = get_api_client()
        result = api_client.get_key_statistics(symbol)

        if "error" in result:
            return None

        # Return the key statistics data if available
        if result.get("success") and result.get("key_statistics"):
            return result["key_statistics"]

        return None
    except Exception as e:
        print(f"Error fetching key statistics: {e}")
        return None


def get_institutional_holders(
    symbol: str, limit: int = 10
) -> Optional[List[Dict[str, Any]]]:
    """
    Get institutional holders for a symbol from the API

    Args:
        symbol: Stock symbol
        limit: Maximum number of holders to return (default: 10)

    Returns:
        List of holder dictionaries, or None if not available
    """
    try:
        from api_client import get_api_client

        api_client = get_api_client()
        result = api_client.get_institutional_holders(symbol, limit=limit)

        if "error" in result:
            return None

        # Return the holders list if available
        if result.get("success") and result.get("holders"):
            return result["holders"]

        return None
    except Exception as e:
        print(f"Error fetching institutional holders: {e}")
        return None


def _process_holder_data(holder: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process individual holder data for display.

    Returns processed data with Direction and numeric % Change (absolute value).
    """
    percent_change_val = holder.get("percent_change")

    if percent_change_val is not None:
        change_pct = float(percent_change_val) * 100
        # Store absolute value rounded to 2 decimals (no sign, no % symbol) for numeric sorting
        # Take absolute value FIRST, then round to avoid any sign issues
        change_numeric = round(abs(change_pct), 2)
        # Double-check: ensure it's never negative (handle edge cases)
        if change_numeric < 0:
            change_numeric = abs(change_numeric)
        # Store sign for color coding: 1 (positive), -1 (negative), 0 (neutral)
        change_sign = 1 if change_pct > 0 else (-1 if change_pct < 0 else 0)
        # Direction text
        direction = "Up" if change_pct > 0 else ("Down" if change_pct < 0 else "-")
    else:
        change_numeric = None
        change_sign = None
        direction = "N/A"

    return {
        "Institution": holder.get("holder_name", "N/A"),
        "Shares": holder.get("shares_display", "N/A"),
        "Value": holder.get("value_display", "N/A"),
        "% Held": holder.get("percent_held_display", "N/A"),
        "Direction": direction,
        "% Change": change_numeric,  # Absolute value, numeric, sortable (always positive or None)
        "_change_sign": change_sign,  # Hidden: used only for color coding
        "Date Reported": holder.get("date_reported", "N/A"),
    }


def _create_institutional_holders_dataframe(
    holders: List[Dict[str, Any]],
) -> pd.DataFrame:
    """Create DataFrame from holder data with all formatting applied."""
    holders_data = [_process_holder_data(holder) for holder in holders]
    df = pd.DataFrame(holders_data)
    # Ensure % Change column is always positive (absolute values only)
    if "% Change" in df.columns:
        df["% Change"] = df["% Change"].apply(
            lambda x: abs(x) if x is not None and pd.notna(x) and x < 0 else x
        )
    return df


def _setup_color_css() -> None:
    """Add CSS styles for color-coded % Change cells."""
    st.markdown(
        """
    <style>
    .positive-pct-change {
        background-color: #d4edda !important;
        color: #155724 !important;
        font-weight: 500;
    }
    .negative-pct-change {
        background-color: #f8d7da !important;
        color: #721c24 !important;
        font-weight: 500;
    }
    .neutral-pct-change {
        background-color: #e2e3e5 !important;
        color: #383d41 !important;
    }
    </style>
    """,
        unsafe_allow_html=True,
    )


def _configure_aggrid_columns(gb: "GridOptionsBuilder") -> None:
    """Configure ag-grid column definitions with all required settings (no filters)."""
    # Institution column
    gb.configure_column("Institution", width=300, filterable=False)

    # Shares column
    gb.configure_column("Shares", width=120, filterable=False)

    # Value column
    gb.configure_column("Value", width=120, filterable=False)

    # % Held column
    gb.configure_column("% Held", width=100, filterable=False)

    # Direction column
    gb.configure_column("Direction", width=80, filterable=False)

    # % Change column: numeric, sortable, color-coded, formatted with % symbol
    # Value is always positive (absolute), sign determined by _change_sign for coloring
    gb.configure_column(
        "% Change",
        width=120,
        type=["numericColumn"],
        filterable=False,
        cellClassRules={
            "positive-pct-change": "params.data._change_sign === 1",
            "negative-pct-change": "params.data._change_sign === -1",
            "neutral-pct-change": "params.data._change_sign === 0 || params.data._change_sign === null || params.data._change_sign === undefined",
        },
        # Format as absolute value with % symbol (no +/- signs)
        valueFormatter="params.value !== null && params.value !== undefined ? Math.abs(params.value).toFixed(2) + '%' : 'N/A'",
    )

    # Hide helper column used for color coding
    gb.configure_column("_change_sign", hide=True, filterable=False)

    # Date Reported column
    gb.configure_column("Date Reported", width=130, filterable=False)


def _display_summary_metrics(
    holders: List[Dict[str, Any]], before_table: bool = False
) -> None:
    """
    Display summary metrics above or below the grid.

    Args:
        holders: List of holder dictionaries
        before_table: If True, display directly before table (no expander); if False, display after table with divider
    """
    total_holders = len(holders)
    total_shares = sum(h.get("shares", 0) or 0 for h in holders)
    total_value = sum(h.get("value", 0) or 0 for h in holders)

    # Display metrics in columns
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Number of Holders", total_holders)
    with col2:
        if total_shares > 0:
            st.metric("Total Shares", format_number(total_shares))
        else:
            st.metric("Total Shares", "N/A")
    with col3:
        if total_value > 0:
            st.metric("Total Value", format_currency(total_value))
        else:
            st.metric("Total Value", "N/A")

    # Add divider only when displaying after table
    if not before_table:
        st.markdown("---")


def _display_fallback_dataframe(holders: List[Dict[str, Any]]) -> None:
    """Fallback display using standard Streamlit dataframe."""
    holders_data = []
    for holder in holders:
        processed = _process_holder_data(holder)
        # For fallback, format % Change as string
        pct_change = processed.get("% Change")
        if pct_change is not None:
            processed["% Change"] = f"{pct_change:.2f}%"
        holders_data.append(processed)

    # Remove hidden column
    for row in holders_data:
        row.pop("_change_sign", None)

    df = pd.DataFrame(holders_data)
    st.dataframe(df, width="stretch", hide_index=True)


def display_institutional_holders_grid(
    holders: List[Dict[str, Any]], height: int = 400, show_summary: bool = True
) -> None:
    """
    Display institutional holders in a standardized ag-grid format.

    Features:
    - Numeric, sortable % Change column (absolute value, no +/- signs, displays with %)
    - Direction column (Up/Down/-) indicating change direction
    - Color-coded cells: green (positive), red (negative), gray (neutral)
    - All columns sortable and resizable
    - Summary metrics displayed between header and table

    Args:
        holders: List of holder dictionaries from API
        height: Grid height in pixels (default: 400)
        show_summary: Whether to display summary metrics (default: True)
    """
    # Handle empty data
    if not holders:
        st.info(
            "Institutional holders data is not available for this symbol. Holder data may not have been loaded yet."
        )
        return

    # Display summary metrics before table if requested
    if show_summary:
        _display_summary_metrics(holders, before_table=True)

    # Try to use ag-grid
    try:
        from st_aggrid import AgGrid, GridOptionsBuilder

        # Process data and create DataFrame
        holders_df = _create_institutional_holders_dataframe(holders)

        # Setup CSS for color coding
        _setup_color_css()

        # Configure ag-grid
        gb = GridOptionsBuilder.from_dataframe(holders_df)
        gb.configure_pagination(paginationAutoPageSize=True)
        gb.configure_side_bar(filters_panel=False, columns_panel=True)
        gb.configure_default_column(
            groupable=True, sortable=True, filterable=False, resizable=True
        )

        # Configure individual columns
        _configure_aggrid_columns(gb)

        # Build and display grid
        grid_options = gb.build()
        AgGrid(
            holders_df,
            gridOptions=grid_options,
            theme="streamlit",
            height=height,
            allow_unsafe_jscode=False,
        )

    except ImportError:
        # Fallback if ag-grid is not available
        st.warning("[WARN] ag-grid not available. Using standard dataframe display.")
        _display_fallback_dataframe(holders)

    except Exception as e:
        # Error fallback
        st.error(f"Error displaying institutional holders grid: {e}")
        _display_fallback_dataframe(holders)


# -- Market status banner ------------------------------------------------------


def _parse_market_dt(s: str) -> "datetime | None":
    from datetime import datetime

    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            ts = s.replace("Z", "+00:00") if s.endswith("Z") else s
            return datetime.strptime(ts, fmt)
        except ValueError:
            continue
    return None


def render_market_banner(clock: dict) -> None:
    """Render a consistent market open/closed status banner.

    Uses the same CSS classes as styles.css (.market-open-banner /
    .market-closed-banner) so the appearance is identical on every page.
    """
    is_open: bool = clock.get("is_open", False)
    next_open = _parse_market_dt(clock.get("next_open", ""))
    next_close = _parse_market_dt(clock.get("next_close", ""))

    if is_open:
        css_class = "market-open-banner"
        dot = "*"
        status = "Market Open"
        if next_close:
            try:
                closes = next_close.strftime("%I:%M %p ET")
            except Exception:
                closes = str(next_close)
            detail = f'<span class="market-time">Closes {closes}</span>'
        else:
            detail = ""
    else:
        css_class = "market-closed-banner"
        dot = "o"
        status = "Market Closed"
        if next_open:
            try:
                opens = next_open.strftime("%I:%M %p ET")
            except Exception:
                opens = str(next_open)
            detail = f'<span class="market-time">Opens {opens}</span>'
        else:
            detail = ""

    st.markdown(
        f'<div class="market-banner {css_class}">'
        f"{dot}&nbsp;&nbsp;<strong>{status}</strong>&nbsp;&nbsp;{detail}"
        f"</div>",
        unsafe_allow_html=True,
    )
