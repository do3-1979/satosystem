# Mean Reversion 戦略 実装計画

**策定日**: 2026-01-05  
**対象タスク**: ACTION_LIST.md No.38b  
**目的**: 2025年レンジ相場に適合する Mean Reversion (平均回帰) 戦略を実装・評価し、既存Donchianブレイクアウトとの入れ替え採用を判断する

---

## 1. 背景と目的

### 1.1 VCP戦略の失敗から学んだ教訓

**VCP戦略 (Task 38a) の問題点**:
- 2025年: 44トレード, 勝率22.7%, **-11,537 USD** (❌)
- 全期間: 55トレード, 勝率25.5%, **-8,209 USD** (❌)
- VCP適用により勝率が半減 (45.1% → 22.7%)
- 最適化スクリプトのバグで初期評価を誤認 (false positive)

**教訓**:
1. ✅ **早期検証**: 実装前に理論的妥当性を確認
2. ✅ **段階的評価**: 1四半期ずつ評価し、早期に問題を発見
3. ✅ **厳格な採用基準**: PF > 1.0 を絶対条件とする
4. ✅ **ベースライン比較**: 既存戦略との比較を常に実施

### 1.2 Mean Reversion戦略の理論的根拠

**対象市場**: 2025年の高ボラティリティ・レンジ相場

**シグナル**: 
- **Bollinger Band 2σ逸脱** (価格 < BB下限)
- **RSI < 30** (売られすぎ)
- → 平均回帰 (価格が平均に戻る) を狙う

**既存Donchianとの違い**:
| 戦略 | 市場適合性 | シグナル |
|------|-----------|---------|
| **Donchian Breakout** | トレンド相場 (2024年) | 高値ブレイク → トレンド継続 |
| **Mean Reversion** | レンジ相場 (2025年) | 2σ逸脱 → 平均回帰 |

**重要**: Mean Reversion評価期間中は**Donchianブレイクアウトを無効化**し、Mean Reversionを主シグナルとして評価する。効果的であればDonchianと入れ替えて採用を検討。

---

## 2. 実装手順 (Phase 0-4)

### Phase 0: 事前評価 (30分)

**目的**: 実装前に理論的妥当性を確認

**実施内容**:
1. **2025年市場特性の再確認**
   - tools/analyze_vcp_signals.py を参考に、2025年のボラティリティ・レンジ特性を数値化
   - BB 2σ逸脱頻度とその後の価格挙動を簡易分析

2. **既存ログからの簡易検証**
   - 2025年Q1の既存ログから、BB下限到達時のその後の価格推移をサンプリング
   - 平均回帰が発生している割合を確認 (目標: 60%以上)

3. **Go/No-Go判断**
   - 平均回帰発生率 < 50%: Phase 1 に進まず、代替戦略 (Task 38c) を検討
   - 平均回帰発生率 ≥ 60%: Phase 1 実装開始

**成果物**: Phase 0 評価レポート (docs/analysis/mean_reversion_phase0_evaluation.md)

---

### Phase 1: 最小実装 (2-3時間)

**目的**: Mean Reversion戦略のコア機能を実装し、Q1 2025で初期検証

#### 1.1 実装ファイル

**新規作成**:
- `src/mean_reversion_strategy.py` (250行程度)
  - BB計算 (period=20, std_dev=2.0)
  - RSI計算 (period=14, oversold_threshold=30)
  - エントリーシグナル判定
  - ログフィールド生成

**修正ファイル**:
- `src/config.ini` - [MeanReversionStrategy] セクション追加
  ```ini
  [MeanReversionStrategy]
  enable_mean_reversion_strategy = 0  # デフォルト無効
  bb_period = 20
  bb_std_dev = 2.0
  rsi_period = 14
  rsi_oversold_threshold = 30
  ```

- `src/config.py` - Mean Reversion設定読み込み追加
  ```python
  def get_enable_mean_reversion_strategy():
      return _config.getint('MeanReversionStrategy', 'enable_mean_reversion_strategy', fallback=0)
  # 他のパラメータ読み込みメソッドも追加
  ```

- `src/trading_strategy.py` - **Donchian無効化 + Mean Reversion統合**
  ```python
  # Donchianシグナル判定を一時的にコメントアウト
  # if self.donchian_strategy.evaluate_entry(...):
  #     signals["donchian"]["signal"] = True
  
  # Mean Reversionシグナル判定を追加
  if self.mean_reversion_strategy.enable_mean_reversion_strategy:
      mr_result = self.mean_reversion_strategy.evaluate_entry(...)
      self.mr_signal_latest = mr_result['signal']
      self.mr_bb_position_latest = mr_result['bb_position']
      self.mr_rsi_value_latest = mr_result['rsi_value']
  ```

- `src/bot.py` - Mean Reversionログフィールド追加
  ```python
  'mean_reversion_signal': getattr(self.strategy, 'mr_signal_latest', 0),
  'bb_position': getattr(self.strategy, 'mr_bb_position_latest', 0.0),
  'rsi_value': getattr(self.strategy, 'mr_rsi_value_latest', 0.0)
  ```

