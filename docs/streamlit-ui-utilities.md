# Streamlit UI Utilities - Usage Examples

## Overview
The `utils.py` module provides common utilities for the Trading System Streamlit UI, including formatting, data processing, chart creation, and session state management.

## Error handling and encoding

- Shared helpers (`utils.py`, `api_client.py`, `streamlit_app.py`, `css_config.py`) use **ASCII-only** Python strings. User-visible errors typically use a `[Error]` or `[WARN]` text prefix instead of emoji.
- **Multipage app content** in `streamlit_ui/pages/` may still use Unicode for labels and narrative text (project policy). Do not move display-only Unicode into shared modules if that would break the ASCII rule.
- Functions such as `display_api_error`, `show_success_message`, and `show_error_message` centralize feedback; prefer them over ad hoc `st.error` strings for consistency.

## Formatting Utilities

### Currency Formatting
```python
from ..utils import format_currency

# Basic currency formatting
value = 1250000
formatted = format_currency(value)  # "$1.25M"

# Custom currency and decimals
formatted = format_currency(value, currency="€", decimals=1)  # "€1.3M"
```

### Percentage Formatting
```python
from ..utils import format_percentage

# Basic percentage formatting
return_rate = 0.152
formatted = format_percentage(return_rate)  # "+15.20%"

# Without sign
formatted = format_percentage(return_rate, show_sign=False)  # "15.20%"
```

### Number Formatting
```python
from ..utils import format_number

# Automatic scaling
volume = 1500000
formatted = format_number(volume)  # "1.50M"
```

## Data Processing Utilities

### Timeframe and Date Range
```python
from ..utils import get_timeframe_days, get_date_range

# Get days for timeframe
days = get_timeframe_days("1M")  # 30

# Get date range
start_date, end_date = get_date_range("1M")
# Returns: ("2024-09-25T10:30:00", "2024-10-25T10:30:00")
```

### Financial Calculations
```python
from ..utils import calculate_returns, calculate_volatility, calculate_sharpe_ratio

# Calculate returns from prices
returns = calculate_returns(price_series)

# Calculate rolling volatility
volatility = calculate_volatility(returns, window=30)

# Calculate Sharpe ratio
sharpe = calculate_sharpe_ratio(returns, risk_free_rate=0.02)
```

## Chart Creation Utilities

### Price Charts
```python
from ..utils import create_price_chart

# Create a simple price chart
fig = create_price_chart(
    dates=dates_series,
    prices=prices_series,
    title="AAPL Price Chart",
    symbol="AAPL",
    color="#2E8B57"
)
st.plotly_chart(fig, width='stretch')
```

### Candlestick Charts
```python
from ..utils import create_candlestick_chart

# Create OHLC candlestick chart
fig = create_candlestick_chart(
    dates=dates_series,
    open_prices=open_series,
    high_prices=high_series,
    low_prices=low_series,
    close_prices=close_series,
    title="AAPL OHLC Chart",
    symbol="AAPL"
)
st.plotly_chart(fig, width='stretch')
```

### Volume Charts
```python
from ..utils import create_volume_chart

# Create volume bar chart
fig = create_volume_chart(
    dates=dates_series,
    volumes=volume_series,
    title="AAPL Volume",
    color="lightblue"
)
st.plotly_chart(fig, width='stretch')
```

### Pie Charts
```python
from ..utils import create_pie_chart

# Create portfolio allocation pie chart
fig = create_pie_chart(
    labels=["Stocks", "Bonds", "Cash"],
    values=[70, 20, 10],
    title="Portfolio Allocation",
    colors=["#1f77b4", "#ff7f0e", "#2ca02c"]
)
st.plotly_chart(fig, width='stretch')
```

## Session State Management

### Initialization
```python
from ..utils import initialize_session_state

# Initialize all default session state values
initialize_session_state()
```

### Getting and Setting Values
```python
from ..utils import get_session_state, update_session_state

# Get session state value with default
symbol = get_session_state('selected_symbol', 'AAPL')

# Update session state
update_session_state('portfolio_value', 150000)
```

### Reset Session State
```python
from ..utils import reset_session_state

# Reset all session state to defaults
reset_session_state()
```

## UI Components

### Metric Cards
```python
from ..utils import create_metric_card

# Create styled metric card
create_metric_card(
    title="Portfolio Value",
    value="$125,000",
    delta="$5,000",
    delta_color="normal"
)
```

### Info Cards
```python
from ..utils import create_info_card

# Create info card
create_info_card(
    title="Market Status",
    content="Market is currently open. Next close at 4:00 PM EST."
)
```

### Expandable Sections
```python
from ..utils import create_expandable_section

# Create expandable section
create_expandable_section(
    title="Debug Information",
    content="Session state values and system status",
    expanded=False
)
```

## Error Handling and Messages

### Loading Spinners
```python
from ..utils import show_loading_spinner

# Show loading spinner
with show_loading_spinner("Loading market data..."):
    # Your data loading code here
    data = load_market_data()
```

### User Messages
```python
from ..utils import show_success_message, show_warning_message, show_error_message, show_info_message

# Show different types of messages
show_success_message("Data loaded successfully!")
show_warning_message("API rate limit approaching")
show_error_message("Failed to connect to database")
show_info_message("Market will close in 30 minutes")
```

## Data Validation

### Input Validation
```python
from ..utils import validate_symbol, validate_numeric_input, validate_date_range

# Validate stock symbol
if validate_symbol("AAPL"):
    st.success("Valid symbol")

# Validate numeric input
if validate_numeric_input(portfolio_value, min_val=0, max_val=1000000):
    st.success("Valid portfolio value")

# Validate date range
if validate_date_range("2024-01-01", "2024-12-31"):
    st.success("Valid date range")
```

## Complete Example

Here's a complete example of using the utilities in a Streamlit page:

```python
import streamlit as st
import pandas as pd
from ..utils import (
    initialize_session_state, format_currency, format_percentage,
    create_price_chart, create_metric_card, show_loading_spinner,
    validate_symbol, show_error_message
)

def analysis_page():
    # Initialize session state
    initialize_session_state()
    
    st.title("Market Analysis")
    
    # Get symbol from session state
    symbol = st.session_state.get('selected_symbol', 'AAPL')
    
    # Validate symbol
    if not validate_symbol(symbol):
        show_error_message("Invalid symbol selected")
        return
    
    # Show loading spinner while processing
    with show_loading_spinner("Loading market data..."):
        # Load your data here
        data = load_market_data(symbol)
    
    # Create metric cards
    col1, col2, col3 = st.columns(3)
    
    with col1:
        create_metric_card(
            title="Current Price",
            value=format_currency(data['price']),
            delta=format_percentage(data['change'])
        )
    
    with col2:
        create_metric_card(
            title="Volume",
            value=format_number(data['volume']),
            delta="+5.2%"
        )
    
    with col3:
        create_metric_card(
            title="Market Cap",
            value=format_currency(data['market_cap']),
            delta=None
        )
    
    # Create price chart
    fig = create_price_chart(
        dates=data['dates'],
        prices=data['prices'],
        title=f"{symbol} Price Chart",
        symbol=symbol
    )
    
    st.plotly_chart(fig, width='stretch')
```

## Benefits

1. **Consistency**: All pages use the same formatting and styling
2. **Reusability**: Common functions can be used across multiple pages
3. **Maintainability**: Changes to utilities affect all pages automatically
4. **Error Handling**: Centralized error handling and user feedback
5. **Validation**: Consistent data validation across the application
6. **Performance**: Optimized chart creation and data processing
