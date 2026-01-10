# Range Breakout Enhanced - 実装計画

**Task ID**: 38c  
**優先度**: ★★★★☆  
**作成日**: 2026-01-07  
**目的**: 既存Donchian戦略を強化し、偽ブレイク回避と出来高確認で2025年成績を改善

---

## 1. 背景と課題

### 現状のDonchian戦略の問題点

**2025年の成績悪化**:
- 2025 Q1: -138.31 USD (勝率16.7%)
- 2025 Q2: +17.94 USD (勝率70.0%)
- 2025年累計: -48.14 USD

**根本原因**:
1. **偽ブレイク（False Breakout）**: Donchian高値/安値タッチ後すぐに反転
2. **出来高不足**: ブレイク時の勢い（momentum）が弱い
3. **ノイズブレイク**: 短期的な価格変動でのブレイク検出

### 既存フィルターの限界

現在適用中のフィルター:
- ✅ **PVOフィルター**: 出来高トレンドの確認（threshold=10）
- ✅ **ADXフィルター**: トレンド強度の確認（threshold=31）

これらは**全体的なマーケット環境**を判定するが、**個別ブレイク時の強度**は確認していない。

---

## 2. 実装目標

### Phase 1: 真のブレイク判定

**目的**: 単純なタッチではなく、明確なブレイクを確認

**実装内容**:
1. **ブレイク確認の閾値**: 
   - 終値がDonchian高値の `1.0-2.0%` 上で確定
   - または、Donchian安値の `1.0-2.0%` 下で確定

2. **複数足での確認**:
   - ブレイク後、次の1-2足もブレイク維持を確認
   - 即座の反転（whipsaw）を回避

3. **ブレイク強度の測定**:
   - ブレイク幅 = (現在価格 - Donchian高値) / Donchian高値 × 100
   - 閾値以上の場合のみエントリー

### Phase 2: 出来高確認

**目的**: ブレイク時の勢い（momentum）を確認

**実装内容**:
1. **相対出来高の計算**:
   - 現在の出来高 / 過去N期間の平均出来高
   - N = 20 (Donchian期間と同等)

2. **出来高閾値**:
   - 相対出来高 > 1.5 (平均の1.5倍以上)
   - 設定可能なパラメータ

3. **PVOとの併用**:
   - PVO: 長期トレンドの出来高確認
   - 相対出来高: 個別ブレイク時の勢い確認

### Phase 3: 偽ブレイク回避

**目的**: ノイズによる誤検出を削減

**実装内容**:
1. **ATR（Average True Range）による正規化**:
   - ブレイク幅をATRで正規化
   - ノイズレベル以上のブレイクのみ検出

2. **レンジ相場判定**:
   - Donchian高値 - Donchian安値 < ATR × 3
   - レンジ相場では、より厳格な閾値を適用

3. **フィルター段階的適用**:
   ```
   1st: Donchianタッチ検出
   2nd: ブレイク閾値確認 (1-2%)
   3rd: 出来高確認 (>1.5倍)
   4th: ADXフィルター (≥31)
   5th: PVOフィルター (>10)
   ```

---

## 3. 実装構造

### Option A: trading_strategy.py の拡張（推奨）

**メリット**:
- 既存コードの自然な拡張
- フィルターロジックの統合が容易
- デバッグが簡単

**実装箇所**:
- Lines 235-280: Donchianブロック内に追加ロジック
- Lines 320-350: 既存フィルターとの統合

**追加メソッド**:
```python
def _calculate_breakout_strength(self, price, donchian_level, direction):
    """ブレイク強度を計算"""
    
def _calculate_relative_volume(self, current_volume, lookback=20):
    """相対出来高を計算"""
    
def _is_genuine_breakout(self, price, donchian_high, donchian_low, volume):
    """真のブレイク判定"""
```

### Option B: range_breakout_enhanced.py 新規作成

**メリット**:
- 独立したモジュール
- A/Bテスト（既存Donchian vs Enhanced）が容易
- 将来的な戦略切り替えが簡単

**デメリット**:
- コード重複が増える
- 統合の手間が大きい

**判定**: Option A（既存拡張）を採用

---

## 4. 設定パラメータ

### config.ini への追加

```ini
[RangeBreakoutEnhanced]
# Range Breakout Enhanced 設定（Task 38c）
enable_range_breakout_enhanced = 1

# ブレイク確認閾値（%）
breakout_threshold_percent = 1.5     # 1.5% のブレイク幅を要求

# 相対出来高閾値（倍率）
relative_volume_threshold = 1.5      # 平均の1.5倍以上

# ATR正規化
enable_atr_normalization = 1
atr_period = 14                       # ATR計算期間
atr_breakout_multiplier = 2.0        # ATR × 2.0 以上のブレイク

# レンジ相場判定
range_detection_atr_multiplier = 3.0 # Donchian幅 < ATR × 3.0 でレンジ判定
```

### config.py への追加

