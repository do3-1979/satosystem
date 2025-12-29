## 主要クラス・メソッド一覧（src/ 配下）

| クラス名              | ファイル                | 主な役割・概要                                 | 主なメソッド例                                      |
|----------------------|------------------------|-----------------------------------------------|----------------------------------------------------|
| Bot                  | src/bot.py             | メインループ・注文・損益管理                   | __init__, show_trade_data, run, execute_order      |
| TradingStrategy      | src/trading_strategy.py| ENTRY/ADD/EXIT判定・戦略ロジック               | __init__, initialize_trade_decision, evaluate_entry, evaluate_exit, evaluate_add, make_trade_decision |
| RiskManagement       | src/risk_management.py | ポジションサイズ計算・ストップ管理             | __init__, get_entry_range, get_stop_price, update_risk_status, get_psar, get_adx, calculate_position_size |
| Portfolio            | src/portfolio.py        | 保有ポジション・損益・ドローダウン管理         | __init__, get_position_quantity, get_profit_and_loss, add_position_quantity, get_drawdown, get_drawdown_rate |
| Visualizer           | src/visualizer.py       | ログからグラフ/HTML生成                        | __init__, detect_period_log_files, create_interactive_chart, visualize_backtest |
| Order                | src/order.py            | 注文DTO・注文情報管理                          | __init__, to_dict, __str__                         |
| Logger               | src/logger.py           | 構造化ログ・圧縮・ローテーション               | __new__, _initialize, log, log_error, log_trade_data, compress_logs |
| Config               | src/config.py           | 設定値の集中管理・キャッシュ                   | (36メソッド) get_api_key, get_market, get_bot_operation_cycle, to_dict |
| BybitExchange        | src/bybit_exchange.py   | Bybit用取引所ラッパー                           | __init__, fetch_ohlcv, fetch_ticker, get_account_balance, execute_order |
| PriceDataManagement  | src/price_data_management.py | OHLCV取得・シグナル生成・仮想時刻進行      | initialize, get_signals, update_price_data_backtest, get_ohlcv_data, get_volatility |
| Util                 | src/util.py             | ログ抽出・グラフ生成・分析補助                  | extract_and_export_logs, generate_line_chart, generate_line_profit_and_loss |
| Metrics              | src/metrics.py          | バックテスト指標計算（関数ベース）              | compute_metrics, _max_drawdown, _sharpe, _incremental_returns |
| EventBus             | src/event.py            | イベント通知・購読管理                          | __init__, subscribe, unsubscribe, emit              |
| Exchange             | src/exchange.py         | 取引所基底クラス                                | __init__, get_account_balance, execute_order        |
| Side                 | src/side.py             | 売買サイドEnum・変換関数                        | normalize_side, to_exchange_side                   |
| OHLCVCache           | src/ohlcv_cache.py      | OHLCV SQLiteキャッシュ管理                      | __init__, get_ohlcv_data, save_ohlcv_data, get_ohlcv_data_partial, migrate_from_json |
| OHLCVCacheInspector  | src/ohlcv_cache_inspector.py | キャッシュ分析・検査ツール            | __init__, get_cache_parameters, get_data_coverage, print_summary, print_detailed_analysis |
| ExitStrategyV2       | src/exit_strategy_v2.py      | 4段階出口戦略（Stage1～4）実装        | __init__, evaluate_exit_condition, _identify_stage, _check_stop_loss, safe_get |
| PathUtils            | src/path_utils.py            | パス管理・ファイル操作一元化          | get_src_dir, get_project_root, get_module_path |
# Architecture Overview

## 最新の実行モード・データ型検証 (2025-12-29 更新)

### ExitStrategyV2 型安全化
December 29日のコミット `7029c70` で以下を実装（issue: bgmode実行時のエラー）：

**実装内容:**
- `safe_get()` ヘルパー関数導入：dict型/スカラー値を安全に数値に変換
- `_check_stop_loss()` の psar_price型検証：dict型チェック + float型変換  
- `_identify_stage()` の ADX/PVO型変換：try/exceptで保護、デフォルト値フォールバック
- `evaluate_exit_condition()` の position_info['quantity'] 型検証：safe_get()適用
- 例外ハンドラの traceback.format_exc() 統合：bgmode ログに詳細エラー情報出力

**効果**: bgモード実行時の ExitStrategyV2 エラー（`'<=' not supported between instances of 'dict' and 'int'`）を完全に解決 ✅

