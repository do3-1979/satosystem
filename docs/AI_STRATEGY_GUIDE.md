# satosystem gen2 — AI Reference Guide

**Purpose**: This document is written for AI assistants (e.g., Claude, GPT-4, Gemini) to analyze the project and propose next trading strategies. It contains structured, machine-readable context about the system design, current performance, and open improvement hypotheses.

**Last Updated**: 2026-04-04  
**Branch**: gen2  
**Language**: Python 3  
**Target Exchange**: Bybit (data) + Bitget (execution); migration to OKX/Gate.io in progress

---

## 1. PROJECT IDENTITY

```
Project    : satosystem gen2
Goal       : Automated BTC/USDT perpetual futures trading
Target ROI : ≥ 50% annual return
Capital    : 100–300 USD initial (leverage 10×)
Timeframe  : 4H (240 min) candles
Exchange   : Bybit OHLCV data → Bitget order execution
Hardware   : Raspberry Pi (24/7, uptime 100+ days)
```

---

## 2. CORE STRATEGY (Current Production)

### 2.1 Entry Conditions (ALL must be true)

| # | Condition | Parameter | Value |
|---|-----------|-----------|-------|
| 1 | PVO > threshold | pvo_threshold | 10 |
| 2 | Close > Donchian High (LONG) or Close < Donchian Low (SHORT) | donchian_buy_term / donchian_sell_term | 30 |
| 3 | ADX > adx_bull_threshold | adx_bull_threshold | 24 |
| 4 | TSMOM filter direction match | tsmom_filter_lookback | 150 |

Optional additional filters (disabled by default):
- Weekend filter: skip entries on Saturday/Sunday UTC
- Strategy B (BB+RSI+SMA): disabled
- Strategy C (MACD composite): disabled
- Mean Reversion: disabled

### 2.2 Exit Conditions (Priority order)

1. **PSAR Trailing Stop** [PRIMARY]: Parabolic SAR with lookback=300, AF=0.02→0.20
2. **Surge exit**: Price moves violently against position → immediate exit  
3. Stage 1–4 composite (implemented, partially active):
   - Stage 1: ADX > 50 (strong trend) → hold
   - Stage 2: 30 < ADX < 50 (weakening) → partial exit 50%
   - Stage 3: Time-based (max 72h, disabled)
   - Stage 4: General fallback
4. Additional exits (all **disabled** in production):
   - Chandelier Exit (ATR-based trailing, period=22, mult=3.0)
   - Profit Step Lock: floor at MFE 2/4/8% tiers
   - Volume Climax: exit when volume spikes 3× with >0.5% profit
   - Composite Score: ADX drop + PVO drop + volume drop

### 2.3 Position Sizing

```
position_size = (account_balance × risk_percentage) / (ATR × stop_range × leverage)
risk_percentage = 0.30  (0.3% of account per trade)
leverage        = 10
stop_range      = 1.0   (ATR multiplier for stop distance)
entry_times     = 2     (pyramiding: up to 2 entries)
entry_range     = 4     (ATR multiplier for 2nd entry trigger)
```

---

## 3. CURRENT PERFORMANCE BASELINE

**Baseline version**: ParamSweep_TSMOM150_PSAR300 (v2026.03.04-stable-v5)

### 3.1 Quarterly Results (100 USD initial capital, 10× leverage)

| Quarter | PnL (USD) | Win Rate | Profit Factor | Max DD (USD) | DD% | Sharpe | Trades |
|---------|-----------|----------|---------------|--------------|-----|--------|--------|
| Q1 2024 | +603.93   | 75%      | 6.01          | 116.03       | 24.2% | 1.04  | 4      |
| Q2 2024 | −103.85   | 25%      | 0.01          | 104.46       | 34.8% | −1.68 | 4      |
| Q3 2024 | −49.91    | 75%      | 0.65          | 142.09       | 36.2% | −0.36 | 4      |
| Q4 2024 | +1,477.40 | 100%     | 15.78         | 74.77        | 9.3%  | 1.63  | 7      |
| Q1 2025 | −59.77    | 50%      | 0.00          | 59.77        | 19.9% | −1.39 | 2      |
| Q2 2025 | +210.36   | 100%     | 1.84          | 206.09       | 28.8% | 0.58  | 6      |
| Q3 2025 | +185.23   | 100%     | —             | 0.00         | 0.0%  | 1.04  | 2      |
| Q4 2025 | +160.80   | 100%     | —             | —            | 0.0%  | 1.40   | —      |
| Q1 2026 | −29.72    | 75%      | 0.65          | —            | 23.8% | −0.38 | —      |
| **TOTAL (9Q)** | **+2,394.47** | — | — | — | — | — | — |

