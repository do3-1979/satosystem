# Architecture Overview

## Component Responsibilities
| Component | Responsibility | Key Interactions |
|-----------|---------------|------------------|
| Config | Centralized parameter access from config.ini | All modules read cached values |
| BybitExchange | ccxt wrapper for market/balance/order/OHLCV | PriceDataManagement, Bot (orders) |
| PriceDataManagement | Fetches & buffers OHLCV, derives signals (Donchian, PVO) & volatility; backtest time progression | TradingStrategy, RiskManagement |
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
