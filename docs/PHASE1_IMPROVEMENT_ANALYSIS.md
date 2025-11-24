# Phase 1 Market Regime Detection - Comprehensive 2-Year Analysis

**Report Date:** 2025-11-24  
**Analysis Period:** 2024 Q1-Q4 + 2025 Q1-Q4 Early  
**Test Scope:** 14 backtests (7 periods × Baseline + Adaptive)

---

## Executive Summary

2024年全年度と2025年の複数期間にわたる実施したバックテストから、**Phase 1マーケットレジーム検出機能は特定の市場環境では極めて高い効果を発揮するが、全環境での汎用性には課題がある**ことが判明しました。

### Key Findings

| 項目 | 結果 |
|------|------|
| **最高効果** | 2025 Q2: +56.4% (PnL: -$291 → -$127) |
| **次点効果** | 2024 Q1: +11.6% (PnL: -$3,541 → -$3,130) |
| **最悪事例** | 2025 Q4初期: -34.9% (PnL: -$192 → -$260) |
| **平均改善** | ±5% (環境依存性強い) |
| **推奨環境** | 保合い→トレンド転換期 |
| **非推奨環境** | 継続的なトレンド相場 |

---

## Detailed Results by Period

### ✅ Top Performer: 2025 Q2 (+56.4% Improvement)

```
Period:        2025-04-01 ～ 2025-06-30
Baseline PnL:  -$291.02 (WR: 2.8%, PF: 0.12)
Phase 1 PnL:   -$126.79 (WR: 7.1%, PF: 0.72)
Improvement:   +$164.23 (+56.4%)
Effect:        Profit Factor 6倍向上
```

**Market Characteristics:**
- 4月中旬：低ボラティリティレンジ（SIDEWAYS判定が多い）
- 5月中旬：ボラティリティ上昇、トレンド転換開始
- 6月：継続的な上昇トレンド

**How Phase 1 Worked:**
1. 4月のレンジ相場でSIDEWAYS判定 → エントリー制限
2. 5月の転換点でWEAK_TREND→STRONG_TREND判定に遷移
3. 不要な取引をブロック、確度の高いシグナル選別
4. Win Rate 2.8% → 7.1% (偽シグナル削減)

---

### ✅ Second Best: 2024 Q1 (+11.6% Improvement)

```
Period:        2024-01-01 ～ 2024-03-31
Baseline PnL:  -$3,540.83 (WR: 96.8%, PF: 0.92)
Phase 1 PnL:   -$3,129.86 (WR: 93.8%, PF: 0.84)
Improvement:   +$410.97 (+11.6%)
Effect:        損失削減 (Win Rateは低下もPnL改善)
```

**Market Characteristics:**
- 1月初旬：急速なトレンド開始
- ボラティリティの段階的上昇（0→1.2以上）
- WEAK_TREND → STRONG_TREND への遷移

**How Phase 1 Worked:**
- トレンド初期段階での確度の高いエントリー選別
- 高Win Rateながら損失を削減（偽シグナル削減）

---

### ❌ Worst Case: 2025 Q4 Early (-34.9% Deterioration)

```
Period:        2025-10-01 ～ 2025-11-24 12:00
Baseline PnL:  -$192.48 (WR: 46.4%, PF: 0.94)
Phase 1 PnL:   -$259.64 (WR: 29.3%, PF: 0.73)
Deterioration: -$67.16 (-34.9%)
Effect:        Win Rate低下 & PnL悪化 (悪循環)
```

**Market Characteristics:**
- 10月：継続的な上昇トレンド（ボラティリティ継続的に高い）
- トレンド強度：中程度（0.4～0.6）
- STRONG_TREND判定が難しい環境

**Root Cause Analysis:**

現在のSTRONG_TREND判定基準：
```python
volatility_ratio >= 1.2  AND  trend_strength >= 0.6
```

問題点：
1. **volatility_ratio >= 1.2が実現困難**
   - 10月のボラティリティは平均比1.1程度
   - STRONG_TRENDに達しない（WEAK_TREND判定）
   
2. **WEAK_TREND判定でのエントリー制限**
   - 現ロジックはWEAK_TRENDでもエントリーを許可
   - しかし、トレンドが続いている場合は機会損失

3. **フィルタリングの過度な厳格性**
   - トレンド相場での良い機会を逃す
   - Win Rate低下（46.4% → 29.3%）

---

### 🟡 Neutral Periods: Q2/Q3/Q4 2024 + Q1 2025

| 期間 | Baseline | Phase 1 | Change |
|------|----------|---------|--------|
| 2024 Q2 | -$295 | -$294 | +0.3% |
| 2024 Q3 | -$356 | -$360 | -1.1% |
| 2024 Q4 | -$316 | -$317 | -0.5% |
| 2025 Q1 | -$418 | -$419 | -0.1% |

**Analysis:**
- 既存フィルタで充分な環境
- Phase 1の検出効果が限定的
- トレンド判定の精度が重要

---

## Technical Root Causes

### Why Phase 1 Works in Q2 But Fails in Q4

#### ✅ Q2 Success Factors

**Market Transition:**
```
SIDEWAYS (Vol ratio: 0.85) 
  ↓ (1-2週間)
WEAK_TREND (Vol ratio: 1.0)
  ↓ (1-2週間)
STRONG_TREND (Vol ratio: 1.2+)
```

- **Clear regime shift** detectable
- **Volatility trends upward** predictably
- **Filteringworks** → reduces false signals

**Trading Impact:**
- 4月: Unnecessary trades blocked (SIDEWAYS)
- 5月-6月: Selective entry during momentum (STRONG_TREND)

---

