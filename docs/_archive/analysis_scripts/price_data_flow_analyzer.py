"""
価格データフロー分析ツール

バックテスト時とホットテスト時の価格データ取得・処理フローを分析し、
JSON 形式で出力して、今後の設計参考資料として保存します。

分析対象:
- price_data_management.py の OHLCV データ管理フロー
- bybit_exchange.py の API 呼び出しパターン
- ohlcv_cache.py のキャッシュ戦略
- trading_strategy.py でのデータ利用パターン
"""

import os
import sys
import json
from datetime import datetime
import inspect

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
ANALYSIS_DIR = os.path.join(WORKSPACE_ROOT, "docs/analysis")

sys.path.insert(0, SRC_DIR)


class PriceDataFlowAnalyzer:
    """価格データフロー分析クラス"""
    
    def __init__(self):
        self.analysis = {
            "metadata": {
                "title": "価格データフロー分析",
                "description": "バックテスト時とホットテスト時の価格データ取得・処理フロー",
                "analyzed_at": datetime.now().isoformat(),
                "workspace_root": WORKSPACE_ROOT
            },
            "backtest_mode": self._analyze_backtest_flow(),
            "hot_test_mode": self._analyze_hot_test_flow(),
            "key_components": self._identify_key_components(),
            "data_flow_diagram": self._create_data_flow_diagram(),
            "design_considerations": self._extract_design_considerations()
        }
    
    def _analyze_backtest_flow(self):
        """バックテスト時のデータフロー分析"""
        return {
            "mode": "Backtest (back_test = 1)",
            "description": "過去データを使用したシミュレーション実行",
            "flow_steps": [
                {
                    "step": 1,
                    "component": "backtest.py",
                    "operation": "バックテスト開始",
                    "description": "config.ini から期間設定を読み込み",
                    "data_source": "config.ini ([Backtest] セクション)",
                    "input": {
                        "start_time": "開始時刻 (epoch)",
                        "end_time": "終了時刻 (epoch)",
                        "period": "分析期間 (日数)"
                    }
                },
                {
                    "step": 2,
                    "component": "ohlcv_cache.py",
                    "operation": "キャッシュからデータ取得",
                    "description": "SQLite キャッシュDB から該当期間の OHLCV データを一括取得",
                    "data_source": "ohlcv_cache.db",
                    "input": {
                        "time_frame": "タイムフレーム (分単位)",
                        "symbol": "取引ペア (BTC/USD など)",
                        "start_epoch": "開始時刻",
                        "end_epoch": "終了時刻"
                    },
                    "output": {
                        "ohlcv_data": "OHLCV レコードリスト",
                        "record_count": "データポイント数"
                    }
                },
                {
                    "step": 3,
                    "component": "price_data_management.py",
                    "operation": "バックテスト用データセット構築",
                    "description": "取得した OHLCV データをメモリ上に展開",
                    "data_structure": "back_test_ohlcv_data[]: 複数タイムフレーム対応",
                    "attributes": [
                        "time_frame: タイムフレーム",
                        "data: OHLCV レコード配列",
                        "prev_index: 前回処理時のインデックス"
                    ]
                },
                {
                    "step": 4,
                    "component": "backtest.py",
                    "operation": "時系列ループ処理",
                    "description": "各タイムフレームの終値時刻ごとに bot.py の main_process() を呼び出し",
                    "loop_variable": "progress_time (次に処理する終値時刻)",
                    "per_iteration": {
                        "operation": "update_price_data() 呼び出し",
                        "data_retrieval": "back_test_ohlcv_data から該当時刻のレコードを取得",
                        "processing": "trading_strategy.py で売買判定を実行"
                    }
                },
                {
                    "step": 5,
                    "component": "price_data_management.py",
                    "operation": "更新処理（バックテストモード専用）",
                    "method": "update_price_data() - バックテスト分岐",
                    "operations": [
                        "progress_time に基づき back_test_ohlcv_data から OHLCV データを取得",
                        "price_data_management.ohlcv_data を更新（最新値）",
                        "ticker（現在価格）を更新",
                        "ボラティリティを計算",
                        "トレードシグナル（Donchian, PVO）を算出"
                    ]
                },
                {
                    "step": 6,
                    "component": "trading_strategy.py",
                    "operation": "売買判定ロジック実行",
                    "description": "現在の OHLCV 状態に基づいて ENTRY/ADD/EXIT を判定",
                    "uses": [
                        "price_data_management.ohlcv_data (現在値)",
                        "price_data_management.signals (シグナル)",
                        "price_data_management.volatility (ボラティリティ)"
                    ]
                },
                {
                    "step": 7,
                    "component": "bot.py",
                    "operation": "約定シミュレーション",
                    "description": "売買シグナルに基づいてポジション更新、損益計算",
                    "output": [
                        "ポジション情報",
                        "実現損益",
                        "含み益損"
                    ]
                },
                {
                    "step": 8,
                    "component": "visualizer.py",
                    "operation": "バックテスト結果の可視化",
                    "description": "すべての売買履歴と損益推移をグラフ化",
                    "output_files": [
                        "backtest_visualization.html",
                        "latest_backtest.log"
                    ]
                }
            ],
            "data_flow_characteristics": {
                "source": "SQLite キャッシュ（過去データ）",
                "timing": "バッチ処理（全データを一括読み込み）",
                "latency": "なし（シミュレーション）",
                "update_frequency": "ループイテレーション単位",
                "volume": "数百〜数千レコード"
            },
            "cache_usage": {
                "purpose": "過去データの高速読み込み",
                "strategy": "SQLite から該当期間を一括取得",
                "optimization": "インデックスによる範囲検索の高速化"
            }
        }
    
    def _analyze_hot_test_flow(self):
        """ホットテスト（ライブ/ダミー取引）時のデータフロー分析"""
        return {
            "mode": "Hot Test (back_test = 0)",
            "description": "リアルタイムデータを使用した実運用",
            "flow_steps": [
                {
                    "step": 1,
                    "component": "bot.py",
                    "operation": "継続的なリアルタイム処理ループ",
                    "description": "無限ループで bot_operation_cycle (秒) ごとに main_process() を実行",
                    "cycle_time": "config.ini [Backtest] セクション: bot_operation_cycle",
                    "default": "60 秒"
                },
                {
                    "step": 2,
                    "component": "bybit_exchange.py",
                    "operation": "リアルタイム API 呼び出し",
                    "method": "fetch_ticker(symbol, interval)",
                    "description": "Bybit REST API から現在の OHLCV データを取得",
                    "api_endpoint": "GET /v5/market/kline",
                    "parameters": {
                        "symbol": "取引ペア (BTCUSD など)",
                        "interval": "タイムフレーム (120 = 120分足)",
                        "limit": "取得件数（通常 200 件）"
                    },
                    "response": {
                        "structure": "[[timestamp, open, high, low, close, volume], ...]",
                        "count": "最大 200 レコード（直近から遡って）"
                    }
                },
                {
                    "step": 3,
                    "component": "ohlcv_cache.py",
                    "operation": "キャッシュへの新規データ登録",
                    "method": "insert_or_update()",
                    "description": "API から取得した新規 OHLCV レコードを SQLite に保存",
                    "database": "ohlcv_cache.db",
                    "operation_mode": "INSERT OR REPLACE（新規 or 更新）",
                    "frequency": "毎サイクル（毎回の API 呼び出し後）"
                },
                {
                    "step": 4,
                    "component": "price_data_management.py",
                    "operation": "メモリ上の OHLCV データ更新",
                    "method": "update_price_data() - ホットテスト分岐",
                    "description": "API から取得した新規データでメモリ上の ohlcv_data を更新",
                    "operations": [
                        "API レスポンスの OHLCV データを解析",
                        "ohlcv_data[0].data（主軸フレーム）を更新",
                        "ohlcv_data[1].data（PSAR フレーム）を更新",
                        "latest_ohlcv_data（未確定値）を分離"
                    ]
                },
                {
                    "step": 5,
                    "component": "price_data_management.py",
                    "operation": "時系列データの整理",
                    "description": "複数タイムフレームのデータを同期",
                    "is_update_ohlcv_2": {
                        "purpose": "120分足と他のタイムフレーム間のデータ整合性保証",
                        "trigger": "120分足の新規確定値が出現した時",
                        "operation": "他のフレームのメモリ上のデータセットを 120分足に合わせて再構築"
                    }
                },
                {
                    "step": 6,
                    "component": "price_data_management.py",
                    "operation": "指標計算",
                    "description": "最新の OHLCV データに基づいて trading_strategy で使用する指標を計算",
                    "indicators": [
                        {
                            "name": "Donchian Channel",
                            "purpose": "サポート/レジスタンスの特定",
                            "calculation": "過去 N 期間の高値/安値"
                        },
                        {
                            "name": "PVO (Percentage Volume Oscillator)",
                            "purpose": "出来高トレンドの把握",
                            "calculation": "EMA(短期) - EMA(長期) / EMA(長期)"
                        }
                    ],
                    "update_timing": "毎サイクル"
                },
                {
                    "step": 7,
                    "component": "trading_strategy.py",
                    "operation": "売買判定ロジック実行",
                    "description": "現在の OHLCV と指標に基づいて ENTRY/ADD/EXIT を判定",
                    "decision_methods": [
                        "evaluate_entry(): エントリー条件判定",
                        "evaluate_add(): ピラミッディング判定",
                        "evaluate_exit(): エグジット条件判定"
                    ]
                },
                {
                    "step": 8,
                    "component": "bot.py / portfolio.py",
                    "operation": "売買シグナルの実行",
                    "description": "売買判定結果に基づいてポジションを更新",
                    "execution_mode": "hot_test_dummy_mode に応じて",
                    "modes": {
                        "dummy_mode_on": "ダミー取引（実際の注文は発行しない、ポジション情報のみ更新）",
                        "dummy_mode_off": "実際の API 呼び出しで注文発行（実運用モード）"
                    }
                },
                {
                    "step": 9,
                    "component": "logger.py",
                    "operation": "リアルタイムログ出力",
                    "description": "每サイクルの トレード状態をログファイルに記録",
                    "log_file": "log.txt",
                    "log_content": [
                        "時刻: 処理実行時刻",
                        "価格: 最新 ticker",
                        "シグナル: Donchian, PVO",
                        "ポジション状態: ENTRY/EXIT 状態",
                        "含み益損: 現在値ベースの損益"
                    ],
                    "update_frequency": "毎サイクル（60秒ごと）"
                }
            ],
            "data_flow_characteristics": {
                "source": "Bybit REST API（リアルタイムデータ）",
                "timing": "イベント駆動（毎サイクル定期実行）",
                "latency": "API 呼び出し遅延 + ネットワーク遅延（100-500ms 程度）",
                "update_frequency": "bot_operation_cycle ごと（デフォルト 60 秒）",
                "volume": "毎サイクル 200 件の最新レコード"
            },
            "cache_usage": {
                "purpose": "過去データの蓄積と履歴参照",
                "strategy": "毎サイクルの新規データを INSERT OR REPLACE で保存",
                "benefit": [
                    "ホットテスト中断・再開時の状態復帰",
                    "事後分析用の完全なデータログ",
                    "指標計算に必要な過去データの確保"
                ]
            }
        }
    
    def _identify_key_components(self):
        """主要なコンポーネントと責務の整理"""
        return [
            {
                "component": "price_data_management.py",
                "class": "PriceDataManagement",
                "responsibility": "価格データの一元管理と条件分岐",
                "critical_methods": [
                    {
                        "name": "update_price_data()",
                        "purpose": "最新の OHLCV データをメモリに同期",
                        "backtest_behavior": "back_test_ohlcv_data から該当時刻のレコード取得",
                        "hot_test_behavior": "Bybit API から取得したデータを処理"
                    },
                    {
                        "name": "get_ohlcv_data()",
                        "purpose": "確定済の OHLCV データを返却",
                        "usage": "trading_strategy での指標計算に使用"
                    }
                ]
            },
            {
                "component": "bybit_exchange.py",
                "class": "BybitExchange",
                "responsibility": "Bybit API との通信",
                "critical_methods": [
                    {
                        "name": "fetch_ticker()",
                        "purpose": "最新の OHLCV データを API から取得",
                        "used_in": "ホットテスト（hot_test = 0）のみ"
                    }
                ]
            },
            {
                "component": "ohlcv_cache.py",
                "class": "OHLCVCache",
                "responsibility": "SQLite キャッシュの管理",
                "critical_methods": [
                    {
                        "name": "query_range()",
                        "purpose": "指定期間の OHLCV データを取得",
                        "used_in": "バックテスト初期化時（back_test = 1）"
                    },
                    {
                        "name": "insert_or_update()",
                        "purpose": "新規データの保存・更新",
                        "used_in": "ホットテスト（毎サイクル）"
                    }
                ]
            },
            {
                "component": "trading_strategy.py",
                "class": "TradingStrategy",
                "responsibility": "売買判定ロジック",
                "critical_methods": [
                    {
                        "name": "evaluate_entry()",
                        "purpose": "エントリー条件判定",
                        "dependencies": [
                            "price_data_management.ohlcv_data",
                            "price_data_management.signals"
                        ]
                    }
                ]
            }
        ]
    
    def _create_data_flow_diagram(self):
        """データフローの図式化（テキスト表現）"""
        return {
            "backtest_flow": """
┌────────────────────────────────────────────────────────────────────────┐
│                         BACKTEST MODE FLOW                             │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  config.ini                                                            │
│  ┌─ [Backtest] section:                                               │
│  │  start_time, end_time, period                                     │
│  │                                                                    │
│  └──> backtest.py ──────────────────┐                                │
│                                      │                               │
│                              ohlcv_cache.db (SQLite)                  │
│                              ┌─ query_range()                        │
│                              │  returns: list of OHLCV               │
│                              │                                       │
│                     price_data_management                            │
│                     ┌─ back_test_ohlcv_data                          │
│                     │  [{"time_frame": 120, "data": [...]}, ...]    │
│                     │                                               │
│                     └──> for each progress_time:                    │
│                          │                                          │
│                          ├─> update_price_data()                   │
│                          │   ├─ Extract OHLCV at progress_time     │
│                          │   ├─ Update ohlcv_data (in-memory)      │
│                          │   └─ Calculate signals (Donchian, PVO)  │
│                          │                                         │
│                          ├─> trading_strategy.make_trade_decision()│
│                          │   ├─ evaluate_entry()                   │
│                          │   ├─ evaluate_add()                    │
│                          │   └─ evaluate_exit()                   │
│                          │                                         │
│                          └─> bot.main_process()                    │
│                              └─ Update portfolio & P&L             │
│                                                                    │
│  visualizer.py                                                       │
│  └─ Generate: backtest_visualization.html                           │
│                                                                    │
└────────────────────────────────────────────────────────────────────────┘
            """,
            "hot_test_flow": """
┌────────────────────────────────────────────────────────────────────────┐
│                      HOT TEST MODE FLOW                                │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  bot.py (Infinite loop)                                               │
│  ┌─ every bot_operation_cycle seconds (default: 60s)                 │
│  │                                                                    │
│  └──> bybit_exchange.fetch_ticker()                                  │
│       ┌─ REST API: GET /v5/market/kline                              │
│       │ Parameters: symbol, interval, limit=200                      │
│       └─ Response: [[timestamp, O, H, L, C, V], ...]                │
│                                                                      │
│       ohlcv_cache.py                                                  │
│       ┌─ insert_or_update()                                          │
│       │  Save new OHLCV records to SQLite                            │
│       └─ Persist to ohlcv_cache.db                                   │
│                                                                      │
│       price_data_management                                          │
│       ┌─ update_price_data()                                         │
│       │  ├─ Parse API response                                      │
│       │  ├─ Update ohlcv_data (in-memory)                           │
│       │  ├─ Separate latest_ohlcv_data (unconfirmed)                │
│       │  ├─ Check is_update_ohlcv_2                                 │
│       │  │  (Sync multi-timeframe if main TF changed)               │
│       │  └─ Calculate signals (Donchian, PVO)                       │
│       │                                                             │
│       trading_strategy.make_trade_decision()                         │
│       ├─ evaluate_entry()                                           │
│       ├─ evaluate_add()                                             │
│       └─ evaluate_exit()                                            │
│                                                                      │
│       bot.main_process()                                             │
│       ├─ if signal == ENTRY: create order                           │
│       ├─ if signal == ADD: increase position                        │
│       ├─ if signal == EXIT: close position                          │
│       │                                                             │
│       │  Execution Mode:                                            │
│       │  ├─ hot_test_dummy_mode = 1: Dummy (no real order)          │
│       │  └─ hot_test_dummy_mode = 0: Live (real order)              │
│       │                                                             │
│       └─ portfolio.py: Update position & P&L                        │
│                                                                      │
│       logger.py                                                       │
│       └─ Write to log.txt:                                           │
│          - timestamp, price, signals, position, P&L                  │
│                                                                      │
│  Sleep until next cycle                                              │
│                                                                      │
└────────────────────────────────────────────────────────────────────────┘
            """
        }
    
    def _extract_design_considerations(self):
        """今後の設計参考事項の抽出"""
        return {
            "critical_data_sync_points": [
                {
                    "name": "is_update_ohlcv_2",
                    "importance": "CRITICAL",
                    "description": "複数タイムフレーム間でのデータ整合性保証",
                    "issue": "120分足が新規確定した際、他タイムフレームのデータセットも同期する必要がある",
                    "implementation": "price_data_management.update_price_data() 内で条件判定",
                    "design_note": "削除すると backtest 結果が大きく変わる（重大な依存性あり）"
                },
                {
                    "name": "ohlcv_data vs latest_ohlcv_data",
                    "importance": "HIGH",
                    "description": "確定値と未確定値の分離",
                    "ohlcv_data": "確定済のローソク足（指標計算と trading_strategy に使用）",
                    "latest_ohlcv_data": "未確定の最新値（リアルタイム表示用）",
                    "design_note": "混在させるとシグナルの信頼性が低下"
                }
            ],
            "performance_optimization_opportunities": [
                {
                    "area": "API call frequency",
                    "current": "毎サイクル 1 回（60 秒ごと）",
                    "optimization": "ボラティリティ / サイクル延長検討可能だが、シグナル遅延の代償あり"
                },
                {
                    "area": "SQLite cache lookup",
                    "current": "毎サイクル INSERT OR REPLACE（200 レコード）",
                    "optimization": "バッファリング / バッチ挿入で DB I/O を削減可能"
                },
                {
                    "area": "Indicator recalculation",
                    "current": "毎サイクル全指標を再計算",
                    "optimization": "変化があった OHLCV のみ更新（キャッシュ計算）"
                }
            ],
            "backtest_vs_hot_test_differences": [
                {
                    "aspect": "Data Source",
                    "backtest": "SQLite（完全性保証）",
                    "hot_test": "Bybit API（リアルタイム性）",
                    "design_implication": "SQLite フォールバック機構の検討"
                },
                {
                    "aspect": "Data Availability",
                    "backtest": "全期間のデータ（初期段階で一括読み込み）",
                    "hot_test": "リアルタイムデータのみ（API limit: 200 件）",
                    "design_implication": "indicator_lookback_period は API limit 内に収まるよう設計"
                },
                {
                    "aspect": "Execution Latency",
                    "backtest": "なし（シミュレーション）",
                    "hot_test": "API 遅延 + ネットワーク遅延（100-500ms）",
                    "design_implication": "API timeout 処理とリトライロジックの重要性"
                },
                {
                    "aspect": "State Persistence",
                    "backtest": "不要（全期間一度に処理）",
                    "hot_test": "重要（中断・再開対応）",
                    "design_implication": "ポジション情報・キャッシュの永続化戦略"
                }
            ],
            "future_enhancements": [
                {
                    "feature": "Multi-symbol support",
                    "current_limitation": "単一ペア（BTC/USD）のみ",
                    "data_flow_impact": "PriceDataManagement と OHLCVCache を複数インスタンス化必要"
                },
                {
                    "feature": "Real-time alert system",
                    "current_limitation": "ログ出力のみ",
                    "data_flow_impact": "Signal pipeline に webhook / Slack 連携"
                },
                {
                    "feature": "Adaptive timeframe selection",
                    "current_limitation": "固定タイムフレーム（120分）",
                    "data_flow_impact": "市場変動に応じたフレーム切り替え（動的 is_update_ohlcv_2）"
                }
            ]
        }
    
    def save_analysis(self):
        """分析結果を JSON ファイルに保存"""
        output_file = os.path.join(ANALYSIS_DIR, "price_data_flow_analysis.json")
        
        os.makedirs(ANALYSIS_DIR, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.analysis, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 価格データフロー分析を保存しました: {output_file}")
        return output_file
    
    def generate_markdown_report(self):
        """マークダウン形式のレポートを生成"""
        report_file = os.path.join(WORKSPACE_ROOT, "docs/PRICE_DATA_FLOW_DESIGN.md")
        
        report = r"""# 価格データフロー分析レポート

## 概要
本レポートは、satosystem のバックテスト時とホットテスト時における価格データの取得・処理フローを分析し、
今後の設計改善の参考資料として作成されました。

## バックテストモード（back_test = 1）の流れ

### データソース
- **SQLite キャッシュ**: `ohlcv_cache.db`
- **特徴**: 過去データの完全性が保証される

### 処理フロー
1. **初期化フェーズ**
   - `config.ini` から期間設定（start_time, end_time）を読み込み
   - `ohlcv_cache.py` が該当期間の OHLCV データを一括取得
   - `price_data_management.back_test_ohlcv_data` にデータを展開

2. **ループフェーズ**
   - 各タイムフレームの終値時刻ごとに `bot.main_process()` を呼び出し
   - `progress_time` を進めながら時系列処理

3. **各イテレーション**
   - `update_price_data()` で該当時刻の OHLCV レコードを取得
   - `trading_strategy` で売買判定を実行
   - `portfolio` でポジション更新と損益計算

### 重要な設計要素

#### is_update_ohlcv_2
- **目的**: 複数タイムフレーム間での整合性保証
- **トリガー**: 主軸タイムフレーム（120分）が新規確定した時
- **処理**: 他のタイムフレームのメモリ上データセットを再構築
- **重要度**: **CRITICAL** - 削除すると結果が大きく変わる

#### ohlcv_data 管理
```python
ohlcv_data = [
    {"time_frame": 120, "data": [...]},      # 主軸フレーム
    {"time_frame": psar_frame, "data": [...]} # PSAR 用フレーム
]
```

---

## ホットテストモード（back_test = 0）の流れ

### データソース
- **Bybit REST API**: `/v5/market/kline`
- **特徴**: リアルタイムデータ（最大 200 件までの履歴）

### 処理フロー
1. **無限ループ**
   - `bot_operation_cycle`（デフォルト 60 秒）ごとに実行

2. **API 呼び出し**
   - `bybit_exchange.fetch_ticker()` で最新 OHLCV を取得
   - レスポンス: `[[timestamp, O, H, L, C, V], ...]`

3. **キャッシュ保存**
   - `ohlcv_cache.insert_or_update()` で SQLite に保存
   - 履歴参照と状態復帰を支援

4. **メモリ同期**
   - `update_price_data()` で メモリ上の `ohlcv_data` を更新
   - 指標計算（Donchian, PVO）を実行

5. **売買判定と実行**
   - `trading_strategy.make_trade_decision()` で判定
   - `hot_test_dummy_mode` に応じて：
     - ダミーモード: ポジション情報のみ更新
     - 実運用モード: 実際に API 注文発行

6. **リアルタイムログ**
   - 毎サイクル `log.txt` に状態を記録

### 重要な設計要素

#### latest_ohlcv_data の分離
- **確定値**: `ohlcv_data` - 指標計算・売買判定に使用
- **未確定値**: `latest_ohlcv_data` - リアルタイム表示用
- **理由**: シグナルの信頼性保証

#### multi-timeframe 同期
- `is_update_ohlcv_2` フラグで主軸フレーム変化を検出
- 他フレームのデータセットを同期
- API から取得可能な履歴（200 件）内で動作

---

## バックテスト vs ホットテスト比較

| 項目 | バックテスト | ホットテスト |
|------|-----------|----------|
| **データソース** | SQLite キャッシュ | Bybit API |
| **データ完全性** | ✅ 完全 | ⚠️ 最大 200 件 |
| **処理タイミング** | バッチ（全期間一括） | イベント駆動（毎 60 秒） |
| **実行レイテンシ** | なし（シミュレーション） | API 遅延 + ネットワーク |
| **状態保存** | 不要 | 必須（中断・再開対応） |
| **出力** | 結果ファイル + グラフ | リアルタイムログ + ポジション |

---

## 設計上の考慮事項

### 1. is_update_ohlcv_2 の重要性
このフラグは削除不可の **重大な依存性** があります。複数タイムフレーム間の整合性を保証していない場合、
バックテスト結果が数百倍のズレを生じる可能性があります。

### 2. API データ量の制限
Bybit API は最大 200 件のローソク足しか返却しないため、indicator_lookback_period を
この制限内に収める必要があります。

### 3. キャッシュ戦略の二重性
- **バックテスト**: 履歴参照（高速な期間検索）
- **ホットテスト**: 新規データの蓄積（毎サイクルの INSERT OR REPLACE）

### 4. 入出力の明確化
```
バックテスト: config.ini → SQLite → 結果ファイル
ホットテスト: Bybit API → SQLite → ログ + ポジション（リアルタイム）
```

---

## 今後の拡張性

### 検討可能な改善
1. **複数シンボル対応**: PriceDataManagement のマルチインスタンス化
2. **リアルタイムアラート**: Signal pipeline への webhook 統合
3. **適応的タイムフレーム**: 市場変動に応じた動的フレーム切り替え
4. **API リトライロジック**: ネットワーク障害への耐性向上

---

## 参考ファイル
- `docs/analysis/price_data_flow_analysis.json` - 詳細な JSON 形式の分析

**生成日**: {generated_at}
"""
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report.format(generated_at=datetime.now().isoformat()))
        
        print(f"✅ マークダウンレポートを生成しました: {report_file}")
        return report_file


def main():
    """メイン処理"""
    print("=" * 70)
    print("🔍 価格データフロー分析")
    print("=" * 70)
    print()
    
    analyzer = PriceDataFlowAnalyzer()
    json_file = analyzer.save_analysis()
    md_file = analyzer.generate_markdown_report()
    
    print()
    print("=" * 70)
    print("✅ 分析完了")
    print("=" * 70)
    print()
    print("📄 生成されたファイル:")
    print(f"  1. JSON 形式: {json_file}")
    print(f"  2. マークダウン: {md_file}")
    print()
    print("次回以降、設計変更時にこれらを参照してください。")


if __name__ == "__main__":
    main()