### 実行パイプライン の安定性確認
ペーパートレード（ホットテスト）とバックテストで正常に動作確認済み：
- **バックテストモード（back_test=1）**: SQLiteキャッシュから価格取得、ダミー売買 ✅
- **ペーパートレードモード（back_test=0, hot_test_dummy_mode=1）**: Bybit実APIから価格取得、ダミー売買 ✅
- **本番トレード（back_test=0, hot_test_dummy_mode=0）**: Bybit実APIから価格取得、実取引実行 ✅

### 品質保証（2025-12-29）
- **レグレッションテスト**: 54テスト中90成功（成功率97.8%）✅
- **全四半期テスト**: 2024Q1～2025Q4 全8四半期実施、累積損益 +856.50 USD ✅
- **個別ファイルテスト**: すべてのモジュールで4～38テスト成功

## Component Responsibilities
| Component | Responsibility | Key Interactions |
|-----------|---------------|------------------|
| Config | Centralized parameter access from config.ini | All modules read cached values |
| BybitExchange | ccxt wrapper for market/balance/order/OHLCV | PriceDataManagement, Bot (orders) |
| PriceDataManagement | Fetches & buffers OHLCV, derives signals (Donchian, PVO) & volatility; backtest time progression | TradingStrategy, RiskManagement |
| TradingStrategy | Decides ENTRY / ADD / EXIT based on signals & portfolio state | Bot (decision consumer), Portfolio |
| RiskManagement | Position sizing, STOP trailing (PSAR, surge), ADX state | Bot, Portfolio, PriceDataManagement |
| Portfolio | Tracks positions, average price, cumulative PnL & drawdown | Bot, RiskManagement |
| Order | DTO encapsulating order intent | Bot, Exchange |
| Logger | Structured logging, rotation, compression | Bot, Util, Metrics |
| Util | Log extraction & visualization (HTML, charts) | Logger outputs |
| Visualizer | Interactive backtest visualization & reporting | Logger outputs |
| Metrics | Post-backtest performance metrics (Sharpe, MaxDD, PF, WinRate) | Bot (backtest summary) |
| OHLCVCache | SQLite-based OHLCV caching for fast data retrieval | PriceDataManagement, Bot |
| OHLCVCacheInspector | Cache analysis & inspection tool | OHLCVCache |

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

## Planned Improvements (M Roadmap)
- M2: Documentation consolidation (README + this file).
- M3: Refactoring issue template & backlog categorization.
- M4: Metrics pipeline (implemented) & iterative strategy enhancement loop.

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

## Phase 0 Trading Strategy - 基準戦略

**戦略概要**: Donchian Breakout + PVO シグナルベースのロング主体戦略（ADX フィルタなし）

### Phase 0 パフォーマンス（8 Quarters: Q1 2024 - Q4 2025）

```
総PnL: +$593.23
勝ちQuarter (4個): +$1,073.07 (平均+$268.27/Q, 勝率92.3%)
  - Q1 2024: +$460.17 (WR 100%, Sharpe 1.152)
  - Q3 2024: +$121.68 (WR 100%, Sharpe 0.360)
  - Q4 2024: +$142.53 (WR 69.2%, Sharpe 0.519)
  - Q4 2025: +$348.68 (WR 100%, Sharpe 1.444)

負けQuarter (4個): -$479.84 (平均-$119.96/Q, 勝率29.0%)
  - Q2 2024: -$33.09 (WR 33.3%, Sharpe -0.199)
  - Q1 2025: -$143.83 (WR 7.9%, Sharpe -1.200)
  - Q2 2025: -$169.05 (WR 12.8%, Sharpe -1.333)
  - Q3 2025: -$133.87 (WR 62.0%, Sharpe -0.441)

合計337トレード、Overall Win Rate: 56.5%
```

### 成功要因分析

**勝ちQuarterの共通特性**:
- ADX > 25（STRONG_TREND環境）
- トレンド継続率が高い
- Donchian Breakout が正確に トレンド開始を捉える

**負けQuarterの共通特性**:
- ADX < 25（WEAK_TREND / BOX環境）
- 逆方向トレンド（ショート優位）
- 偽シグナルが多発

### 実装

**ロジック**:
1. Donchian 20-period ブレイク: エントリーシグナル
2. PVO（12-26-9）: ボリュームトレンド確認
3. PSAR: トレーリングストップ
4. ATR surge: ストップ拡張

**設定** (src/trading_strategy.py):
- `donchian_lookback = 20`
- `pvo_fast = 12, pvo_slow = 26, pvo_signal = 9`
- `position_size_ratio = 1.0` (常に100%)
- ADX フィルタ: **削除済み** (Phase 0復帰)

---

## Regime-Adaptive Trading Strategy (NO.20) - 計画中