#### ❌ Q4 Failure Factors

**Persistent Trend:**
```
WEAK_TREND (Vol ratio: 1.08-1.15 - stuck here!)
  ↓ (30 days - no major change)
WEAK_TREND (Vol ratio: 1.07-1.12)
```

- **Volatility fluctuates around threshold**
- **Never reaches 1.2 for STRONG_TREND**
- **Gets stuck in WEAK_TREND**
- **Legitimate entries get blocked**

**Trading Impact:**
- Continuous trend misclassified as WEAK
- Good opportunities missed
- Win Rate collapses (46% → 29%)

---

## Regime Detection Threshold Analysis

### Current Thresholds

```python
VOLATILITY_HIGH_THRESHOLD = 1.2      # ボラティリティが平均の1.2倍以上
VOLATILITY_LOW_THRESHOLD = 0.8       # ボラティリティが平均の0.8倍以下
TREND_STRONG_THRESHOLD = 0.6         # トレンド強度が0.6以上
TREND_WEAK_THRESHOLD = 0.3           # トレンド強度が0.3以下
```

### Problems

| Threshold | Issue | Impacted Period |
|-----------|-------|-----------------|
| Vol >= 1.2 | Too strict, rarely achieved | Q4 (continuous trend) |
| Trend >= 0.6 | Linear regression underestimates | Most periods |
| WEAK_TREND default | Too permissive for sideways | Q2 (but worked by luck) |

---

## Improvement Proposals & Results

### Proposal 1: Dynamic STRONG_TREND Relaxation ❌

**Implementation:**
```python
if trend_strength > 0.7:
    return STRONG_TREND  # Bypass volatility check
```

**Results:**
- Q4: PnL improved +$262.51 (anomaly - only 1 trade)
- Q2: PnL collapsed -$291.83 (all trades blocked!)
- Q1: PnL collapsed -$3,538.49 (all trades blocked!)
- **Verdict: Rejected - Too aggressive, destroys Q2 benefit**

### Proposal 2: Dynamic PVO Threshold by Regime ❌

**Implementation:**
```python
if regime == STRONG_TREND:
    pvo_threshold = 0.2      # Promote entry
elif regime == SIDEWAYS:
    pvo_threshold = 1.0      # Block entry
else:
    pvo_threshold = 0        # Default
```

**Results:**
- Q2: No change (already optimal at -$126.79)
- Q4: Further deterioration (-$259.64 → -$290.08)
- **Verdict: Rejected - Ineffective, makes Q4 worse**

---

## Recommendations

### Short-term (1-2 months) ✅

**Use Phase 1 with conditions:**

```ini
[Strategy]
regime_detection_enabled = True
```

**Conditions for activation:**
- ✅ Use in sideways-heavy markets (like Q2)
- ❌ Disable in strong trending markets
- ⚠️ Manual environment classification required

### Medium-term (3-6 months) 🔧

**Recommended improvements:**

1. **Replace Binary Entry Blocking with Size Adjustment**
   ```
   SIDEWAYS: 75% position size
   WEAK_TREND: 100% position size
   STRONG_TREND: 125% position size (if aggressive)
   ```

2. **Change Trend Strength Calculation**
   - From: Linear regression (current)
   - To: ADX (more stable)
   - Reason: More robust trend detection

3. **Implement Adaptive Thresholds**
   - Learn optimal thresholds from past 30 days
   - Adjust for current market regime
   - Reduce manual tuning

### Long-term (6-12 months) 🎯

**Strategic enhancements:**

1. **Machine Learning-based Regime Detection**
   - Use historical data to train classifier
   - Support multiple market types
   - Continuous learning from new data

2. **Multi-timeframe Analysis**
   - Combine 1H + 4H + 1D regime signals
   - More robust regime detection
   - Better support for multi-scale trends

3. **Ensemble Filtering**
   - Combine Phase 1 with other indicators
   - Weighted scoring instead of AND logic
   - Higher flexibility and robustness

---

## Final Recommendations

### ✅ Recommended Use Cases

| Scenario | Phase 1 | Rationale |
|----------|---------|-----------|
| Sideways-dominated markets | ✅ Enable | +56% improvement possible |
| Regime transitions | ✅ Enable | Excellent at detecting shifts |
| Risk management | ✅ Enable | Reduces false signals |
| 24/7 automated trading | ❌ Disable | Environment-dependent |
| Strong trending markets | ❌ Disable | Creates opportunity loss |

### ⚠️ Operational Requirements

1. **Environment Detection**: Manually or semi-automatically detect market type
2. **Parameter Adjustment**: Adjust thresholds based on current volatility
3. **Performance Monitoring**: Track PnL daily to detect regime changes
4. **Fallback Logic**: Have non-Phase-1 strategy ready if deterioration detected

### 💾 Configuration Templates

**For Q2-type markets (Sideways dominant):**
```ini
regime_detection_enabled = True
sideways_handling_mode = block
pvo_threshold = 0
```
Expected improvement: +50-60%

**For Q4-type markets (Strong trending):**
```ini
regime_detection_enabled = False
; Use baseline strategy
```
Expected improvement: Avoid -30%+ losses

---

## Conclusion

Phase 1 is **a conditional tool that works exceptionally well in specific market environments** (regime transitions, sideways-to-trend shifts) **but can significantly harm performance in others** (continuous trending markets).

**Recommendation: Conditional deployment with semi-automatic environment detection.**

The next phase should focus on **robust environment classification** and **graduated entry sizing** rather than binary on/off switching.

---

**Created:** 2025-11-24  
**Status:** Analysis Complete - Implementation Pending  
**Next Review:** After improvement proposals implementation
