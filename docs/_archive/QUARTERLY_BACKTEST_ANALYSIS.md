# 四半期バックテスト結果の分析と対応方針

## 🔍 実験結果の分析

### 実施内容
2024年を4四半期に分割し、各四半期で以下を実施:
1. **Training期間** (最初の2ヶ月): バックテスト実行 → k2/k3最適化
2. **Validation期間** (最後の1ヶ月): 固定閾値 vs 適応型閾値で比較

### 結果サマリー
```
全四半期で PnL改善 = 0.00
→ 閾値変更が取引結果に影響なし
```

| 四半期 | 最適化k2 | 最適化k3 | 固定PnL | 適応PnL | 改善 |
|-------|---------|---------|---------|---------|------|
| 2024 Q1 | 2.5 | 1.7 | 953.03 | 953.03 | 0.00 |
| 2024 Q2 | 2.1 | 1.8 | -89.20 | -89.20 | 0.00 |
| 2024 Q3 | 3.1 | 1.9 | -172.13 | -172.13 | 0.00 |
| 2024 Q4 | 2.3 | 1.8 | -267.26 | -267.26 | 0.00 |

---

## 🧩 原因分析

### classification_k2/k3 の現在の役割

**コード確認結果**:
```python
# src/config.ini
classification_k2 = 2.2  # TREND分類の MFE/ATR 閾値
classification_k3 = 1.6  # FALSE_BREAK分類の MAE/ATR 閾値
```

これらのパラメータは、`tools/reclassify_trades_grid.py`などで**取引完了後の分類（事後分析）にのみ使用**されています。

### 現在の使用箇所
1. **事後分類ツール** (`reclassify_trades_grid.py`)
   - 完了した取引をMFE/MAEに基づき分類
   - TREND / FALSE_BREAK / OTHER の判定
   - 分析・可視化のみ（トレード判断には無関係）

2. **トレード分析** (`tools/dynamic_classification_optimizer.py`)
   - 既存トレードのMFE/MAE分布から推奨k2/k3を算出
   - レポート生成のみ

### なぜ取引結果が変わらないか

**バックテスト実行時のエントリー/EXIT判定は以下のみに依存**:
- Donchian Channel ブレイク
- PVO (出来高オシレータ) 閾値
- PSAR trailing stop
- Keltner Channel (オプション)
- max_hold_bars (時間切れEXIT)

**classification_k2/k3 は判定ロジックに関与していない**

---

## 💡 適応型分類閾値の本来の意図

### 誤解していた用途
「k2/k3を調整することでエントリー精度が向上する」
→ **実際には取引判断に使用されていない**

### 正しい用途
「完了した取引を事後分析し、TREND取引とFALSE_BREAK取引を区別してパフォーマンスを評価する」
→ **分析ツールとしての価値**

---

## 🔄 2つの対応方針

### 方針A: 事後分析ツールとして運用 (推奨)

**位置付け**:
- classification_k2/k3 は**分析専用パラメータ**
- 四半期ごとに再計算し、戦略の健全性を監視
- TRENDキャッチ率、FALSE_BREAK回避率を KPI化

**運用フロー**:
```
1. 四半期終了後
2. dynamic_classification_optimizer.py 実行
3. TREND/FALSE_BREAK比率を確認
4. 戦略パラメータ（PVO閾値、Donchian期間など）を調整判断
```

**メリット**:
- 実装変更不要（既存ツールで実現可能）
- 戦略の健全性を定量評価
- 市場環境変化の早期検出

**デメリット**:
- k2/k3変更が直接トレードに影響しない
- 間接的な戦略改善のみ

---

### 方針B: 取引判断ロジックに統合 (高コスト)

**実装内容**:
k2/k3を使って**リアルタイムでトレード品質を予測**し、低品質取引を回避

**実装例**:
```python
# trading_strategy.py の evaluate_entry() 内

# 現在のATR取得
current_atr = self.price_data_management.get_volatility()

# 期待MFE/MAEを予測（直近N取引の統計から）
expected_mfe_atr_ratio = calculate_expected_mfe(recent_trades)
expected_mae_atr_ratio = calculate_expected_mae(recent_trades)

# 分類予測
k2 = Config.get_classification_k2()
k3 = Config.get_classification_k3()

if expected_mfe_atr_ratio > k2:
    # TREND期待 → エントリー許可
    pass
elif expected_mae_atr_ratio > k3:
    # FALSE_BREAK懸念 → エントリー見送り
    return 'NONE'
```

