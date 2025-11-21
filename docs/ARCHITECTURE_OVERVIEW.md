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
| Order | DTO encapsulating order intent (including MFE/MAE metrics) | Bot, Exchange |
| Logger | Structured logging, rotation, compression | Bot, Util, Metrics |
| Util | Log extraction & visualization (Excel, charts) | Logger outputs |
| Metrics | Post-backtest performance metrics (Sharpe, MaxDD, PF, WinRate, Recovery Period) | Bot (backtest summary) |

## Execution Rules

### Bot Execution Standard
**MUST use `bot_run.sh` for all backtest/live executions.**

Rationale:
- Unified API key management (injection/restoration via `replace_api_key.sh`)
- Consistent log cleanup and error handling
- Prevents accidental key leaks in config.ini commits

**Direct `python bot.py` execution is PROHIBITED** except for debugging purposes.

All automated scripts (batch backtests, A/B experiments, etc.) must invoke `bot_run.sh` instead of `bot.py` directly.

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

## Strategy Optimization History

### Keltner Channel Filter (Rejected)
**Decision Date**: 2025-11-21  
**Test Period**: 2025/10/01 - 2025/11/01  
**Result**: Not adopted

Tested 12 parameter combinations (EMA periods: 10/20/30 × ATR multipliers: 1.5/2.0/2.5/3.0):
- All configurations resulted in identical poor performance: PnL -35.21 (vs baseline 9.94)
- Profit Factor: 0.70, Max DD Rate: 58.18%, Win Rate: 46.67%, Trades: 15
- 0/12 configurations beat baseline → conclusively rejected

**Current Status**: `keltner_enabled=False` in config.ini; code remains for future reference

### Pyramiding Optimization (Adopted: entry_times=4)
**Decision Date**: 2025-11-21  
**Test Period**: 2025/10/01 - 2025/11/01  
**Result**: entry_times=4 selected as optimal balance

Tested configurations (entry_times: 2, 3, 4, 5, 10):

| entry_times | PnL | DD Rate | Risk-Adjusted Score | PF | Sharpe | Win Rate |
|-------------|-----|---------|---------------------|-----|--------|----------|
| **4 (Adopted)** | **107.10** | **49.75%** | **215.27** | **1.25** | **0.343** | **93.33%** |
| 2 | 281.68 | 70.07% | 402.02 | 1.20 | 0.287 | 100% |
| 5 | 69.78 | 44.94% | 155.28 | 1.23 | 0.32 | 93.33% |
| 3 | 45.33 | 64.47% | 70.31 | 1.08 | 0.12 | 93.33% |
| 10 (Baseline) | 9.94 | 113.17% | 8.78 | 1.53 | 0.63 | 94.12% |

**Selection Rationale**:
- DD rate under 50% (practical risk threshold for live trading)
- Highest Sharpe ratio (0.343) indicating best risk-adjusted returns
- PnL improvement: +977% vs baseline
- Balanced approach: prioritizes stability over maximum profit
- Suitable for long-term operation

**Current Status**: `entry_times=4` in config.ini

## Planned Improvements (M Roadmap)
- M2: Documentation consolidation (README + this file).
- M3: Refactoring issue template & backlog categorization.
- M4: Metrics pipeline (implemented) & iterative strategy enhancement loop.
- M5: Trade classification optimization (k1,k2,k3,L thresholds for TREND vs FALSE_BREAK)
- M6: Partial exit functionality for multi-position holdings
- M7: EXIT condition refinement (trailing stop, profit target)
- M8: PVO threshold re-optimization on latest data

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

## Priority Action Items (2025 Q1)

### 🔴 CRITICAL: 適応型分類閾値システム導入
**課題**: 現状の固定閾値 (k2=2.2, k3=1.6) が2024年データで最適化されたが、2025年の市場環境変化により勝率が97.80% → 1.92%へ壊滅的に劣化。

**対策**: 
- **月次MFE/MAE分布再計算** (dynamic_classification_optimizer.py実装済)
- **四半期ごとのk2/k3自動調整** (ドリフト検出閾値: 15%乖離で再最適化)
- **市場レジーム分類** (トレンド型 vs レンジ型の自動判定)
- **閾値バウンド制御** (極端値回避: k2 ∈ [1.0, 4.0], k3 ∈ [0.8, 2.5])

**実装優先度**: 🔴 最優先 (システム稼働条件)

### 🟡 エントリー戦略改善
**現状課題**: 
- Keltnerフィルタは効果不明 (押し目買いでもベースライン超え未確認)
- ピラミッディング最適値は entry_times=4 で確定 (2025/11リバランス完了)

**対策**:
- **ボラティリティ適応エントリー**: ATR上昇時はエントリー閾値を動的に引き上げ
- **出来高確認強化**: PVO閾値の市場状況別調整
- **時間帯フィルタ**: 低流動性時間帯のエントリー抑制

**実装優先度**: 🟡 中優先

### 🟡 EXIT戦略拡張
**現状課題**:
- PSAR trailing stopがレンジ相場で機能不全
- 部分利確効果は限定的 (別期間での正確な同一比較が必要)

**対策**:
- **レンジ相場専用EXIT**: Bollinger Band平均回帰ロジック
- **時間ベースEXIT**: 保持期間上限設定 (過度なホールド防止)
- **ADX連動EXIT**: トレンド強度低下時の早期撤退
- **部分利確パラメータ最適化**: profit_rate (0.08-0.12), ratio (0.33-0.67) グリッド探索

**実装優先度**: 🟡 中優先

---
This document complements `Readme.md` and analysis files; update incrementally.