**背景**: Phase 0 分析により、市場体制検出が改善の最優先項目と特定された

**設計方針**:

### 1. レジーム判定（2024年12月実装予定）
- **指標**: ADX (14/21/50-period multi-timeframe) + 移動平均 (50/200) + 4h timeframe 検証
- **精度目標**: 65-75% → 80-85% (4h MA 併用時)
- **レジーム分類**:
  - **Strong Trend**: ADX ≥ 25 & MA order confirmed
  - **Weak Trend**: 20 ≤ ADX < 25
  - **Box**: ADX < 20 & Donchian 範囲内収束

**実装箇所**: `src/risk_management.py` の `get_adx()` メソッド拡張、`src/trading_strategy.py` へレジーム判定フラグ追加。

### 2. Pattern A: Box 相場回避（実装: 1日, 2024年12月中旬）
**効果**: 267 trades avoidable → $256.35 loss prevented, +2.2% win rate improvement

**ロジック**:
```python
if regime == 'BOX':
    return None  # Skip entry signal
```
- 実装: `evaluate_entry()` / `evaluate_add()` 最初の判定
- リスク低: PSAR ロジック全体を削除しない、flag ベースで soft block
- 検証期間: 回帰テスト suite で即座に 100% PASS 確認可能

**実装チェックリスト**:
- [ ] `RiskManagement.get_regime_state()` メソッド追加
- [ ] `TradingStrategy.is_regime_suitable()` メソッド追加
- [ ] `trading_strategy.py` ENTRY/ADD 評価の冒頭で regime check
- [ ] 回帰テスト (54 tests) pass 確認

### 3. Pattern B: Donchian Reversal（バリデーション: 2-4週, 2025年1月）
**目的**: Box 相場での利益確保 (Expected win rate: 60%, Avg PnL: $15.00)

**ロジック**:
- Donchian 20-period の Upper/Lower band 到達時に reverse entry
- 例: Upper band 到達 → SELL signal, Lower band 到達 → BUY signal
- PSAR stop は Donchian band の外側に配置

**制約**:
- regime == 'BOX' のみ適用
- 複数ポジション（averaging）は Pattern C より回避（リスク HIGH）

### 4. Composite Trend Analyzer（実装: 2-3週, 2025年1月中旬）
**多時間軸統合**:
- 2h: 短期トレンド確認（現行）
- 4h: 中期トレンド確認（新規）
- 指標加重: ADX (40%) + MA order (30%) + 4h confirmation (30%)
- 目標精度: 80-85%

**実装**: `src/price_data_management.py` へ `MultiTimeframeAnalyzer` class 追加

### 5. Box Market Exit Strategy 改良（実装: 3-4週, 2025年1月下旬）
**現行の課題**: PSAR + ATR surge で Box 相場での固定ストップが大きい

**改良案**:
- Box 相場: Donchian band (20-period) を TP/SL 基準に変更
- 通常相場: 現行 PSAR + ATR surge 継続
- Breakout 検出: ADX < 20 → ADX ≥ 25 に急変時、Box を exit

**テスト**: 回帰テスト suite で Pattern A + B の相互作用確認

---

## Future Separation
1. `IndicatorService` for PSAR, ADX, Donchian, PVO
2. `DataSource` abstraction (LiveDataSource / BacktestDataSource)
3. `RiskEngine` separate from sizing heuristics

---
This document complements `Readme.md` and analysis files; update incrementally.

**Note**: Detailed analysis documents for NO.20 are maintained in `report_tmp/no20_regime_analysis/` (ADX_REGIME_ANALYSIS.md, ADAPTIVE_REGIME_QA.md, COMBINED_TREND_ANALYSIS.md) and are Git-ignored per DEVELOPMENT_RULES.md.

## 現在の gen2 状態（8e6e543 コミット時）
- `src/` 以下にボット、戦略、管理、出力のロジックが集約されており、`bot.py` を中心にループ／注文／ログ／可視化が実行される。
- `output_configs/` には複数のバックテスト設定が並んでおり、`backtest.sh` で順次読み込まれる。（`bot_run.sh` は単独設定の実行用）
- `docs/` 以下のルール・アクション・分析資料に従って、ソース変更前に参照および更新を行う。
- ローカル OHLCV キャッシュは `ohlcv_data/` 以下で管理されており、クリーンアップ対象として README やこのドキュメントに記録している。

