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
| Satostrategy         | src/satostrategy.py     | 独自戦略クラス（TradingStrategy拡張）           | __init__                                           |
| OHLCVCache           | src/ohlcv_cache.py      | OHLCV SQLiteキャッシュ管理                      | __init__, get_ohlcv_data, save_ohlcv_data, get_ohlcv_data_partial, migrate_from_json |
| OHLCVCacheInspector  | src/ohlcv_cache_inspector.py | キャッシュ分析・検査ツール            | __init__, get_cache_parameters, get_data_coverage, print_summary, print_detailed_analysis |
# Architecture Overview

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

## Future Separation
1. `IndicatorService` for PSAR, ADX, Donchian, PVO
2. `DataSource` abstraction (LiveDataSource / BacktestDataSource)
3. `RiskEngine` separate from sizing heuristics

---
This document complements `Readme.md` and analysis files; update incrementally.

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
