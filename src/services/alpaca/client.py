"""
Alpaca Trading API Client
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, cast

import pandas as pd
from alpaca.common.exceptions import APIError
from alpaca.data.enums import Adjustment
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.models import BarSet
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import QueryOrderStatus
from alpaca.trading.models import Clock, Order, Position, TradeAccount
from alpaca.trading.requests import (
    GetOrdersRequest,
    LimitOrderRequest,
    MarketOrderRequest,
    StopOrderRequest,
)

from .exceptions import AlpacaAPIError, AlpacaAuthenticationError, AlpacaConnectionError

logger = logging.getLogger(__name__)


class AlpacaClient:
    """Alpaca Trading API Client for paper trading"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        base_url: Optional[str] = None,
        is_paper: bool = True,
    ):
        """
        Initialize Alpaca client

        Args:
            api_key: Alpaca API key
            secret_key: Alpaca secret key
            base_url: Alpaca API base URL
            is_paper: Whether to use paper trading
        """
        self.api_key = api_key or os.getenv("ALPACA_API_KEY")
        self.secret_key = secret_key or os.getenv("ALPACA_SECRET_KEY")
        self.is_paper = is_paper

        if is_paper:
            self.base_url = base_url or "https://paper-api.alpaca.markets"
        else:
            self.base_url = base_url or "https://api.alpaca.markets"

        if not self.api_key or not self.secret_key:
            raise AlpacaAuthenticationError("Alpaca API credentials not provided")

        try:
            self.client = TradingClient(
                api_key=self.api_key,
                secret_key=self.secret_key,
                paper=is_paper,
            )
            self.data_client = StockHistoricalDataClient(
                api_key=self.api_key,
                secret_key=self.secret_key,
            )
            mode = "paper" if is_paper else "live"
            logger.info("Alpaca client initialized for %s trading", mode)
        except Exception as e:
            raise AlpacaConnectionError(f"Failed to initialize Alpaca client: {str(e)}")

    async def get_account(self) -> Dict[str, Any]:
        """Get account information"""
        try:
            account = cast(TradeAccount, self.client.get_account())
            return {
                "id": str(account.id),
                "account_number": account.account_number,
                "status": account.status,
                "currency": account.currency,
                "buying_power": float(account.buying_power or 0),
                "cash": float(account.cash or 0),
                "portfolio_value": float(account.portfolio_value or 0),
                "equity": float(account.equity or 0),
                "last_equity": float(account.last_equity or 0),
                "created_at": (
                    account.created_at.isoformat() if account.created_at else None
                ),
                "trading_blocked": account.trading_blocked,
                "transfers_blocked": account.transfers_blocked,
                "account_blocked": account.account_blocked,
                "shorting_enabled": account.shorting_enabled,
                "multiplier": float(account.multiplier or 0),
                "long_market_value": float(account.long_market_value or 0),
                "short_market_value": float(account.short_market_value or 0),
                "initial_margin": float(account.initial_margin or 0),
                "maintenance_margin": float(account.maintenance_margin or 0),
                "daytrade_count": account.daytrade_count,
                "pattern_day_trader": account.pattern_day_trader,
            }
        except APIError as e:
            raise AlpacaAPIError(f"Failed to get account: {str(e)}")
        except Exception as e:
            raise AlpacaConnectionError(f"Connection error: {str(e)}")

    async def get_positions(self) -> List[Dict[str, Any]]:
        """Get all positions"""
        try:
            positions = self.client.get_all_positions()
            result = []
            for raw_position in positions:
                position = cast(Position, raw_position)
                result.append(
                    {
                        "asset_id": str(position.asset_id),
                        "symbol": position.symbol,
                        "exchange": position.exchange,
                        "asset_class": position.asset_class,
                        "qty": float(position.qty or 0),
                        "side": position.side,
                        "market_value": float(position.market_value or 0),
                        "cost_basis": float(position.cost_basis or 0),
                        "unrealized_pl": float(position.unrealized_pl or 0),
                        "unrealized_plpc": float(position.unrealized_plpc or 0),
                        "unrealized_intraday_pl": float(
                            position.unrealized_intraday_pl or 0
                        ),
                        "unrealized_intraday_plpc": float(
                            position.unrealized_intraday_plpc or 0
                        ),
                        "current_price": float(position.current_price or 0),
                        "lastday_price": float(position.lastday_price or 0),
                        "change_today": float(position.change_today or 0),
                        "avg_entry_price": float(position.avg_entry_price or 0),
                    }
                )
            return result
        except APIError as e:
            raise AlpacaAPIError(f"Failed to get positions: {str(e)}")
        except Exception as e:
            raise AlpacaConnectionError(f"Connection error: {str(e)}")

    async def get_orders(
        self, status: str = "open", limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get orders.

        `status` accepts either a QueryOrderStatus value ("open", "closed", "all")
        or a specific order status (e.g. "filled", "canceled") for client-side
        filtering, since Alpaca's QueryOrderStatus only distinguishes
        open/closed/all -- it has no server-side filter for individual statuses.
        """
        try:
            query_status_values = {qs.value for qs in QueryOrderStatus}
            if status in query_status_values:
                query_status = QueryOrderStatus(status)
                status_filter = None
            else:
                query_status = QueryOrderStatus.ALL
                status_filter = status

            request = GetOrdersRequest(status=query_status, limit=limit)
            orders = self.client.get_orders(filter=request)
            result = []
            for raw_order in orders:
                order = cast(Order, raw_order)
                if status_filter is not None and order.status != status_filter:
                    continue
                result.append(
                    {
                        "id": str(order.id),
                        "client_order_id": order.client_order_id,
                        "created_at": (
                            order.created_at.isoformat() if order.created_at else None
                        ),
                        "updated_at": (
                            order.updated_at.isoformat() if order.updated_at else None
                        ),
                        "submitted_at": (
                            order.submitted_at.isoformat()
                            if order.submitted_at
                            else None
                        ),
                        "filled_at": (
                            order.filled_at.isoformat() if order.filled_at else None
                        ),
                        "expired_at": (
                            order.expired_at.isoformat() if order.expired_at else None
                        ),
                        "canceled_at": (
                            order.canceled_at.isoformat() if order.canceled_at else None
                        ),
                        "failed_at": (
                            order.failed_at.isoformat() if order.failed_at else None
                        ),
                        "replaced_at": (
                            order.replaced_at.isoformat() if order.replaced_at else None
                        ),
                        "replaced_by": (
                            str(order.replaced_by) if order.replaced_by else None
                        ),
                        "replaces": str(order.replaces) if order.replaces else None,
                        "asset_id": str(order.asset_id),
                        "symbol": order.symbol,
                        "asset_class": order.asset_class,
                        "notional": float(order.notional) if order.notional else None,
                        "qty": float(order.qty) if order.qty else None,
                        "filled_qty": (
                            float(order.filled_qty) if order.filled_qty else None
                        ),
                        "filled_avg_price": (
                            float(order.filled_avg_price)
                            if order.filled_avg_price
                            else None
                        ),
                        "order_class": order.order_class,
                        "order_type": order.order_type,
                        "type": order.type,
                        "side": order.side,
                        "time_in_force": order.time_in_force,
                        "limit_price": (
                            float(order.limit_price) if order.limit_price else None
                        ),
                        "stop_price": (
                            float(order.stop_price) if order.stop_price else None
                        ),
                        "status": order.status,
                        "extended_hours": order.extended_hours,
                        "legs": order.legs,
                        "trail_percent": (
                            float(order.trail_percent) if order.trail_percent else None
                        ),
                        "trail_price": (
                            float(order.trail_price) if order.trail_price else None
                        ),
                        "hwm": float(order.hwm) if order.hwm else None,
                    }
                )
            return result
        except APIError as e:
            raise AlpacaAPIError(f"Failed to get orders: {str(e)}")
        except Exception as e:
            raise AlpacaConnectionError(f"Connection error: {str(e)}")

    async def get_clock(self) -> Dict[str, Any]:
        """Get market clock"""
        try:
            clock = cast(Clock, self.client.get_clock())
            return {
                "timestamp": clock.timestamp.isoformat() if clock.timestamp else None,
                "is_open": clock.is_open,
                "next_open": clock.next_open.isoformat() if clock.next_open else None,
                "next_close": (
                    clock.next_close.isoformat() if clock.next_close else None
                ),
            }
        except APIError as e:
            raise AlpacaAPIError(f"Failed to get clock: {str(e)}")
        except Exception as e:
            raise AlpacaConnectionError(f"Connection error: {str(e)}")

    async def close_position(self, symbol: str) -> Dict[str, Any]:
        """Close a position"""
        try:
            result = cast(Order, self.client.close_position(symbol))
            return {
                "id": str(result.id),
                "client_order_id": result.client_order_id,
                "created_at": (
                    result.created_at.isoformat() if result.created_at else None
                ),
                "symbol": result.symbol,
                "qty": float(result.qty) if result.qty else None,
                "side": result.side,
                "status": result.status,
            }
        except APIError as e:
            raise AlpacaAPIError(f"Failed to close position {symbol}: {str(e)}")
        except Exception as e:
            raise AlpacaConnectionError(f"Connection error: {str(e)}")

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        try:
            self.client.cancel_order_by_id(order_id)
            return True
        except APIError as e:
            raise AlpacaAPIError(f"Failed to cancel order {order_id}: {str(e)}")
        except Exception as e:
            raise AlpacaConnectionError(f"Connection error: {str(e)}")

    async def get_bars(
        self,
        symbol: str,
        limit: int = 500,
        adjustment: str = "all",
    ) -> pd.Series:
        """
        Fetch the last `limit` hourly bars for a symbol.

        Returns a pd.Series of close prices indexed by UTC timestamp.
        Uses Alpaca's market data API - includes today's intraday bars,
        unlike the DB which is end-of-day only.

        A start date is required: without it the Alpaca v2 API returns only
        the current day's bars regardless of the limit value.
        We request enough calendar days to cover `limit` hourly bars
        (assuming ~7 market hours/day, 5 days/week -> ~3.5 bars/calendar day).
        """
        # 4 calendar days per bar is conservative enough to always cover limit
        lookback_days = max(7, (limit * 4) // 7)
        start = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        try:
            request = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=TimeFrame.Hour,
                start=start,
                limit=limit,
                adjustment=Adjustment(adjustment),
            )
            bars = cast(BarSet, self.data_client.get_stock_bars(request))
            if bars is None or len(bars.df) == 0:
                return pd.Series(dtype=float, name=symbol)
            df: pd.DataFrame = bars.df
            if isinstance(df.index, pd.MultiIndex):
                df = cast(pd.DataFrame, df.xs(symbol, level="symbol"))
            df.index = pd.to_datetime(df.index, utc=True)
            return pd.Series(df["close"].rename(symbol), dtype=float)
        except APIError as e:
            raise AlpacaAPIError(f"Failed to get bars for {symbol}: {str(e)}")
        except Exception as e:
            raise AlpacaConnectionError(f"Connection error fetching bars: {str(e)}")

    async def place_order(
        self,
        symbol: str,
        qty: int,
        side: str,
        order_type: str = "market",
        time_in_force: str = "day",
        limit_price: Optional[float] = None,
        stop_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Place an order"""
        try:
            if order_type == "limit":
                order_request: Any = LimitOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=side,
                    time_in_force=time_in_force,
                    limit_price=limit_price,
                )
            elif order_type == "stop":
                order_request = StopOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=side,
                    time_in_force=time_in_force,
                    stop_price=stop_price,
                )
            else:
                order_request = MarketOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=side,
                    time_in_force=time_in_force,
                )
            order = cast(Order, self.client.submit_order(order_data=order_request))
            return {
                "id": str(order.id),
                "client_order_id": order.client_order_id,
                "created_at": (
                    order.created_at.isoformat() if order.created_at else None
                ),
                "symbol": order.symbol,
                "qty": float(order.qty) if order.qty else None,
                "side": order.side,
                "order_type": order.order_type,
                "status": order.status,
            }
        except APIError as e:
            raise AlpacaAPIError(f"Failed to place order: {str(e)}")
        except Exception as e:
            raise AlpacaConnectionError(f"Connection error: {str(e)}")