**課題**:
1. **事前予測の困難性**: MFE/MAEは取引完了後にしか確定しない
2. **過学習リスク**: 過去統計が将来を保証しない
3. **実装コスト**: 予測ロジック、統計計算、バックテスト検証が必要

**メリット**:
- k2/k3が直接トレード判断に影響
- 低品質取引の事前回避

**デメリット**:
- 実装・検証コストが高い
- 効果が不確実（予測精度に依存）

---

## 🎯 推奨アクション

### 即座に実施 (方針A)

1. **四半期レポート運用開始**
   ```bash
   # 四半期終了ごとに実行
   python tools/adaptive_threshold_monitor.py --check --src-root .
   python tools/adaptive_threshold_monitor.py --quarterly-report --src-root .
   ```

2. **KPI監視体制確立**
   - TREND取引比率 (目標: > 40%)
   - FALSE_BREAK取引比率 (目標: < 30%)
   - TREND取引のPnL寄与率 (目標: > 50%)

3. **戦略パラメータ調整判断**
   - TREND比率低下 → PVO閾値引き下げ、Donchian期間見直し
   - FALSE_BREAK増加 → Keltnerフィルタ有効化、ADX連動強化

### 長期検討 (方針B)

**優先度**: 低 (他の施策を先行)

現時点では以下を優先:
- **優先度B**: EXIT戦略拡張 (max_hold_bars最適化、ADX連動EXIT)
- **優先度C**: バックテスト高速化
- **優先度D**: エントリー戦略改善 (PVO軽量版再最適化)

方針Bは上記完了後、余力があれば検討。

---

## 📝 ドキュメント修正

### IMPLEMENTATION_ROADMAP.md の修正内容

**修正前**:
> 適応型分類閾値システムで k2/k3 を四半期ごとに調整し、トレード精度を向上

**修正後**:
> 適応型分類閾値システムで k2/k3 を四半期ごとに再計算し、戦略の健全性を監視。TREND/FALSE_BREAK比率をKPI化し、間接的に戦略パラメータ調整判断に活用。

### 成功指標の見直し

**変更前**:
- [ ] 2025年勝率 > 50%
- [ ] Profit Factor > 1.2

**変更後**:
- [ ] TREND取引比率 > 40% (四半期平均)
- [ ] FALSE_BREAK取引比率 < 30% (四半期平均)
- [ ] TREND取引のPnL寄与率 > 50%
- [ ] 四半期レポート自動生成率 100%

---

## 🔍 追加調査項目

### 1. 取引分類の現状確認
```bash
# 最新のtrend_tradesを分析
python tools/reclassify_trades_grid.py \
  --input report/trend_trades_<latest>.json \
  --k2 2.2 --k3 1.6
```

**確認項目**:
- TREND取引は何%か？
- FALSE_BREAK取引は何%か？
- 各分類のPnL寄与は？

### 2. 分類閾値感度分析
```bash
# k2/k3を変えて分類がどう変わるか
python tools/reclassify_trades_grid.py \
  --input report/trend_trades_<latest>.json \
  --k2-range '1.5,2.0,2.5,3.0' \
  --k3-range '1.2,1.6,2.0'
```

**目的**: 現k2=2.2, k3=1.6 の妥当性検証

---

## 📊 結論

### 四半期バックテスト実験の意義

**❌ 期待していた効果**: k2/k3変更でPnL改善  
**✅ 実際の価値**: 事後分析による戦略健全性監視

### 今後の運用方針

1. **classification_k2/k3 は分析専用パラメータとして運用**
2. **四半期ごとに TREND/FALSE_BREAK 比率を監視**
3. **異常検知時に戦略パラメータ（PVO, Donchian等）を調整**
4. **取引判断ロジックへの統合は長期検討課題**

### 優先度再評価

```
優先度A: 適応型分類閾値 → 85% → 95% (運用方針確定)
  - 事後分析ツールとして完成
  - 四半期レポート運用開始

優先度B: EXIT戦略拡張 → 30% (次の注力領域)
優先度C: バックテスト高速化 → 0%
優先度D: エントリー戦略改善 → 20%
```

---

**記録日時**: 2025-11-21 14:50  
**次のアクション**: 優先度Bのmax_hold_barsグリッド探索へ移行
