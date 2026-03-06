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
import sys
import time
import fcntl
from datetime import datetime

# src/ ディレクトリを sys.path に追加（実行ディレクトリに依存しない）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from logger import Logger
from config import Config
from price_data_management import PriceDataManagement
from bybit_exchange import BybitExchange
from bitget_exchange import BitgetExchange
from trading_strategy import TradingStrategy
from risk_management import RiskManagement
from portfolio import Portfolio
from order import Order
from event import EventBus, EventType
from metrics import compute_metrics
from trade_logger import TradeLogger
from risk_overlay import RiskOverlay
from alert import Alert

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
        # トレードログ記録
        self.trade_logger = TradeLogger(Config.get_log_dir_name())

        self.market_type = Config.get_market()
        self.bot_operation_cycle = Config.get_bot_operation_cycle()
        # バックテスト用損益履歴
        self.pnl_history = []
        # 約定履歴カウント (勝率計算用)
        self.trade_results = []  # list of bool win( True ) / loss( False )
        # per-trade損益リスト (期待値・RR比率計算用)
        self.trade_pnls = []  # list of float per-trade PnL (USD)
        # Task 40c: リスク・オーバーレイ（キルスイッチ）
        self.risk_overlay = RiskOverlay()
        # Task 40g: アラート通知（Discord Webhook, alert_enabled=0でデフォルト無効）
        self.alert = Alert()

    def show_trade_data(self, trade_data):
        # 毎周期データは JSON ログ（latest_status.json）に記録するため、
        # テキストログへの出力は廃止。エラーは log_error() で出力される。
        pass

        return

    def run(self):
        """
        ボットのメインループを実行します。口座残高を取得し、取引戦略に基づいてトレードを実行します。
        """
        config_instance = Config()
        back_test_mode = config_instance.get_back_test_mode()
        # Task42: キャッシュベースホットテストモード判定
        # back_test=0 かつ hot_test_dummy_mode=1 かつ use_cached_data_for_hot_test=1
        use_cached_hot_test = (
            back_test_mode == 0
            and Config.get_hot_test_dummy_mode() == 1
            and Config.get_use_cached_data_for_hot_test() == 1
        )
        
        # 多重起動防止: PIDロックファイル（バックテスト以外のみ）
        pid_lock_file = None
        if back_test_mode == 0:
            pid_path = '/tmp/satosystem_bot.pid'
            try:
                pid_lock_file = open(pid_path, 'w')
                fcntl.flock(pid_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                pid_lock_file.write(str(os.getpid()))
                pid_lock_file.flush()
            except IOError:
                print(f"ERROR: BOTが既に起動しています（{pid_path}）。多重起動を防止します。")
                sys.exit(1)

        if back_test_mode == 1:
            self.logger.log("--- BOT START (BACK TEST MODE)-------------------------")
            self.price_data_management.initialise_back_test_ohlcv_data()
        elif use_cached_hot_test:
            self.logger.log("--- BOT START (CACHED HOT TEST MODE - DUMMY TRADE)-----")
            self.price_data_management.initialise_back_test_ohlcv_data()
        else:
            self.logger.log("--- BOT START -----------------------------------------")

        self.logger.log(str(config_instance))
        self.logger.log("-------------------------------------------------------")
        # Task 40g: システム起動通知（ライブ/ダミーモードのみ、alert_enabled=0でno-op）
        if back_test_mode == 0:
            mode_str = "HOT_TEST (DUMMY)" if Config.get_hot_test_dummy_mode() == 1 else "LIVE"
            self.alert.notify_system_start(mode_str, Config.get_account_balance())
        
        # メモリ監視機能の初期化（リアルタイムモードのみ）
        memory_check_interval = 3600  # 1時間ごと
        last_memory_check = time.time() if back_test_mode == 0 else 0

        while True:
            try:
                log_zipped = False
                trade_executed = False
                # --------------------------------------------
                # 最初に価格情報の更新
                # --------------------------------------------
                if back_test_mode == 1 or use_cached_hot_test:
                    is_end = self.price_data_management.update_price_data_backtest()
                    # イベント: ティック
                    self.events.emit(EventType.TICK, {
                        'time': self.price_data_management.get_latest_close_time(),
                        'price': self.price_data_management.get_ticker()
                    })
                    # TODO 結果の別ファイル出力とバックテストでの結果集計
                    # バックテスト終端だったら抜ける
                    if is_end == True:
                        self.logger.log("-------------------------------------------------------")
                        self.logger.log(f"最終ポートフォリオ: {self.portfolio.get_position_quantity()}")
                        self.logger.log(f"最終損益: {self.portfolio.get_profit_and_loss():>4.0f} [BTC/USD]")
                        self.logger.log(f"プロフィットファクター: {self.portfolio.get_profit_factor():>4.2f}")
                        self.logger.log(f"最大ドローダウン: {self.portfolio.get_drawdown():>4.2f} [BTC/USD]")
                        self.logger.log(f"最大ドローダウン率: {self.portfolio.get_drawdown_rate():>4.2f} [%]")

                        # 追加メトリクス計算（初期資本を渡してDD率を正しく計算）
                        initial_balance = Config.get_account_balance()
                        metrics = compute_metrics(self.pnl_history, self.trade_results, initial_balance, trade_pnls=self.trade_pnls)
                        self.logger.log(f"Sharpe: {metrics['sharpe']:.3f}  Sortino: {metrics['sortino']:.3f}")
                        self.logger.log(f"RecoveryFactor: {metrics['recovery_factor']:.3f}  PayoffRatio: {metrics['payoff_ratio']:.3f}")
                        self.logger.log(f"Expectancy: {metrics['expectancy']:.2f} USD  MaxConseqLoss: {metrics['max_consec_losses']}")
                        self.logger.log(f"WinRate: {metrics['win_rate']:.2f}% Trades: {metrics['trades']}")
                        # JSON出力
                        try:
                            import json, time as _t
                            log_dir = Config.get_log_dir_name()
                            ts = _t.strftime('%Y%m%d%H%M%S')
                            summary_path = os.path.join(log_dir, f"backtest_summary_{ts}.json")
                            with open(summary_path, 'w', encoding='utf-8') as f:
                                json.dump(metrics, f, ensure_ascii=False, indent=2)
                            self.logger.log(f"バックテストサマリ出力: {summary_path}")

                            # トレードログを JSON で保存
                            trade_log_path = self.trade_logger.save_trades_json(f"trade_log_{ts}.json")
                            if trade_log_path:
                                self.logger.log(f"トレードログ出力: {trade_log_path}")
                                # トレードログの統計情報を表示
                                stats = self.trade_logger.get_statistics()
                                self.logger.log(f"トレード統計: 総数={stats['total_trades']}, 完了={stats['completed_trades']}, 勝={stats['wins']}, 負={stats['losses']}, 勝率={stats['win_rate']:.1f}%")

                            # latest_status.json にバックテスト結果を書き出し
                            self.logger.set_backtest_result({
                                **metrics,
                                "summary_file": os.path.basename(summary_path),
                                "total_pnl": self.portfolio.get_profit_and_loss(),
                                "finished_at": _t.strftime('%Y/%m/%d %H:%M:%S'),
                            })
                        except Exception as e:
                            self.logger.log_error(f"バックテストメトリクス/トレードログ出力失敗: {e}")
                        
                        self.logger.close_log_file()
                        self.logger.log("--- BOT END -------------------------------------------")
                        # Task 40g: システム終了通知
                        _final_pnl = self.portfolio.get_profit_and_loss()
                        self.alert.notify_system_stop(
                            "END",
                            config_instance.get_account_balance() + _final_pnl,
                            _final_pnl
                        )
                        break
                else:
                    self.price_data_management.update_price_data()
                
                # 取得情報を表示
                # self.price_data_management.show_latest_ohlcv()
                # 最新価格を取得
                price = self.price_data_management.get_ticker()

                # 取引所から口座残高を取得
                if back_test_mode == 1 or use_cached_hot_test:
                    # バックテスト / キャッシュベースホットテスト: 初期資産 + 累積損益（APIコール不要）
                    balance_tether = config_instance.get_account_balance() + self.portfolio.get_profit_and_loss()
                else:
                    # 本番: Bybit実際の残高 + 累積損益
                    balance = self.exchange.get_account_balance_total()
                    balance_tether = balance + self.portfolio.get_profit_and_loss()

                # --------------------------------------------
                # 取引戦略に口座残高を渡してトレード判断を取得
                # --------------------------------------------
                try:
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
                # --------------------------------------------
                # 取引決定の場合
                # --------------------------------------------
                # Task 40c: キルスイッチチェック（ENTRY/ADDのみ。EXITは常に許可）
                if trade_decision["decision"] in ('ENTRY', 'ADD'):
                    can_trade, stop_reason = self.risk_overlay.check_can_trade(self.portfolio)
                    if not can_trade:
                        self.logger.log(f"⛔ RiskOverlay: 取引停止 [{stop_reason}]")
                        # Task 40g: キルスイッチ通知（ライブモードのみ、alert_enabled=0でno-op）
                        if back_test_mode == 0:
                            if "DD_STOP" in stop_reason:
                                self.alert.notify_large_drawdown(
                                    self.portfolio.get_drawdown_rate(),
                                    balance_tether,
                                    balance_tether + self.portfolio.get_drawdown()
                                )
                            elif "CONSEC_STOP" in stop_reason:
                                _ov_status = self.risk_overlay.get_status()
                                self.alert.notify_consecutive_losses(
                                    _ov_status["consecutive_losses"],
                                    _ov_status["daily_loss_usd"]
                                )
                        trade_decision = {"decision": "NONE"}

                if trade_decision["decision"] != 'NONE' and trade_executed == False:
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
                        order_response = self.execute_order(order.to_dict(), trade_decision["decision"])
                        #self.logger.log(f"注文実行: {order_response}")
                        self.events.emit(EventType.ORDER_EXECUTED, order.to_dict())
                    except Exception as e:
                        self.logger.log_error(f"注文実行エラー: {e}")
                        continue  # 注文失敗時はポートフォリオ更新をスキップ

                    # Task 40g: ENTRY/ADD取引実行通知（ライブモードのみ、EXITはpnl確定後に通知）
                    if back_test_mode == 0 and trade_decision["decision"] in ("ENTRY", "ADD"):
                        self.alert.notify_trade_execution(
                            side=trade_decision["side"],
                            price=price,
                            quantity=quantity
                        )

                    # --------------------------------------------
                    # portfolio更新
                    # --------------------------------------------
                    if trade_decision["decision"] == "EXIT":
                        exit_price = price
                        pnl = self.portfolio.get_profit_and_loss()
                        is_backtest = Config.get_back_test_mode()  # Task 40b
                        self.portfolio.clear_position_quantity(price, is_backtest=is_backtest)
                        # EXITで確定した損益を勝敗判定 (正なら勝ち)
                        self.trade_results.append(pnl >= 0)
                        # per-trade損益を記録 (期待値・RR比率計算用)
                        self.trade_pnls.append(pnl)
                        # Task 40c: RiskOverlayに損益を通知
                        self.risk_overlay.notify_trade_result(pnl)
                        # Task 40g: EXIT取引実行通知（ライブモードのみ）
                        if back_test_mode == 0:
                            self.alert.notify_trade_execution(
                                side=trade_decision["side"],
                                price=price,
                                quantity=quantity,
                                pnl=pnl
                            )
                        
                        # トレードログ: EXIT記録
                        try:
                            entry_time = self.price_data_management.get_latest_close_time()
                            entry_time_dt = self.price_data_management.get_latest_close_time_dt()
                            current_price = self.price_data_management.get_ticker()
                            signals = self.price_data_management.get_signals()
                            
                            exit_data = {
                                'timestamp': entry_time,
                                'close_time_dt': entry_time_dt,
                                'price': exit_price,
                                'pnl_usd': pnl,
                                'pnl_pct': (pnl / self.portfolio.get_position_price() * 100) if self.portfolio.get_position_price() > 0 else 0,
                                'max_drawdown_usd': self.portfolio.get_drawdown(),
                                'max_drawdown_pct': self.portfolio.get_drawdown_rate(),
                                'bars_held': getattr(self.risk_management, 'bars_held', 0),
                                'duration_minutes': 0,  # 計算は後で
                                'reason': trade_decision.get('exit_reason', 'STOP_LOSS'),
                                'cumulative_pnl': self.portfolio.get_profit_and_loss()
                            }
                            self.trade_logger.log_exit(exit_data)
                        except Exception as e:
                            self.logger.log_error(f"トレードログEXIT記録失敗: {e}")
                            
                    elif trade_decision["decision"] == "ENTRY" or trade_decision["decision"] == "ADD":
                        is_backtest = Config.get_back_test_mode()  # Task 40b
                        self.portfolio.add_position_quantity(quantity, trade_decision["side"], price, is_backtest=is_backtest)
                        # 前回のエントリ価格を更新
                        self.risk_management.update_last_entry_price(price)
                        
                        # トレードログ: ENTRY記録
                        if trade_decision["decision"] == "ENTRY":  # 初回エントリーのみ
                            try:
                                entry_time = self.price_data_management.get_latest_close_time()
                                entry_time_dt = self.price_data_management.get_latest_close_time_dt()
                                signals = self.price_data_management.get_signals()
                                
                                entry_data = {
                                    'timestamp': entry_time,
                                    'close_time_dt': entry_time_dt,
                                    'side': trade_decision["side"],
                                    'price': price,
                                    'pvo_signal': signals['pvo']['signal'],
                                    'pvo_value': signals['pvo']['info'].get('value', 0),
                                    'pvo_threshold': Config.get_pvo_threshold(),
                                    'adx_value': self.risk_management.get_adx() if hasattr(self.risk_management, 'get_adx') else 0,
                                    'adx_threshold': Config.get_adx_filter_threshold(),
                                    'adx_filter_pass': (self.risk_management.get_adx() >= Config.get_adx_filter_threshold()) if hasattr(self.risk_management, 'get_adx') else False,
                                    'volume': self.price_data_management.get_latest_volume(),
                                    'volume_threshold': Config.get_volume_filter_threshold(),
                                    'volume_filter_pass': self.price_data_management.get_latest_volume() >= Config.get_volume_filter_threshold(),
                                    'volatility': self.price_data_management.get_volatility(),
                                    'volatility_threshold': Config.get_volatility_filter_threshold(),
                                    'volatility_filter_pass': self.price_data_management.get_volatility() <= Config.get_volatility_filter_threshold(),
                                    'pvo_filter_pass': signals['pvo']['info'].get('value', 0) > Config.get_pvo_threshold(),
                                    'donchian_signal': signals['donchian']['signal'],
                                    'strategy_signal': getattr(self.strategy, 'current_strategy_signal', 'NONE'),
                                    'market_regime': getattr(self.strategy, 'current_market_regime', 'UNKNOWN'),
                                    'market_regime_confidence': getattr(self.strategy, 'market_regime_confidence', 0.0),
                                    'market_regime_reason': getattr(self.strategy, 'current_market_regime_reason', ''),
                                    'market_regime_filter_enabled': Config.get_enable_market_regime_detection(),
                                    'vcp_signal': getattr(self.strategy, 'vcp_signal_latest', 0),
                                    'vcp_confidence': getattr(self.strategy, 'vcp_confidence_latest', 0.0),
                                    'vcp_reason': getattr(self.strategy, 'vcp_reason_latest', ''),
                                    
                                    # Mean Reversion Strategy (Phase 1評価中)
                                    'mean_reversion_signal': getattr(self.strategy, 'mr_signal_latest', False),
                                    'bb_position': getattr(self.strategy, 'mr_bb_position_latest', 0.0),
                                    'rsi_value': getattr(self.strategy, 'mr_rsi_latest', None),
                                    'mr_reason': getattr(self.strategy, 'mr_reason_latest', '')
                                }
                                self.trade_logger.log_entry(entry_data)
                            except Exception as e:
                                self.logger.log_error(f"トレードログENTRY記録失敗: {e}")
                        
                    # ポートフォリオ更新イベント
                    self.events.emit(EventType.PORTFOLIO_UPDATED, self.portfolio.get_position_quantity())
                    #self.logger.log(f"ポートフォリオ更新: {self.portfolio.get_position_quantity()}")
                    #self.logger.log(f"損益: {self.portfolio.get_profit_and_loss()} [BTC/USD]")
                    
                    trade_executed = True
                else:
                    trade_executed = False

                # --------------------------------------------
                # リスク制御を更新
                # -------- ------------------------------------
                try:
                    self.risk_management.update_risk_status()
                except Exception as e:
                    self.logger.log_error(f"リスク管理更新エラー: {e}")
                else:
                    self.events.emit(EventType.RISK_UPDATED, {
                        'stop': self.risk_management.get_stop_price(),
                        'psar': self.risk_management.get_psar(),
                    })

                # --------------------------------------------
                # ログに記録
                # --------------------------------------------
                trade_data = self.price_data_management.get_latest_ohlcv()
                # バックテスト / キャッシュベースホットテスト時はclose priceをシミュレータ値に更新
                if back_test_mode == 1 or use_cached_hot_test:
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
                # 損益履歴へ追加 (バックテスト & キャッシュベースホットテスト)
                if back_test_mode == 1 or use_cached_hot_test:
                    self.pnl_history.append(trade_data['total_profit_and_loss'])
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
                # 取引データを表示
                # if back_test_mode == 0:
                self.show_trade_data(trade_data)
                
                # 取引データを記録
                self.logger.log_trade_data(trade_data)
            
                # イベント初期化
                self.strategy.initialize_trade_decision()
            
                # 一定の待ち時間を設けてループを繰り返す。キャッシュベース時は即時処理（sleepなし）
                if back_test_mode == 0 and not use_cached_hot_test:
                    time.sleep(self.bot_operation_cycle)

                # 2時間ごとにファイルを分けるかチェック
                if back_test_mode == 0:
                    current_time = datetime.now()
                else:
                    current_time = datetime.fromtimestamp(self.price_data_management.get_latest_close_time())

                # メモリ監視ログ（リアルタイムモード、1時間ごと）
                if back_test_mode == 0:
                    current_timestamp = time.time()
                    if current_timestamp - last_memory_check > memory_check_interval:
                        try:
                            import psutil
                            process = psutil.Process()
                            mem_info = process.memory_info()
                            mem_percent = process.memory_percent()
                            self.logger.log(f"【メモリ監視】 RSS: {mem_info.rss / 1024 / 1024:.2f}MB, VMS: {mem_info.vms / 1024 / 1024:.2f}MB, 使用率: {mem_percent:.2f}%")
                            last_memory_check = current_timestamp
                        except Exception as e:
                            self.logger.log_error(f"メモリ監視エラー: {e}")
                if log_zipped == False and int(current_time.strftime("%H")) == 0 and int(current_time.strftime("%M")) == 0:
                    # 深夜0時に1日1回ログをローテート（以前は2時間ごとで細かすぎた）
                    self.logger.close_log_file()
                    self.logger.compress_logs()  # 圧縮
                    self.logger.open_log_file()
                    log_zipped = True
                else:
                    log_zipped = False

            except Exception as e:
                self.logger.log_error(f"メインループエラー: {e}")
                self.events.emit(EventType.LOOP_ERROR, {'error': str(e)})
                if back_test_mode == 0 and not use_cached_hot_test:
                    time.sleep(self.bot_operation_cycle)

    def execute_order(self, order, decision='ENTRY'):
        """
        注文を実行します。

        指値注文戦略を使用してエントリー・決済を実行。
        ダミーモード（hot_test_dummy_mode = 1）では、実際の取引は行われません。

        Args:
            order (dict): トレード判断に基づいた注文情報
                - symbol: 取引ペア（例: 'BTC/USD'）
                - side: 'BUY' または 'SELL'（内部表記）
                - quantity: 注文数量
                - price: 注文価格（market注文時は無視）
                - order_type: 'limit' または 'market'
            decision (str): 取引決定種別 'ENTRY'/'ADD'/'EXIT'

        Returns:
            dict: 注文の実行結果
        """
        from side import to_exchange_side
        
        symbol = order['symbol'] # execute orderには使わない
        side = order['side']
        quantity = order['quantity']
        order_type = order['order_type']
        if order_type == 'limit':
            price = order['price']
        else:
            price = 0

        try:
            # 現在値を取得
            current_price = self.price_data_management.get_ticker()
            
            # 内部表記 'BUY'/'SELL' を取引所API用の 'buy'/'sell' に変換
            exchange_side = to_exchange_side(side)
            if exchange_side in ['buy', 'sell']:
                if decision == 'EXIT':
                    # 決済注文: reduceOnly=Trueで既存ポジションのみクローズ
                    order_response = self.exchange.execute_exit_order(
                        side=exchange_side,
                        quantity=quantity
                    )
                    self.logger.log(f"✅ 決済注文実行: {exchange_side.upper()} {quantity} @ {current_price:.2f}")
                else:
                    # エントリー/追加注文
                    order_response = self.exchange.execute_entry_order(
                        side=exchange_side,
                        quantity=quantity,
                        current_price=current_price
                    )
                    self.logger.log(f"✅ エントリー注文実行: {exchange_side.upper()} {quantity} @ {current_price:.2f}")
            else:
                # 予期しないサイドの場合
                self.logger.log_error(f"❌ 不正なサイド: {side}")
                return False
            
            return order_response
            
        except Exception as e:
            self.logger.log_error(f"❌ 注文実行エラー: {str(e)}")
            # Task 40g: API障害通知
            self.alert.notify_api_failure("exchange", str(e), 0)
            return False

if __name__ == "__main__":
    # コマンドライン引数処理: python src/bot.py test 2024-01-01 2024-03-31
    if len(sys.argv) >= 4 and sys.argv[1] == "test":
        # バックテストモード: 日付範囲を動的に設定
        start_date = sys.argv[2]  # YYYY-MM-DD
        end_date = sys.argv[3]    # YYYY-MM-DD
        
        # Config に日付を設定（実行時上書き）
        Config._override_start_time = f"{start_date.replace('-', '/')} 00:00"
        Config._override_end_time = f"{end_date.replace('-', '/')} 23:59"
        
        # デバッグ用
        print(f"[バックテスト期間] {Config.get_start_time()} ~ {Config.get_end_time()}")
    
    # bot class test flag
    bot_order_test = False
    
    # 注文執行用の取引所クラスを初期化（ハイブリッド構成）
    exchange_type = Config.get_exchange_trade()
    if exchange_type == 'bitget':
        exchange = BitgetExchange(Config.get_bitget_api_key(), Config.get_bitget_api_secret(), Config.get_bitget_api_passphrase())
    else:  # デフォルトは bybit
        exchange = BybitExchange(Config.get_bybit_api_key(), Config.get_bybit_api_secret())

    # 資産管理クラスを初期化（初期資産を渡す）
    initial_balance = Config.get_account_balance()
    portfolio = Portfolio(initial_balance)
    
    # 価格情報クラスを初期化
    price_data_management = PriceDataManagement()

    # リスク戦略クラスを初期化
    risk_management = RiskManagement(price_data_management, portfolio)

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
