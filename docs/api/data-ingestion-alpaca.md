# Alpaca Integration

## Overview

Alpaca Markets provides real-time trading data and account information for live trading operations. The integration supports account management, position tracking, order execution, and trade monitoring.

**Status**: ✅ Implemented (v1.0.0)  
**Data Type**: Real-time account data, positions, orders, trades  
**Use Case**: Live trading operations, position management, order execution

## Existing Implementation

- **Client**: Located in `src/services/alpaca/client.py`
- **Rate Limiting**: 200 calls/minute
- **Data Types**: Account, positions, orders, trades
- **Integration**: Already integrated with trading system

## Capabilities

### Account Data
- Account balance and equity
- Buying power and cash
- Account status and trading permissions
- Portfolio value and performance

### Position Management
- Current positions with quantities
- Average entry prices
- Unrealized P&L
- Market values

### Order Management
- Order placement (market, limit, stop)
- Order status tracking
- Order history
- Execution monitoring

### Trade Data
- Trade execution details
- Fill prices and quantities
- Commission tracking
- Settlement information

## Integration Details

### Client Implementation

The Alpaca client is located in `src/services/alpaca/client.py` and provides:
- Account information retrieval
- Position management
- Order placement and tracking
- Trade execution monitoring

### SDK: alpaca-py (not alpaca-trade-api)

**As of 2026-07-05, the client uses `alpaca-py`** (`TradingClient`, `StockHistoricalDataClient`),
not the legacy `alpaca-trade-api` package (`REST`). Do not reintroduce `alpaca-trade-api` --
this was a deliberate migration, not an accident.

**Why**: `alpaca-trade-api==3.2.0` (latest, unmaintained) hard-pins `websockets<11`.
`prefect>=3.4.14` requires `websockets>=15.0.1`. There is no `websockets` version that
satisfies both, so any fresh `pip install -r requirements.txt` fails with
`ResolutionImpossible`. `alpaca-py` has no such upper bound, so it coexists with modern
Prefect/Streamlit releases.

**What changed**:
- `requirements.txt`: `alpaca-trade-api>=3.2.0` -> `alpaca-py>=0.43.0`
- `src/services/alpaca/client.py`: `alpaca_trade_api.REST` -> `alpaca.trading.client.TradingClient`
  (+ `alpaca.data.historical.StockHistoricalDataClient` for `get_bars`)
- Method name changes: `list_positions` -> `get_all_positions`, `list_orders` -> `get_orders`
  (now takes a `GetOrdersRequest` filter with `QueryOrderStatus` enum, not a raw string),
  `cancel_order` -> `cancel_order_by_id`, `submit_order` now takes an `order_data=` request
  object (`MarketOrderRequest`/`LimitOrderRequest`/`StopOrderRequest`) instead of kwargs.
