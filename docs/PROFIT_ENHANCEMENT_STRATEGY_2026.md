# 利益拡大戦略 2026 - 包括的提案

**作成日**: 2026-01-11  
**最終更新**: 2026-03-07 (実装状況反映)  
**現状**: 累積損益 +2,402.94 USD（8四半期バックテスト、ParamSweep PSAR/TSMOM最適化後）  
**目的**: 損失削減と利益拡大による事業資金確保

---

## 🎯 エグゼクティブサマリー

### 現状分析の重要な発見

1. **2024年が異常に良好** (+1,658 USD) → **2025年で大幅悪化** (-288 USD改善前)
2. **Q4 2024が突出** (+1,540 USD) → 全体の80%を占める
3. **トレード数が非常に少ない** → 年間22-26件（月2-3件）
4. **勝率よりもPFが重要** → 勝率75%でも損失の四半期あり

### 戦略の方向性

#### ❌ これまでの失敗パターン
- **複雑化の罠**: VCP, Mean Reversion, Candlestick → 全て不採用
- **フィルター追加**: 季節性、マーケットレジーム → 効果なし
- **パラメータ最適化**: 過学習のリスク

#### ✅ 新しいアプローチ
1. **トレード機会の増加** - 現在の機会損失を削減
2. **時間軸の最適化** - 240分足の限界を突破
3. **EXIT戦略の革新** - 利益の取りこぼし防止
4. **リスク管理の高度化** - ドローダウン制御
5. **市場環境の精密判定** - マルチタイムフレーム統合

---

## 📊 カテゴリー別戦略（優先度順）

### **Priority 1: EXIT戦略の革命的改善** ⭐⭐⭐⭐⭐

#### 現状の問題
- Q4 2024: +1,540 USD (87.5%勝率) → **異常値**
- Q1 2025: -143 USD (20%勝率) → **STOP_LOSSによる強制退場**
- 平均保有時間が不明だが、早期Exit/遅延Exitの可能性

#### 提案A1: **Trailing Profit Target（トレーリング利確）** — ✖ **不採用（Task 39a, 2026-01-11）**

> **失敗結果**: バックテストでベースライン比 -1,077 USD悪化。不採用とし、ExitStrategyV2内で `trailing_profit_enabled = False` に固定。

**コンセプト**: 利益が一定額に達したら、逆方向の押し・戻りでStopを段階的に上げる

```python
# 実装イメージ
if unrealized_pnl > entry_price * 0.02:  # 2%利益
    # Trailing Stopを発動
    trailing_stop = max(current_price - volatility * 1.5, trailing_stop)
    
if unrealized_pnl > entry_price * 0.05:  # 5%利益
    # さらに厳格化
    trailing_stop = max(current_price - volatility * 1.0, trailing_stop)
```

**期待効果**:
- Q4 2024のような大勝ちトレードの利益を守る
- 平均勝ち額を +30-50% 向上（推定 +$200-400 / 年）

**実装難易度**: ★★☆☆☆（2-3時間）

---

#### 提案A2: **Time-Based Exit（時間ベース強制決済）** — ✅ **実装済み（Task 39d, 2026-02-08）**

> **実装**: ExitStrategyV2._check_time_based_exit() で実装。config.ini `enable_time_based_exit=1`, `max_holding_hours=72`。

**コンセプト**: 長期ポジション（48-72時間以上）は強制決済

**根拠**:
- Donchian Breakoutは短中期トレンド向け
- 240分足で12-18本（48-72時間）以上持つと、トレンドが反転している可能性
- 「塩漬け防止」

```python
# 実装イメージ
holding_duration_hours = (current_time - entry_time) / 3600

if holding_duration_hours > 72:  # 3日間
    if unrealized_pnl > 0:
        # 利益確定
        exit_trade(reason="TIME_LIMIT_PROFIT")
    else:
        # 損切り（既存Stop Lossより優先）
        exit_trade(reason="TIME_LIMIT_LOSS")
```

**期待効果**:
- Q1 2025の大損失トレード（-143 USD）を防ぐ
- 平均保有時間の最適化
- 年間 +$100-200 の損失削減

**実装難易度**: ★☆☆☆☆（1-2時間）

---

#### 提案A3: **Dynamic Stop Loss Width（動的ストップ幅）** — ✅ **実装済み（Task 39e）**

> **実装**: RiskManagement.get_dynamic_stop_range() でADXに応じた動的ストップ幅を実装。

**現状**: `stop_range = 2` で固定 → ボラティリティ変化に非対応

**提案**: ATR（Average True Range）に基づく動的調整

```python
# 低ボラ環境（ADX < 25）
stop_width = volatility * 1.5  # 狭いストップ

# 中ボラ環境（ADX 25-40）
stop_width = volatility * 2.0  # 現在と同じ

# 高ボラ環境（ADX > 40）
stop_width = volatility * 2.5  # 広いストップ（ノイズ回避）
```