- `src/trade_logger.py` - ログエントリー構造にMRフィールド追加

#### 1.2 初期評価 (Q1 2025のみ)

**実行**:
```bash
# config.iniで enable_mean_reversion_strategy = 1 に設定
python3 run_quarterly_backtest.py --quarter 2025-Q1
```

**評価基準**:
- トレード数: 10-20件 (適切なシグナル頻度)
- PF: > 0.8 (最低限の効果)
- 勝率: > 40%
- Q1損益: > -50 USD (Q1はベースラインでも赤字なので緩い基準)

**Go/No-Go判断**:
- ✅ PF > 0.8 → Phase 2 (Q2-Q4評価) に進む
- ❌ PF < 0.5 → 戦略却下、Task 38c (Range Breakout Enhanced) を検討

**成果物**: Q1評価レポート (docs/analysis/mean_reversion_q1_evaluation.md)

---

### Phase 2: 段階的評価 (Q2-Q4, 各1-2時間)

**目的**: 四半期ごとに評価し、問題の早期発見

#### 2.1 Q2 2025評価

**実行**:
```bash
python3 run_quarterly_backtest.py --quarter 2025-Q2
```

**評価基準**:
- PF: > 1.0 (Q2はボラティリティ高く、Mean Reversionに有利)
- Q2損益: > +100 USD
- Q1+Q2累積: > +50 USD

**判断**:
- ✅ 基準達成 → Q3評価へ
- ⚠️ PF < 1.0 but > 0.8 → パラメータ微調整 (bb_std_dev, rsi_threshold) 後、再評価
- ❌ PF < 0.8 → Phase 2中断、原因分析後に継続可否判断

#### 2.2 Q3 2025評価

**実行**:
```bash
python3 run_quarterly_backtest.py --quarter 2025-Q3
```

**評価基準**:
- PF: > 1.0
- Q3損益: > 0 USD (最低限プラス)
- Q1-Q3累積: > +100 USD

#### 2.3 Q4 2025評価

**実行**:
```bash
python3 run_quarterly_backtest.py --quarter 2025-Q4
```

**評価基準**:
- PF: > 1.0
- Q4損益: > 0 USD
- **2025年通年累積: > +200 USD** (重要指標)

**成果物**: Q2-Q4評価レポート (各四半期ごとに docs/analysis/ に作成)

---

### Phase 3: 2024年影響確認 (1-2時間)

**目的**: Mean Reversionが2024年トレンド相場に悪影響を与えないか確認

**実行**:
```bash
python3 run_quarterly_backtest.py --year 2024
```

**評価基準**:
- 2024年通年損益: ベースライン比で **-15%以内の劣化** (許容範囲)
- 2024年PF: > 0.8 (深刻な悪化でないこと)

**判断**:
- ✅ -15%以内 → Phase 4 (最終判定) へ
- ⚠️ -15% ~ -30% → ハイブリッド戦略検討 (2024: Donchian, 2025: Mean Reversion)
- ❌ -30%以上 → 2025年のみMean Reversion適用を検討、または却下

**成果物**: 2024年影響分析レポート (docs/analysis/mean_reversion_2024_impact.md)

---

### Phase 4: 最適化と検証 (2-3時間)

**目的**: 最終パラメータ調整とPRE_INTEGRATION_CHECKLIST実行

#### 4.1 パラメータ微調整 (必要に応じて)

**調整対象**:
- bb_period: 15, 20, 25
- bb_std_dev: 1.5, 2.0, 2.5
- rsi_oversold_threshold: 25, 30, 35

**方法**: 軽量スイープテスト (9-15パターン)

**評価基準**:
- 2025年通年損益が最大化されるパラメータを選択
- ただし、2024年劣化が-15%を超えないこと

#### 4.2 PRE_INTEGRATION_CHECKLIST実行

**参照**: docs/PRE_INTEGRATION_CHECKLIST.md

**実行項目**:
1. ✅ 全Qテスト (8四半期)
   ```bash
   python3 run_quarterly_backtest.py
   ```
   - 目標: 2024+2025通年で +500 USD以上

2. ✅ レグレッションテスト (111tests)
   ```bash
   python3 test/regression_test_suite.py
   ```

3. ✅ グラフ描画テスト
   ```bash
   bash backtest_and_visualize.sh
   ```

4. ✅ 分析JSON整合性
   - docs/analysis/src/mean_reversion_strategy.json 作成

5. ✅ recent_changes更新
   - 関連ファイルにコメント追加

**成果物**: 
- PRE_INTEGRATION_CHECKLIST完了レポート
- 最終評価レポート (docs/MEAN_REVERSION_FINAL_EVALUATION.md)

---

## 3. 採用判断基準

### 3.1 絶対条件 (1つでも満たさない場合は却下)

