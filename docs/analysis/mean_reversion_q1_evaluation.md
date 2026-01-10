# Mean Reversion Strategy - Phase 1 Evaluation Report

**評価期間**: 2025 Q1 (2025-01-01 ~ 2025-03-31)  
**評価日**: 2026-01-07  
**判定**: ❌ **NO-GO（不採用）**

---

## Executive Summary

Mean Reversion（平均回帰）戦略のPhase 1評価を完了しました。BB（Bollinger Bands）2σ逸脱 + RSI<30の条件でレンジ相場の反転を狙う逆張り戦略として実装・テストした結果、**採用基準を大幅に下回るパフォーマンス**を記録したため、不採用と判定しました。

---

## 1. Strategy Overview

### 戦略コンセプト
- **目的**: 2025年のレンジ相場環境に対応するため、売られすぎ局面での反転を狙う
- **シグナル条件**:
  - 価格 < BB下限（20期間、2.0σ）
  - RSI < 30（14期間）
- **エントリー**: LONG（買い）のみ
- **想定市場**: ADX < 25のレンジ相場

### 実装詳細
- **ファイル**: [src/mean_reversion_strategy.py](../../src/mean_reversion_strategy.py) (250行)
- **統合**: [src/trading_strategy.py](../../src/trading_strategy.py) (Lines 175-218)
- **設定**: [src/config.ini](../../src/config.ini) `[MeanReversionStrategy]`
- **フィルター**: PVOフィルターのみ適用（ADXフィルター無効化）

---

## 2. Performance Results

### Q1 2025 Backtest Results

| 指標 | 実績値 | 目標値 | 判定 |
|------|--------|--------|------|
| **Profit Factor** | **0.07** | >0.8 | ❌ **91.3% 未達** |
| **Win Rate** | **7.14%** | >40% | ❌ **82.2% 未達** |
| **Total Trades** | **14** | >10 | ✅ **PASS** |
| **Net Profit** | **-198 USD** | >0 | ❌ **FAIL** |
| **Max Drawdown** | 213.69 USD | - | - |
| **Sharpe Ratio** | -2.367 | - | 負の値（高リスク） |

### 勝敗内訳
- 総トレード: 14件
- 勝ちトレード: 1件（7.14%）
- 負けトレード: 13件（92.86%）
- 平均損失/トレード: -14.14 USD

---

## 3. Root Cause Analysis

### 主要な問題点

#### 3.1 ADXフィルター無効化の影響
- **問題**: レンジ相場向け戦略のため、ADXフィルター（≥31）を無効化
- **結果**: トレンド相場でも逆張りエントリーし、順張りトレンドに逆らって損失
- **証拠**: 2025年1月はトレンド相場が多く、BB下限タッチ後も下落継続

#### 3.2 RSI<30条件の不十分性
- **問題**: RSI<30だけでは「売られすぎ」を十分に判定できない
- **観測**: RSI<30でも下落トレンドが継続するケースが多数
- **理由**: 240分足では、4時間の間に市場センチメントが大きく変化

#### 3.3 BB下限タッチの反転シグナルとしての弱さ
- **問題**: BB下限到達 ≠ 反転確定
- **観測**: BB下限タッチ後、さらに2-5%下落するケースが多数
- **改善案**: BB逸脱率（-0.10 ~ -0.21）をより厳格化する必要あり

---

## 4. Implementation Progress

### 完了した実装 (Phase 1)

✅ **Core Logic** (mean_reversion_strategy.py):
- Bollinger Bands計算（20期間、2.0σ）
- RSI計算（14期間）
- エントリーシグナル判定ロジック

✅ **Configuration** (config.ini):
- `[MeanReversionStrategy]` セクション追加
- 5パラメータ設定（enable, bb_period, bb_std_dev, rsi_period, rsi_oversold_threshold）

✅ **Integration** (trading_strategy.py):
- Mean Reversionシグナル生成（Lines 175-218）
- フィルター統合（PVOフィルターのみ）
- Donchian戦略との排他制御

✅ **Logging** (bot.py, trade_logger.py):
- mean_reversion_signal, bb_position, rsi_value フィールド追加

✅ **Debugging**:
- Config parsing (inline comment issue)
- OHLCV data access (dict vs array)
- Logger method signature
- Side normalization (LONG → BUY)
- Filter integration architecture