**期待効果**:
- Q3 2024 (-23 USD) のような「勝率は高いが負け」を削減
- 年間 +$100-150 の改善

**実装難易度**: ★★☆☆☆（2-3時間）

---

### **Priority 2: トレード機会の増加** ⭐⭐⭐⭐☆

#### 現状の問題
- **年間22-26トレードは少なすぎる**（月2-3件）
- ADX=31フィルターが厳しすぎる可能性
- PVO=10も保守的

#### 提案B1: **Two-Tier Entry System（二段階エントリー）** — ✅ **実装済み (+378 USD, Task 39b, 2026-02-01)**

> **実装結果**: +904.35 USD → +1,282.62 USD (+378.27 USD, +41.8%).
> TradingStrategy.evaluate_entry() 内でTier1/Tier2分岐とポジションサイズ比調整を実装。

**コンセプト**: 高確度（現行）と中確度（新規）の2種類のエントリー

```python
# Tier 1: 高確度エントリー（現行維持）
if adx >= 31 and pvo >= 10:
    entry_size = 1.0  # フルポジション
    
# Tier 2: 中確度エントリー（新規追加）
elif adx >= 25 and pvo >= 5:
    entry_size = 0.5  # ハーフポジション
    max_tier2_concurrent = 1  # 同時1件まで
```

**期待効果**:
- トレード機会 +50-100%（年間33-52件）
- Tier 2の勝率が45-55%でもPF > 1.5なら十分
- 年間 +$300-600 の増加

**実装難易度**: ★★★☆☆（3-4時間）

---

#### 提案B2: **Mean Reversion Hybrid（平均回帰ハイブリッド）** — ✖ **不採用（Phase 1評価完了, 2026-01-07）**

> **実装結果**: バックテストPF=0.07, 勝率=7.14%。不採用基準未達。config.ini `enable_mean_reversion_strategy=0`。

**これまでの失敗を踏まえた改良版**:

現在のMean Reversion戦略が失敗した理由:
1. Donchianと**逆方向**にエントリー → トレンドに逆らう
2. RSI < 30 だけでは不十分 → さらに売られ続ける
3. ADXフィルター無効化 → トレンド相場で大損失

**改良案**: 
- Mean Reversionは**Donchianと同方向のみ**
- 「押し目買い」「戻り売り」として使用
- ADXフィルター必須

```python
# 例: ロングの押し目買い
if donchian_signal == "BUY" and adx >= 31:
    # 通常のエントリー条件
    if price > donchian_high:
        entry_primary()
    
    # 押し目買い条件（Mean Reversion的）
    elif price < bb_middle and rsi < 40:
        # トレンド方向への押し目
        entry_pullback()
```

**期待効果**:
- トレード機会 +30-50%
- トレンド方向の押し目で有利な価格取得
- 年間 +$200-400

**実装難易度**: ★★★☆☆（4-5時間）

---

### **Priority 3: マルチタイムフレーム統合** ⭐⭐⭐⭐☆

#### 現状の問題
- 240分足（4時間足）のみ → 中期トレンドの見落とし
- 短期ノイズに振り回される可能性

#### 提案C1: **1時間 + 4時間 + 日足の三重確認** — ✖ **不採用（Task 39c, 2026-02-01）**

> **実装結果**: フィルターが厳しすぎてトレード数=0になったため破棄。MTFは現在不採用。

```python
# 1h足: エントリータイミング（細かい押し目/戻り）
# 4h足: メインシグナル（現行）
# 1d足: 大局トレンド確認

def multi_timeframe_check():
    # 日足チェック
    daily_trend = get_trend_direction(timeframe='1d')
    
    # 4時間足チェック（現行）
    h4_signal = check_donchian_breakout(timeframe='4h')
    
    # 1時間足チェック（タイミング）
    h1_pullback = check_pullback_entry(timeframe='1h')
    
    # 統合判定
    if daily_trend == h4_signal == h1_pullback:
        return "STRONG_ENTRY"  # フルポジション
    elif daily_trend == h4_signal:
        return "MEDIUM_ENTRY"  # ハーフポジション
    else:
        return "NO_ENTRY"
```

**期待効果**:
- フェイク・ブレイクを50-70%削減
- 大局トレンドに逆らわない
- 年間 +$400-700

**実装難易度**: ★★★★☆（6-8時間）

---

### **Priority 4: リスク管理の高度化** ⭐⭐⭐☆☆

#### 提案D1: **Maximum Drawdown Limit（最大DD制限）** — ✅ **実装済み（RiskOverlay, Task 40c, 2026-03-01）**

> **実装**: src/risk_overlay.py。DD_STOP / DAILY_STOP / CONSEC_STOPの3種停止条件。config.ini `enabled=0`でデフォルト無効。

