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
 
    def initialize_trade_decision(self):
        """
        trade_decision 辞書を初期化します。
        """
        self.trade_decision = {'decision': None, 'side': None, 'order_type': 'Market'}
 
    def evaluate_entry(self):
        """
        エントリー条件を評価し、エントリーするかどうかを決定します。

        条件:
        1. ポジションを保有していない
        2. ドンチャンチャネルブレイクが発生
        3. PVOが閾値範囲内
        """
        side = None
        decision = None
        
        # 保有状態を確認
        portfolio = self.portfolio.get_position_quantity()

        # ポジションがなかったら
        if portfolio["quantity"] == 0:

            # シグナルをチェック
            signals = self.price_data_management.get_signals()

            # PVO有効範囲チェック
            if signals["pvo"]["signal"] == True:
                # ドンチャンチャネルブレイク発生
                if signals["donchian"]["signal"] == True:
                    if signals["pvo"]["side"] == "BUY":
                        side = "BUY"
                        decision = "ENTRY"
                    elif signals["pvo"]["side"] == "SELL":
                        side = "SELL"
                        decision = "ENTRY"

            self.trade_decision["side"] = side
            self.trade_decision["decision"] = decision
            
        return
    
    def evaluate_add(self, price):
        """
        ピラミッド条件を評価し、買い増しするかどうかを決定します。

        条件:
        1. ポジションを保有している
        2. 追加レンジ幅が前回取得値を超過
        """
        side = None
        decision = None
        position_side = None

        portfolio = self.portfolio.get_position_quantity()
        
        # ポジション保有を確認
        if portfolio["quantity"] != 0:        
            # 保有状態を確認 
            position_side = self.portfolio.get_position_side()
            if position_side != None:
                # 追加レンジ幅を取得
                range = self.risk_manager.get_entry_range()
                
                # 前回取得値を取得
                last_entry_price = self.risk_manager.get_last_entry_price()
                
                # 価格がエントリー方向に基準レンジ分だけ進んだか判定する
                # TODO rangeはprice x ボラ x 2の値。妥当？
                if position_side == "BUY" and (price - last_entry_price) > range:
                    side = "BUY"
                    decision = "ADD"
                elif position_side == "SELL" and (last_entry_price - price) > range:
                    side = "SELL"
                    decision = "ADD"
            
                self.trade_decision["side"] = side
                self.trade_decision["decision"] = decision

        return

    def evaluate_exit(self):
        """
        エグジット条件を評価し、ポジションをクローズするかどうかを決定します。

        """
        side = None
        decision = None
        position_side = None

        # 保有状態を確認
        portfolio = self.portfolio.get_position_quantity()
        
        # ポジションがあったら
        if portfolio["quantity"] != 0:
            # ストップ値取得
            stop_price = self.risk_manager.get_stop_price()
            
            # 現在値取得
            price = self.price_data_management.get_ticker()
            
            # 現在値とストップ値比較
            position_side = self.portfolio.get_position_side()
            if position_side == "BUY":
                if price <= stop_price:
                    side = "SELL"
                    decision = "EXIT"
            elif position_side == "SELL":
                if price >= stop_price:
                    side = "BUY"
                    decision = "EXIT"

            self.trade_decision["side"] = side
            self.trade_decision["decision"] = decision

        return

    def make_trade_decision(self):
        """
        トレードの実行判断を行います。

        """
        price = self.price_data_management.get_ticker()
        
        self.evaluate_entry()
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