### 3.2 Key Observations

- **Q4 2024 is the dominant quarter** (+$1,477 = 61% of total). This corresponds to BTC's major bull run.
- Strategy is **momentum/trend-following**: performs well in strong trends, poorly in choppy/range-bound markets.
- **Low trade frequency**: ~4–7 trades per quarter. Each trade has high impact.
- **Win rate is binary**: either very high (100%) or very low (25%). Strategy has high payoff ratio but inconsistent hit rate.
- **Max Drawdown** can reach ~36% in flat quarters (Q2–Q3 2024).
- Trade count is very low which makes statistical significance questionable.

---

## 4. SYSTEM ARCHITECTURE

### 4.1 Component Map

```
config.ini
    └── Config (singleton)
            ├── Bot (main loop, 60s cycle)
            │     ├── PriceDataManagement  ← BybitExchange (OHLCV)
            │     │     └── signals: Donchian, PVO, ADX, TSMOM, BB, RSI, SMA, MACD
            │     ├── TradingStrategy
            │     │     ├── evaluate_entry()  → ENTRY/ADD
            │     │     ├── evaluate_exit()   → EXIT
            │     │     ├── ExitStrategyV2 (multi-stage)
            │     │     ├── MarketRegimeDetector (TREND/RANGE/TRANSITION)
            │     │     ├── VCPStrategy (volume contraction pattern)
            │     │     └── MeanReversionStrategy (counter-trend)
            │     ├── RiskManagement
            │     │     ├── position_size calculation
            │     │     ├── PSAR trailing stop
            │     │     └── NewIndicators (BB, RSI, SMA, MACD)
            │     ├── Portfolio (PnL, drawdown tracking)
            │     ├── RiskOverlay (DD killswitch, disabled)
            │     ├── CostModel (fee/slippage, disabled)
            │     └── BitgetExchange (order execution)
            └── Logger → Metrics → Visualizer
```

### 4.2 Data Flow

```
Bybit API ──(OHLCV 4H)──► OHLCVCache (SQLite)
                               │
                               ▼
                     PriceDataManagement
                     ├── Donchian Channel
                     ├── PVO (vol oscillator)
                     ├── ADX / DI+/-
                     ├── TSMOM (150-bar momentum)
                     ├── ATR (volatility)
                     └── signals dict
                               │
                               ▼
                     TradingStrategy.evaluate_entry()
                     ├── Check PVO > 10
                     ├── Check Donchian breakout
                     ├── Check ADX > 24
                     ├── Check TSMOM direction
                     └── decision: ENTRY / ADD / EXIT / NONE
                               │
                               ▼
                     RiskManagement.calculate_position_size()
                               │
                               ▼
                     BitgetExchange.execute_order()
                               │
                               ▼
                     Portfolio.add_position() / close_position()
```

### 4.3 Backtest vs Live

| Setting | Backtest | Paper Trade | Live |
|---------|----------|-------------|------|
| back_test | 1 | 0 | 0 |
| hot_test_dummy_mode | 1 | 1 | 0 |
| data source | SQLite cache | Bybit live | Bybit live |
| order execution | none (simulated) | none (simulated) | Bitget real |

---

## 5. IMPLEMENTED BUT INACTIVE FEATURES

These are ready to activate in `config.ini`. Enabling them changes backtest results.

### 5.1 RiskOverlay (DDキルスイッチ)
- `enabled = 0` → set to `1` to activate
- 3 stop modes: `DD_STOP` (portfolio drawdown%), `DAILY_STOP` (daily loss%), `CONSEC_STOP` (consecutive losses)
- Use case: protect capital during extended drawdown periods

### 5.2 CostModel
- `enabled = 0` → set to `1` to use realistic backtest
- Models: taker fee (0.06%), slippage estimate, execution delay
- Critical for realistic P&L estimation