```python
# 月次DD制限
if monthly_drawdown > initial_capital * 0.10:  # 10%
    # 新規エントリー停止
    pause_trading_until_next_month()

# 四半期DD制限
if quarterly_drawdown > initial_capital * 0.20:  # 20%
    # ポジションサイズ削減
    reduce_position_size(factor=0.5)
```

**期待効果**:
- Q1 2025 (-143 USD) のような連敗を途中で停止
- 心理的負担軽減
- 年間 -$100-200 の損失防止

**実装難易度**: ★★☆☆☆（2-3時間）

---

#### 提案D2: **Correlation-Based Position Sizing（相関ベースのサイズ調整）**

**コンセプト**: BTC/USDとBTC/JPY、または株式市場との相関を監視

```python
# BTC/USDとS&P500の相関が高い時期
if btc_sp500_correlation > 0.7:
    # リスクオン相場
    position_size *= 1.2  # サイズ増
    
# 相関が低い時期
elif btc_sp500_correlation < 0.3:
    # 独立相場（BTC独自の動き）
    position_size *= 1.0  # 通常
    
# 逆相関
elif btc_sp500_correlation < -0.3:
    # リスクオフ
    position_size *= 0.7  # サイズ減
```

**期待効果**:
- マクロ環境に適応
- 年間 +$200-300

**実装難易度**: ★★★★☆（5-6時間）

---

### **Priority 5: 時間フィルター（逆説的アプローチ）** ⭐⭐⭐☆☆

#### 提案E1: **Weekend/Holiday Avoidance（週末・休日回避）** — ✅ **実装済み（Task 39f, 2026-03-02）**

> **実装**: TradingStrategy.evaluate_entry()内の週末フィルター。config.ini `weekend_filter_enabled=0`でデフォルト無効。

**根拠**: 
- 週末・休日は流動性低下
- フェイク・ブレイク多発
- スプレッド拡大

```python
# 金曜21:00～日曜21:00は新規エントリー禁止
if is_weekend():
    skip_entry()

# 米国祝日（感謝祭、クリスマス etc）
if is_us_holiday():
    skip_entry()
```

**期待効果**:
- 低流動性トレードを回避
- 年間 +$100-200

**実装難易度**: ★★☆☆☆（2時間）

---

#### 提案E2: **Peak Volatility Hours（ボラティリティ・ピーク時間）**

**コンセプト**: 欧州・米国市場オープン時間に集中

```python
# UTC基準
HIGH_VOLATILITY_HOURS = [
    (7, 9),   # 欧州オープン
    (13, 15), # 米国オープン
    (20, 22)  # 米国クローズ前
]

current_hour = get_utc_hour()

if current_hour in HIGH_VOLATILITY_HOURS:
    # エントリー優先
    priority_entry = True
else:
    # フィルター厳格化
    adx_threshold += 5
    pvo_threshold += 5
```

**期待効果**:
- 高流動性時間帯でのエントリー増加
- 年間 +$150-300

**実装難易度**: ★★☆☆☆（2-3時間）

---

### **Priority 6: AI/機械学習の導入（長期戦略）** ⭐⭐☆☆☆

#### 提案F1: **Reinforcement Learning for Entry Timing**

**コンセプト**: 過去のトレードログをAIに学習させる

- 勝ちトレードの共通パターン
- 負けトレードの共通パターン
- 最適なエントリー/Exit タイミング

**期待効果**:
- 人間が見落とすパターンを発見
- 年間 +$500-1000（推定）

**実装難易度**: ★★★★★（20-40時間、専門知識必要）

---

## 💰 Expected ROI（期待投資収益率）

| 戦略 | 実装状況 | 実装時間 | 期待利益増加 | ROI |
|------|------|----|----------|-----|
| A1: Trailing Profit | ✖ 不採用 (-1,077 USD悪化) | 2-3h | N/A | — |
| A2: Time-Based Exit | ✅ 実装済み | 1-2h | +$100-200 | ⭐⭐⭐⭐⭐ |
| A3: Dynamic Stop | ✅ 実装済み | 2-3h | +$100-150 | ⭐⭐⭐⭐☆ |
| B1: Two-Tier Entry | ✅ 実装済み (+378 USD) | 3-4h | +$300-600 | ⭐⭐⭐⭐⭐ |
| B2: MR Hybrid | ✖ 不採用 (PF=0.07) | 4-5h | N/A | — |
| C1: Multi-Timeframe | ✖ 不採用 (トレード数=0) | 6-8h | N/A | — |
| D1: DD Limit | ✅ 実装済み (RiskOverlay) | 2-3h | +$100-200 | ⭐⭐⭐☆☆ |
| D2: Correlation | 未実装 | 5-6h | +$200-300 | ⭐⭐⭐☆☆ |
| E1: Weekend Avoid | ✅ 実装済み | 2h | +$100-200 | ⭐⭐⭐⭐☆ |
| E2: Peak Hours | 未実装 | 2-3h | +$150-300 | ⭐⭐⭐⭐☆ |

