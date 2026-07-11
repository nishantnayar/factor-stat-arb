# Strategy Engine API — Pairs Trading

> **Status**: ✅ Implemented in v1.1.0
> **Base URL**: `http://localhost:8001/api/strategies/pairs`

The Strategy Engine implements a statistical arbitrage (pairs trading) strategy. It discovers cointegrated stock pairs, computes hourly z-scores on the price spread, generates entry/exit signals, and executes two-legged paper trades via Alpaca.

---

## Architecture

```
pair_registry (DB)
      │
      ▼
SpreadCalculator ──→ pair_spread (DB)
      │
      ▼
SignalGenerator ──→ pair_signal (DB)
      │
      ▼
KellySizer
      │
      ▼
PairExecutor ──→ Alpaca paper-api ──→ pair_trade (DB)
      │
      ▼
PairPerformance (DB)
```

**Price source**: Alpaca `get_bars()` (live intraday hourly bars) — not the end-of-day `market_data` table.

---

## Endpoints

### GET /status

Returns strategy-level summary: active pair count, total P&L, last update time.

**Response:**
```json
{
  "is_active": true,
  "total_pairs": 3,
  "active_pairs": 1,
  "total_pnl": 142.50,
  "last_update": "2026-03-28T14:00:00+00:00"
}
```

---

### GET /active

Returns all active pairs with their current z-score and open trade state.

**Response:**
```json
{
  "pairs": [
    {
      "id": 1,
      "name": "QRVO/SWKS",
      "status": "OPEN",
      "z_score": -1.842,
      "pnl": 87.30,
      "correlation": 0.8697,
      "days_held": 1
    }
  ]
}
```

---

### GET /performance

Aggregated performance metrics across all closed trades.

**Response:**
```json
{
  "total_pnl": 142.50,
  "sharpe_ratio": 0.516,
  "max_drawdown": 8.2,
  "win_rate": 0.615,
  "avg_hold_time": 11.4
}
```

---

### GET /{pair_id}/history

Z-score time series for a pair. Used to render the z-score chart in the UI.

**Query Parameters:**
- `days` (int, default 30): How many days of history to return

**Response:**
```json
{
  "history": [
    {
      "timestamp": 1743000000000,
      "z_score": -1.842,
      "spread": 0.0312
    }
  ],
  "entry_threshold": 2.0,
  "exit_threshold": 0.5
}
```

---

### GET /{pair_id}/details

Full pair details: registry stats, open trade, and last signal.

**Response:**
```json
{
  "hedge_ratio": 0.9231,
  "half_life": 18.4,
  "cointegration_pvalue": 0.0024,
  "correlation": 0.8697,
  "open_trade": {
    "id": 12,
    "side": "LONG_SPREAD",
    "entry_time": "2026-03-28T14:00:00+00:00",
    "entry_z_score": -2.14,
    "qty1": 15,
    "qty2": 14,
    "entry_price1": 68.42,
    "entry_price2": 74.11
  },
  "last_signal": {
    "type": "LONG_SPREAD",
    "z_score": -2.14,
    "timestamp": "2026-03-28T14:00:00+00:00"
  }
}
```

---

### GET /config

Returns the current strategy thresholds from `config/pairs.yaml`.

**Response:**
```json
{
  "entry_threshold": 2.0,
  "exit_threshold": 0.5,
  "stop_loss_threshold": 3.0,
  "max_hold_hours": 72.0,
  "position_pct": 0.02
}
```

---

### POST /config

Update strategy thresholds. Changes are persisted to `config/pairs.yaml`.

**Request Body:**
```json
{
  "entry_threshold": 2.0,
  "exit_threshold": 0.5,
  "stop_loss_threshold": 3.0,
  "max_hold_hours": 72.0,
  "position_pct": 0.02
}
```

---

### POST /start

Marks the strategy as running (informational — actual execution is triggered by the Prefect scheduled flow).

**Response:** `{ "message": "Strategy started" }`

---

### POST /stop

Marks the strategy as stopped.

**Response:** `{ "message": "Strategy stopped" }`

---

### POST /emergency-stop

Immediately closes all open pair trades via Alpaca market orders.

**Response:** `{ "message": "Emergency stop executed for N pairs" }`

---

### POST /{pair_id}/close

Manually close an open trade for a specific pair.

**Response:** `{ "message": "Pair QRVO/SWKS closed successfully" }`