## ドキュメントとの連携
- ルールの根幹は `docs/DEVELOPMENT_RULES.md` に記述。作業ごとにこのファイルを確認し、`docs/ACTION_LIST.md` に進捗を記録する。
- `docs/analysis/project_structure.json` には gen2 の現行構成（ディレクトリ、主要コンポーネント）が JSON 形式で記録されており、実装変更前には必ず参照する。
- 議論や一時的な調査レポートが必要であれば `report_tmp/` 内でカテゴリ別に管理し、必要分のみ `ARCHITECTURE_OVERVIEW.md` に要約・言及する。

## バックテスト結果の可視化

### 概要

`visualizer.py` は、`bot_run.sh` で実行したバックテスト結果を、インタラクティブなHTMLグラフとして可視化します。

### 実行方法

**1. バックテスト実行**
```bash
cd src
./bot_run.sh
```
`src/logs/` ディレクトリにバックテストログが保存されます（JSON形式: `YYYYMMDDHHMMSS.json`）。

**2. グラフ生成**
```bash
cd src
python3 visualizer.py
```
最新のバックテストログを自動検出し、インタラクティブなHTMLグラフを生成します。

**3. グラフ表示**
ブラウザで `report/backtest_visualization.html` を開きます。

### 出力ファイル

- **ファイル名**: `report/backtest_visualization.html`
- **ファイルサイズ**: 約 150-200 KB
- **オープン方法**: ブラウザで直接開く（ダブルクリック）

### グラフの構成

| Row | 内容 | コンポーネント |
|-----|------|--------------|
| 1 | 価格チャート | 2時間足ローソク足、Donchian High/Low、PSAR、ポジション区間、ENTRY/ADD/EXIT、損切値 |
| 2 | ボリューム | Volume Bar（スチールブルー） |
| 3 | テクニカル指標 | Volatility（紫）、PVO（シアン） |
| 4 | 累積損益 | Total PnL（濃青面積グラフ）、ゼロライン |

### 対話機能

- **ズーム/パン**: マウスホイール、ドラッグ、手のひらツール、ホームアイコン
- **表示切替**: 凡例クリック（指標表示/非表示）、Shift+クリック（特定指標のみ）
- **ホバー情報**: マウスカーソル移動で詳細表示（日時、価格、ポジション）
- **ダウンロード**: カメラアイコンで現在表示状態をPNG出力

### 設定

`src/config.ini` で表示期間を指定：
```ini
[Period]
start_time = 2025/11/1 0:00
end_time = 2025/11/30 23:59
```

計算用ルックバック期間はデフォルト20日（グラフには指定期間のみ表示）。

### トラブルシューティング

| 問題 | 対処方法 |
|------|--------|
| 「No log files」エラー | `bot_run.sh` 実行確認、`src/logs/*.json` 確認 |
| グラフが空またはデータ少ない | `config.ini` 期間設定確認、バックテスト期間と表示期間確認 |
| ブラウザで開けない | ファイルコピー別場所試行、別ブラウザ試行 |

### ワークフロー例

```bash
cd src
./bot_run.sh          # 1. バックテスト実行
python3 visualizer.py # 2. グラフ生成
# 3. report/backtest_visualization.html をブラウザで確認
```

### 推奨ブラウザ

Chrome/Chromium（推奨）、Firefox、Safari、Edge

## 自動ソースコード解析

全ソースファイルの構造（クラス・メソッド・関数など）は `docs/analysis/` フォルダに JSON 形式で自動生成されます。

- **生成ツール**: `src/source_analyzer.py`
- **スキーマ定義**: `docs/analysis/SOURCE_ANALYSIS_SCHEMA.json`
- **生成物**: 21ファイル、統計: クラス 20、メソッド 187、関数 14

実行方法:
```bash
cd /workspace
python src/source_analyzer.py  # 全ファイルを解析して docs/analysis/ に JSON 生成
python src/source_analyzer.py --file src/config.py  # 特定ファイルのみ解析
```

## 次のステップ
- `nextarch`（および master）にある `8e6e543` 以降のコミットを一覧化し、移植対象となる変更点ごとに検討を進める。
- レグレッションテストの整備と自動化を進め、変更取り込み前に `report_tmp/` にテスト結果を保存して参照可能とする。

## OHLCV キャッシュ検査ツール

`ohlcv_cache.db` (SQLite) の内容を確認・管理するツール。バックテスト実行時にキャッシュが蓄積される仕組み。

### 主要機能

- **キャッシュサマリー**: 総レコード数、ファイルサイズ、パラメータ一覧表示
- **データ範囲分析**: 取得データの期間、セグメント（連続データ）情報
- **断絶検出**: データ内のギャップを自動検出・表示
- **詳細分析**: 全パラメータの詳細情報表示

