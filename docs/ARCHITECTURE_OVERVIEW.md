# Architecture Overview

## Component Responsibilities
| Component | Responsibility | Key Interactions |
|-----------|---------------|------------------|
| Config | Centralized parameter access from config.ini | All modules read cached values |
| BybitExchange | ccxt wrapper for market/balance/order/OHLCV | PriceDataManagement, Bot (orders) |
| PriceDataManagement | Fetches & buffers OHLCV, derives signals (Donchian, PVO) & volatility; backtest time progression | TradingStrategy, RiskManagement |
| OHLCVCache | SQLite persistence for multi-timeframe OHLCV (1m / 120m) with upsert & sufficiency check | PriceDataManagement (initial backtest load) |
| TradingStrategy | Decides ENTRY / ADD / EXIT based on signals & portfolio state | Bot (decision consumer), Portfolio |
| RiskManagement | Position sizing, STOP trailing (PSAR, surge), ADX state | Bot, Portfolio, PriceDataManagement |
| Portfolio | Tracks positions, average price, cumulative PnL & drawdown | Bot, RiskManagement |
| Order | DTO encapsulating order intent | Bot, Exchange |
| Logger | Structured logging, rotation, compression | Bot, Util, Metrics |
| Util | Log extraction & visualization (Excel, charts) | Logger outputs |
| Metrics | Post-backtest performance metrics (Sharpe, MaxDD, PF, WinRate) | Bot (backtest summary) |

## Data Flow (Backtest & Live)
```
          +-------------+
          |   Config    |
          +------+------+         +------------------+
                 |                |  BybitExchange    |
                 | OHLCV/ticker   +---------+---------+
          +------+------++-------------------+
          | PriceData   | signals/volatility |
          | Management  |<-------------------+
          +------+------+                    |
                 |                           |
          +------+------+
          |  Strategy   | ENTRY/ADD/EXIT
          +------+------+
                 | decision
          +------+------+
          |    Bot      | loop orchestration
          +--+-------+--+
             |       |
     sizing/STOP   order DTO
             |       v
          +--v--+  +--v-------------+
          |Risk |  |    Order       |
          |Mgmt |  +-------+--------+
          +--+--+          |
             |             |
             |   exec      v
          +--v-------------+--+
          |    Exchange       |
          +--+----------------+
             |
             | fills/update
          +--v--+
          |Portfolio (PnL history) |
          +--+--+
             |
             v
          +--+--+
          |Logger|--> JSON log files --> Util / Metrics
          +--+--+
             |
             v (backtest end)
          +--+--+
          |Metrics| summary JSON
          +------+ 

## Timeframe & Cache Architecture (C6)
The system consumes two granularities:
- 2h timeframe (120m) for strategy & risk decisions.
- 1m timeframe for fine-grained progression and latest ticker/volume.

Both are stored in a single SQLite table `candles` keyed by `(symbol, timeframe, close_time)`:
```
CREATE TABLE candles (
   symbol TEXT,
   timeframe INTEGER,      -- minutes (1, 15, 120 ...)
   close_time INTEGER,     -- epoch seconds (end of candle)
   open_price REAL,
   high_price REAL,
   low_price REAL,
   close_price REAL,
   volume REAL,
   PRIMARY KEY(symbol, timeframe, close_time)
)
```

### Initial Backtest Loading
`PriceDataManagement.initialise_back_test_ohlcv_data()` sequence:
1. Compute extended start (start - initial_term * timeframe).
2. For each timeframe (1, 15?, 120) attempt legacy JSON load (current + old path) -> upsert into DB.
3. Call `has_sufficient_cache(symbol, timeframe, start, end)`; if False, fetch full range from API and upsert.
4. Pull unified range via `get_range(...)` into memory arrays.
5. Emit compatibility JSON for tools that still expect file-based OHLCV.

### Re-Fetch Suppression
`has_sufficient_cache` compares actual row count with expected (allowing a tolerance of 2 candles). If sufficient, no API call. This preserves rate limits by avoiding repeat downloads of identical historical windows.

### Current Limitations
- Sufficiency is count-based; internal gaps (missing contiguous candles) are not detected.
- 2h candles are fetched directly rather than rolled up from 1m data (opportunity to remove duplication).
- Full-range fetch on insufficiency (could be narrowed to only missing segments).

### Future Enhancements
- Gap detection: identify discontinuities (`delta(close_time) > timeframe*60`) and fetch only missing spans.
- Roll-up engine: derive higher timeframes from 1m base series for consistency & less external dependency.
- Integrity audit: periodic report (boundary coverage, gap count, latest update timestamp).
- Adaptive tolerance: dynamic permissible missing count based on timeframe length & strategy warm-up needs.

### VCS & Reproducibility
Cache DB (`src/ohlcv_data/ohlcv_cache.db` + WAL/SHM) is ignored—backtests regenerate needed ranges. Legacy JSON files remain for compatibility and may be pruned once all consumers migrate to DB queries.

```

## Backtest Progression
- `PriceDataManagement.update_price_data_backtest()` advances a virtual clock minute by minute.
- Signals recalculated only on frame completion (e.g. 2h / 15m).
- Bot collects `total_profit_and_loss` into `pnl_history` each iteration.
- End condition triggers metrics summary JSON.

## Extensibility Points
| Point | Strategy | Alternative | Notes |
|-------|----------|-------------|-------|
| Indicator Calc | In Price/Risk | Dedicated IndicatorService | Reduces class bloat |
| Data Source | Single class | Interface (Live vs Backtest) | Improves testability |
| STOP Logic | Mixed (PSAR + surge) | Policy objects | Composable trailing algorithms |
| Logging Schema | Implicit dict | Versioned schema file | Safe evolution of fields |

## Planned Improvements (M Roadmap)
- M2: Documentation consolidation (README + this file).
- M3: Refactoring issue template & backlog categorization.
- M4: Metrics pipeline (implemented) & iterative strategy enhancement loop.

## Metrics Calculated
| Metric | Source | Formula (Simplified) |
|--------|--------|----------------------|
| total_pnl | cumulative PnL | last(pnl_history) |
| profit_factor | incremental returns | sum(pos)/abs(sum(neg)) |
| max_drawdown | pnl_history | max(peak - trough) |
| max_drawdown_rate | pnl_history | max_drawdown / peak * 100 |
| sharpe | incremental returns | mean(ret)/std(ret)*sqrt(n) |
| win_rate | trade_results | wins / trades * 100 |

## Testing Considerations
- Unit test metric functions with synthetic pnl paths (monotonic, volatile, flat).
- Edge cases: empty history, all losses, single sample.

## Enum Standardization (Planned C2)
Adopt internal `Side` enum (BUY, SELL, NONE) for all decision & portfolio interactions; convert only at exchange boundary.

## Security / Failure Handling
- Network/API retry: basic loop with sleep; needs max-attempt & exponential backoff.
- API keys sourced from config; avoid logging secrets.

## Future Separation
1. `IndicatorService` for PSAR, ADX, Donchian, PVO
2. `DataSource` abstraction (LiveDataSource / BacktestDataSource)
3. `RiskEngine` separate from sizing heuristics

---
This document complements `Readme.md` and analysis files; update incrementally.
