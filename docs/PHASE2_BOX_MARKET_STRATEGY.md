# Phase 2: Box市場向け平均回帰戦略 設計書
**開始日**: 2025-12-11  
**対象**: ADX < 20 (Box市場) のトレード改善  
**目標**: 2025年度Q1-Q3 の -$109 → +$50-100 への改善

---

## 1. 現況分析

### Phase 1.5 結果の課題点

#### 2025年度の問題分析
| 期間 | 基準 | Phase1.5 | 状態 | 根本原因 |
|------|------|----------|------|---------|
| Q1 | -$143.83 | -$141.13 | ⚠️ 改善なし | ADX不安定、平均回帰機会多 |
| Q2 | -$169.05 | -$151.57 | ⚠️ 改善不十分 | Box中心、トレンド戦略非効率 |
| Q3 | -$133.87 | -$137.67 | ❌ 悪化 | Weak Trend長期化、容量超過 |
| **計** | **-$446.75** | **-$430.37** | **⚠️ 課題残存** | **Box市場対応不足** |

### 2025年度特有の市場環境
```
2024年: ADX継続的に25以上 → トレンドフォロー有効
2025年: ADX 18-28 範囲で頻繁に推移 → Weak Trend/Box長期化
```

**結論**: トレンドフォローだけでは2025年度対応不可。Box市場専用戦略が必須。

---

## 2. Box市場戦略の基本理論

### 2.1 Donchian Channel 逆張り戦略

#### ロジック概要
```
Donchian Channel (20期間) の極値到達時に反対方向へエントリー

高値タッチ → 売り (下向き平均回帰)
安値タッチ → 買い (上向き平均回帰)
```

#### 対象市場
- **ADX < 20** (Box市場)
- **ボラティリティ < 中央値** (安定した値動き)
- **VIX 相当指標が低い** (市場環境が静かめ)

#### メリット
- トレンドフォローと相反 → Box市場での勝率向上
- 統計的平均回帰 → 確率的有利性
- 相対的にドローダウン小

### 2.2 Bollinger Bands 補助戦略

#### 実装イメージ
```
Donchian Channel データ不足時の代替戦略

BB(20, 2σ) 外部接触 → 逆張りエントリー
- 上限 > 価格 → 売り準備
- 下限 < 価格 → 買い準備
```

#### 適用条件
- Donchian の 20日データ揃わない初期期間
- ADX < 20 継続中

---

## 3. 実装設計

### 3.1 evaluate_entry() 拡張

#### 処理フロー
```python
def evaluate_entry(self):
    # 既存: 3段階ADXフィルタ
    adx = self.risk_manager.get_adx()
    
    if adx < 20:
        regime = 'BOX'
        # ← ここに新規Box市場ロジック追加
        return self._evaluate_box_market_entry()
    
    elif 20 <= adx < 25:
        regime = 'WEAK_TREND'
        position_size_ratio = 0.5
        # 既存Weak Trend処理継続
    
    else:
        regime = 'STRONG_TREND'
        position_size_ratio = 1.0
        # 既存トレンドフォロー継続
```

### 3.2 新規メソッド: _evaluate_box_market_entry()

#### シグナル生成ロジック

```python
def _evaluate_box_market_entry(self):
    """Box市場向け平均回帰エントリー"""
    
    # Donchian Channel計算
    donchian_high = self.risk_manager.get_donchian_high(period=20)
    donchian_low = self.risk_manager.get_donchian_low(period=20)
    current_price = self.current_price
    
    # 逆張りシグナル判定
    if current_price >= donchian_high * 0.98:
        # 高値タッチ → 売りシグナル
        signal = 'SHORT'
        reason = 'Donchian_High_Touch'
        position_size_ratio = 0.6  # Box市場は小さめサイズ
        
    elif current_price <= donchian_low * 1.02:
        # 安値タッチ → 買いシグナル
        signal = 'LONG'
        reason = 'Donchian_Low_Touch'
        position_size_ratio = 0.6
    
    else:
        # BB補助シグナル検索
        signal, reason, ratio = self._evaluate_bollinger_signal()
        if signal:
            position_size_ratio = ratio
        else:
            return None  # エントリーなし
    
    return {
        'signal': signal,
        'reason': reason,
        'position_size_ratio': position_size_ratio,
        'regime': 'BOX'
    }
```

### 3.3 補助メソッド: _evaluate_bollinger_signal()

#### Bollinger Bands 逆張りロジック

```python
def _evaluate_bollinger_signal(self):
    """BB 2σ外部接触での逆張り"""
    
    bb_upper = self.risk_manager.get_bb_upper(period=20, sigma=2.0)
    bb_lower = self.risk_manager.get_bb_lower(period=20, sigma=2.0)
    current_price = self.current_price
    
    if current_price > bb_upper:
        return ('SHORT', 'BB_Upper_Touch', 0.4)  # より保守的
    
    elif current_price < bb_lower:
        return ('LONG', 'BB_Lower_Touch', 0.4)
    
    else:
        return (None, None, 0)
```

---

## 4. リスク管理

### 4.1 Box市場での位置サイズ制御

