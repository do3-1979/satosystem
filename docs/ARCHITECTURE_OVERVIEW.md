## 主要クラス・メソッド一覧（src/ 配下）

| クラス名              | ファイル                | 主な役割・概要                                 | 主なメソッド例                                      |
|----------------------|------------------------|-----------------------------------------------|----------------------------------------------------|
| Bot                  | src/bot.py             | メインループ・注文・損益管理                   | __init__, show_trade_data, main_loop, execute_trade|
| TradingStrategy      | src/trading_strategy.py| ENTRY/ADD/EXIT判定・戦略ロジック               | __init__, initialize_trade_decision, evaluate_entry, evaluate_exit |
| RiskManagement       | src/risk_management.py | ポジションサイズ計算・ストップ管理             | __init__, get_entry_range, get_stop_price, update_risk_status |
| Portfolio            | src/portfolio.py        | 保有ポジション・損益・ドローダウン管理         | __init__, get_position_quantity, get_profit_and_loss, add_position_quantity |
| Visualizer           | src/visualizer.py       | ログからグラフ/Excel生成                       | plot_trade_log, export_to_excel                    |
| Order                | src/order.py            | 注文DTO・注文情報管理                          | __init__, to_dict, __str__                         |
| Logger               | src/logger.py           | 構造化ログ・圧縮・ローテーション               | __new__, log, log_error, compress_logs              |
| Config               | src/config.py           | 設定値の集中管理・キャッシュ                   | __init__, to_dict, get_market, get_bot_operation_cycle |
| BybitExchange        | src/bybit_exchange.py   | Bybit用取引所ラッパー                           | __init__, fetch_ohlcv, place_order                 |
| PriceDataManagement  | src/price_data_management.py | OHLCV取得・シグナル生成・仮想時刻進行      | __init__, get_signals, update_price_data_backtest   |
| Util                 | src/util.py             | ログ抽出・Excel/グラフ生成・分析補助            | extract_and_export_logs, generate_line_chart, extract_parameters_and_results |
| Metrics              | src/metrics.py          | バックテスト指標計算                            | compute_metrics, _max_drawdown, _sharpe             |
| EventBus             | src/event.py            | イベント通知・購読管理                          | __init__, publish, subscribe                        |
| Exchange             | src/exchange.py         | 取引所基底クラス                                | __init__, get_account_balance, execute_order        |
| Side                 | src/side.py             | 売買サイドEnum・変換                            | normalize_side, to_exchange_side                   |
| Satostrategy         | src/satostrategy.py     | 独自戦略クラス（TradingStrategy拡張）           | __init__                                           |
| ConfigGenerator      | src/config_generator.py | 設定ファイル自動生成                            | generate_configs                                   |
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
| Util | Log extraction & visualization (Excel, charts) | Logger outputs |
| Metrics | Post-backtest performance metrics (Sharpe, MaxDD, PF, WinRate) | Bot (backtest summary) |

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

## 次のステップ
- `nextarch`（および master）にある `8e6e543` 以降のコミットを一覧化し、移植対象となる変更点ごとに検討を進める。
- レグレッションテストの整備と自動化を進め、変更取り込み前に `report_tmp/` にテスト結果を保存して参照可能とする。
