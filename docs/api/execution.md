# Execution Engine API

> **📋 Implementation Status**: ✅ Core Features Implemented (v1.0.0)  
> **Current Status**: Account management, position tracking, order viewing/cancellation, market clock available

This guide covers the execution engine API endpoints for order management, trade execution, and position tracking through the Alpaca trading API.

## Overview

The execution engine provides REST API endpoints for:
- ✅ Account management and monitoring
- ✅ Position tracking and management
- ✅ Order viewing and cancellation
- ✅ Market status and clock information
- 🚧 Order placement (planned for v1.1.0)
- 🚧 Advanced order types (planned for v1.1.0)

## Base URL

```
http://localhost:8001/api/alpaca
```

## Authentication

All endpoints require Alpaca API credentials configured in your environment:

```bash
ALPACA_API_KEY=your_api_key_here
ALPACA_SECRET_KEY=your_secret_key_here
ALPACA_BASE_URL=https://paper-api.alpaca.markets
```

## Endpoints

### Account Management

#### Get Account Information
```http
GET /api/alpaca/account
```

**Response:**
```json
{
  "account_id": "string",
  "status": "ACTIVE|ONBOARDING|ACCOUNT_CLOSED",
  "currency": "USD",
  "buying_power": "100000.00",
  "regt_buying_power": "50000.00",
  "daytrading_buying_power": "100000.00",
  "cash": "100000.00",
  "portfolio_value": "100000.00",
  "pattern_day_trader": false,
  "trading_blocked": false,
  "transfers_blocked": false,
  "account_blocked": false,
  "created_at": "2023-01-01T00:00:00Z",
  "trade_suspended_by_user": false,
  "multiplier": "4",
  "shorting_enabled": true,
  "equity": "100000.00",
  "last_equity": "100000.00",
  "long_market_value": "0.00",
  "short_market_value": "0.00",
  "initial_margin": "0.00",
  "maintenance_margin": "0.00",
  "last_maintenance_margin": "0.00",
  "sma": "100000.00",
  "daytrade_count": 0
}
```

### Position Management

#### Get All Positions
```http
GET /api/alpaca/positions
```

**Response:**
```json
[
  {
    "asset_id": "string",
    "symbol": "AAPL",
    "exchange": "NASDAQ",
    "asset_class": "us_equity",
    "qty": "100",
    "side": "long",
    "market_value": "15000.00",
    "cost_basis": "14000.00",
    "unrealized_pl": "1000.00",
    "unrealized_plpc": "0.0714",
    "unrealized_intraday_pl": "100.00",
    "unrealized_intraday_plpc": "0.0067",
    "current_price": "150.00",
    "lastday_price": "149.00",
    "change_today": "0.67"
  }
]
```

#### Close Position
```http
POST /api/alpaca/positions/{symbol}/close
```

**Parameters:**
- `symbol` (path): The symbol of the position to close

**Response:**
```json
{
  "order_id": "string",
  "symbol": "AAPL",
  "side": "sell",
  "quantity": "100",
  "order_type": "market",
  "status": "accepted",
  "created_at": "2023-01-01T00:00:00Z"
}
```

### Order Management

#### Get Orders
```http
GET /api/alpaca/orders
```

**Query Parameters:**
- `status` (optional): Filter by order status (`open`, `closed`, `all`)

**Response:**
```json
[
  {
    "id": "string",
    "client_order_id": "string",
    "created_at": "2023-01-01T00:00:00Z",
    "updated_at": "2023-01-01T00:00:00Z",
    "submitted_at": "2023-01-01T00:00:00Z",
    "filled_at": null,
    "expired_at": null,
    "canceled_at": null,
    "failed_at": null,
    "replaced_at": null,
    "replaced_by": null,
    "replaces": null,
    "asset_id": "string",
    "symbol": "AAPL",
    "asset_class": "us_equity",
    "notional": null,
    "qty": "100",
    "filled_qty": "0",
    "filled_avg_price": null,
    "order_class": "simple",
    "order_type": "market",
    "type": "market",
    "side": "buy",
    "time_in_force": "day",
    "limit_price": null,
    "stop_price": null,
    "status": "new",
    "extended_hours": false,
    "legs": null,
    "trail_percent": null,
    "trail_price": null,
    "hwm": null
  }
]
```

#### Place Order
```http
POST /api/alpaca/orders
```

**Request Body:**
```json
{
  "symbol": "AAPL",
  "qty": "100",
  "side": "buy",
  "type": "market",
  "time_in_force": "day"
}
```

