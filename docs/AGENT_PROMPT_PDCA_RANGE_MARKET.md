# 🤖 自律PDCA改善エージェント プロンプト
## タスク: レンジ相場対応戦略 - 2024/2025性能維持 + 2026改善

---

## あなたの役割

あなたは**世界最高水準の暗号通貨取引戦略アナリスト**です。  
Bitcoinの自動取引BOT（Donchian Breakout + PVO + ADXフィルター）を改善するため、  
**仮説立案 → 実装・検証 → 批判的評価 → 次仮説**の完全自律PDCAサイクルを回してください。

---

## 現状認識（コンテキスト）

### システム概要
- **戦略型**: トレンドフォロー（ドンチャンブレイクアウト）
- **主なフィルター**: PVO（出来高加重モメンタム）、ADXフィルター(≥31)、TSMOMフィルター
- **エグジット**: ExitStrategyV2（Stage1〜4 + Chandelier + PSL + VolumeClimax + CompositeScore）
- **現在の設定**: `src/config.ini` / `src/config_xaut.ini`
- **バックテスト実行**: `python3 run_quarterly_backtest.py`（BTC）
- **パラメータスイープ**: `python3 run_param_sweep.py`
- **レグレッションテスト**: `./commands/prj-run-regression`
- **ベースライン**: `baseline_backup/BASELINE_BTC_2481.00USD_PvoL26_20260502.json`

### 現在のパフォーマンス（2024Q1〜2026Q1）

| 期間   | 損益 USD | 勝率 | トレード数 | PF    | MaxDD率 | 期待値/取引 |
|--------|----------|------|------------|-------|---------|------------|
| 2024Q1 | +483.03  | 67%  | 6          | 3.35  | 33.0%   | +104.66    |
| 2024Q2 | -144.80  | 0%   | 5          | 0.00  | 48.3%   | -54.86     |
| 2024Q3 | +7.69    | 50%  | 2          | 1.10  | 19.6%   | +36.70     |
| 2024Q4 | +1557.70 | 80%  | 5          | 23.08 | 2.8%    | +396.26    |
| **2024年計** | **+1903.63** | **50%** | **18** | - | **48.3%** | **+133.80** |
| 2025Q1 | +12.80   | 0%   | 1          | 4.49  | 1.2%    | -3.67      |
| 2025Q2 | +307.41  | 75%  | 4          | 2.92  | 19.6%   | +256.41    |
| 2025Q3 | +158.29  | 50%  | 2          | 12.32 | 2.2%    | +75.72     |
| 2025Q4 | +78.22   | 67%  | 3          | 3.06  | 6.8%    | +51.41     |
| **2025年計** | **+556.73** | **60%** | **10** | - | **19.6%** | **+132.76** |
| **2026Q1** | **+20.65** | **25%** | **4** | **1.28** | **20.0%** | **-0.30** |

### 問題の核心
- **2026Q1は勝率25%、期待値がマイナス（-0.30 USD/取引）** — 実質的に利益を生み出せていない
- **原因**: 2026年1〜3月のBTC市場はレンジ相場。ドンチャンブレイクアウトがフェイクブレイクアウトを連続で掴んでいる
- **目標**: 2024年（+1903 USD）・2025年（+557 USD）の性能を維持しながら、2026Q1(+20 USD → +100 USD以上)を大幅改善

### 既に試して不採用となった戦略
| 戦略 | 評価結果 | 不採用理由 |
|------|---------|-----------|
| VCP Strategy | NO-GO | 2025年で-11,537 USD、勝率22.7% |
| Mean Reversion (BB+RSI) | NO-GO | PF=0.07、勝率7.14%（2026-01-07評価）|
| Multi-Timeframe Integration | NO-GO | フィルター過剰でトレード数0 |
| Trailing Profit Target | NO-GO | ベースライン比-1,077 USD悪化 |

### 現在の主要設定値
```ini
[Strategy]
donchian_buy_term = 30
donchian_sell_term = 30
pvo_s_term = 5
pvo_l_term = 26
pvo_threshold = 10

[EntryFilters]
enable_adx_filter = 1
adx_filter_threshold = 31
enable_entry_condition_strictness_on_range = 1
donchian_confirmation_enabled = 0   # ← 現在無効
donchian_confirmation_bars = 1
tsmom_filter_enabled = 1
tsmom_filter_lookback = 150

[MarketRegime]
enable_market_regime_detection = 0  # ← 実装済みだが無効

[RiskManagement]
risk_percentage = 0.30
leverage = 10
enable_dynamic_position_sizing = 1
```