---

## 5. Alternative Approaches (Not Pursued)

以下の改善案は、Phase 1評価でNO-GO判定のため実施しませんでした:

### Option B: パラメータ調整
- RSI閾値を20-25に引き下げ（より厳格な売られすぎ条件）
- BB逸脱率を1.5%以上に設定（より明確な逸脱）
- ADXフィルターを再有効化（ADX<25でのみエントリー）

**不採用理由**: 根本的なロジックの問題（逆張りのタイミング判定）が解決されない

### Option C: エグジット戦略改善
- BB中心線到達で決済（利益確定）
- ATR倍率ベースのストップロス（ボラティリティ適応）
- RSI>50で決済（買われすぎへの転換）

**不採用理由**: エントリー精度が低いため、エグジット改善では対応不可

---

## 6. Lessons Learned

### 実装・デバッグでの知見

1. **Config.iniのインライン・コメント**: `int()`パース失敗を引き起こす（別行に分離必須）
2. **OHLCV Data Format**: `candle[4]` → `candle['close_price']`（dict形式）
3. **Side Normalization**: `"LONG"` → `normalize_side()` → `"NONE"` になる（`"BUY"`を使用）
4. **Filter Architecture**: `if not enable_mr and allow_entry:` の条件で、Mean Reversionが全フィルターをスキップ

### 戦略設計での知見

1. **逆張り戦略の難しさ**: トレンド判定（ADX）なしでの逆張りは極めて危険
2. **タイムフレームの重要性**: 240分足では反転シグナルの精度が低い（60分足の方が適切か）
3. **複合指標の必要性**: BB + RSI だけでは不十分、出来高・ADX・マルチタイムフレーム確認が必須

---

## 7. Decision & Next Steps

### Final Decision

**❌ NO-GO（不採用）**: Mean Reversion戦略はPhase 1で終了

**理由**:
- Profit Factor 0.07 << 0.8（目標の8.75%）
- Win Rate 7.14% << 40%（目標の17.9%）
- 2025 Q1で -198 USD の損失（ベースライン: -48.17 USD）

### Configuration Changes

```ini
[MeanReversionStrategy]
enable_mean_reversion_strategy = 0  # 無効化

[EntryFilters]
enable_adx_filter = 1  # 再有効化（ベースライン復元）
adx_filter_threshold = 31
```

### Next Task (ACTION_LIST.md)

**Task 38c: Range Breakout Enhanced 実装**
- 真のブレイク判定 + 出来高確認
- 既存Donchian強化版（偽ブレイク回避）
- 優先度: ★★★★☆

---

## 8. Appendix

### Test Execution Details

**Command**:
```bash
python3 src/bot.py test 2025-01-01 2025-03-31
```

**Output Log**: [logs/trade_log_20260107004156.json](../../logs/trade_log_20260107004156.json)

**Sample Signals** (2025-01-01 ~ 2025-01-10):
```
Mean Reversion シグナル: Price=118962.90 < BB_Lower=119333.90 (逸脱=0.31%), RSI=20.5 < 30.0
Mean Reversion シグナル: Price=116606.50 < BB_Lower=117351.09 (逸脱=0.63%), RSI=18.3 < 30.0
Mean Reversion シグナル: Price=112732.50 < BB_Lower=113964.93 (逸脱=1.08%), RSI=12.0 < 30.0
```

**Trade Example** (2025-10-10 21:00):
```
エントリー: BUY @ 118963, Quantity=0.0252
決済: (損失) -6.75 USD
```

### Code Preservation

Mean Reversion戦略の実装コードは保持します（将来の参考資料として）:
- [src/mean_reversion_strategy.py](../../src/mean_reversion_strategy.py)
- 無効化状態で残存（`enable_mean_reversion_strategy=0`）

---

## Conclusion

Mean Reversion戦略は、実装・統合・デバッグが完了し、正常に動作することを確認しましたが、**2025 Q1のパフォーマンスが採用基準を大幅に下回ったため不採用**と判定しました。レンジ相場向け戦略としてのコンセプトは有効ですが、シグナル精度の低さ（特にトレンド判定不足）が致命的でした。

次のタスク（Task 38c: Range Breakout Enhanced）では、Donchian既存戦略を強化し、偽ブレイク回避と出来高確認を追加することで、2025年の成績改善を目指します。