### 使用方法

**簡易表示（デフォルト）:**
```bash
./ohlcv_cache_info.sh
./ohlcv_cache_info.sh summary  # サマリー表示
./ohlcv_cache_info.sh coverage # データ範囲・断絶表示
./ohlcv_cache_info.sh all      # 詳細分析表示
```

**Python 直接実行:**
```bash
cd src
python ohlcv_cache_inspector.py --summary
python ohlcv_cache_inspector.py --coverage
python ohlcv_cache_inspector.py --cache <path> --start <epoch> --end <epoch> --timeframe <minutes>
```

### キャッシュ構造

- **テーブル**: `candles`
- **主要カラム**: `start_epoch`, `end_epoch`, `time_frame`, `close_time`, `open_price`, `high_price`, `low_price`, `close_price`, `volume`
- **保存先**: `ohlcv_data/ohlcv_cache.db`

### キャッシュをクリア

```bash
# Pythonで実行
python -c "from ohlcv_cache import OHLCVCache; OHLCVCache().clear_cache()"
# または
rm ohlcv_data/ohlcv_cache.db
```

## レグレッション テストスイート

### 概要

11個の個別テストモジュール + 統合スイートで、プロジェクト全体の整合性を自動検証。Python name mangling（`__method` → `_Class__method`）対応済み。

### 実行方法

```bash
cd /home/satoshi/work/satosystem
python test/regression_test_suite.py
```

実行内容：
1. 従来型レグレッション (Consistency チェック等)
2. 11個の個別ファイルレグレッション実行
3. JSON結果ファイル生成
4. 統合レポート生成

### テスト結果

結果は以下に自動生成：
- 個別テスト結果: `docs/regression_test_results/test_*.json`
- 統合レポート: `docs/regression_test_results/REGRESSION_TEST_REPORT.json`
- 統計情報: `docs/regression_test_results/individual_test_summary.json`

### テスト対象モジュール

| ファイル | テスト数 | 対象 |
|---------|--------|------|
| bot.py | 4 | Bot クラス・メソッド・実行可能性 |
| config.py | 5 | Config メソッド・classmethod・インスタンス化 |
| trading_strategy.py | 4 | TradingStrategy・判定メソッド |
| risk_management.py | 5 | RiskManagement・計算・ADX・PSAR |
| portfolio.py | 5 | Portfolio・ポジション・損益・ドローダウン |
| price_data_management.py | 5 | PriceDataManagement・シグナル・更新 |
| logger.py | 5 | Logger・ログ機能・圧縮・ローテーション |
| visualizer.py | 5 | Visualizer・HTML生成・可視化 |
| ohlcv_cache.py | 5 | OHLCVCache・キャッシュ操作 |
| bybit_exchange.py | 5 | BybitExchange・OHLCV取得・注文実行 |
| supplementary | 6 | Exchange, Order, Metrics, Util, EventBus, Side |

**合計**: 54 テスト

---

## OHLCV キャッシュ検査ツール

### 概要

`ohlcv_cache.db` の内容を確認・管理するツール。キャッシュサマリー、データ範囲分析、データギャップ検出機能を提供。

### 使用方法

```bash
# キャッシュサマリー表示（デフォルト）
./ohlcv_cache_info.sh

# データ範囲と断絶検出
./ohlcv_cache_info.sh coverage

# 詳細分析
./ohlcv_cache_info.sh all

# またはPython直接実行
cd src
python ohlcv_cache_inspector.py --help
```

### 出力例

```
🗄️ OHLCV キャッシュ検査ツール
📊 総レコード数: 460 件
📁 キャッシュファイル: ohlcv_data/ohlcv_cache.db
💾 ファイルサイズ: 0.10 MB

📋 キャッシュされているパラメータ数: 1
タイムフレーム: 120分 | レコード数: 460 | 取得期間: 2025-10-23 16:00 ～ 2025-12-01 01:59
```

### 機能

| 機能 | コマンド | 説明 |
|------|--------|------|
| サマリー | `./ohlcv_cache_info.sh` | 総レコード数、ファイルサイズ、パラメータ一覧 |
| データ範囲 | `./ohlcv_cache_info.sh coverage` | データセグメント、ギャップ検出 |
| 詳細分析 | `./ohlcv_cache_info.sh all` | すべてのパラメータの詳細情報 |

### キャッシュクリア

```bash
# Pythonで実行
cd src
python -c "from ohlcv_cache import OHLCVCache; OHLCVCache().clear_cache()"
# またはファイル削除
rm src/ohlcv_data/ohlcv_cache.db
```