**実賟効果合計**: +1,282.62 USD（ベースライン +2,402.94 USD、導入戦略による「ParamSweep」追加含む）

---

## 📋 実装ロードマップ

### Phase 1: Quick Wins（1-2週間）
1. ✅ A2: Time-Based Exit — 実装済み
2. ✅ E1: Weekend Avoidance — 実装済み
3. ✖ A1: Trailing Profit Target — 不採用 (-1,077 USD悪化)

**期待効果**: +$400-800 / 年

---

### Phase 2: High-Impact（2-4週間）
4. ✅ B1: Two-Tier Entry System — 実装済み (+378 USD)
5. ✅ A3: Dynamic Stop Loss — 実装済み
6. E2: Peak Volatility Hours — 未実装

**期待効果**: +$550-1,250 / 年（累積）

---

### Phase 3: Advanced（1-2ヶ月）
7. ✖ C1: Multi-Timeframe Integration — 不採用 (トレード数 0件)
8. ✖ B2: Mean Reversion Hybrid — 不採用 (PF=0.07)
9. ✅ D1: Drawdown Limit (RiskOverlay) — 実装済み

**期待効果**: +$700-1,300 / 年（累積）

---

### Phase 4: Pro Level（3-6ヶ月）
10. ✅ D2: Correlation-Based Sizing
11. ✅ F1: AI/ML Integration (optional)

**期待効果**: +$200-1,300 / 年（累積）

---

## ⚠️ リスクと注意事項

### 過学習のリスク
- バックテストでの改善 ≠ 実運用での改善
- 2024年データに過適応する危険性
- **対策**: 2025年データでの検証必須

### 複雑化のリスク
- システムが複雑になりすぎるとメンテナンス困難
- **対策**: 段階的実装、各Phaseでの効果測定

### 市場環境変化のリスク
- 2026年の市場環境が2024-2025と異なる可能性
- **対策**: リアルタイム監視、月次レビュー

---

## 🎯 推奨実装順序（Top 3）

### 1位: **A1 Trailing Profit Target** ⭐⭐⭐⭐⭐
- **理由**: 実装が簡単で効果大、Q4 2024の利益を守る
- **実装時間**: 2-3時間
- **期待効果**: +$200-400 / 年

### 2位: **B1 Two-Tier Entry System** ⭐⭐⭐⭐⭐
- **理由**: トレード機会が2倍、リスクは限定的
- **実装時間**: 3-4時間
- **期待効果**: +$300-600 / 年

### 3位: **C1 Multi-Timeframe Integration** ⭐⭐⭐⭐⭐
- **理由**: 根本的な改善、フェイク・ブレイク削減
- **実装時間**: 6-8時間
- **期待効果**: +$400-700 / 年

---

## 📊 成功の測定基準（KPI）

### 短期（1-3ヶ月）
- トレード数: 22件/年 → 35-45件/年
- 勝率: 55-60% 維持
- Profit Factor: 1.5 → 2.0+

### 中期（6-12ヶ月）
- 年間損益: +1,936 USD → +3,500-4,500 USD
- 最大DD: -143 USD → -80 USD以下
- Sharpe Ratio: 0.5 → 1.0+

### 長期（1-2年）
- 累積資産: 目標 $10,000+
- 月次安定性: 赤字月 < 20%
- 事業資金として独立可能

---

## 結論

実装済み戦略の効果まとめ（現時点）：
- **Two-Tier Entry System** (+378 USD): 最大の貢献、ベースライン向上を確認
- **RiskOverlay (DDキルスイッチ)**: 資産保護セーフティネット（デフォルト無効）
- **Time-Based Exit / Dynamic Stop / Weekend Filter**: リスク微調整として実装済み

不採用戦略の教訓：
- **A1 Trailing Profit** / **B2 MR Hybrid** / **C1 Multi-Timeframe**: バックテストでネガティブまたはトレード数=0。複雑化しすぎるより現行システムを維持する方が良い

次の優先タスク候補：
1. **D2: Correlation-Based Sizing**—マクロ環境適応
2. **E2: Peak Volatility Hours**—高流動性時間帯フィルター
3. **Chandelier Exit / Profit Step Lock**—細かい利益確定改善
4. **Volume Climax Exit / Composite Score Exit**—トレンド失速検出

現在のドライバー: Donchian 30期間 + ADXフィルター(=31) + PVOフィルター + TSMOMフィルター(lookback=150) + PSARストップ。バックテストベースライン: +2,402.94 USD (8四半期)。