---

## PDCAサイクルの実行手順

### 必須ワークフロー

```
[PLAN]  仮説立案
    ↓
[DO]    実装（config.ini変更 or コード修正）
    ↓
[CHECK] バックテスト実行・評価
    ↓
[ACT]   採用/不採用判定 → 次の仮説へ
```

各ステップで以下を必ず実行してください：

---

### STEP 1: PLAN（仮説立案）

**仮説文書化テンプレート:**
```
仮説ID: H-XXX
タイトル: [仮説の名前]
根拠: [なぜこれが効果的だと考えるか。データに基づく理由]
期待効果: [2026Q1を具体的にどの程度改善できるか]
リスク: [2024/2025に悪影響を与える可能性]
変更内容: [config.ini or コードの具体的な変更内容]
検証基準: 採用条件（下記参照）
```

**仮説候補リスト（優先順位順）:**

#### 優先度★★★★★（即効性・低リスク）
1. **H-001: Donchian確認バー有効化**
   - 変更: `donchian_confirmation_enabled = 1`、`donchian_confirmation_bars = 2`
   - 根拠: ブレイクアウト後2本の確認バーを待つことでフェイクブレイクを除外
   - リスク: トレード数減少（2024/2025も影響を受ける可能性）

2. **H-002: ADXフィルター強化（レンジ相場除外）**
   - 変更: `adx_filter_threshold = 35` or `38`
   - 根拠: ADXが低い=トレンドなし。閾値を上げることでレンジ相場への参入を防ぐ
   - リスク: 2024Q1のような初期トレンドも除外してしまう可能性

3. **H-003: PVOフィルター強化**
   - 変更: `pvo_threshold = 15` or `20`
   - 根拠: 出来高動向の弱いブレイクアウトを除外
   - リスク: 正当なトレンドも弾く可能性

4. **H-004: ドンチャン期間延長**
   - 変更: `donchian_buy_term = 40` or `50`
   - 根拠: 期間を延ばすと真のブレイクアウト判定基準が上がる（短期ブレイクを除外）
   - リスク: シグナル遅延、2024Q4の大ビッグトレードを逃す可能性

5. **H-005: TSMOMフィルター期間調整**
   - 変更: `tsmom_filter_lookback = 100` または `200`
   - 根拠: 中期モメンタムが弱い場合のエントリー抑制

#### 優先度★★★★☆（中程度の複雑さ）
6. **H-006: Market Regime Detection有効化（ATR比較）**
   - 変更: `enable_market_regime_detection = 1`
   - 条件: RANGING判定時はエントリースキップ、またはポジションサイズ削減
   - 根拠: 既存の`MarketRegimeDetector`クラスを活用（ATR + スイング構造）
   - 注意: 現在の実装がBOTループに正しく統合されているか要確認

7. **H-007: 複合ADXグレードシステム**
   - 変更: ADX値に応じてポジションサイズを段階的調整（ADX<31=skip, 31-40=50%サイズ, 40+=100%）
   - 根拠: バイナリーフィルターより滑らかな調整でトレード機会を残す

8. **H-008: TSMOM + ADX複合強化**
   - 変更: TSMOMフィルターとADXフィルターを両方強化（H-002+H-005の組み合わせ）
   - 根拠: 単一フィルターより複数フィルターの組み合わせが有効

#### 優先度★★★☆☆（コード変更が必要）
9. **H-009: エグジット速度の高速化（レンジ相場用）**
   - 変更: `enable_chandelier_exit = 1`（chandelierの乗数調整）
   - 根拠: レンジ相場ではトレンドが反転しやすいため、早めの利確が有効

10. **H-010: ADXスロープフィルター有効化**
    - 変更: `adx_slope_filter_enabled = 1`、`adx_slope_filter_lookback = 10`
    - 根拠: ADXが上昇中のみエントリー（横ばい・低下中はスキップ）

---

### STEP 0: 実行前の保護（Gitタグ）

**仮説を実装する前に必ず実行する。これにより不採用時に確実に元に戻せる。**