### 5.3 Dynamic Position Sizing
- `enable_dynamic_position_sizing = 0`
- Scales risk% down when portfolio is in drawdown state:
  - 90%+ of initial: risk=0.30
  - 70–90%: risk=0.20
  - 50–70%: risk=0.15
  - <50%: risk=0.10

### 5.4 Chandelier Exit
- `chandelier_exit_enabled = False`
- Period=22, ATR multiplier=3.0
- Higher volatility adaptability than PSAR

### 5.5 Profit Step Lock (PSL)
- `profit_step_lock_enabled = False`
- Tier 1: MFE ≥ 2% → floor at 1%
- Tier 2: MFE ≥ 4% → floor at 2.5%
- Tier 3: MFE ≥ 8% → floor at 6%

### 5.6 Volume Climax Exit
- `volume_climax_exit_enabled = False`
- threshold=3.0× average volume, min_profit=0.5%

### 5.7 Composite Score Exit
- `composite_score_exit_enabled = False`
- Detects trend exhaustion via multi-indicator deterioration

### 5.8 Market Regime Detector
- `MarketRegimeDetector` exists in `src/market_regime_detector.py`
- Detects: TREND / RANGE / TRANSITION
- NOT yet integrated into entry/exit decisions
- Proposed use: skip entries during RANGE regime → reduce loss trades

---

## 6. STRATEGY WEAKNESSES & KNOWN ISSUES

### 6.1 High Concentration Risk
- Q4 2024 alone = 61% of total P&L. Strategy is sensitive to "once-in-a-year" bull moves.
- Risk: in a year without a major BTC uptrend (e.g., 2022 bear market), cumulative P&L would be deeply negative.

### 6.2 Low Trade Frequency
- Average ~3–5 trades per quarter. Small sample size creates high variance.
- Statistical significance of backtest results is uncertain.

### 6.3 No Range-Market Adaptation
- All filters (Donchian, ADX, TSMOM) are trend-following. During sideways markets, system generates small losses.
- MarketRegimeDetector is implemented but not used to skip range-market entries.

### 6.4 PSAR Dependency
- The primary exit is PSAR, which has a fixed lookback (300). In low-volatility periods, PSAR may exit too early; in high-volatility, too late.
- Alternative exits (Chandelier, PSL) are implemented but not validated.

### 6.5 Exchange Migration (Active Issue)
- Bybit Japan Close-Only as of 2026-03-23. Bitget has 240-day OHLCV limit (insufficient for backtesting).
- Migration to OKX or Gate.io required.

### 6.6 No Real Cost Model in Backtest
- CostModel is implemented but disabled. Current baseline ignores fees and slippage.
- Realistic backtests may show lower P&L.

---

## 7. REJECTED STRATEGIES (Do Not Re-Implement Without New Evidence)

| Strategy | Task | Result | Reason for Rejection |
|----------|------|--------|----------------------|
| Trailing Profit Target | 39a | −$1,077 vs baseline | Exits too early, misses large trends |
| Multi-Timeframe Integration | 39c | 0 trades | Filters too strict, no entries |
| ETH/USDT diversification | 40i-eth | BTC −$1,982 gap | PVO filter ineffective on ETH; too few trades |

---

## 8. OPEN STRATEGY HYPOTHESES (Prioritized)

These hypotheses have NOT been validated. An AI can propose concrete implementations.

### P1 (Priority ★★★★★): Exchange Migration
- **Task 44**: Migrate OHLCV data source from Bybit to OKX or Gate.io
- Gate.io: 4H historical data 2+ years available, Japanese access confirmed
- OKX: 4H historical data available, Japan access needs verification
- Implementation: new `OKXExchange` / `GateIOExchange` class in `src/`

### P2 (★★★★): Market Regime Filtering
- **Task 40h**: Use `MarketRegimeDetector` to skip entries during RANGE regime
- Hypothesis: Avoiding range-market entries will reduce losing trades in Q2 2024, Q3 2024, Q1 2025
- Risk: May over-filter and reduce total trade count below statistical threshold
- Implementation: `if self.current_market_regime == 'RANGE': return` in `evaluate_entry()`

