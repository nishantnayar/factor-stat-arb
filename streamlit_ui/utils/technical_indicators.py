"""
Technical Indicator Calculations
RSI, MACD, Moving Averages, etc.

This module uses pandas-ta library for technical indicator calculations
while maintaining a simple API that accepts lists and returns single values.
"""

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

# Import pandas_ta to register the pandas DataFrame extension (df.ta.*)
# We use df.ta.sma(), df.ta.ema(), etc. in the code, so we need the extension registered
try:
    import pandas_ta as ta  # type: ignore[import-untyped]
except ImportError:
    # pandas-ta-classic might register the extension when the package is installed
    # Try to verify the extension is available
    if hasattr(pd.DataFrame, 'ta'):
        # Extension is already registered (might be auto-registered by pandas-ta-classic)
        ta = None  # type: ignore[assignment, unused-ignore]
    else:
        # Try to import pandas_ta_classic to register the extension
        try:
            import pandas_ta_classic  # type: ignore[import-untyped]

            # Check if extension is now available
            if not hasattr(pd.DataFrame, 'ta'):
                raise ImportError(
                    "pandas.ta extension not available. "
                    "Please ensure 'pandas-ta-classic>=0.3.15' is properly installed."
                )
            ta = None  # type: ignore[assignment, unused-ignore]
        except ImportError:
            raise ImportError(
                "pandas_ta module not found and pandas.ta extension not available. "
                "Please install 'pandas-ta-classic>=0.3.15' for Python 3.11."
            )


def calculate_sma(prices: List[float], period: int) -> Optional[float]:
    """
    Calculate Simple Moving Average using pandas-ta
    
    Args:
        prices: List of prices
        period: Period for SMA
        
    Returns:
        SMA value or None if insufficient data
    """
    if len(prices) < period:
        return None
    
    df = pd.DataFrame({'close': prices})
    df.ta.sma(length=period, append=True)
    result = df[f'SMA_{period}'].iloc[-1]
    return float(result) if pd.notna(result) else None


def calculate_ema(prices: List[float], period: int, alpha: Optional[float] = None) -> Optional[float]:
    """
    Calculate Exponential Moving Average using pandas-ta
    
    Args:
        prices: List of prices
        period: Period for EMA
        alpha: Smoothing factor (ignored, pandas-ta calculates automatically)
        
    Returns:
        EMA value or None if insufficient data
    """
    if len(prices) < period:
        return None
    
    df = pd.DataFrame({'close': prices})
    df.ta.ema(length=period, append=True)
    result = df[f'EMA_{period}'].iloc[-1]
    return float(result) if pd.notna(result) else None


def calculate_rsi(prices: List[float], period: int = 14) -> Optional[float]:
    """
    Calculate Relative Strength Index (RSI) using pandas-ta
    
    Args:
        prices: List of closing prices
        period: RSI period (default: 14)
        
    Returns:
        RSI value (0-100) or None if insufficient data
    """
    if len(prices) < period + 1:
        return None
    
    df = pd.DataFrame({'close': prices})
    df.ta.rsi(length=period, append=True)
    result = df[f'RSI_{period}'].iloc[-1]
    return float(result) if pd.notna(result) else None


def calculate_macd(
    prices: List[float], 
    fast_period: int = 12, 
    slow_period: int = 26, 
    signal_period: int = 9
) -> Optional[Dict[str, float]]:
    """
    Calculate MACD (Moving Average Convergence Divergence) using pandas-ta
    
    Args:
        prices: List of closing prices
        fast_period: Fast EMA period (default: 12)
        slow_period: Slow EMA period (default: 26)
        signal_period: Signal line EMA period (default: 9)
        
    Returns:
        Dictionary with 'macd', 'signal', and 'histogram' values
    """
    if len(prices) < slow_period + signal_period:
        return None
    
    df = pd.DataFrame({'close': prices})
    df.ta.macd(fast=fast_period, slow=slow_period, signal=signal_period, append=True)
    
    # pandas-ta column names: MACD_12_26_9, MACDs_12_26_9, MACDh_12_26_9
    macd_col = f'MACD_{fast_period}_{slow_period}_{signal_period}'
    signal_col = f'MACDs_{fast_period}_{slow_period}_{signal_period}'
    hist_col = f'MACDh_{fast_period}_{slow_period}_{signal_period}'
    
    macd_line = df[macd_col].iloc[-1]
    signal_line = df[signal_col].iloc[-1]
    histogram = df[hist_col].iloc[-1]
    
    if pd.isna(macd_line) or pd.isna(signal_line) or pd.isna(histogram):
        return None
    
    return {
        'macd': float(macd_line),
        'signal': float(signal_line),
        'histogram': float(histogram)
    }


def calculate_bollinger_bands(
    prices: List[float], 
    period: int = 20, 
    std_dev: float = 2.0
) -> Optional[Dict[str, float]]:
    """
    Calculate Bollinger Bands using pandas-ta
    
    Args:
        prices: List of closing prices
        period: Period for moving average (default: 20)
        std_dev: Standard deviation multiplier (default: 2.0)
        
    Returns:
        Dictionary with 'upper', 'middle', and 'lower' band values
    """
    if len(prices) < period:
        return None
    
    df = pd.DataFrame({'close': prices})
    df.ta.bbands(length=period, std=std_dev, append=True)
    
    # pandas-ta column names: BBU_20_2.0, BBM_20_2.0, BBL_20_2.0
    # Find columns dynamically to handle different std_dev formats
    upper_cols = [col for col in df.columns if col.startswith('BBU_')]
    middle_cols = [col for col in df.columns if col.startswith('BBM_')]
    lower_cols = [col for col in df.columns if col.startswith('BBL_')]
    
    if not (upper_cols and middle_cols and lower_cols):
        return None
    
    upper = df[upper_cols[0]].iloc[-1]
    middle = df[middle_cols[0]].iloc[-1]
    lower = df[lower_cols[0]].iloc[-1]
    
    if pd.isna(upper) or pd.isna(middle) or pd.isna(lower):
        return None
    
    return {
        'upper': float(upper),
        'middle': float(middle),
        'lower': float(lower)
    }


def calculate_price_change(prices: List[float], periods: int = 1) -> Optional[float]:
    """
    Calculate price change percentage
    
    Args:
        prices: List of prices
        periods: Number of periods to look back (default: 1)
        
    Returns:
        Price change percentage or None if insufficient data
    """
    if len(prices) < periods + 1:
        return None
    
    current = prices[-1]
    previous = prices[-(periods + 1)]
    
    if previous == 0:
        return None
    
    change_pct = ((current - previous) / previous) * 100
    return float(change_pct)


def calculate_volatility(prices: List[float], period: int = 20) -> Optional[float]:
    """
    Calculate price volatility (standard deviation of returns)
    
    Args:
        prices: List of closing prices
        period: Period for calculation (default: 20)
        
    Returns:
        Volatility (annualized) or None if insufficient data
    """
    if len(prices) < period + 1:
        return None
    
    # Calculate returns using pandas
    df = pd.DataFrame({'close': prices})
    returns = df['close'].pct_change().dropna()
    
    # Get the last 'period' returns
    recent_returns = returns.iloc[-period:]
    
    if len(recent_returns) == 0:
        return None
    
    # Calculate standard deviation and annualize (assuming daily data)
    std_dev = recent_returns.std()
    annualized_vol = std_dev * np.sqrt(252) * 100  # Convert to percentage
    
    return float(annualized_vol)

