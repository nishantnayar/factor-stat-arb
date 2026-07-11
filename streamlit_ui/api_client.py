"""
API Client for connecting Streamlit UI to the Trading System API
"""

import os
from typing import Any, Dict, List, Optional

import requests
import streamlit as st


class TradingSystemAPI:
    """Client for interacting with the Trading System API"""
    
    def __init__(self, base_url: str = "http://localhost:8001"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
    
    def _make_request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request to API with error handling"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError:
            st.error(
                "[Error] Cannot connect to API server. "
                "Please ensure the API is running on port 8001."
            )
            return {"error": "Connection failed"}
        except requests.exceptions.HTTPError as e:
            st.error(f"[Error] API Error: {e}")
            return {"error": f"HTTP {e.response.status_code}"}
        except Exception as e:
            st.error(f"[Error] Unexpected error: {e}")
            return {"error": str(e)}
    
    def health_check(self) -> Dict[str, Any]:
        """Check API health status"""
        return self._make_request("GET", "/health")
    
    # Market Data API
    def get_market_data(
        self,
        symbol: str,
        limit: Optional[int] = None,
        offset: int = 0,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        data_source: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get market data for a specific symbol"""
        params = {
            "offset": offset,
            "start_date": start_date,
            "end_date": end_date,
            "data_source": data_source,
        }
        # Only add limit if provided
        if limit is not None:
            params["limit"] = limit
        
        # Filter out None values
        params = {k: v for k, v in params.items() if v is not None}
        result = self._make_request("GET", f"/api/market-data/data/{symbol}", params=params)
        return result if isinstance(result, list) else []

    def get_latest_market_data(self, symbol: str, data_source: Optional[str] = None) -> Dict[str, Any]:
        """Get latest market data for a specific symbol"""
        params = {"data_source": data_source} if data_source else {}
        return self._make_request("GET", f"/api/market-data/data/{symbol}/latest", params=params)

    def get_ohlc_summary(self, symbol: str) -> Dict[str, Any]:
        """Get OHLC summary for a specific symbol"""
        return self._make_request("GET", f"/api/market-data/data/{symbol}/ohlc")

    def get_available_sources(self, symbol: str) -> Dict[str, Any]:
        """Get available data sources for a specific symbol"""
        return self._make_request("GET", f"/api/market-data/data/{symbol}/sources")
    
    # Company Information API
    @st.cache_data(ttl=1800)  # Cache for 30 minutes
    def get_company_info(_self, symbol: str) -> Dict[str, Any]:
        """Get company information for a symbol"""
        return _self._make_request("GET", f"/api/company-info/{symbol}")
    
    @st.cache_data(ttl=3600)  # Cache for 1 hour
    def get_sectors(_self) -> List[str]:
        """Get list of unique sectors from database"""
        result = _self._make_request("GET", "/api/company-info/filters/sectors")
        return result if isinstance(result, list) else []
    
    @st.cache_data(ttl=3600)  # Cache for 1 hour
    def get_industries(_self, sector: Optional[str] = None) -> List[str]:
        """Get list of unique industries from database, optionally filtered by sector"""
        params = {}
        if sector:
            params["sector"] = sector
        
        result = _self._make_request("GET", "/api/company-info/filters/industries", params=params)
        return result if isinstance(result, list) else []
    
    @st.cache_data(ttl=3600)  # Cache for 1 hour
    def get_symbols_by_filter(_self, sector: Optional[str] = None, industry: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get symbols filtered by sector and/or industry"""
        params = {}
        if sector:
            params["sector"] = sector
        if industry:
            params["industry"] = industry
        
        result = _self._make_request("GET", "/api/company-info/filters/symbols", params=params)
        return result if isinstance(result, list) else []
    
    def get_all_symbols(self) -> List[Dict[str, Any]]:
        """Get all symbols from database"""
        return self.get_symbols_by_filter()
    
    def get_symbols_by_industry(self, industry: str) -> List[Dict[str, Any]]:
        """Get symbols filtered by industry"""
        return self.get_symbols_by_filter(industry=industry)
    
    def get_symbols_by_sector(self, sector: str) -> List[Dict[str, Any]]:
        """Get symbols filtered by sector"""
        return self.get_symbols_by_filter(sector=sector)
    
    def get_symbols_by_industry_and_sector(self, industry: str, sector: str) -> List[Dict[str, Any]]:
        """Get symbols filtered by both industry and sector"""
        return self.get_symbols_by_filter(sector=sector, industry=industry)
    
    # --- Alpaca Trading API (live data - no caching) ---

    def get_market_clock(self) -> Dict[str, Any]:
        """Get current market clock (open/closed, next open/close times)."""
        return self._make_request("GET", "/clock")

    def get_alpaca_account(self) -> Dict[str, Any]:
        """Get Alpaca account information (equity, cash, buying power, etc.)."""
        return self._make_request("GET", "/account")

    def get_alpaca_positions(self) -> List[Dict[str, Any]]:
        """Get all open positions."""
        result = self._make_request("GET", "/positions")
        return result if isinstance(result, list) else []

    def get_alpaca_orders(self, status: str = "open", limit: int = 50) -> List[Dict[str, Any]]:
        """Get orders filtered by status ('open', 'closed', 'all')."""
        result = self._make_request("GET", "/orders", params={"status": status, "limit": limit})
        return result if isinstance(result, list) else []

    def get_alpaca_trades(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent filled trades."""
        result = self._make_request("GET", "/trades", params={"limit": limit})
        return result if isinstance(result, list) else []

    def place_order(
        self,
        symbol: str,
        qty: int,
        side: str,
        order_type: str = "market",
        time_in_force: str = "day",
        limit_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Place a new order."""
        params: Dict[str, Any] = {
            "symbol": symbol,
            "qty": qty,
            "side": side,
            "order_type": order_type,
            "time_in_force": time_in_force,
        }
        if limit_price is not None:
            params["limit_price"] = limit_price
        return self._make_request("POST", "/orders", params=params)

    def close_position(self, symbol: str) -> Dict[str, Any]:
        """Close an open position by symbol."""
        return self._make_request("POST", f"/positions/{symbol}/close")

    def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel an open order by ID."""
        return self._make_request("DELETE", f"/orders/{order_id}")

    # Data Quality API
    def get_data_quality_summary(self) -> Dict[str, Any]:
        """Get overall data ingestion health summary."""
        return self._make_request("GET", "/api/data-quality/summary")

    def get_ingestion_status(self) -> List[Dict[str, Any]]:
        """Get per-symbol ingestion status with staleness info."""
        result = self._make_request("GET", "/api/data-quality/ingestion-status")
        return result if isinstance(result, list) else []

    def get_data_quality_alerts(self) -> List[Dict[str, Any]]:
        """Get stale or failed ingestion entries only."""
        result = self._make_request("GET", "/api/data-quality/alerts")
        return result if isinstance(result, list) else []

    # Key Statistics API
    @st.cache_data(ttl=3600)  # Cache for 1 hour
    def get_key_statistics(_self, symbol: str) -> Dict[str, Any]:
        """Get key statistics for a symbol"""
        return _self._make_request("GET", f"/api/key-statistics/{symbol}")
    
    # Institutional Holders API
    @st.cache_data(ttl=3600)  # Cache for 1 hour
    def get_institutional_holders(_self, symbol: str, limit: int = 10) -> Dict[str, Any]:
        """Get institutional holders for a symbol"""
        params = {"limit": limit}
        return _self._make_request("GET", f"/api/institutional-holders/{symbol}", params=params)


# Global API client instance
@st.cache_resource
def get_api_client() -> TradingSystemAPI:
    """Get cached API client instance"""
    base_url = os.getenv("API_BASE_URL", "http://localhost:8001")
    return TradingSystemAPI(base_url)


def format_currency(value: float) -> str:
    """Format currency values"""
    if value >= 1_000_000:
        return f"${value/1_000_000:.1f}M"
    elif value >= 1_000:
        return f"${value/1_000:.1f}K"
    else:
        return f"${value:,.2f}"


def format_percentage(value: float) -> str:
    """Format percentage values"""
    return f"{value:.2f}%"


def get_timeframe_days(timeframe: str) -> int:
    """Convert timeframe string to days"""
    timeframe_map = {
        "1D": 1,
        "1W": 7,
        "1M": 30,
        "3M": 90,
        "6M": 180,
        "1Y": 365
    }
    return timeframe_map.get(timeframe, 30)