| 指標 | 基準 | 理由 |
|------|------|------|
| **2025年通年PF** | > 1.0 | 損失戦略は採用不可 |
| **2025年通年損益** | > +200 USD | 実用的な利益水準 |
| **2024年劣化** | < -15% | 過去実績への影響を最小化 |
| **レグレッション** | 111/111 PASS | システム安定性 |

### 3.2 推奨条件 (多く満たすほど採用推奨度が高い)

| 指標 | 推奨値 | 理由 |
|------|--------|------|
| **2025年勝率** | > 45% | VCPの失敗 (22.7%) を回避 |
| **Q1-Q4全てPF** | > 0.8 | 四半期ごとの安定性 |
| **2024年PF** | > 1.0 | トレンド相場でも機能 |
| **トレード数** | 50-100件/年 | 適切な機会頻度 |

### 3.3 採用判定パターン

**パターンA: 完全採用** (Donchian完全置き換え)
- ✅ 2025年PF > 1.2, 2024年劣化 < -10%
- → Mean Reversionを主シグナルとして採用
- → config.ini: enable_mean_reversion_strategy = 1, Donchianは無効化

**パターンB: 条件付き採用** (ハイブリッド戦略)
- ✅ 2025年PF > 1.0, 2024年劣化 -15% ~ -25%
- → 年度ごとに戦略切り替え (2024: Donchian, 2025: Mean Reversion)
- → 将来的にMarket Regime検出で自動切り替え検討

**パターンC: 却下**
- ❌ 2025年PF < 1.0 または 2024年劣化 > -30%
- → Mean Reversion不採用、Task 38c (Range Breakout Enhanced) へ移行
- → ACTION_LIST.md: Task 38bを「不採用判定」としてDONEへ

---

## 4. リスクと対策

### 4.1 想定リスク

| リスク | 影響 | 対策 |
|--------|------|------|
| **逆張り失敗** | 2σ逸脱後さらに下落 | ストップロス厳格化 (1-2%) |
| **トレンド相場で逆行** | 2024年で大幅損失 | Phase 3で早期検出、ハイブリッド化 |
| **シグナル頻度不足** | トレード数 < 30件/年 | bb_std_dev を 1.5 に緩和 |
| **Donchianとの競合** | 同時シグナル発生 | Mean Reversion優先ロジック実装 |

### 4.2 早期撤退基準

以下の条件に該当した場合、直ちにPhase中断:

1. **Phase 1 (Q1)**: PF < 0.5 → 戦略理論が不適合
2. **Phase 2 (Q2)**: Q1+Q2累積 < -100 USD → 連続損失で見込みなし
3. **Phase 3 (2024)**: 劣化 > -30% → 過去実績への影響が深刻

---

## 5. タイムライン

| Phase | 作業内容 | 所要時間 | 累積時間 |
|-------|---------|---------|---------|
| **Phase 0** | 事前評価 | 30分 | 0.5h |
| **Phase 1** | 最小実装 + Q1評価 | 2-3時間 | 3.5h |
| **Phase 2** | Q2-Q4段階評価 | 3-6時間 | 9.5h |
| **Phase 3** | 2024年影響確認 | 1-2時間 | 11.5h |
| **Phase 4** | 最適化 + PRE_INTEGRATION | 2-3時間 | 14.5h |
| **合計** | | **約12-15時間** | |

**目標完了日**: 2026-01-06 (実装開始から1.5-2日)

---

## 6. 成果物一覧

| ファイル | 目的 | Phase |
|---------|------|-------|
| `docs/analysis/mean_reversion_phase0_evaluation.md` | Phase 0評価結果 | 0 |
| `src/mean_reversion_strategy.py` | 戦略実装 | 1 |
| `docs/analysis/mean_reversion_q1_evaluation.md` | Q1評価結果 | 1 |
| `docs/analysis/mean_reversion_q2_evaluation.md` | Q2評価結果 | 2 |
| `docs/analysis/mean_reversion_q3_evaluation.md` | Q3評価結果 | 2 |
| `docs/analysis/mean_reversion_q4_evaluation.md` | Q4評価結果 | 2 |
| `docs/analysis/mean_reversion_2024_impact.md` | 2024年影響分析 | 3 |
| `docs/MEAN_REVERSION_FINAL_EVALUATION.md` | 最終評価・採用判断 | 4 |
| `docs/analysis/src/mean_reversion_strategy.json` | 分析JSON | 4 |

---

## 7. 次のステップ

**採用の場合**:
1. Donchianブレイクアウトを完全無効化
2. Mean Reversionを主シグナルとして本番環境適用
3. Task 38c (Range Breakout Enhanced) を中優先度に変更

**却下の場合**:
1. Mean Reversion実装は保持 (enable=0で無効化)
2. Donchianブレイクアウトを再有効化
3. Task 38c (Range Breakout Enhanced) に移行
4. ACTION_LIST.md: Task 38bを「不採用判定」としてDONEへ

---

**策定者**: GitHub Copilot  
**最終更新**: 2026-01-05  
**関連タスク**: [ACTION_LIST.md](ACTION_LIST.md) No.38b
