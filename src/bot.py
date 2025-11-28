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
from regime_detector import RegimeDetector

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
        
        # 適応型レジーム検出器
        self.regime_detector = RegimeDetector()
        self._regime_update_counter = 0
        self._regime_update_interval = 10  # 10バーごとにレジーム更新

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
        
        # Logger に config 情報を埋め込み
        config_metadata = {
            'leverage': config_instance.get_leverage(),
            'entry_times': Config.get_entry_times(),
            'entry_range': Config.get_entry_range(),
            'stop_range': Config.get_stop_range(),
            'volatility_term': Config.get_volatility_term(),
            'donchian_buy_term': Config.get_donchian_buy_term(),
            'donchian_sell_term': Config.get_donchian_sell_term(),
            'pvo_s_term': Config.get_pvo_s_term(),
            'pvo_l_term': Config.get_pvo_l_term(),
            'pvo_threshold': Config.get_pvo_threshold(),
            'regime_detection_enabled': config_instance.config['Strategy'].getboolean('regime_detection_enabled', fallback=False),
            'keltner_enabled': Config.get_keltner_enabled(),
            'market': Config.get_market(),
            'time_frame': Config.get_time_frame(),
        }
        self.logger.set_config_metadata(config_metadata)
        
        if back_test_mode == 1:
            self.logger.log("--- BOT START (BACK TEST MODE)-------------------------")
            try:
                self.price_data_management.initialise_back_test_ohlcv_data()
            except Exception as e:
                self.logger.log_error(f"バックテストデータ初期化エラー: {e}")
                self.logger.log("バックテスト中止")
                import json, os, time as _t
                # スキップ時も空のレポートを出力
                metrics = {
                    "status": "SKIPPED",
                    "error": str(e),
                    "reason": "バックテストデータ初期化失敗"
                }
                report_dir = Config.get_report_dir_name()
                ts = _t.strftime('%Y%m%d%H%M%S')
                os.makedirs(report_dir, exist_ok=True)
                summary_path = os.path.join(report_dir, f"backtest_summary_{ts}.json")
                with open(summary_path, 'w', encoding='utf-8') as f:
                    json.dump(metrics, f, ensure_ascii=False, indent=2)
                self.logger.close_log_file()
                return  # バックテスト実行を終了
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
                                # 技術指標を取得
                                volatility = self.price_data_management.get_volatility()
                                current_stop = self.risk_management.get_stop_price()
                                current_psar = self.risk_management.get_psar()
                                # Keltner チャネル情報があれば取得（なければ 0）
                                keltner_upper = getattr(self.risk_management, 'keltner_upper', 0)
                                keltner_lower = getattr(self.risk_management, 'keltner_lower', 0)
                                
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
                                    'classification': classification,
                                    'volatility_at_exit': volatility,
                                    'stop_loss_price': current_stop,
                                    'psar_at_exit': current_psar,
                                    'keltner_upper': keltner_upper,
                                    'keltner_lower': keltner_lower,
                                    'stop_loss_hit': self.open_trade.get('stop_loss_hit', False)
                                })
                                self.open_trade = None
                            # EOB決済をPnL履歴へ追記
                            self.pnl_history.append(self.portfolio.get_profit_and_loss())
                            self.close_times.append(self.price_data_management.get_latest_close_time_dt())
                        
                        self.logger.log("-------------------------------------------------------")
                        self.logger.log(f"最終ポートフォリオ: {self.portfolio.get_position_quantity()}")
                        
                        # ===== P0-1 修正: trade_results を closed_trades から再構築 =====
                        # closed_trades に記録されたデータから win/loss を判定
                        reconstructed_trade_results = [t.get('realized_pnl', 0) >= 0 for t in self.closed_trades]
                        if len(reconstructed_trade_results) != len(self.trade_results):
                            self.logger.log(f"[P0-1修正] trade_results 再構築: {len(self.trade_results)} → {len(reconstructed_trade_results)}")
                            self.trade_results = reconstructed_trade_results
                        
                        # メトリクス計算 (統一的なドローダウン計算を使用)
                        metrics = compute_metrics(self.pnl_history, self.trade_results)
                        self.logger.log(f"最終損益: {metrics['total_pnl']:>4.0f} [BTC/USD]")
                        self.logger.log(f"プロフィットファクター: {metrics['profit_factor']:>4.2f}")
                        self.logger.log(f"最大ドローダウン: {metrics['max_drawdown']:>4.2f} [BTC/USD]")
                        self.logger.log(f"最大ドローダウン率: {metrics['max_drawdown_rate']:>4.2f} [%]")
                        self.logger.log(f"Sharpe: {metrics['sharpe']:.3f}")
                        self.logger.log(f"WinRate: {metrics['win_rate']:.2f}% Trades: {metrics['trades']}")
                        
                        # レジーム統計を出力
                        regime_stats = self.regime_detector.get_regime_stats()
                        if regime_stats:
                            self.logger.log("-------------------------------------------------------")
                            self.logger.log("[レジーム統計]")
                            self.logger.log(f"レジーム変更回数: {regime_stats.get('regime_change_count', 0)}")
                            percentages = regime_stats.get('regime_percentages', {})
                            for regime, pct in percentages.items():
                                self.logger.log(f"  {regime}: {pct:.1f}%")
                            self.logger.log(f"平均ボラティリティ比: {regime_stats.get('avg_volatility_ratio', 0):.2f}")
                            self.logger.log(f"平均トレンド強度: {regime_stats.get('avg_trend_strength', 0):.2f}")
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
                            # メトリクス（レジーム統計を追加）
                            regime_stats = self.regime_detector.get_regime_stats()
                            metrics['regime_stats'] = regime_stats
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
                            
                            # fast_summary_mode チェック
                            fast_summary_mode = config_instance.get_fast_summary_mode()
                            
                            # PnL時系列出力
                            if self.pnl_history and self.close_times:
                                pnl_csv, pnl_json = generate_pnl_timeseries(self.pnl_history, self.close_times, report_dir, prefix="pnl_timeseries")
                                self.logger.log(f"PnL時系列出力 (CSV): {pnl_csv}")
                                self.logger.log(f"PnL時系列出力 (JSON): {pnl_json}")
                                
                                # 高速モード時はレポート・可視化をスキップ
                                if fast_summary_mode == 0:
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
                                else:
                                    self.logger.log("[高速サマリモード] Markdown レポート・可視化をスキップ")
                        except Exception as e:
                            self.logger.log_error(f"バックテストメトリクス/パフォーマンス/PnL出力失敗: {e}")
                        
                        # ログファイルをクローズ（ZIP圧縮含む）
                        self.logger.close_log_file()
                        
                        # ログ圧縮後に可視化を生成（新しいZIPファイルを確実に読み込むため）
                        if fast_summary_mode == 0:
                            try:
                                # Config を明示的にリロード（キャッシュクリア）
                                Config.reload_config()
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
                        
                        # 高速モード時とExcel出力無効時はExcel・CSV出力をスキップ
                        enable_excel = config_instance.get_enable_excel_export()
                        if fast_summary_mode == 0 and enable_excel == 1:
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
                        else:
                            self.logger.log("[高速サマリモード] Excel・CSV出力をスキップ")
                        
                        self.logger.log("--- BOT END -------------------------------------------")
                        
                        # ログファイルをZIP圧縮（期間情報をファイル名に含める）
                        try:
                            start_time = config_instance.get_start_time()
                            end_time = config_instance.get_end_time()
                            self.logger.compress_log_with_period(start_time, end_time)
                        except Exception as e:
                            self.logger.log_error(f"ログ圧縮失敗: {e}")
                        
                        break

                else:
                    self.price_data_management.update_price_data()
                    t_price_end = perf_counter(); self.perf.record('price_update', t_price_start, t_price_end)
                
                # --------------------------------------------
                # 適応型レジーム検出と動的パラメータ調整
                # --------------------------------------------
                self._regime_update_counter += 1
                if self._regime_update_counter >= self._regime_update_interval:
                    t_regime_start = perf_counter()
                    current_regime = self.regime_detector.detect_regime(self.price_data_management)
                    regime_params = self.regime_detector.get_regime_parameters(current_regime)
                    
                    # 動的パラメータ適用（risk_managementに反映）
                    self.risk_management.entry_range = regime_params['entry_range']
                    self.risk_management.initial_stop_range = regime_params['stop_range']
                    self.risk_management.leverage = regime_params['leverage']
                    
                    # 注意: keltner_atr_multiplier は indicator_service で管理されているため、
                    # 現時点では適用せず（次フェーズで実装）
                    
                    self._regime_update_counter = 0
                    t_regime_end = perf_counter(); self.perf.record('regime_detection', t_regime_start, t_regime_end)
                
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
                            # Phase 1: signals に regime_stats を追加（レジーム検出用）
                            regime_stats = self.regime_detector.get_regime_stats()
                            self.price_data_management.signals['regime_stats'] = regime_stats
                            trade_decision = self.strategy.make_trade_decision()
                    else:
                        # Phase 1: signals に regime_stats を追加（レジーム検出用）
                        regime_stats = self.regime_detector.get_regime_stats()
                        self.price_data_management.signals['regime_stats'] = regime_stats
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
                
                # ====================================================
                # ストップロス判定（戦略シグナルより優先）
                # ====================================================
                # ポジションがある場合、ストップロス判定を実施
                position = self.portfolio.get_position_quantity()
                if position['quantity'] > 0 and position['side'] != 'NONE':
                    current_price = self.price_data_management.get_ticker()
                    stop_price = self.risk_management.get_stop_price()
                    side = position['side']
                    
                    # 【重要】ポジション成立直後（bars=0）のストップロス判定をスキップ
                    # ENTRY/ADD直後の極限価格でのストップロス発火を防ぐ
                    skip_stoploss = False
                    if self.open_trade and self.open_trade.get('bars', 0) == 0:
                        skip_stoploss = True
                        self.logger.log(f"[ストップロス判定スキップ] 1バー目のため (bars=0)")
                    
                    if not skip_stoploss:
                        stop_hit = False
                        if side == "BUY" and current_price <= stop_price:
                            stop_hit = True
                            self.logger.log(f"[STOP LOSS HIT - BUY] Price={current_price:.2f} <= Stop={stop_price:.2f}")
                        elif side == "SELL" and current_price >= stop_price:
                            stop_hit = True
                            self.logger.log(f"[STOP LOSS HIT - SELL] Price={current_price:.2f} >= Stop={stop_price:.2f}")
                        
                        if stop_hit:
                            # open_trade に stop_loss_hit フラグを設定
                            if self.open_trade:
                                self.open_trade['stop_loss_hit'] = True
                            # ストップロス発動時は EXIT を強制
                            trade_decision = {
                                "decision": "EXIT",
                                "side": "SELL" if side == "BUY" else "BUY",
                                "order_type": "market",
                                "reason": "stop_loss"
                            }
                            self.logger.log(f"[EXIT DECISION] Triggered by stop loss: {position['side']} position closed")
                
                # ====================================================
                # 取引決定の場合
                # ====================================================
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
                        order_executed_successfully = True
                    except Exception as e:
                        self.logger.log_error(f"注文実行エラー: {e}")
                        order_executed_successfully = False

                    # 注文実行失敗時の処理
                    if not order_executed_successfully:
                        self.logger.log(f"[注文失敗] トレード決定をリセット: decision={trade_decision['decision']}")
                        # open_tradeをクリア（ENTRYが実行されていないため）
                        if trade_decision["decision"] == "ENTRY":
                            self.open_trade = None
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
                            # 技術指標を取得
                            volatility = self.price_data_management.get_volatility()
                            current_stop = self.risk_management.get_stop_price()
                            current_psar = self.risk_management.get_psar()
                            # Keltner チャネル情報があれば取得（なければ 0）
                            keltner_upper = getattr(self.risk_management, 'keltner_upper', 0)
                            keltner_lower = getattr(self.risk_management, 'keltner_lower', 0)
                            
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
                                'classification': classification,
                                'volatility_at_exit': volatility,
                                'stop_loss_price': current_stop,
                                'psar_at_exit': current_psar,
                                'keltner_upper': keltner_upper,
                                'keltner_lower': keltner_lower,
                                'stop_loss_hit': self.open_trade.get('stop_loss_hit', False)
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
                            self.open_trade = {'entry_price': avg_entry, 'side': trade_decision['side'], 'atr': atr_val, 'mfe': 0.0, 'mae': 0.0, 'bars': 0, 'stop_loss_hit': False}
                        else:
                            # ADD実行時：平均価格を更新し、bars=0にリセット（同じバー内でのEXIT判定をスキップ）
                            self.open_trade['entry_price'] = avg_entry
                            self.open_trade['bars'] = -1  # -1にリセット → bars()インクリメント後に0になる
                            self.logger.log(f"[ADD実行] bars をリセット（-1にセット、次ローソク足で0になる）")
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
                    side = position_size['side']
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
                    psar_val = self.risk_management.get_psar()
                    psarbull_val = self.risk_management.get_psarbull()
                    psarbear_val = self.risk_management.get_psarbear()
                    trade_data['psar'] = psar_val
                    trade_data['psarbull'] = psarbull_val
                    trade_data['psarbear'] = psarbear_val
                    
                    # 取引詳細情報の追加
                    trade_data['entry_price'] = None  # ENTRY時のエントリー価格
                    trade_data['avg_entry_price'] = None  # ADD を含めた平均購入価格
                    trade_data['exit_price'] = None  # EXIT時の清算価格
                    
                    # ENTRY/ADD/EXIT アクション情報から詳細を取得（trade_data内のdecisionフィールドから）
                    decision_name = None
                    if 'action_name' in trade_data and trade_data['action_name']:
                        decision_name = trade_data['action_name']
                    elif 'decision' in trade_data:
                        decision_name = trade_data['decision']
                    
                    if decision_name == 'ENTRY':
                        trade_data['entry_price'] = price
                        trade_data['avg_entry_price'] = price
                    elif decision_name == 'ADD':
                        # 平均購入価格を更新（保有中の場合）
                        if quantity > 0 and self.portfolio.get_position_price() > 0:
                            trade_data['avg_entry_price'] = self.portfolio.get_position_price()
                        trade_data['entry_price'] = price  # ADD時の追加価格
                    elif decision_name == 'EXIT':
                        trade_data['exit_price'] = price
                        trade_data['avg_entry_price'] = self.portfolio.get_position_price()
                    
                    # ポジション保有中の場合、PSAR値をストップとして記録
                    if quantity > 0:
                        if side == "BUY" and psarbear_val is not None and psarbear_val != 0:
                            trade_data['stop_price'] = psarbear_val
                        elif side == "SELL" and psarbull_val is not None and psarbull_val != 0:
                            trade_data['stop_price'] = psarbull_val
                    
                    trade_data['adx'] = self.risk_management.get_adx()
                    trade_data['adx_bull'] = self.risk_management.get_adx_bull()
                    trade_data['adx_bear'] = self.risk_management.get_adx_bear()

                    trade_data.update(trade_decision)
                    trade_data.update(signals)
                    
                    # action_name をログに記録
                    if 'decision' in trade_decision:
                        trade_data['action_name'] = trade_decision['decision']

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
    
    # Path utilities をインポート
    from path_utils import PathManager, load_api_keys_from_file
    
    # APIキーを .api_key ファイルから読み込む（優先度高）
    api_key_file = PathManager.get_api_key_file()
    api_key = None
    api_secret = None
    
    if api_key_file.exists():
        print(f"[INFO] Loading API keys from: {api_key_file}")
        api_key, api_secret = load_api_keys_from_file()
    
    # APIキーが見つからない場合は config.ini から読み込む
    if not api_key or not api_secret:
        api_key = Config.get_api_key()
        api_secret = Config.get_api_secret()
        
        # テンプレート値の場合は警告
        if api_key == "YOUR_API_KEY" or api_secret == "YOUR_API_SECRET":
            print("[ERROR] API keys are not configured!")
            print("[ERROR] Please create src/.api_key with API credentials")
            exit(1)
    else:
        # .api_key から読み込めた場合は、Config クラスにも反映させる
        # 一時的な config ファイルを作成して使用
        import shutil
        temp_config_path = PathManager.get_project_root() / "config_temp_bot.ini"
        config_src = PathManager.get_config_file()
        
        try:
            shutil.copy(config_src, temp_config_path)
            
            # APIキーを注入
            with open(temp_config_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            content = content.replace("YOUR_API_KEY", api_key)
            content = content.replace("YOUR_API_SECRET", api_secret)
            
            with open(temp_config_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Config を temp_config で読み込む
            Config.set_config_file(temp_config_path)
            Config.reload_config()
            print("[INFO] Config reloaded with API keys from .api_key file")
        except Exception as e:
            print(f"[WARN] Failed to create temp config: {e}")
    
    # 取引所クラスを初期化
    exchange = BybitExchange(api_key, api_secret)

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