```python
@staticmethod
def get_enable_range_breakout_enhanced():
    return Config._get_int('RangeBreakoutEnhanced', 'enable_range_breakout_enhanced', 0)

@staticmethod
def get_breakout_threshold_percent():
    return Config._get_float('RangeBreakoutEnhanced', 'breakout_threshold_percent', 1.5)

# ... 他のgetterメソッド
```

---

## 5. テスト計画

### Phase 0: 実装前ベースライン確認（✅ 完了）

- 全Qテスト: 1975.72 USD（8四半期）
- レグレッション: 111/111 PASS

### Phase 1: Enhanced実装・単体テスト

**テスト項目**:
1. ブレイク強度計算の正確性
2. 相対出来高計算の正確性
3. ATR正規化の動作確認

**テストコマンド**:
```bash
python3 -c "from src.trading_strategy import TradingStrategy; ..."
```

### Phase 2: 統合テスト（短期間）

**テスト期間**: 2025-01-01 ~ 2025-01-31（1ヶ月）

**期待結果**:
- トレード数: 減少（偽ブレイクフィルター効果）
- 勝率: 改善（真のブレイクのみエントリー）
- PnL: 改善（損失トレード削減）

**テストコマンド**:
```bash
python3 src/bot.py test 2025-01-01 2025-01-31
```

### Phase 3: Q1 2025 評価

**テスト期間**: 2025-01-01 ~ 2025-03-31

**目標**:
- Q1 PnL: -138.31 USD → >0 USD（黒字化）
- 勝率: 16.7% → >50%
- トレード数: 6件 → 4-8件（過度な減少は避ける）

**採用基準**:
- **必須**: Q1黒字化
- **推奨**: 2025年累計 -48.14 USD → >0 USD

### Phase 4: 全期間評価

**テスト期間**: 2024 Q1 ~ 2025 Q4（8四半期）

**目標**:
- 累積PnL: 1975.72 USD → >2000 USD（+1.2%改善）
- 2024年: 維持または改善
- 2025年: 大幅改善

---

## 6. リスクと対策

### リスク1: トレード数の過度な減少

**原因**: フィルター条件が厳しすぎる

**対策**:
- 閾値のパラメータ調整（1.5% → 1.0%）
- enable_range_breakout_enhanced = 0 で即座に無効化可能

### リスク2: 2024年成績の悪化

**原因**: 2024年は既存Donchianで好成績（+2023.86 USD）

**対策**:
- 2024年でのA/Bテスト実施
- 悪化する場合は、年度別設定の検討

### リスク3: 実装の複雑化

**原因**: 既存コードへの追加ロジック

**対策**:
- メソッド分割で可読性維持
- 十分なコメント・ドキュメント
- 段階的実装（Phase 1 → Phase 2 → Phase 3）

---

## 7. 実装スケジュール

### Day 1: Phase 1 実装（本日）

**作業内容**:
1. config.ini に [RangeBreakoutEnhanced] 追加
2. config.py に getterメソッド追加
3. trading_strategy.py に3つのメソッド追加
4. ブレイク閾値ロジックの統合

**所要時間**: 2-3時間

### Day 1: Phase 2 実装（本日）

**作業内容**:
1. 相対出来高計算の実装
2. 出来高フィルターの統合
3. 短期間テスト（2025-01）

**所要時間**: 1-2時間

### Day 1: Phase 3 評価（本日）

**作業内容**:
1. Q1 2025 バックテスト実行
2. 結果分析・パラメータ調整
3. 全期間テスト

**所要時間**: 1-2時間

### Day 2: Phase 4 最終評価（翌日）

**作業内容**:
1. 全Qテスト実行
2. レグレッションテスト
3. 最終調整・ドキュメント更新

**所要時間**: 2-3時間

---

## 8. 成功基準

### 必須条件

1. ✅ **Q1 2025 黒字化**: -138.31 USD → >0 USD
2. ✅ **2025年 黒字化**: -48.14 USD → >0 USD
3. ✅ **2024年 維持**: +2023.86 USD の90%以上（>1821 USD）

### 推奨条件

4. ✅ **累積PnL 改善**: 1975.72 USD → >2000 USD
5. ✅ **Q1勝率 改善**: 16.7% → >50%
6. ✅ **全期間勝率 維持**: 現状60-70% → 維持

### 判定基準

- **GO**: 必須3条件すべて達成
- **CONDITIONAL GO**: 必須2条件 + 推奨2条件達成
- **NO-GO**: 必須条件1つでも未達成

---

## 9. 関連ドキュメント

- [ACTION_LIST.md](ACTION_LIST.md) - Task 38c
- [DEVELOPMENT_RULES.md](DEVELOPMENT_RULES.md) - 開発ルール
- [ARCHITECTURE_OVERVIEW.md](ARCHITECTURE_OVERVIEW.md) - システム構造

---

**作成者**: GitHub Copilot  
**レビュー**: Pending  
**ステータス**: Phase 0 完了、Phase 1 開始準備完了