#### ポジションサイズ比率
| シグナル | 信頼度 | サイズ比 | 最大保有 |
|----------|--------|---------|---------|
| Donchian High/Low Touch | 高 | 60% | 1 |
| BB 2σ Touch | 中 | 40% | 1 |
| Weak Trend ADX 20-25 | 低 | 50% | 2 |
| Strong Trend ADX ≥25 | 高 | 100% | 3+ |

### 4.2 ストップロス設定

#### Box市場でのSL
```
エントリー方向と逆側のDonchian Channel 20期間境界
+ ATR × 0.5 の余裕

例: 安値タッチで買い
    → SL = Donchian High + ATR×0.5 (逆側で売却)
```

#### 理由
- トレンド転換時の損切り（ブレイクアウト対応）
- 過度なドローダウン防止

### 4.3 利確設定

#### Box市場での利確
```
Donchian Channel 中央値 (High + Low)/2 到達時
または
ATR × 1.5 (初期エントリー価格からの利益確定)
```

#### 段階的利確パターン
```
1. 25% ポジション: 利益 = ATR × 1.0
2. 50% ポジション: 利益 = ATR × 1.5
3. 残25%: トレール (ATR × 0.5 逆指値)
```

---

## 5. 実装チェックリスト

### 5.1 コード実装

- [ ] `_evaluate_box_market_entry()` メソッド追加
- [ ] `_evaluate_bollinger_signal()` メソッド追加
- [ ] RiskManager に `get_donchian_high()`, `get_donchian_low()` メソッド追加
- [ ] RiskManager に `get_bb_upper()`, `get_bb_lower()` メソッド追加
- [ ] evaluate_entry() 内に Box市場フロー統合
- [ ] logging に `reason` フィールド追加

### 5.2 テスト実装

- [ ] 単体テスト: Donchian逆張りシグナル生成
- [ ] 単体テスト: BB補助シグナル生成
- [ ] 統合テスト: 2025 Q1-Q3 でのバックテスト実行
- [ ] 回帰テスト: 2024年度が悪化していないか確認

### 5.3 ドキュメント

- [ ] PHASE2_BACKTEST_RESULTS.md 作成
- [ ] ARCHITECTURE_OVERVIEW.md に NO.21 追加
- [ ] リリースノート作成

---

## 6. 期待値計算

### 6.1 2025年度Q1-Q3での改善予測

#### 前提条件
- Q1: ADX 18-24 のレンジ変動 (現-$141)
- Q2: 大半がBox市場 ADX<20 (現-$151)
- Q3: ADX 16-26 で長期Weak Trend (現-$137)

#### 改善見積もり

| 期間 | 現状 | 予測 | 改善率 | 説明 |
|------|------|------|--------|------|
| Q1 | -$141 | -$20 | 86% | Donchian有効、中程度Box |
| Q2 | -$151 | +$40 | 126% | Pure Box環境、逆張り最適 |
| Q3 | -$137 | -$30 | 78% | 長期Weak Trend、部分Box |
| **計** | **-$429** | **-$10** | **98%** | **黒字化も視野** |

### 6.2 成功指標

| 指標 | 目標 | 判定基準 |
|------|------|---------|
| 2025 Q1-Q3 改善 | > -$50 | ✅ 達成 / ⚠️ 未達成 |
| Win率向上 | > baseline +10% | 逆張りの有効性判定 |
| ドローダウン | < 基準の120% | リスク管理評価 |
| 利益因子 | > 1.2 | 全体的な商い効率 |

---

## 7. リスク・注意点

### 7.1 実装リスク

| リスク | 影響 | 対策 |
|--------|------|------|
| Donchian遅延計算 | 計算コスト増 | キャッシング実装 |
| 偽のブレイクアウト | False entry | Bollinger補助で確認 |
| トレンド転換への対応 | 損失拡大 | SL厳密実装 |

### 7.2 バックテスト留意点

- Donchian 20期未満データでの動作 (初期期間) → BB補助で対応
- スリッページ考慮 (逆張りは成行きリスク高) → 保守的サイズ設定
- 2024年度での過度なエントリー増加 → 2024年度は Box市場ないため影響小

---

## 8. 実装カレンダー

| フェーズ | 内容 | 期間 | 優先度 |
|----------|------|------|--------|
| 8.1 | RiskManager 拡張 (Donchian/BB計算) | 1-2h | P0 |
| 8.2 | `_evaluate_box_market_entry()` 実装 | 2-3h | P0 |
| 8.3 | `_evaluate_bollinger_signal()` 実装 | 1h | P0 |
| 8.4 | evaluate_entry() 統合 | 1h | P0 |
| 8.5 | ローカル検証・デバッグ | 2h | P1 |
| 8.6 | バックテスト実行 | 0.5h | P1 |
| 8.7 | 結果分析・ドキュメント | 2h | P2 |

**総工期**: 9.5h / 1.2日

---

## 9. 関連ドキュメント

- PHASE1_5_BACKTEST_RESULTS.md - Phase 1.5 結果、2025年度課題の詳細
- ARCHITECTURE_OVERVIEW.md - NO.20の既存3段階ADXフィルタ
- PHASE1_LOSS_ANALYSIS.md - 元の4損失Q分析