---

### POST /backtest

Run a backtest for a pair using historical DB data. Results are saved to `backtest_run` table.

**Request Body:**
```json
{
  "pair_id": 1,
  "start_date": "2025-09-01",
  "end_date": "2026-03-01",
  "entry_threshold": 2.0,
  "exit_threshold": 0.5,
  "stop_loss_threshold": 3.0,
  "initial_capital": 100000
}
```

**Response:**
```json
{
  "run_id": 5,
  "pair_id": 1,
  "total_return": 0.042,
  "annualized_return": 0.091,
  "sharpe_ratio": 0.516,
  "max_drawdown": 0.082,
  "win_rate": 0.615,
  "profit_factor": 1.31,
  "total_trades": 26,
  "avg_hold_time_hours": 11.4,
  "kelly_fraction": 0.18,
  "passed_gate": true,
  "equity_curve": [...],
  "trade_log": [...]
}
```

**Gate thresholds** (applied automatically):
- Sharpe ratio > 0.5
- Win rate > 45%
- Max drawdown < 15%

---

### GET /backtest/history

List all past backtest runs, optionally filtered by pair.

**Query Parameters:**
- `pair_id` (int, optional): Filter to a specific pair

**Response:**
```json
[
  {
    "id": 5,
    "pair_id": 1,
    "run_date": "2026-03-27",
    "start_date": "2025-09-01",
    "end_date": "2026-03-01",
    "sharpe_ratio": 0.516,
    "max_drawdown": 0.082,
    "win_rate": 0.615,
    "total_trades": 26,
    "passed_gate": true
  }
]
```

---

## Signal Types

| Signal | Condition | Action |
|---|---|---|
| `LONG_SPREAD` | z-score < −entry_threshold | Long symbol1, short symbol2 |
| `SHORT_SPREAD` | z-score > +entry_threshold | Short symbol1, long symbol2 |
| `EXIT` | abs(z-score) < exit_threshold | Close both legs |
| `STOP_LOSS` | abs(z-score) > stop_loss_threshold | Close both legs |
| `EXPIRE` | hold time > 3× half-life hours | Close both legs |

---

## Position Sizing (Kelly Criterion)

**Bootstrap phase** (< 20 closed trades): Fixed 2% of portfolio equity per leg.

**Full phase** (≥ 20 closed trades):
```
kelly_f = win_rate - (1 - win_rate) / avg_win_ratio
half_kelly = kelly_f / 2
per_leg_capital = half_kelly × equity / 2
shares = floor(per_leg_capital / current_price)
```

Hard cap: 12% of portfolio per leg.

---

## Spread Formula

```
spread = log(price1) - hedge_ratio × log(price2)
z_score = (spread − rolling_mean(window)) / rolling_std(window)
```

`window = z_score_window` (default 40 bars = 2× half-life for QRVO/SWKS)

---

## Database Tables

| Table | Purpose |
|---|---|
| `strategy_engine.pair_registry` | Validated pair definitions, thresholds, rank score |
| `strategy_engine.pair_spread` | Hourly spread + z-score time series |
| `strategy_engine.pair_signal` | Generated signals with reason |
| `strategy_engine.pair_trade` | Open and closed two-legged trades |
| `strategy_engine.pair_performance` | Daily cumulative performance per pair |
| `strategy_engine.backtest_run` | Historical backtest results + equity curve (JSONB) |

---

## Prefect Flow

**File**: `src/shared/prefect/flows/strategy_engine/pairs_flow.py`
**Schedule**: `0 14-21 * * 1-5` UTC (9 AM–5 PM ET, Mon–Fri, hourly)

```bash
# Dry-run (one cycle, market check skipped):
python src/shared/prefect/flows/strategy_engine/pairs_flow.py

# Register as scheduled deployment in Prefect UI:
python src/shared/prefect/flows/strategy_engine/pairs_flow.py --deploy
```

---

## Related

- [Backtest Review UI](../user-guide/strategies.md)
- [Pairs Trading Monitoring Page](../user-guide/strategies.md#live-monitoring)
- SQL migrations: `scripts/21_create_strategy_engine_tables.sql`, `scripts/22_strategy_engine_schema_fixes.sql`

---

**Last Updated**: 4/3/2026
**Status**: ✅ Live (paper trading) — QRVO/SWKS active pair
