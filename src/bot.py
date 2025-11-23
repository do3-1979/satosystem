"""
Bot クラス:

メインのボットクラスです。Exchange、TradingStrategy、Portfolio、RiskManagement などのクラスを組み合わせて、トレードの実行と監視を行います。
メインループを持ち、定期的に取引を実行し、ポートフォリオの状態を更新します。

このサンプルコードでは、Bot クラスが取引所と取引戦略との連携を行っています。
Bot クラスは定期的に口座残高を取得し、取引戦略に渡してトレード判断を取得します。
トレード判断に基づいて注文を実行し、一定の待ち時間を設けてループを繰り返します。

また、取引戦略については YourStrategy() の部分にあなたの取引戦略クラスを指定してください。
取引戦略クラスは、口座残高や市場データを分析し、トレード判断を返すロジックを実装する必要があります。

ファイル概要:
このファイルは、取引ボットのメインクラスである `Bot` を実装しています。以下の機能を提供します:
- 取引所との連携
- 取引戦略の実行
- リスク管理の適用
- ポートフォリオの更新と管理
- トレードデータのログ記録
- バックテストモードとリアルタイムモードのサポート
"""
import os
import time
from time import perf_counter
from datetime import datetime
from logger import Logger
from config import Config
from price_data_management import PriceDataManagement
from bybit_exchange import BybitExchange
from trading_strategy import TradingStrategy
from risk_management import RiskManagement
from portfolio import Portfolio
from order import Order
from event import EventBus, EventType
from metrics import compute_metrics
from indicator_service import IndicatorService
from pnl_reporter import generate_pnl_timeseries
from report_generator import generate_markdown_report
from visualizer import Visualizer
from util import Util

# 再発防止: ラッパ非経由実行検出 (bot_run.sh が BOT_WRAPPER_INVOKED を設定)
if os.getenv("BOT_WRAPPER_INVOKED") != "1":
    # 直接呼び出し時は警告 (バックテスト/本番共通)
    print("[WARN] bot.py を直接実行しています。標準の前後処理(APIキー復元/ログ掃除/サマリ表示)を保証するため ./bot_run.sh run の使用を推奨します。環境変数 BOT_WRAPPER_INVOKED=1 で抑制可能。")

class PerformanceTracker:
    def __init__(self):
        self.totals = {}
        self.iterations = 0

    def record(self, name, start, end):
        duration = end - start
        if name not in self.totals:
            self.totals[name] = 0.0
        self.totals[name] += duration

    def summary(self):
        grand_total = sum(self.totals.values()) if self.totals else 0.0
        result = {
            'iterations': self.iterations,
            'grand_total_sec': grand_total,
            'phases': []
        }
        for k, v in sorted(self.totals.items(), key=lambda x: -x[1]):
            avg = v / self.iterations if self.iterations else 0.0
            pct = (v / grand_total * 100) if grand_total else 0.0
            result['phases'].append({
                'name': k,
                'total_sec': v,
                'avg_per_iteration_sec': avg,
                'percent': pct
            })
        return result

