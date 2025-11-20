"""
TradingStrategyクラス:

このクラスはトレーディング戦略を表現します。トレーディングアルゴリズムを実装し、エントリーポイントと出口ポイントを決定します。
異なる戦略をサポートするために、複数の戦略クラスを作成し、戦略の切り替えが可能になるようにします。

TradingStrategyクラスはエントリー条件とエグジット条件を評価してポジションの管理を行います。
エントリー条件とエグジット条件は価格データに対して評価され、
条件を満たす場合にポジションの開始やクローズなどの操作を行います。

必要に応じて、エントリー条件とエグジット条件をカスタマイズし、自分の取引戦略に合わせて設定できます。
また、このクラスを拡張してさまざまな取引戦略を実装できます。
"""
from logger import Logger
from config import Config
from price_data_management import PriceDataManagement
from risk_management import RiskManagement
from portfolio import Portfolio

class TradingStrategy:
    """
    トレーディング戦略を表現するクラス。

    このクラスはトレーディングアルゴリズムを実装し、エントリーポイントと出口ポイントを決定します。
    異なる戦略をサポートするために、複数の戦略クラスを作成し、戦略の切り替えが可能になるようにします。

    TradingStrategyクラスはエントリー条件、ピラミッディング条件、エグジット条件を評価してポジションの管理を行います。
    エントリー条件とエグジット条件は価格データに対して評価され、条件を満たす場合にポジションの開始やクローズなどの操作を行います。

    Attributes:
        position (dict): ポジション情報を格納する辞書

    """

    def __init__(self, price_data_management, risk_manager, portfolio):
        self.logger = Logger()
        self.trade_decision = ()
        self.price_data_management = price_data_management
        self.risk_manager = risk_manager
        self.portfolio = portfolio
        self.initialize_trade_decision()
        
        # 重複ログ抑制用フラグ
        self._add_limit_logged = False  # ADD上限到達ログ表示済みフラグ
        self._last_keltner_filter_log = 0  # 最後にKeltnerフィルタログを出力した時刻（秒）
 
    def initialize_trade_decision(self):
        """
        trade_decision 辞書を初期化します。
        """
        self.trade_decision = {'decision': 'NONE', 'side': 'NONE', 'order_type': 'market'}
 
    def evaluate_entry(self):
        """
        エントリー条件を評価し、エントリーするかどうかを決定します。

        Phase B条件:
        1. ポジションを保有していない
        2. PVOが閾値範囲内
        3. ドンチャンチャネルブレイクが発生
        4. Keltner幅が拡大中
        5. 中央線へプルバック後に再上昇/再下落
        """
        side = 'NONE'
        decision = 'NONE'

        signals = self.price_data_management.get_signals()

        # PVO有効範囲チェック
        if signals["pvo"]["signal"] == True:
            # ドンチャンチャネルブレイク発生
            if signals["donchian"]["signal"] == True:
                # Keltnerフィルタチェック（アクション1: トグル可能）
                keltner_enabled = Config.get_keltner_enabled()
                keltner_pass = True
                if keltner_enabled and "keltner" in signals:
                    keltner_pass = signals["keltner"]["signal"]
                    if not keltner_pass:
                        # Keltnerフィルタログは10分（600秒）ごとに出力
                        # バックテストモードでは価格データの時刻を使用
                        current_time = self.price_data_management.get_latest_close_time()
                        if current_time - self._last_keltner_filter_log >= 600:
                            self.logger.log(f"[条件判定:ENTRY] Keltnerフィルタで除外 (10分ごと表示)")
                            self._last_keltner_filter_log = current_time

                # Phase B: Donchian + PVO + Keltner(オプション)
                if keltner_pass:
                    donchian_side = signals["donchian"]["side"]
                    if donchian_side == "BUY":
                        self.logger.log(f"[条件判定:ENTRY] BUY成立 (Donchian + PVO + Keltner={keltner_enabled})")
                        side = "BUY"
                        decision = "ENTRY"
                        # 新規エントリー時にフラグリセット
                        self._add_limit_logged = False
                    elif donchian_side == "SELL":
                        self.logger.log(f"[条件判定:ENTRY] SELL成立 (Donchian + PVO + Keltner={keltner_enabled})")
                        side = "SELL"
                        decision = "ENTRY"
                        # 新規エントリー時にフラグリセット
                        self._add_limit_logged = False

        self.trade_decision["side"] = side
        self.trade_decision["decision"] = decision
            
        return
    
    def evaluate_add(self, price):
        """
        ピラミッド条件を評価し、買い増しするかどうかを決定します。

        Phase C条件:
        1. ポジションを保有している
        2. 追加回数3回未満
        3. entry_rangeレンジ内のみ追加
        """
        side = 'NONE'
        decision = 'NONE'
  
        position_side = self.portfolio.get_position_side()
        
        if position_side != 'NONE':
            # Phase C: entry_times回上限チェック
            add_count = getattr(self.portfolio, 'add_count', 0)
            max_entries = Config.get_entry_times()
            if add_count >= max_entries:
                # 初回のみログ出力
                if not self._add_limit_logged:
                    self.logger.log(f"[条件判定:ADD] 上限到達 add_count={add_count}, max={max_entries}")
                    self._add_limit_logged = True
                return

            # 追加レンジ幅を取得
            range_val = self.risk_manager.get_add_range()
            last_entry_price = self.risk_manager.get_last_entry_price()
            
            # 価格がエントリー方向に基準レンジ分だけ進んだか判定する
            if position_side == "BUY" and (price - last_entry_price) > range_val:
                self.logger.log(f"[条件判定:ADD] 価格変動 {(price - last_entry_price):.2f} が変動幅 {range_val:.2f} を超過")
                side = "BUY"
                decision = "ADD"
                self.trade_decision["side"] = side
                self.trade_decision["decision"] = decision
                self.portfolio.add_count = add_count + 1  # Phase C: 回数カウント

            elif position_side == "SELL" and (last_entry_price - price) > range_val:
                self.logger.log(f"[条件判定:ADD] 価格変動 {(last_entry_price - price):.2f} が変動幅 {range_val:.2f} を超過")
                side = "SELL"
                decision = "ADD"
                self.trade_decision["side"] = side
                self.trade_decision["decision"] = decision
                self.portfolio.add_count = add_count + 1  # Phase C: 回数カウント

        return

    def evaluate_exit(self):
        """
        エグジット条件を評価し、ポジションをクローズするかどうかを決定します。

        Phase D条件:
        1. ストップロス判定
        2. 利益率>10%で50%部分決済
        """
        side = 'NONE'
        decision = 'NONE'
        position_side = 'NONE'

        stop_price = self.risk_manager.get_stop_price()
        
        price = self.price_data_management.get_latest_ohlcv()
        high_price = price['high_price']
        low_price = price['low_price']
        close_price = price['close_price']
        
        position_side = self.portfolio.get_position_side()

        # Phase D: 部分決済チェック（利益率>10%で半分決済）
        # TODO: bot.pyでPARTIAL_EXIT処理を実装後に有効化
        # if position_side != 'NONE':
        #     avg_entry = self.risk_manager.get_average_entry_price()
        #     partial_closed = getattr(self.portfolio, 'partial_closed', False)
        #     if not partial_closed and avg_entry > 0:
        #         profit_rate = 0
        #         if position_side == "BUY":
        #             profit_rate = (close_price - avg_entry) / avg_entry
        #         elif position_side == "SELL":
        #             profit_rate = (avg_entry - close_price) / avg_entry
        #
        #         if profit_rate > 0.10:
        #             self.logger.log(f"[条件判定:PARTIAL_EXIT] 利益率 {profit_rate*100:.2f}% で50%決済")
        #             side = "SELL" if position_side == "BUY" else "BUY"
        #             decision = "PARTIAL_EXIT"
        #             self.trade_decision["side"] = side
        #             self.trade_decision["decision"] = decision
        #             self.portfolio.partial_closed = True
        #             return

        #-------------------------------------------------------
        # 現在値とストップ値比較
        #-------------------------------------------------------
        if position_side == "BUY":
            if close_price <= stop_price:
                self.logger.log(f"[条件判定:EXIT] 現在値 {close_price:.2f} がストップ値 {stop_price:.2f} を割り込みました")
                side = "SELL"
                decision = "EXIT"
                self.trade_decision["side"] = side
                self.trade_decision["decision"] = decision
                # ポジションクローズ時にフラグリセット
                self._add_limit_logged = False

        elif position_side == "SELL":
            if close_price >= stop_price:
                self.logger.log(f"[条件判定:EXIT] 現在値 {close_price:.2f} がストップ値 {stop_price:.2f} を超過しました")
                side = "BUY"
                decision = "EXIT"
                self.trade_decision["side"] = side
                self.trade_decision["decision"] = decision
                # ポジションクローズ時にフラグリセット
                self._add_limit_logged = False

        return

    def make_trade_decision(self):
        """
        トレードの実行判断を行います。

        """
        portfolio = self.portfolio.get_position_quantity()
        
        # エントリ・買い増し直後に離脱しないように
        if portfolio["quantity"] == 0:        
            self.evaluate_entry()
        else:
            price = self.price_data_management.get_ticker()
            
            self.evaluate_add(price)
            self.evaluate_exit()
 
        return self.trade_decision
    
    def __str__(self):
        return f"Trade Decision: Decision = {self.trade_decision['decision']}, Side = {self.trade_decision['side']}, Order Type = {self.trade_decision['order_type']}"

if __name__ == "__main__":
    # TradingStrategyクラスの初期化
    portfolio = Portfolio()
    price_data_management = PriceDataManagement()
    risk_manager = RiskManagement(price_data_management, portfolio)
    strategy = TradingStrategy(price_data_management, risk_manager, portfolio)

    # 取引情報を決定
    print(strategy)

