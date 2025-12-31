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
        # 約定履歴カウント (勝率計算用)
        self.trade_results = []  # list of bool win( True ) / loss( False )

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
                if back_test_mode == 1:
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

                        # 追加メトリクス計算
                        metrics = compute_metrics(self.pnl_history, self.trade_results)
                        self.logger.log(f"Sharpe: {metrics['sharpe']:.3f}")
                        self.logger.log(f"WinRate: {metrics['win_rate']:.2f}% Trades: {metrics['trades']}")
                        # JSON出力
                        try:
                            import json, os, time as _t
                            log_dir = Config.get_log_dir_name()
                            ts = _t.strftime('%Y%m%d%H%M%S')
                            summary_path = os.path.join(log_dir, f"backtest_summary_{ts}.json")
                            with open(summary_path, 'w', encoding='utf-8') as f:
                                json.dump(metrics, f, ensure_ascii=False, indent=2)
                            self.logger.log(f"バックテストサマリ出力: {summary_path}")
                        except Exception as e:
                            self.logger.log_error(f"バックテストメトリクス出力失敗: {e}")
                        
                        self.logger.close_log_file()
                        self.logger.log("--- BOT END -------------------------------------------")
                        break
                else:
                    self.price_data_management.update_price_data()
                
                # 取得情報を表示
                # self.price_data_management.show_latest_ohlcv()
                # 最新価格を取得
                price = self.price_data_management.get_ticker()

                # 取引所から口座残高を取得
                if back_test_mode == 1:
                    # バックテスト: 初期資産 + 累積損益
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
                        order_response = self.execute_order(order.to_dict())
                        #self.logger.log(f"注文実行: {order_response}")
                        self.events.emit(EventType.ORDER_EXECUTED, order.to_dict())
                    except Exception as e:
                        self.logger.log_error(f"注文実行エラー: {e}")
                        continue  # 注文失敗時はポートフォリオ更新をスキップ

                    # --------------------------------------------
                    # portfolio更新
                    # --------------------------------------------
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
            
                # 一定の待ち時間を設けてループを繰り返す
                if back_test_mode == 0:
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

        指値注文戦略を使用してエントリー・決済を実行。
        ダミーモード（hot_test_dummy_mode = 1）では、実際の取引は行われません。

        Args:
            order (dict): トレード判断に基づいた注文情報
                - symbol: 取引ペア（例: 'BTC/USD'）
                - side: 'BUY' または 'SELL'（内部表記）
                - quantity: 注文数量
                - price: 注文価格（market注文時は無視）
                - order_type: 'limit' または 'market'

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
            
            # エントリー注文と決済注文を判定
            # 内部表記 'BUY'/'SELL' を取引所API用の 'buy'/'sell' に変換
            exchange_side = to_exchange_side(side)
            if exchange_side in ['buy', 'sell']:
                # エントリー注文：指値で約定を狙う
                # 失敗時は成行にフォールバック
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
            return False

if __name__ == "__main__":
    # bot class test flag
    bot_order_test = False
    
    # 取引所クラスを初期化（動的に選択）
    exchange_type = Config.get_exchange()
    if exchange_type == 'bitget':
        exchange = BitgetExchange(Config.get_api_key(), Config.get_api_secret(), Config.get_api_passphrase())
    else:  # デフォルトは bybit
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
