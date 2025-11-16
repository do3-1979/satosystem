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
from pnl_reporter import generate_pnl_timeseries
from report_generator import generate_markdown_report

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
        # パフォーマンス計測用トラッカー
        self.perf = PerformanceTracker()

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
        while True:
            try:
                log_zipped = False
                trade_executed = False
                # タイムアウト監視（全体）
                if (perf_counter() - run_start) >= run_timeout:
                    self.logger.log_error(f"実行タイムアウト到達: {run_timeout} 秒。処理を終了します。")
                    # タイムアウト時も可能ならメトリクスを出力
                    try:
                        import json, os, time as _t
                        metrics = compute_metrics(self.pnl_history, self.trade_results)
                        log_dir = Config.get_log_dir_name()
                        ts = _t.strftime('%Y%m%d%H%M%S')
                        summary_path = os.path.join(log_dir, f"backtest_summary_{ts}.json")
                        with open(summary_path, 'w', encoding='utf-8') as f:
                            json.dump(metrics, f, ensure_ascii=False, indent=2)
                        perf_summary = self.perf.summary()
                        perf_path = os.path.join(log_dir, f"performance_summary_{ts}.json")
                        with open(perf_path, 'w', encoding='utf-8') as pf:
                            json.dump(perf_summary, pf, ensure_ascii=False, indent=2)
                        if self.pnl_history and self.close_times:
                            pnl_csv, pnl_json = generate_pnl_timeseries(self.pnl_history, self.close_times, log_dir, prefix="pnl_timeseries")
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
                            # EOB決済をPnL履歴へ追記
                            self.pnl_history.append(self.portfolio.get_profit_and_loss())
                            self.close_times.append(self.price_data_management.get_latest_close_time_dt())
                        
                        self.logger.log("-------------------------------------------------------")
                        self.logger.log(f"最終ポートフォリオ: {self.portfolio.get_position_quantity()}")
                        self.logger.log(f"最終損益: {self.portfolio.get_profit_and_loss():>4.0f} [BTC/USD]")
                        self.logger.log(f"プロフィットファクター: {self.portfolio.get_profit_factor():>4.2f}")
                        self.logger.log(f"最大ドローダウン: {self.portfolio.get_drawdown():>4.2f} [BTC/USD]")
                        self.logger.log(f"最大ドローダウン率: {self.portfolio.get_drawdown_rate():>4.2f} [%]")

                        # 追加メトリクス計算
                        metrics = compute_metrics(self.pnl_history, self.trade_results)
                        self.logger.log(f"Sharpe: {metrics['sharpe']:.3f}")
                        self.logger.log(f"WinRate: {metrics['win_rate']:.2f}% Trades: {metrics['trades']}")
                        # JSON出力
                        try:
                            import json, os, time as _t
                            log_dir = Config.get_log_dir_name()
                            ts = _t.strftime('%Y%m%d%H%M%S')
                            # メトリクス
                            summary_path = os.path.join(log_dir, f"backtest_summary_{ts}.json")
                            with open(summary_path, 'w', encoding='utf-8') as f:
                                json.dump(metrics, f, ensure_ascii=False, indent=2)
                            self.logger.log(f"バックテストサマリ出力: {summary_path} / パフォーマンス計測件数: {self.perf.iterations}")
                            # パフォーマンスサマリ
                            perf_summary = self.perf.summary()
                            perf_path = os.path.join(log_dir, f"performance_summary_{ts}.json")
                            with open(perf_path, 'w', encoding='utf-8') as pf:
                                json.dump(perf_summary, pf, ensure_ascii=False, indent=2)
                            self.logger.log(f"パフォーマンスサマリ出力: {perf_path}")
                            # PnL時系列出力
                            if self.pnl_history and self.close_times:
                                pnl_csv, pnl_json = generate_pnl_timeseries(self.pnl_history, self.close_times, log_dir, prefix="pnl_timeseries")
                                self.logger.log(f"PnL時系列出力 (CSV): {pnl_csv}")
                                self.logger.log(f"PnL時系列出力 (JSON): {pnl_json}")
                                # レポート自動生成 (Markdown)
                                try:
                                    report_md = generate_markdown_report(
                                        metrics=metrics,
                                        perf_summary=perf_summary,
                                        output_dir=log_dir,
                                        ts=ts,
                                        pnl_csv_path=pnl_csv,
                                        pnl_json_path=pnl_json,
                                        extra_notes=None,
                                    )
                                    self.logger.log(f"レポート出力 (Markdown): {report_md}")
                                except Exception as re:
                                    self.logger.log_error(f"レポート出力失敗: {re}")
                        except Exception as e:
                            self.logger.log_error(f"バックテストメトリクス/パフォーマンス/PnL出力失敗: {e}")
                        
                        self.logger.close_log_file()
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
                    elif trade_decision["decision"] == "ENTRY" or trade_decision["decision"] == "ADD":
                        self.portfolio.add_position_quantity(quantity, trade_decision["side"], price)
                        # 前回のエントリ価格を更新
                        self.risk_management.update_last_entry_price(price)
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
                # ログに記録
                # --------------------------------------------
                t_logging_start = perf_counter()
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

                # 取引データを表示
                # if back_test_mode == 0:
                self.show_trade_data(trade_data)
                # 取引データを記録
                self.logger.log_trade_data(trade_data)
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
                    # ログをローテート
                    self.logger.close_log_file()
                    self.logger.compress_logs()  # 圧縮
                    self.logger.open_log_file()
                    log_zipped = True
                else:
                    log_zipped = False

            except Exception as e:
                self.logger.log_error(f"メインループエラー: {e}")
                self.events.emit(EventType.LOOP_ERROR, {'error': str(e)})
                if back_test_mode == 0:
                    time.sleep(self.bot_operation_cycle)

    def execute_order(self, order):
        """
        注文を実行します。

        Args:
            trade_decision (dict): トレード判断に基づいた注文情報

        Returns:
            dict: 注文の実行結果
        """
        symbol = order['symbol'] # execute orderには使わない
        side = order['side']
        quantity = order['quantity']
        order_type = order['order_type']
        if order_type == 'limit':
            price = order['price']
        else:
            price = 0

        # TODO テスト処理
        order_response = 0
        #order_response = self.exchange.execute_order(side, quantity, price, order_type)
        return order_response

if __name__ == "__main__":
    # bot class test flag
    bot_order_test = False
    
    # 取引所クラスを初期化
    exchange = BybitExchange(Config.get_api_key(), Config.get_api_secret())

    # 資産管理クラスを初期化
    portfolio = Portfolio()
    
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