### P3 (★★★★): Realistic Cost Model
- **Task 40b**: Enable CostModel in backtest to accurately measure true performance
- Bitget taker fee: ~0.06%. On small capital with leverage, this becomes significant
- Implementation: `CostModel.calculate_entry_cost()` / `calculate_exit_cost()` already exist

### P4 (★★★): Chandelier Exit vs PSAR Comparison
- Replace or supplement PSAR with Chandelier Exit (ATR × 3.0)
- Chandelier adapts better to volatility changes
- Validation: run backtest with `chandelier_exit_enabled=True`, `chandelier_replaces_psar=True`
- Target: maintain Q4 2024 gains while reducing Q2/Q3 2024 losses

### P5 (★★★): Profit Step Lock Validation
- Enable PSL (Tier1/2/3: MFE 2/4/8%) to protect accumulated gains
- Risk: conflicts with trend-following (exits early in large moves like Q4 2024)
- Recommendation: test with Q4 2024 data separately before enabling globally

### P6 (★★★): Fear & Greed Index Filter
- **Task 23a**: Skip LONG entries when Fear & Greed Index > 80 (extreme greed)
- Alternative fear/greed proxy: use funding rate from Bybit/Bitget as sentiment indicator
- Data source: `https://api.alternative.me/fng/?limit=1` (free, no auth required)

### P7 (★★★): Dynamic Position Sizing Validation
- Enable `enable_dynamic_position_sizing=1`
- Reduce position sizes during drawdown periods
- Risk: reduces profits in recovery phase; need to balance

### P8 (★★): Volume Profile Analysis
- **Task 38d**: Detect high-volume price levels as support/resistance
- Use volume-by-price histogram to identify entry levels with high probability of continuation
- Implementation: analyze cumulative volume at each price level in recent N candles

### P9 (★★): Multi-Asset Correlation Management
- **Task 40i**: Monitor BTC-ETH correlation; when correlation drops (<0.7), consider ETH entry
- Prerequisite: fix PVO issue on ETH (ETH volume always exceeds threshold)
- Alternative: use different filters for ETH (e.g., replace PVO with different volume metric)

### P10 (★★): RSI Entry Guard
- **Task 23b**: Block LONG entries when RSI > 70 (overbought)
- Expected improvement: +2–3% performance
- Integration point: `evaluate_entry()` in `trading_strategy.py`

---

## 9. PARAMETER SPACE FOR OPTIMIZATION

Key parameters with their current values and tested ranges:

| Parameter | Current | Tested Range | Note |
|-----------|---------|--------------|------|
| donchian_buy_term | 30 | 15–50 | Sweep confirmed 30 is optimal |
| psar_lookback_term | 300 | 100–500 | Sweep confirmed 300 |
| tsmom_filter_lookback | 150 | 50–300 | Sweep confirmed 150 |
| pvo_threshold | 10 | 5–20 | Lower = more trades; tested for ETH |
| adx_bull_threshold | 24 | 18–35 | |
| risk_percentage | 0.30 | 0.10–0.50 | Higher = more volatility |
| leverage | 10 | 5–20 | Fixed by exchange limits |
| chandelier_mult | 3.0 | 2.0–4.0 | Not yet validated |
| chandelier_period | 22 | 14–50 | Not yet validated |

**Overfitting warning**: Backtest spans only 8 quarters (2 years). High optimization risk with too many parameters. Any new parameter should be validated on out-of-sample (OOS) quarters before adoption.

---

## 10. CODE STRUCTURE REFERENCE

```
src/
├── bot.py                    # Main loop, orchestration
├── trading_strategy.py       # Entry/exit signal logic
├── risk_management.py        # Position sizing, PSAR, ADX
├── price_data_management.py  # OHLCV fetch, indicator computation, backtest progression
├── exit_strategy_v2.py       # Multi-stage exit (Stage1-4 + Chandelier + PSL + VC + CS)
├── portfolio.py              # Position tracking, PnL, drawdown
├── config.py                 # Config singleton (reads config.ini)
├── config.ini                # All parameters
├── bybit_exchange.py         # OHLCV/ticker data (ccxt.bybit)
├── bitget_exchange.py        # Order execution (ccxt.bitget)
├── ohlcv_cache.py            # SQLite cache for backtesting
├── new_indicators.py         # BB, RSI, SMA, MACD calculations
├── market_regime_detector.py # TREND/RANGE/TRANSITION classifier
├── vcp_strategy.py           # Volume Contraction Pattern (experimental)
├── mean_reversion_strategy.py # Counter-trend strategy (experimental)
├── risk_overlay.py           # DD killswitch (enabled=0)
├── cost_model.py             # Fee/slippage model (enabled=0)
├── logger.py                 # Structured logging
├── metrics.py                # Backtest metrics (Sharpe, MaxDD, PF, WinRate)
└── visualizer.py             # HTML chart generation
```