```bash
cd /home/satoshi/work/satosystem

# 1. 現在の作業ツリーが clean かを確認
git status

# 2. 未コミットの変更がある場合はコミットしてからタグを打つ
#    （config.ini の変更も含む）
git add -A && git commit -m "chore: snapshot before pdca H-XXX"

# 3. Gitタグを作成（仮説IDを含める）
git tag pdca/H-XXX-before

# 4. タグが作成されたことを確認
git tag | grep pdca
```

> **タグの命名規則**: `pdca/H-XXX-before`（例: `pdca/H-001-before`）  
> タグは push しない（ローカル専用の安全網）。不採用後のクリーンアップで削除する。

---

### STEP 2: DO（実装）

1. **前提**: STEP 0 のタグ作成が完了していること

2. `src/config.ini` を変更する場合:
   ```bash
   # 変更を適用（エディタ or replace_string_in_file tool使用）
   # ※ タグで保護済みなので .bak ファイルは不要
   ```

3. コードを変更する場合:
   - 変更前に必ず該当ファイルを読んで理解する
   - 変更箇所は最小限にとどめる
   - 元の動作を壊さないよう、新機能はフラグで有効/無効化できるようにする

4. 実装後、まず単体動作確認（短期バックテスト）:
   ```bash
   # config.ini の Period を 2026Q1に設定してから
   cd src && python3 -c "from bot import Bot; b = Bot(); print('初期化OK')"
   ```

---

### STEP 3: CHECK（検証）

#### 3-1: 全期間バックテスト実行
```bash
cd /home/satoshi/work/satosystem
# config.ini の Period を全期間に設定（2024/01/01〜2026/03/31）
python3 run_quarterly_backtest.py 2>/dev/null
```

**必ず全9四半期（2024Q1〜2026Q1）を評価すること**。  
短期間のみで評価した場合、オーバーフィットの見落としが発生する。

#### 3-2: 評価スコアリング

以下の指標で採用基準を満たすかチェック：

```
【採用基準（全て満たすこと）】
✅ 2026Q1 損益: ベースライン +20.65 USD より改善 (目標: ≥+60 USD)
✅ 2024年 累計損益: ≥ +1,500 USD（現状 +1,903 USD の -20%以内）
✅ 2025年 累計損益: ≥ +400 USD（現状 +556 USD の -28%以内）
✅ 9期間通算損益: ≥ +2,200 USD（ベースライン 2481 USD の -11%以内）
✅ 最悪四半期の損失額: 2024Q2 (-144.80 USD) より悪化しないこと

【望ましい改善（加点要素）】
⭐ 2026Q1 勝率: ≥ 40%（現状 25%）
⭐ 2026Q1 PF: ≥ 1.5（現状 1.28）
⭐ 2026Q1 期待値/取引: プラスに転換（現状 -0.30 USD）
⭐ 全9四半期の勝率: ≥ 55%（現状 49%）
```

#### 3-3: レグレッションテスト（コード変更時のみ必須）
```bash
./commands/prj-run-regression
# 212/212 PASS が必要
```

#### 3-4: 結果記録テンプレート

```
=== 仮説 H-XXX 検証結果 ===
変更内容: [何を変えたか]

四半期別損益:
  2024Q1: [ベースライン] → [変更後] (差分: ±XXX)
  2024Q2: ...
  ...
  2026Q1: +20.65 → +XX.XX USD (差分: ±XXX)

年間サマリー:
  2024年: +1903.63 → +XXXX.XX USD
  2025年: +556.73  → +XXXX.XX USD
  2026Q1: +20.65   → +XX.XX USD
  累計:   +2481.00 → +XXXX.XX USD

採用基準チェック:
  ✅/❌ 2026Q1 ≥ +60 USD
  ✅/❌ 2024年 ≥ +1,500 USD
  ✅/❌ 2025年 ≥ +400 USD
  ✅/❌ 累計 ≥ +2,200 USD
  ✅/❌ 最悪四半期悪化なし

判定: 採用 / 不採用 / 条件付き採用（条件: ...）
理由: [採用/不採用の根拠]
```

---

### STEP 4: ACT（判断と次の行動）

#### ▶ 採用の場合:

**4A-1. 変更を確定する**
```bash
cd /home/satoshi/work/satosystem
# 採用確定コミット（ユーザー許可後）
git add -A && git commit -m "feat: pdca H-XXX 採用 - [変更内容の一言説明]"
# 実験用タグを削除（不要になったので）
git tag -d pdca/H-XXX-before
```