- `alpaca.common.exceptions.APIError` replaces `alpaca_trade_api.rest.APIError` (accepts a
  plain string, unlike the old one's dict-based constructor).
- alpaca-py's trading/data methods are typed as returning a model **or** `dict`/`str`
  (the SDK's generic HTTP layer). mypy needs this narrowed with `cast(ModelType, ...)` at
  each call site -- do NOT use `assert isinstance(...)`, since that breaks `Mock()`-based
  unit tests in `tests/unit/test_alpaca_client.py` (a `Mock()` is never an `isinstance` of
  the real model, so the assert raises and gets masked by the generic `except Exception`).
- Several numeric fields on `TradeAccount`/`Position` (e.g. `buying_power`, `qty`) are typed
  `Optional[str]` in alpaca-py's models -- wrap with `float(x or 0)`, not bare `float(x)`.

**Gotcha -- `get_orders(status=...)` only accepts `QueryOrderStatus` values**: unlike the old
`alpaca_trade_api`, which passed `status` through as a free-form string query param,
`alpaca-py`'s `GetOrdersRequest.status` is typed as `QueryOrderStatus` (`open`/`closed`/`all`
only). Passing a specific order status like `"filled"` or `"canceled"` raises
`ValueError: 'filled' is not a valid QueryOrderStatus`. `AlpacaClient.get_orders()` handles
this: if `status` isn't one of the `QueryOrderStatus` values, it queries with
`QueryOrderStatus.ALL` and filters the results client-side by `order.status`. Callers (e.g.
`/trades` in `alpaca_routes.py`, which calls `get_orders(status="filled")`) do not need to
change -- this is handled inside `client.py`.

**If upgrading `alpaca-py` in the future**: re-run `mypy src/services/alpaca/client.py
--ignore-missing-imports` after any alpaca-py version bump; its model/method surface has
changed across versions.

### Prefect Flows

Alpaca data ingestion uses the following Prefect flows:

1. **Account Monitoring Flow**: Monitors account status and positions
2. **Order Monitoring Flow**: Tracks active orders and executions

See [Data Ingestion Overview](data-ingestion-overview.md#prefect-flows) for flow implementation details.

### Data Storage

- **PostgreSQL**: Account data, positions, orders, and trades stored in respective tables
- **Redis**: Real-time account and position data cached
- **Data Source Tag**: All Alpaca data tagged appropriately

## Configuration

### Environment Variables

```bash
ALPACA_API_KEY=your_alpaca_api_key
ALPACA_SECRET_KEY=your_alpaca_secret_key
ALPACA_BASE_URL=https://paper-api.alpaca.markets  # Paper trading
# ALPACA_BASE_URL=https://api.alpaca.markets  # Live trading
ALPACA_UPDATE_INTERVAL=60  # 1 minute (real-time)
```

### Settings

```python
class AlpacaSettings(BaseSettings):
    alpaca_api_key: str = Field(default="", alias="ALPACA_API_KEY")
    alpaca_secret_key: str = Field(default="", alias="ALPACA_SECRET_KEY")
    alpaca_base_url: str = Field(default="https://paper-api.alpaca.markets", alias="ALPACA_BASE_URL")
    alpaca_update_interval: int = Field(default=60, alias="ALPACA_UPDATE_INTERVAL")
```

## Usage Examples

### Account Monitoring

```python
from prefect import flow
from src.services.alpaca.client import AlpacaClient

@flow(name="alpaca_account_monitoring")
async def monitor_account():
    client = AlpacaClient()
    
    # Get account information
    account = await client.get_account()
    
    # Get current positions
    positions = await client.get_positions()
    
    # Update cache
    await update_account_cache(account, positions)
```

### Order Monitoring

```python
@flow(name="alpaca_order_monitoring")
async def monitor_orders():
    client = AlpacaClient()
    
    # Get active orders
    active_orders = await client.get_orders(status="open")
    
    # Get filled orders
    filled_orders = await client.get_orders(status="filled")
    
    # Process order updates
    for order in filled_orders:
        await process_order_execution(order)
```

## Enhancement Plan

### Planned Improvements

- **Standardize Data Models**: Align Alpaca data models with other providers
- **Data Quality Monitoring**: Add data quality checks for Alpaca data
- **Caching Layer**: Implement Redis caching for frequently accessed data
- **Error Recovery**: Add robust error recovery mechanisms
- **WebSocket Support**: Real-time streaming for orders and positions (future)

## Best Practices

1. **Rate Limiting**: Respect 200 calls/minute limit
2. **Error Handling**: Implement retry logic for transient errors
3. **Data Validation**: Validate all data before storage
4. **Real-Time Updates**: Use appropriate update intervals for real-time data
5. **Paper Trading**: Test with paper trading before live trading

## Integration with Trading System

Alpaca integration is used for:
- Real-time account monitoring
- Position tracking and management
- Order execution and monitoring
- Trade reconciliation

The Alpaca client integrates with:
- Execution Service: Order placement and tracking
- Analytics Service: Position and performance tracking
- Risk Management: Position limits and exposure monitoring

## Limitations

- **API Rate Limits**: 200 calls/minute may be limiting for high-frequency operations
- **Paper Trading**: Paper trading environment may have different behavior than live
- **Data Latency**: Network latency affects real-time data freshness

## Future Enhancements

- WebSocket streaming for real-time updates
- Advanced order types (bracket orders, OCO orders)
- Portfolio analytics integration
- Multi-account support

---

**See Also**:
- [Data Ingestion Overview](data-ingestion-overview.md) - Overall architecture and common patterns
- [Polygon.io Integration](data-ingestion-polygon.md) - Historical data integration
- [Yahoo Finance Integration](data-ingestion-yahoo.md) - Fundamental data integration