### Key Method Signatures

```python
# TradingStrategy
strategy.evaluate_entry()   # → sets self.trade_decision
strategy.evaluate_exit()    # → sets self.trade_decision
strategy.make_trade_decision()

# RiskManagement
risk.calculate_position_size(entry_price, stop_price, account_balance)
risk.get_psar()             # → float: current PSAR stop price
risk.get_adx()              # → float: ADX value
risk.get_donchian_high()    # → float
risk.get_donchian_low()     # → float

# ExitStrategyV2
exit_v2.evaluate_exit_condition(current_ohlcv, position_info, entry_info)
# → {"should_exit": bool, "close_ratio": float, "reason": str}

# MarketRegimeDetector
regime_detector.detect(ohlcv_data)
# → {"regime": "TREND"|"RANGE"|"TRANSITION", "confidence": float, "reason": str}

# OHLCVCache
cache.get_ohlcv_data(symbol, timeframe, since, until)
# → list[list]: [[timestamp, open, high, low, close, volume], ...]
```

---

## 11. TESTING FRAMEWORK

```
test/
├── regression_test_suite.py    # Master suite (all tests)
├── test_*_regression.py        # Per-module tests
```

- Current status: **164 tests / 164 PASS (100%)**
- Baseline cumulative PnL: **+2,394.47 USD** (9 quarters, 2024Q1–2026Q1, regression guard)
- Run: `./commands/prj-run-regression`
- Any code change that breaks baseline PnL by >5% is considered a regression

---

## 12. STRATEGIC RECOMMENDATIONS FOR AI ANALYSIS

When proposing a new strategy modification, follow this checklist:

1. **Identify which weakness** (#6) it addresses
2. **Map to existing code**: which file/method to modify
3. **Risk of regression**: does it risk reducing Q4 2024 gains?
4. **Parameter count**: minimize new parameters (overfitting risk)
5. **Validation plan**: which quarters to test first (OOS quarters: Q2 2024, Q3 2024)
6. **Expected impact**: rough estimate in USD based on similar past changes

### High-Value, Low-Risk Suggestions
- Enable CostModel for realistic backtesting (no strategy change, just accuracy)
- Enable MarketRegimeDetector integration to skip RANGE entries
- Test Chandelier Exit on historical data before enabling

### High-Risk Suggestions (Careful Validation Required)
- Changing Donchian period (currently at optimal 30)
- Changing PSAR lookback (currently at optimal 300)
- Adding many filter conditions simultaneously (overfitting)
- Any change that significantly reduces Q4 2024 trade count

---

## 13. GLOSSARY

| Term | Definition |
|------|-----------|
| Donchian Channel | N-period highest high / lowest low |
| PVO | Percentage Volume Oscillator: (fast_vol − slow_vol) / slow_vol × 100 |
| ADX | Average Directional Index: trend strength (0–100) |
| PSAR | Parabolic Stop-and-Reverse: trailing stop indicator |
| TSMOM | Time-Series Momentum: return over lookback period |
| ATR | Average True Range: volatility measure |
| MFE | Maximum Favorable Excursion: best unrealized P&L during trade |
| DD | Drawdown: peak-to-trough decline |
| PF | Profit Factor: total gross profit / total gross loss |
| Sharpe | Sharpe Ratio: return / standard deviation of returns |
| PSL | Profit Step Lock: ratchet-style profit floor |
| VCP | Volume Contraction Pattern: pre-breakout setup |

---

*This document was auto-generated from the satosystem gen2 codebase on 2026-04-04.*
*Reference files: PROGRESS.json, ACTION_LIST.json, docs/ARCHITECTURE_OVERVIEW.md, src/config.ini, baseline_backup/BASELINE_2402.94USD_ParamSweep_20260304.json*