**Response:**
```json
{
  "id": "string",
  "client_order_id": "string",
  "created_at": "2023-01-01T00:00:00Z",
  "updated_at": "2023-01-01T00:00:00Z",
  "submitted_at": "2023-01-01T00:00:00Z",
  "asset_id": "string",
  "symbol": "AAPL",
  "asset_class": "us_equity",
  "notional": null,
  "qty": "100",
  "filled_qty": "0",
  "filled_avg_price": null,
  "order_class": "simple",
  "order_type": "market",
  "type": "market",
  "side": "buy",
  "time_in_force": "day",
  "limit_price": null,
  "stop_price": null,
  "status": "new",
  "extended_hours": false
}
```

#### Cancel Order
```http
DELETE /api/alpaca/orders/{order_id}
```

**Parameters:**
- `order_id` (path): The ID of the order to cancel

**Response:**
```json
{
  "id": "string",
  "status": "canceled",
  "canceled_at": "2023-01-01T00:00:00Z"
}
```

### Trade History

#### Get Recent Trades
```http
GET /api/alpaca/trades
```

**Query Parameters:**
- `limit` (optional): Number of trades to return (default: 20)

**Response:**
```json
[
  {
    "id": "string",
    "order_id": "string",
    "symbol": "AAPL",
    "asset_class": "us_equity",
    "notional": "15000.00",
    "qty": "100",
    "filled_qty": "100",
    "filled_avg_price": "150.00",
    "order_class": "simple",
    "order_type": "market",
    "type": "market",
    "side": "buy",
    "time_in_force": "day",
    "status": "filled",
    "created_at": "2023-01-01T00:00:00Z",
    "filled_at": "2023-01-01T00:00:01Z"
  }
]
```

### Market Information

#### Get Market Clock
```http
GET /api/alpaca/clock
```

**Response:**
```json
{
  "timestamp": "2023-01-01T15:30:00Z",
  "is_open": true,
  "next_open": "2023-01-02T09:30:00Z",
  "next_close": "2023-01-01T16:00:00Z"
}
```

#### Get Alpaca Configuration
```http
GET /api/alpaca/config
```

**Response:**
```json
{
  "base_url": "https://paper-api.alpaca.markets",
  "data_url": "https://data.alpaca.markets",
  "api_key_configured": true,
  "secret_key_configured": true,
  "trading_mode": "paper"
}
```

## Error Handling

All endpoints return appropriate HTTP status codes and error messages:

### Error Response Format
```json
{
  "error": "string",
  "message": "string",
  "code": "integer"
}
```

### Common Error Codes
- `400` - Bad Request (invalid parameters)
- `401` - Unauthorized (invalid API credentials)
- `403` - Forbidden (insufficient permissions)
- `404` - Not Found (resource doesn't exist)
- `429` - Too Many Requests (rate limit exceeded)
- `500` - Internal Server Error (server-side error)

## Rate Limiting

The API respects Alpaca's rate limits:
- **Paper Trading**: 200 requests per minute
- **Live Trading**: 200 requests per minute

The system implements automatic rate limiting and retry logic.

## Examples

### Complete Trading Workflow

1. **Check Market Status**
```bash
curl http://localhost:8001/api/alpaca/clock
```

2. **Get Account Information**
```bash
curl http://localhost:8001/api/alpaca/account
```

3. **Place a Market Order**
```bash
curl -X POST http://localhost:8001/api/alpaca/orders \
  -H "Content-Type: application/json" \
  -d '{
    "symbol": "AAPL",
    "qty": "10",
    "side": "buy",
    "type": "market",
    "time_in_force": "day"
  }'
```

4. **Check Order Status**
```bash
curl http://localhost:8001/api/alpaca/orders
```

5. **Monitor Positions**
```bash
curl http://localhost:8001/api/alpaca/positions
```

6. **Close Position**
```bash
curl -X POST http://localhost:8001/api/alpaca/positions/AAPL/close
```

## Integration with Trading System

The execution engine integrates with other system components:

- **Strategy Engine**: Receives trading signals and executes orders
- **Risk Management**: Validates orders against risk limits
- **Analytics**: Tracks execution performance and slippage
- **Notification**: Sends alerts on order fills and errors

## Security Considerations

- API credentials are stored securely in environment variables
- All communication uses HTTPS
- Rate limiting prevents API abuse
- Order validation prevents unauthorized trades
- Audit logging tracks all trading activities