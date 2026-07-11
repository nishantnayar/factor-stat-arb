"""
Utilities module for Streamlit UI
Re-exports functions from the parent utils.py file
"""

import importlib.util
import os
import sys

# Import from parent utils.py file
# We need to import it as a module from the parent directory
parent_dir = os.path.dirname(os.path.dirname(__file__))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import the utils module (the file, not this package)
utils_file_path = os.path.join(parent_dir, 'utils.py')
spec = importlib.util.spec_from_file_location("streamlit_ui_utils", utils_file_path)
utils_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(utils_module)

# Re-export all public functions and classes
__all__ = [
    'format_currency',
    'format_percentage',
    'format_number',
    'format_date',
    'get_timeframe_days',
    'get_date_range',
    'calculate_returns',
    'calculate_volatility',
    'calculate_sharpe_ratio',
    'calculate_max_drawdown',
    'create_price_chart',
    'create_candlestick_chart',
    'create_volume_chart',
    'create_pie_chart',
    'initialize_session_state',
    'update_session_state',
    'get_session_state',
    'reset_session_state',
    'load_custom_css',
    'create_metric_card',
    'create_info_card',
    'create_expandable_section',
    'validate_symbol',
    'validate_date_range',
    'validate_numeric_input',
    'handle_api_error',
    'show_loading_spinner',
    'show_success_message',
    'show_warning_message',
    'show_error_message',
    'show_info_message',
    'convert_api_data_to_ohlc',
    'get_real_market_data',
    'generate_ohlc_data',
    'create_lightweight_ohlc_chart',
    'create_lightweight_volume_chart',
    'create_lightweight_rsi_chart',
    'create_lightweight_macd_chart',
    'create_candlestick_chart_with_overlays',
    'get_technical_indicators_from_db',
    'get_latest_technical_indicators',
    'get_latest_esg_scores',
    'get_latest_key_statistics',
    'get_institutional_holders',
    'display_institutional_holders_grid',
    'ohlc_data_to_dataframe',
    'filter_ohlc_data_by_timeframe',
    'create_rsi_chart',
    'create_macd_chart',
    'render_market_banner',
]

# Re-export all functions
format_currency = utils_module.format_currency
format_percentage = utils_module.format_percentage
format_number = utils_module.format_number
format_date = utils_module.format_date
get_timeframe_days = utils_module.get_timeframe_days
get_date_range = utils_module.get_date_range
calculate_returns = utils_module.calculate_returns
calculate_volatility = utils_module.calculate_volatility
calculate_sharpe_ratio = utils_module.calculate_sharpe_ratio
calculate_max_drawdown = utils_module.calculate_max_drawdown
create_price_chart = utils_module.create_price_chart
create_candlestick_chart = utils_module.create_candlestick_chart
create_volume_chart = utils_module.create_volume_chart
create_pie_chart = utils_module.create_pie_chart
initialize_session_state = utils_module.initialize_session_state
update_session_state = utils_module.update_session_state
get_session_state = utils_module.get_session_state
reset_session_state = utils_module.reset_session_state
load_custom_css = utils_module.load_custom_css
create_metric_card = utils_module.create_metric_card
create_info_card = utils_module.create_info_card
create_expandable_section = utils_module.create_expandable_section
validate_symbol = utils_module.validate_symbol
validate_date_range = utils_module.validate_date_range
validate_numeric_input = utils_module.validate_numeric_input
handle_api_error = utils_module.handle_api_error
show_loading_spinner = utils_module.show_loading_spinner
show_success_message = utils_module.show_success_message
show_warning_message = utils_module.show_warning_message
show_error_message = utils_module.show_error_message
show_info_message = utils_module.show_info_message
convert_api_data_to_ohlc = utils_module.convert_api_data_to_ohlc
get_real_market_data = utils_module.get_real_market_data
generate_ohlc_data = utils_module.generate_ohlc_data
create_lightweight_ohlc_chart = utils_module.create_lightweight_ohlc_chart
create_lightweight_volume_chart = utils_module.create_lightweight_volume_chart
create_lightweight_rsi_chart = utils_module.create_lightweight_rsi_chart
create_lightweight_macd_chart = utils_module.create_lightweight_macd_chart
create_candlestick_chart_with_overlays = utils_module.create_candlestick_chart_with_overlays
get_technical_indicators_from_db = utils_module.get_technical_indicators_from_db
get_latest_technical_indicators = utils_module.get_latest_technical_indicators
get_latest_esg_scores = utils_module.get_latest_esg_scores
get_latest_key_statistics = utils_module.get_latest_key_statistics
get_institutional_holders = utils_module.get_institutional_holders
display_institutional_holders_grid = utils_module.display_institutional_holders_grid
ohlc_data_to_dataframe = utils_module.ohlc_data_to_dataframe
filter_ohlc_data_by_timeframe = utils_module.filter_ohlc_data_by_timeframe
create_rsi_chart = utils_module.create_rsi_chart
create_macd_chart = utils_module.create_macd_chart
render_market_banner = utils_module.render_market_banner