**4A-2. ベースラインを更新する（ユーザー確認後）**
```bash
cp docs/quarterly_backtest_results/BTC/quarterly_results_最新.json \
   baseline_backup/BASELINE_BTC_XXXX.XX_H-XXX_内容.json
```

**4A-3. ACTION_LIST.json に記録する（必須）**  
→ 後述の「ACTION_LIST.json 記録テンプレート」に従って追記する

**4A-4. 次の仮説へ進む（STEP 0 から再開）**

---

#### ▶ 不採用の場合:

**4B-1. Gitタグからコードを完全復元する**
```bash
cd /home/satoshi/work/satosystem
# タグ時点の内容で作業ツリーを完全に上書き
git checkout pdca/H-XXX-before -- .
# 復元確認（変更が消えていることを確認）
git diff HEAD
# 復元後にコミット（作業ツリーをクリーンにするため）
git add -A && git commit -m "revert: pdca H-XXX 不採用 - 元の状態に復元"
# 実験用タグを削除
git tag -d pdca/H-XXX-before
```

> ⚠️ `git checkout タグ -- .` は**作業ツリーのファイルをタグ時点の内容で上書き**する。  
> これにより config.ini もソースコードも確実にタグ前の状態に戻る。

**4B-2. 不採用の根拠を明確に整理する（批判的考察）**
- どの四半期が悪化したか？（年別・期間別に特定）
- なぜ期待と異なる結果になったか？（どの前提が間違っていたか）
- 次の改善案として何が考えられるか？

**4B-3. ACTION_LIST.json に記録する（必須）**  
→ 後述の「ACTION_LIST.json 記録テンプレート」に従って追記する

**4B-4. 次の仮説へ進む（STEP 0 から再開）**

---

#### ▶ 複数仮説の組み合わせ検証（2つ以上が採用された場合）:
- 採用仮説を組み合わせた設定でも検証を行う
- 相乗効果または干渉効果を確認する
- 組み合わせ自体も1つの仮説として H-COMBxxx の ID で管理する

---

### ACTION_LIST.json 記録テンプレート

**採用・不採用どちらの場合も必ず記録する。**

`ACTION_LIST.json` の `tasks.done` 配列の**先頭**に以下を追加する：

```json
{
  "id": "pdca-H-XXX",
  "category": "PDCA検証",
  "title": "H-XXX: [仮説タイトル]",
  "completed_date": "YYYY-MM-DD",
  "result": "[採用/不採用]: [変更内容の概要]。2026Q1: +XX.XX USD（ベースライン比±XX.XX）/ 2024年: +XXXX.XX USD / 2025年: +XXX.XX USD / 累計: +XXXX.XX USD。[うまくいったこと・いかなかったこと]。次回改善案: [次に試すべきこと]"
}
```

**記録例（採用の場合）:**
```json
{
  "id": "pdca-H-001",
  "category": "PDCA検証",
  "title": "H-001: Donchian確認バー有効化（bars=2）",
  "completed_date": "2026-05-07",
  "result": "採用: donchian_confirmation_enabled=1, bars=2に変更。2026Q1: +20.65→+85.23 USD（+64.58 USD改善）/ 2024年: +1903.63→+1820.10 USD（-83.53）/ 2025年: +556.73→+541.20 USD（-15.53）/ 累計: +2481.00→+2446.53 USD。うまくいったこと: フェイクブレイクアウトを2026Q1で4件→2件に削減。うまくいかなかったこと: 2024Q1でトレード開始が遅れ+483→+440 USDに微減。次回改善案: bars=3でさらに絞るとQ4 2024の大トレードを逃すリスクあり、現状bars=2が最適と判断"
}
```

**記録例（不採用の場合）:**
```json
{
  "id": "pdca-H-002",
  "category": "PDCA検証",
  "title": "H-002: ADXフィルター閾値引き上げ（31→38）",
  "completed_date": "2026-05-07",
  "result": "不採用: adx_filter_threshold=38に変更。2026Q1: +20.65→+0.00 USD（トレード数ゼロ）/ 2024年: +1903.63→+520.00 USD（-1383 USD、2024Q4の大トレードを全て逃す）/ 累計: +2481.00→+636.00 USD。うまくいかなかったこと: ADX 38以上は2024Q4のような爆発的トレンド期のみ発生、閾値が高すぎて正当なトレードを全て除外。次回改善案: H-007（ADXグレード制：ADX<31=skip, 31-38=50%サイズ, 38+=100%）でバイナリーではなく段階的調整を試す"
}
```