class Bot:
    def __init__(self, exchange, strategy, risk_management, price_data_management, portfolio):
        """
        Bot クラスの初期化

        Args:
            exchange (Exchange): 取引所クラスのインスタンス
            strategy (TradingStrategy): 取引戦略クラスのインスタンス
        """
        self.exchange = exchange
        self.strategy = strategy
        self.risk_management = risk_management
        self.price_data_management = price_data_management
        self.portfolio = portfolio
        self.logger = Logger()
        # 軽量イベントバス（外部への副作用なし）
        self.events = EventBus()

        self.market_type = Config.get_market()
        self.bot_operation_cycle = Config.get_bot_operation_cycle()
        # バックテスト用損益履歴
        self.pnl_history = []
        self.close_times = []  # close_time 履歴
        # 約定履歴カウント (勝率計算用)
        self.trade_results = []  # list of bool win( True ) / loss( False )
        # トレード指標管理
        self.open_trade = None  # dict: {entry_price, side, atr, mfe, mae, bars}
        self.closed_trades = []  # list of dict with metrics
        # パフォーマンス計測用トラッカー
        self.perf = PerformanceTracker()
        # ログ出力制御用カウンタ
        self._log_counter = 0
        self._logging_interval = Config.get_logging_interval()
        # 重複ログ抑制用: 前回のエラーメッセージ
        self._last_error_message = None

    def show_trade_data(self, trade_data):
        self.logger.log(f"時刻: {trade_data['real_time']}"
            f"  高値: {trade_data['high_price']:>5.0f}"
            f"  安値: {trade_data['low_price']:>5.0f}"
            f"  終値: {trade_data['close_price']:>5.0f}"
            f"  購入価格: {trade_data['positions']['position_price']:>5.0f}"
            f"  STOP: {trade_data['stop_price']:>5.0f}"
            f"  ボラ: {trade_data['volatility']:>7.2f}"
            f"  出来高: {trade_data['Volume']:>7.2f}"
            f"  SIGNAL: {trade_data['decision']}"
            f" -> {trade_data['side']}"
            f"  購入量: {trade_data['position_size']:.4f}"
            f"  資産: {trade_data['positions']['quantity']:.4f}"
            f"  ポジ: {trade_data['positions']['side']}"
            f"  みなし損益: {trade_data['profit_and_loss']:>4.0f}"
            f"  累計損益: {trade_data['total_profit_and_loss']:>4.0f}"
            #f"  PSAR: {trade_data['psar']:>5.0f}"
            #f"  総量: {trade_data['total_size']}"
            #f"  DCH: {trade_data['dc_h']}"
            #f"  DCL: {trade_data['dc_l']}"
            #f"  PVO: {trade_data['pvo_val']}"
            #f"  出来高: {trade_data['stop_offset']}"
            #f"  出来高: {trade_data['stop_psar_stop_offset']}"
            #f"  出来高: {trade_data['stop_price_surge_stop_offset']}"
        )
        return

    def run(self):
        """
        ボットのメインループを実行します。口座残高を取得し、取引戦略に基づいてトレードを実行します。
        """
        config_instance = Config()
        back_test_mode = config_instance.get_back_test_mode()
        
        if back_test_mode == 1:
            self.logger.log("--- BOT START (BACK TEST MODE)-------------------------")
            self.price_data_management.initialise_back_test_ohlcv_data()
        else:
            self.logger.log("--- BOT START -----------------------------------------")

        self.logger.log(str(config_instance))
        self.logger.log("-------------------------------------------------------")

        run_start = perf_counter()
        run_timeout = Config.get_run_timeout_seconds()
        # バックテスト時は全体タイムアウトを適用しない（完走を優先）
        timeout_enabled = (run_timeout > 0) and (back_test_mode == 0)
        while True:
            try:
                log_zipped = False
                trade_executed = False
                # タイムアウト監視（全体）
                if timeout_enabled and (perf_counter() - run_start) >= run_timeout:
                    self.logger.log_error(f"実行タイムアウト到達: {run_timeout} 秒。処理を終了します。")
                    # タイムアウト時も可能ならメトリクスを出力
                    try:
                        import json, os, time as _t
                        metrics = compute_metrics(self.pnl_history, self.trade_results)
                        report_dir = Config.get_report_dir_name()
                        ts = _t.strftime('%Y%m%d%H%M%S')
                        os.makedirs(report_dir, exist_ok=True)
                        summary_path = os.path.join(report_dir, f"backtest_summary_{ts}.json")
                        with open(summary_path, 'w', encoding='utf-8') as f:
                            json.dump(metrics, f, ensure_ascii=False, indent=2)
                        perf_summary = self.perf.summary()
                        perf_path = os.path.join(report_dir, f"performance_summary_{ts}.json")
                        with open(perf_path, 'w', encoding='utf-8') as pf:
                            json.dump(perf_summary, pf, ensure_ascii=False, indent=2)
                        if self.pnl_history and self.close_times:
                            pnl_csv, pnl_json = generate_pnl_timeseries(self.pnl_history, self.close_times, report_dir, prefix="pnl_timeseries")
                            self.logger.log(f"PnL時系列出力 (CSV): {pnl_csv}")
                            self.logger.log(f"PnL時系列出力 (JSON): {pnl_json}")
                    except Exception as e:
                        self.logger.log_error(f"タイムアウト時の出力でエラー: {e}")
                    finally:
                        self.logger.close_log_file()
                        self.logger.log("--- BOT END (TIMEOUT) ----------------------------------")
                        break
                # --------------------------------------------
                # 最初に価格情報の更新
                # --------------------------------------------
                t_price_start = perf_counter()
                if back_test_mode == 1:
                    is_end = self.price_data_management.update_price_data_backtest()
                    t_price_end = perf_counter(); self.perf.record('price_update', t_price_start, t_price_end)
                    # イベント: ティック
                    self.events.emit(EventType.TICK, {
                        'time': self.price_data_management.get_latest_close_time(),
                        'price': self.price_data_management.get_ticker()
                    })
                    # TODO 結果の別ファイル出力とバックテストでの結果集計
                    # バックテスト終端だったら抜ける
                    if is_end == True:
                        # === 未決済ポジション強制決済処理 ===
                        # バックテスト終了時に未決済ポジションがあれば、現在値で決済
                        open_position = self.portfolio.get_position_quantity()
                        if open_position['quantity'] > 0 and open_position['side'] != 'NONE':
                            ohlcv = self.price_data_management.get_latest_ohlcv()
                            final_price = ohlcv['close_price'] if ohlcv else open_position['position_price']
                            self.logger.log(f"[EOB処理] 未決済ポジション検出: {open_position['quantity']:.4f} {open_position['side']} @ {open_position['position_price']:.0f}")
                            self.logger.log(f"[EOB処理] 最終足価格で強制決済: {final_price:.0f}")
                            self.portfolio.clear_position_quantity(final_price)
                            # 強制決済時にオープントレードが残っていれば分類記録
                            if self.open_trade:
                                pnl_total = self.portfolio.get_profit_and_loss()
                                entry_price = self.open_trade['entry_price']
                                side = self.open_trade['side']
                                mfe = self.open_trade['mfe']
                                mae = self.open_trade['mae']
                                bars = self.open_trade['bars']
                                atr_entry = self.open_trade['atr']
                                capture_ratio = (pnl_total / mfe) if mfe > 0 else 0.0
                                loss_containment_ratio = (abs(pnl_total) / mae) if (mae > 0 and pnl_total < 0) else 0.0
                                k2 = Config.get_classification_k2()
                                k3 = Config.get_classification_k3()
                                if mfe >= atr_entry * k2:
                                    classification = 'TREND'
                                elif mae >= atr_entry * k3 and mfe < atr_entry * k2:
                                    classification = 'FALSE_BREAK'
                                else:
                                    classification = 'NEUTRAL'
                                self.closed_trades.append({
                                    'entry_price': entry_price,
                                    'exit_price': final_price,
                                    'side': side,
                                    'realized_pnl': pnl_total,
                                    'mfe': mfe,
                                    'mae': mae,
                                    'bars_held': bars,
                                    'atr_at_entry': atr_entry,
                                    'capture_ratio': capture_ratio,
                                    'loss_containment_ratio': loss_containment_ratio,
                                    'classification': classification
                                })
                                self.open_trade = None
                            # EOB決済をPnL履歴へ追記
                            self.pnl_history.append(self.portfolio.get_profit_and_loss())
                            self.close_times.append(self.price_data_management.get_latest_close_time_dt())
                        
                        self.logger.log("-------------------------------------------------------")
                        self.logger.log(f"最終ポートフォリオ: {self.portfolio.get_position_quantity()}")
                        
                        # メトリクス計算 (統一的なドローダウン計算を使用)
                        metrics = compute_metrics(self.pnl_history, self.trade_results)
                        self.logger.log(f"最終損益: {metrics['total_pnl']:>4.0f} [BTC/USD]")
                        self.logger.log(f"プロフィットファクター: {metrics['profit_factor']:>4.2f}")
                        self.logger.log(f"最大ドローダウン: {metrics['max_drawdown']:>4.2f} [BTC/USD]")
                        self.logger.log(f"最大ドローダウン率: {metrics['max_drawdown_rate']:>4.2f} [%]")
                        self.logger.log(f"Sharpe: {metrics['sharpe']:.3f}")
                        self.logger.log(f"WinRate: {metrics['win_rate']:.2f}% Trades: {metrics['trades']}")
                        # JSON出力
                        try:
                            import json, os, time as _t, statistics
                            report_dir = Config.get_report_dir_name()
                            ts = _t.strftime('%Y%m%d%H%M%S')
                            # トレンド指標集計
                            trend_summary = {}
                            if self.closed_trades:
                                mfe_vals = [t['mfe'] for t in self.closed_trades]
                                mae_vals = [t['mae'] for t in self.closed_trades]
                                capture_vals = [t['capture_ratio'] for t in self.closed_trades]
                                loss_cont_vals = [t['loss_containment_ratio'] for t in self.closed_trades if t['loss_containment_ratio'] > 0]
                                classifications = {}
                                for t in self.closed_trades:
                                    classifications[t['classification']] = classifications.get(t['classification'], 0) + 1
                                trend_summary = {
                                    'trades': len(self.closed_trades),
                                    'mfe_median': statistics.median(mfe_vals) if mfe_vals else 0,
                                    'mae_median': statistics.median(mae_vals) if mae_vals else 0,
                                    'capture_avg': sum(capture_vals)/len(capture_vals) if capture_vals else 0,
                                    'loss_containment_avg': sum(loss_cont_vals)/len(loss_cont_vals) if loss_cont_vals else 0,
                                    'class_counts': classifications
                                }
                            # 保存
                            trend_trades_path = os.path.join(report_dir, f"trend_trades_{ts}.json")
                            with open(trend_trades_path, 'w', encoding='utf-8') as tf:
                                json.dump(self.closed_trades, tf, ensure_ascii=False, indent=2)
                            trend_summary_path = os.path.join(report_dir, f"trend_summary_{ts}.json")
                            with open(trend_summary_path, 'w', encoding='utf-8') as sf:
                                json.dump(trend_summary, sf, ensure_ascii=False, indent=2)
                            self.logger.log(f"トレンド指標出力: {trend_trades_path}, {trend_summary_path}")
                            os.makedirs(report_dir, exist_ok=True)
                            # メトリクス
                            summary_path = os.path.join(report_dir, f"backtest_summary_{ts}.json")
                            with open(summary_path, 'w', encoding='utf-8') as f:
                                json.dump(metrics, f, ensure_ascii=False, indent=2)
                            self.logger.log(f"バックテストサマリ出力: {summary_path} / パフォーマンス計測件数: {self.perf.iterations}")
                            # パフォーマンスサマリ
                            perf_summary = self.perf.summary()
                            perf_path = os.path.join(report_dir, f"performance_summary_{ts}.json")
                            with open(perf_path, 'w', encoding='utf-8') as pf:
                                json.dump(perf_summary, pf, ensure_ascii=False, indent=2)
                            self.logger.log(f"パフォーマンスサマリ出力: {perf_path}")
                            # PnL時系列出力
                            if self.pnl_history and self.close_times:
                                pnl_csv, pnl_json = generate_pnl_timeseries(self.pnl_history, self.close_times, report_dir, prefix="pnl_timeseries")
                                self.logger.log(f"PnL時系列出力 (CSV): {pnl_csv}")
                                self.logger.log(f"PnL時系列出力 (JSON): {pnl_json}")
                                # レポート自動生成 (Markdown)
                                try:
                                    report_md = generate_markdown_report(
                                        metrics=metrics,
                                        perf_summary=perf_summary,
                                        output_dir=report_dir,
                                        ts=ts,
                                        pnl_csv_path=pnl_csv,
                                        pnl_json_path=pnl_json,
                                        extra_notes=None,
                                    )
                                    self.logger.log(f"レポート出力 (Markdown): {report_md}")
                                except Exception as re:
                                    self.logger.log_error(f"レポート出力失敗: {re}")
                                # インタラクティブ可視化を自動生成
                                try:
                                    vis = Visualizer()
                                    viz_html = os.path.join(report_dir, f"backtest_visualization_{ts}.html")
                                    vis.visualize_backtest(
                                        log_directory="logs",
                                        output_html=viz_html,
                                        start_time=Config.get_start_time(),
                                        end_time=Config.get_end_time()
                                    )
                                    self.logger.log(f"インタラクティブ可視化出力: {viz_html}")
                                except Exception as ve:
                                    import traceback
                                    self.logger.log_error(f"可視化出力失敗: {ve}")
                                    self.logger.log_error(f"詳細: {traceback.format_exc()}")
                        except Exception as e:
                            self.logger.log_error(f"バックテストメトリクス/パフォーマンス/PnL出力失敗: {e}")
                        
                        # ログファイルをクローズ（ZIP圧縮含む）
                        self.logger.close_log_file()
                        
                        # Excel集計を自動生成（ログクローズ後に実行）
                        try:
                            util_instance = Util()
                            excel_path = os.path.join("logs", f"combined_logs_{ts}.xlsx")
                            util_instance.extract_and_export_logs(
                                log_directory="logs",
                                num_logs=999,
                                output_excel_file=excel_path,
                                start_time=Config.get_start_time(),
                                end_time=Config.get_end_time()
                            )
                            self.logger.log(f"Excel集計出力: {excel_path}")
                        except Exception as ue:
                            import traceback
                            self.logger.log_error(f"Excel出力失敗: {ue}")
                            self.logger.log_error(f"詳細: {traceback.format_exc()}")
                        
                        try:
                            # トレードCSVも自動出力
                            util_instance = Util()
                            trades_csv = os.path.join("logs", f"trades_export_{ts}.csv")
                            util_instance.export_trades_csv_from_logs(
                                log_directory="logs",
                                output_csv_file=trades_csv,
                                start_time=Config.get_start_time(),
                                end_time=Config.get_end_time()
                            )
                            self.logger.log(f"トレードCSV出力: {trades_csv}")
                        except Exception as ue:
                            import traceback
                            self.logger.log_error(f"CSV出力失敗: {ue}")
                            self.logger.log_error(f"詳細: {traceback.format_exc()}")
                        self.logger.log("--- BOT END -------------------------------------------")
                        break
                else:
                    self.price_data_management.update_price_data()
                    t_price_end = perf_counter(); self.perf.record('price_update', t_price_start, t_price_end)
                
                # 取得情報を表示
                # self.price_data_management.show_latest_ohlcv()
                # 最新価格を取得
                price = self.price_data_management.get_ticker()

                # 取引所から口座残高を取得
                if back_test_mode == 1:
                    balance_tether = config_instance.get_account_balance() + self.portfolio.get_profit_and_loss()
                else:
                    balance = self.exchange.get_account_balance_total()
                    balance_tether = balance
                    # TODO シミュレーション用　口座0円のため
                    balance_tether = config_instance.get_account_balance() + self.portfolio.get_profit_and_loss()

                # --------------------------------------------
                # 取引戦略に口座残高を渡してトレード判断を取得
                # --------------------------------------------
                t_strategy_start = perf_counter()
                try:
                    # 時間ベースEXITチェック (戦略判定前に実行)
                    max_hold_bars = config_instance.get_max_hold_bars()
                    if max_hold_bars > 0 and self.open_trade is not None:
                        bars_held = self.open_trade['bars']
                        if bars_held >= max_hold_bars:
                            self.logger.log(f"[時間ベースEXIT] 保持バー数 {bars_held} >= 上限 {max_hold_bars} で強制決済")
                            position_side = self.portfolio.get_position_side()
                            trade_decision = {
                                "decision": "EXIT",
                                "side": "SELL" if position_side == "BUY" else "BUY",
                                "order_type": "market"
                            }
                        else:
                            trade_decision = self.strategy.make_trade_decision()
                    else:
                        trade_decision = self.strategy.make_trade_decision()
                except Exception as e:
                    self.logger.log_error(f"取引戦略実行エラー: {e}")
                    trade_decision = {"decision": "NONE"}
                else:
                    # シグナル系イベント
                    if trade_decision.get("decision") == "ENTRY":
                        self.events.emit(EventType.ENTRY_SIGNAL, trade_decision)
                    elif trade_decision.get("decision") == "ADD":
                        self.events.emit(EventType.ADD_SIGNAL, trade_decision)
                    elif trade_decision.get("decision") == "EXIT":
                        self.events.emit(EventType.EXIT_SIGNAL, trade_decision)
                t_strategy_end = perf_counter(); self.perf.record('strategy', t_strategy_start, t_strategy_end)
                # --------------------------------------------
                # 取引決定の場合
                # --------------------------------------------
                if trade_decision["decision"] != 'NONE' and trade_executed == False:
                    t_order_start = perf_counter()
                    # --------------------------------------------
                    # 決定状態を表示
                    #self.logger.log(f"シグナル発生: {strategy}")
                    
                    # 初回の分割ポジション計算
                    if trade_decision["decision"] == "ENTRY":
                        position_size = self.risk_management.calculate_position_size(balance_tether)
                        quantity = position_size
                    # 追加時は初回の分割サイズを踏襲
                    elif trade_decision["decision"] == "ADD":
                        position_size = self.risk_management.get_position_size()
                        quantity = position_size
                    # 清算時は全ポジション
                    elif trade_decision["decision"] == "EXIT":
                        # 保有資産を取得
                        position_size = self.portfolio.get_position_quantity()
                        quantity = position_size['quantity']
                    else:
                        raise

                    # 注文クラス作成
                    order = Order(config_instance.get_market(),
                                  trade_decision["side"],
                                  quantity,
                                  price,
                                  trade_decision["order_type"])

                    #self.logger.log(order.to_dict())
                    try:
                        self.events.emit(EventType.ORDER_SUBMITTED, order.to_dict())
                        order_response = self.execute_order(order.to_dict())
                        #self.logger.log(f"注文実行: {order_response}")
                        self.events.emit(EventType.ORDER_EXECUTED, order.to_dict())
                    except Exception as e:
                        self.logger.log_error(f"注文実行エラー: {e}")
                        continue  # 注文失敗時はポートフォリオ更新をスキップ

                    # --------------------------------------------
                    # portfolio更新
                    # --------------------------------------------
                    t_portfolio_start = perf_counter()
                    if trade_decision["decision"] == "EXIT":
                        self.portfolio.clear_position_quantity(price)
                        # EXITで確定した損益を勝敗判定 (正なら勝ち)
                        pnl = self.portfolio.get_profit_and_loss()
                        self.trade_results.append(pnl >= 0)
                        # トレード指標確定
                        if self.open_trade:
                            realized = pnl  # 累計損益ベース（単一トレード簡易化）
                            entry_price = self.open_trade['entry_price']
                            side = self.open_trade['side']
                            mfe = self.open_trade['mfe']
                            mae = self.open_trade['mae']
                            bars = self.open_trade['bars']
                            atr_entry = self.open_trade['atr']
                            capture_ratio = (realized / mfe) if mfe > 0 else 0.0
                            loss_containment_ratio = (abs(realized) / mae) if (mae > 0 and realized < 0) else 0.0
                            # 分類ロジック: config.iniから読み込み (最適化結果: k2=1.5, k3=1.2)
                            k2 = Config.get_classification_k2()
                            k3 = Config.get_classification_k3()
                            if mfe >= atr_entry * k2:
                                classification = 'TREND'
                            elif mae >= atr_entry * k3 and mfe < atr_entry * k2:
                                classification = 'FALSE_BREAK'
                            else:
                                classification = 'NEUTRAL'
                            self.closed_trades.append({
                                'entry_price': entry_price,
                                'exit_price': price,
                                'side': side,
                                'realized_pnl': realized,
                                'mfe': mfe,
                                'mae': mae,
                                'bars_held': bars,
                                'atr_at_entry': atr_entry,
                                'capture_ratio': capture_ratio,
                                'loss_containment_ratio': loss_containment_ratio,
                                'classification': classification
                            })
                            self.open_trade = None
                    elif trade_decision["decision"] == "PARTIAL_EXIT":
                        ratio = Config.get_partial_exit_ratio()
                        self.portfolio.partial_clear_position_quantity(price, ratio)
                        # 部分決済後もトレードは継続させるため open_trade は保持
                    elif trade_decision["decision"] == "ENTRY" or trade_decision["decision"] == "ADD":
                        self.portfolio.add_position_quantity(quantity, trade_decision["side"], price)
                        # 前回のエントリ価格を更新
                        self.risk_management.update_last_entry_price(price)
                        # ENTRY時に初期化 / ADD時は平均価格再計算
                        avg_entry = self.portfolio.get_position_price()
                        atr_val = self.price_data_management.get_volatility()
                        if trade_decision["decision"] == "ENTRY" or self.open_trade is None:
                            self.open_trade = {'entry_price': avg_entry, 'side': trade_decision['side'], 'atr': atr_val, 'mfe': 0.0, 'mae': 0.0, 'bars': 0}
                        else:
                            self.open_trade['entry_price'] = avg_entry
                    # ポートフォリオ更新イベント
                    self.events.emit(EventType.PORTFOLIO_UPDATED, self.portfolio.get_position_quantity())
                    t_portfolio_end = perf_counter(); self.perf.record('portfolio_update', t_portfolio_start, t_portfolio_end)
                    t_order_end = perf_counter(); self.perf.record('order_exec', t_order_start, t_order_end)
                    #self.logger.log(f"ポートフォリオ更新: {self.portfolio.get_position_quantity()}")
                    #self.logger.log(f"損益: {self.portfolio.get_profit_and_loss()} [BTC/USD]")
                    
                    trade_executed = True
                else:
                    trade_executed = False

                # --------------------------------------------
                # リスク制御を更新
                # --------------------------------------------
                t_risk_start = perf_counter()
                try:
                    self.risk_management.update_risk_status()
                except Exception as e:
                    self.logger.log_error(f"リスク管理更新エラー: {e}")
                else:
                    self.events.emit(EventType.RISK_UPDATED, {
                        'stop': self.risk_management.get_stop_price(),
                        'psar': self.risk_management.get_psar(),
                    })
                t_risk_end = perf_counter(); self.perf.record('risk_update', t_risk_start, t_risk_end)

                # --------------------------------------------
                # ログに記録 (インターバル制御付き)
                # --------------------------------------------
                t_logging_start = perf_counter()
                self._log_counter += 1
                # トレード実行時または定期ログタイミングでログ出力
                force_log = trade_executed or (self._log_counter % self._logging_interval == 0)
                
                if force_log:
                    trade_data = self.price_data_management.get_latest_ohlcv()
                    # バックテスト時はclose priceをシミュレータ値に更新
                    if back_test_mode == 1:
                        trade_data['real_time'] = self.price_data_management.get_latest_close_time_dt()
                        trade_data['close_price'] = price
                    else:
                        dt_now = datetime.now()
                        trade_data['real_time'] = dt_now.strftime('%Y/%m/%d %H:%M:%S')
                    trade_data['stop_price'] = self.risk_management.get_stop_price()
                    trade_data['position_price'] = self.portfolio.get_position_price()
                    trade_data['position_size'] = self.risk_management.get_position_size()
                    position_size = self.portfolio.get_position_quantity()
                    quantity = position_size['quantity']
                    trade_data['position_quantity'] = quantity
                    profit, loss = self.portfolio.calc_position_quantity(price)
                    trade_data['profit_and_loss'] = profit - loss
                    trade_data['total_profit_and_loss'] = self.portfolio.get_profit_and_loss()
                    # 損益履歴へ追加 (バックテストのみ)
                    if back_test_mode == 1:
                        self.pnl_history.append(trade_data['total_profit_and_loss'])
                        self.close_times.append(trade_data['real_time'])
                    trade_data['volatility'] = self.price_data_management.get_volatility()
                    trade_data['stop_offset'] = self.risk_management.get_stop_offset()
                    trade_data['stop_psar_stop_offset'] = self.risk_management.get_psar_stop_offset()
                    trade_data['stop_price_surge_stop_offset'] = self.risk_management.get_price_surge_stop_offset()
                    
                    # signal info
                    signals = self.price_data_management.get_signals()
                    trade_data['dc_h'] = signals['donchian']['info']['highest']
                    trade_data['dc_l'] = signals['donchian']['info']['lowest']
                    trade_data['pvo_val'] = signals['pvo']['info']['value']
                    trade_data['psar'] = self.risk_management.get_psar()
                    trade_data['psarbull'] = self.risk_management.get_psarbull()
                    trade_data['psarbear'] = self.risk_management.get_psarbear()
                    trade_data['adx'] = self.risk_management.get_adx()
                    trade_data['adx_bull'] = self.risk_management.get_adx_bull()
                    trade_data['adx_bear'] = self.risk_management.get_adx_bear()

                    trade_data.update(trade_decision)
                    trade_data.update(signals)

                    # portfolio
                    trade_data['positions'] = self.portfolio.get_position_quantity()

                    # オープントレード指標更新
                    if self.open_trade:
                        avg_entry = self.open_trade['entry_price']
                        side_open = self.open_trade['side']
                        high_p = trade_data['high_price']
                        low_p = trade_data['low_price']
                        if side_open == 'BUY':
                            favorable = high_p - avg_entry
                            adverse = avg_entry - low_p
                        else:  # SELL
                            favorable = avg_entry - low_p
                            adverse = high_p - avg_entry
                        if favorable > self.open_trade['mfe']:
                            self.open_trade['mfe'] = favorable
                        if adverse > self.open_trade['mae']:
                            self.open_trade['mae'] = adverse
                        self.open_trade['bars'] += 1
                        trade_data['open_mfe'] = self.open_trade['mfe']
                        trade_data['open_mae'] = self.open_trade['mae']
                        trade_data['bars_held'] = self.open_trade['bars']
                    # 取引データを表示
                    self.show_trade_data(trade_data)
                    # 取引データを記録
                    self.logger.log_trade_data(trade_data)
                else:
                    # ログスキップ時もPnL履歴は更新 (バックテストのみ)
                    if back_test_mode == 1:
                        self.pnl_history.append(self.portfolio.get_profit_and_loss())
                        self.close_times.append(self.price_data_management.get_latest_close_time_dt())
                
                t_logging_end = perf_counter(); self.perf.record('logging', t_logging_start, t_logging_end)
                self.perf.iterations += 1
            
                # イベント初期化
                self.strategy.initialize_trade_decision()
            
                # 一定の待ち時間を設けてループを繰り返す
                if back_test_mode == 0:
                    time.sleep(self.bot_operation_cycle)

                # 2時間ごとにファイルを分けるかチェック
                if back_test_mode == 0:
                    current_time = datetime.now()
                else:
                    current_time = datetime.fromtimestamp(self.price_data_management.get_latest_close_time())

                if log_zipped == False and int(current_time.strftime("%H")) % 2 == 0 and int(current_time.strftime("%M")) == 0:
                    # ログをローテート（ZIP圧縮は close_log_file() 内で自動実行）
                    self.logger.close_log_file()
                    self.logger.open_log_file()
                    log_zipped = True
                else:
                    log_zipped = False

            except Exception as e:
                # 前回と異なるエラーメッセージの場合のみログ出力
                error_msg = str(e)
                if error_msg != self._last_error_message:
                    self.logger.log_error(f"メインループエラー: {e}")
                    self._last_error_message = error_msg
                self.events.emit(EventType.LOOP_ERROR, {'error': error_msg})
                if back_test_mode == 0:
                    time.sleep(self.bot_operation_cycle)

    def execute_order(self, order):
        """
        注文を実行します。

        Args:
            order (dict): トレード判断に基づいた注文情報

        Returns:
            dict: 注文の実行結果
        """
        symbol = order['symbol']
        side = order['side']
        quantity = order['quantity']
        order_type = order['order_type']
        context = order.get('context', 'entry')
        timeout_sec = order.get('timeout_sec', None)
        
        price = 0
        if order_type == 'limit':
            price = order.get('price', 0)

        # ピラミッティング時はタイムアウト処理付き実行
        if context == 'pyramiding' and timeout_sec:
            order_response = self.exchange.execute_order_with_fallback(
                side=side,
                quantity=quantity,
                price=price,
                order_type=order_type,
                timeout_sec=timeout_sec
            )
        else:
            # 通常の注文実行
            order_response = self.exchange.execute_order(
                side=side,
                quantity=quantity,
                price=price,
                order_type=order_type
            )
        
        # ログ記録
        self.logger.log(f"[EXECUTE] Context={context}, Type={order_type}, Side={side}, Qty={quantity}, Price={price}")
        
        return order_response

if __name__ == "__main__":
    # bot class test flag
    bot_order_test = False
    
    # 取引所クラスを初期化
    exchange = BybitExchange(Config.get_api_key(), Config.get_api_secret())

    # 資産管理クラスを初期化
    portfolio = Portfolio()
    
    # IndicatorServiceを初期化（PriceDataManagementとRiskManagementで共有）
    indicator_service = IndicatorService()
    
    # 価格情報クラスを初期化
    price_data_management = PriceDataManagement(indicator_service=indicator_service)

    # リスク戦略クラスを初期化
    risk_management = RiskManagement(price_data_management, portfolio, indicator_service=indicator_service)

    # 取引戦略クラスを初期化
    strategy = TradingStrategy(price_data_management, risk_management, portfolio)

    # Bot クラスを初期化
    bot = Bot(exchange, strategy, risk_management, price_data_management, portfolio)

    if bot_order_test == True:
        # 注文クラス作成
        price = price_data_management.get_ticker()
        order = Order("BTC/USD", "buy", 1, price, "market")

        print(f"order test: {order}")
        order_response = bot.execute_order(order.to_dict())
        print(f"注文実行:{order_response}")
    else:
        # ボットを実行
        bot.run()