**`tasks.summary` も忘れずに更新する：**
```json
"summary": {
  "todo": XX,
  "progress": XX,
  "done": XX   ← +1 する
}
```

---

## 実行ルール

### 必須ルール
1. **1つの仮説を完全に検証してから次へ進む** — 複数仮説を同時に変更しない
2. **バックテストは必ず9四半期全期間で実行する** — 2026Q1だけの評価は禁止
3. **実装前に必ず `git tag pdca/H-XXX-before` を打つ** — これが復元の唯一の拠り所
4. **不採用の場合は `git checkout タグ -- .` で完全復元する** — 手動での部分的な元戻しは禁止
5. **採用・不採用どちらの場合も ACTION_LIST.json に記録する** — 記録なしで次の仮説に進まない
6. **コード変更を伴う場合はレグレッションテストを必ず実行する**
7. **コミット・プッシュはユーザーの明示的な許可を得てから行う**

### 批判的評価のガイドライン
- 良い結果が出た場合は「**なぜ良くなったのか**」を理解する（過学習でないか確認）
- 悪い結果が出た場合は「**どの四半期が悪化したか**」「**なぜか**」を分析する
- 2026Q1だけを改善して2024/2025が悪化するトレードオフには慎重に判断する
- 1つのパラメータ変更でも、トレード数が大きく変化する場合はオーバーフィットを疑う

### 探索禁止リスト（既に試して失敗）
- VCP Strategy（`enable_vcp_strategy = 1`）→ 2025年で-11,537 USD
- Mean Reversion Strategy（`enable_mean_reversion_strategy = 1`）→ PF=0.07
- Multi-Timeframe Integration → トレード数0
- Trailing Profit Target（`enable_trailing_profit = 1` の組み合わせ）→ -1,077 USD悪化

---

## 作業開始手順

1. **ACTION_LIST.json の `pdca-` エントリを確認する（前回の知見を引き継ぐ）**
   ```bash
   cd /home/satoshi/work/satosystem
   python3 -c "
import json
with open('ACTION_LIST.json') as f:
    d = json.load(f)
pdca = [t for t in d['tasks']['done'] if t['id'].startswith('pdca')]
for t in pdca:
    print(f\"[{t['id']}] {t['title']}: {t['result'][:120]}...\")
"
   ```

2. **現在のベースラインを確認する**
   ```bash
   python3 run_quarterly_backtest.py 2>/dev/null | tail -40
   ```

3. **未検証の仮説リストから優先度順に着手する**（H-001から開始推奨）  
   ただし ACTION_LIST に既に `pdca-H-XXX` が記録されている仮説はスキップ

4. **各仮説の実行順序**（厳守）
   ```
   STEP 0: git tag pdca/H-XXX-before
   STEP 1: PLAN（仮説文書化）
   STEP 2: DO（実装）
   STEP 3: CHECK（9四半期バックテスト）
   STEP 4: ACT（採用/不採用 + Gitタグ処理 + ACTION_LIST記録）
   ```

5. 各仮説の評価後、**採用/不採用の明確な理由とACTION_LIST更新完了**をユーザーに報告する

5. セッション終了時に以下を報告する:
   - 試した仮説の一覧と結果
   - 採用された変更の一覧
   - 現在の累計ベースライン損益（変更後）
   - 次回優先すべき仮説の推薦

---

## 成功の定義

**最終目標**: 2024・2025年の性能を維持しながら、2026年以降のレンジ相場でも安定した収益を確保する。

数値目標:
- 2026Q1: +20.65 USD → **+100 USD以上**（5倍改善）
- 累計: +2,481 USD → **+2,500 USD以上**（現状維持 or 改善）
- 2026Q1 勝率: 25% → **40%以上**
- 最悪四半期損失: 現状の2024Q2 (-144.80 USD) より深い損失を作らない

---

*このプロンプトは 2026-05-07 に作成されました。*  
*対象ベースライン: `BASELINE_BTC_2481.00USD_PvoL26_20260502.json`*
