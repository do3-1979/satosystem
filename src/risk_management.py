"""
RiskManagementクラス:

リスク管理戦略を実装します。許容リスク、損失制限、ポジションサイズの制限など、リスクに関するルールを設定します。

このサンプルコードでは、RiskManagementクラスがリスク許容度とアカウント残高をもとにポジションサイズを計算するメソッドを提供しています。
リスク許容度は取引で許容するリスクの割合を示し、アカウント残高は取引に使用できる資金を表します。
計算されたポジションサイズは、エントリー価格とストップロス価格からリスク管理の観点で適切なサイズを計算します。

必要に応じて、リスク許容度やアカウント残高の設定を変更し、ポジションサイズを計算できます。また、このクラスを拡張してさまざまなリスク管理戦略を実装できます。
"""
from config import Config
from logger import Logger
from price_data_management import PriceDataManagement
from bybit_exchange import BybitExchange
from portfolio import Portfolio
import time

class RiskManagement:
    def __init__(self, price_data_management, portfolio):
        """
        リスク管理クラスを初期化します。

        """
        self.logger = Logger()
        self.price_data_management = price_data_management
        self.portfolio = portfolio
        self.risk_percentage = Config.get_risk_percentage()
        self.account_balance = Config.get_account_balance()

        self.lot_limit_lower = Config.get_lot_limit_lower()
        self.balance_tether_limit = Config.get_balance_tether_limit()
        self.capital_exhausted = False
        
        # 分割制御
        self.leverage = Config.get_leverage()
        self.entry_times = Config.get_entry_times()
        self.entry_range = Config.get_entry_range()
        self.position_size = 0 
        self.total_size = 0
        # ストップ制御
        self.initial_stop_range = Config.get_stop_range() # ボラを基準としたサイズ
        self.stop_AF = Config.get_stop_AF()
        self.stop_AF_add = Config.get_stop_AF_add()
        self.stop_AF_max = Config.get_stop_AF_max()
        self.surge_follow_price_ratio = Config.get_surge_follow_price_ratio()
        self.stop_ATR = 0

        # ストップ値
        self.stop_offset = 0 # 価格ベース
        self.stop_price = 0 # 価格ベース
        self.last_entry_price = 0 # 価格ベース
    
    def get_entry_range(self):
        
        return self.entry_range * self.position_size

    def get_last_entry_price(self):
        
        # TODO 値更新
        return self.last_entry_price

    def update_risk_status(self):
        
        self.__update_stop_price()
        
        return

    def get_stop_price(self):
        
        return self.stop_price

    # パラボリックSARを計算する関数
    def __calc_parabolic_sar(self, data):
        iaf = self.stop_AF_add
        maxaf = self.stop_AF_max

        # データ成型
        high = []
        low = []
        close = []
        psar = []

        datalen = len(data)

        for i in range(0,datalen):
            high.append(data[i]['high_price'])
            low.append(data[i]['low_price'])
            close.append(data[i]['close_price'])
            psar = close

        length = len(close)

        psarbull = [None] * length
        psarbear = [None] * length
        bull = True
        af = iaf
        ep = low[0]
        hp = high[0]
        lp = low[0]

        # 過去データからPSARを計算
        for i in range(2,length):
            if bull:
                psar[i] = psar[i - 1] + af * (hp - psar[i - 1])
            else:
                psar[i] = psar[i - 1] + af * (lp - psar[i - 1])

            reverse = False

            if bull:
                if low[i] < psar[i]:
                    bull = False
                    reverse = True
                    psar[i] = hp
                    lp = low[i]
                    af = iaf
            else:
                if high[i] > psar[i]:
                    bull = True
                    reverse = True
                    psar[i] = lp
                    hp = high[i]
                    af = iaf

            if not reverse:
                if bull:
                    if high[i] > hp:
                        hp = high[i]
                        af = min(af + iaf, maxaf)
                    if low[i - 1] < psar[i]:
                        psar[i] = low[i - 1]
                    if low[i - 2] < psar[i]:
                        psar[i] = low[i - 2]
                else:
                    if low[i] < lp:
                        lp = low[i]
                        af = min(af + iaf, maxaf)
                    if high[i - 1] > psar[i]:
                        psar[i] = high[i - 1]
                    if high[i - 2] > psar[i]:
                        psar[i] = high[i - 2]
            
            if bull:
                psarbull[i] = psar[i]
            else:
                psarbear[i] = psar[i]

        return {"psar":psar, "psarbear":psarbear, "psarbull":psarbull}

    # ストップ値をパラボリックASRにする関数
    # ポジションのBUY/SELLに応じてパラボリックSARの値をストップポジションとする
    def __calc_stop_psar(self, data):
        # 現在のストップレンジ
        prev_stop_offset = self.stop_offset
        # 現在の平均取得単価
        # TODO ポートフォリオから取得
        position_price = 00000

        sar_result = self.__calc_parabolic_sar( data )
        psarbull = sar_result["psarbull"][-1]
        psarbear = sar_result["psarbear"][-1]

        # BUYの時は現在値からpsarbullの差をstopとする。SELLはpserbear
        if self.portfolio.get_position_side() == "BUY" and psarbull != None:
            tmp_stop_offset = round(position_price - psarbull)
        if self.portfolio.get_position_side() == "SELL" and psarbear != None:
            tmp_stop_offset = round(psarbear - position_price)
        
        # 現在のstopより大きければ維持
        stop = min( prev_stop_offset, tmp_stop_offset )

        return stop

    def __follow_price_surge(self, price):
        # ストップ値は「ポジションの取得単価」に対する差額。ポジション取得単価より高い場合は負値。
        # 現在の終値との差額を求めてから新しいストップ値を求める
        prev_stop_offset = self.stop_offset
        surge_follow_price = self.surge_follow_price_ratio * price
        position_price = self.portfolio.get_position_price()

        # 終値とストップ値の差額を出す
        if self.portfolio.get_position_side() == "BUY":
            diff_price = price - ( position_price - prev_stop_offset )
            # 終値との差分が固定値を超えていたらストップ値が固定値以下になるようにする
            if diff_price > surge_follow_price:
                # 新ストップ値はポジション取得単価と目標価格との差額
                tmp_stop_offset = position_price - ( price - surge_follow_price )

        if self.portfolio.get_position_side() == "SELL":
            diff_price = ( position_price + prev_stop_offset ) - price
            # 終値との差分が固定値を超えていたらストップ値が固定値以下になるようにする
            if diff_price > surge_follow_price:
                # 新ストップ値 = 目標値 ( = 現在の終値 + 固定値) とポジション取得単価の差額
                tmp_stop_offset = ( price + surge_follow_price ) - position_price

        return tmp_stop_offset

    def __update_stop_price(self):
        # 現在のstop値取得
        prev_stop_offset = self.stop_offset
          
        # ポジションがある場合
        position = self.portfolio.get_position_quantity()
        quantity = position["quantity"]
        
        if quantity != 0:
            # パラボリックSAR計算
            ohlcv_data = self.price_data_management.get_ohlcv_data()
            psar_stop_offset = self.__calc_stop_psar(ohlcv_data)

            # チャートに依存せず急騰時に追従する
            price = self.price_data_management.get_ticker()
            price_surge_stop_offset = self.__follow_price_surge(ohlcv_data, price)

            # 現在値からレンジ幅でストップ値を計算
            self.stop_offset = min(prev_stop_offset, psar_stop_offset, price_surge_stop_offset)
        
        return

    def calculate_position_size(self, balance_tether, price):
        """
        ポジションサイズ[通貨単位]を計算します。

        Args:
            entry_price (float): エントリー価格
            stop_loss_price (float): ストップロス価格

        Returns:
            float: ポジションサイズ
        """
        position_size = 0

        # 口座残高が最低額を下回ったらエラーとする
        if balance_tether < self.balance_tether_limit:
            self.logger.log_error(f"証拠金{balance_tether}が最低額{self.balance_tether_limit}を下回ったので発注できません")
            self.capital_exhausted = True
        else:
            # 初回のstop値を計算
            # ボラティリティの幅からストップ幅を計算
            volatility = self.price_data_management.get_volatility()
            stop_range = self.initial_stop_range * volatility
            # 総購入数は、総資産 x 失っていい割合 / ボラティリティで動きうる幅で決定
            total_size = round( ( balance_tether * 100 * self.risk_percentage / stop_range / 100 ), 7 )
            # 分割購入するので1買い当たりのサイズに変換
            tmp_size = round( ( total_size * 100 / self.entry_times / 100 ) , 7 )

            # TODO stop値計算に移動
            # self.stop_range = stop_range
            # self.stop_ATR = round( volatility )

            """
            out_log("現在のアカウント残高は{0}USDです\n".format( round(balance,2) ), flag)
            out_log("許容リスクから購入できる枚数は最大{0}lotまでです\n".format( round(calc_lot,4) ), flag)
            out_log("{0}回に分けて{1}lotずつ注文します\n".format( entry_times, round(flag["add-position"]["unit-size"],7 ) ), flag)
            """

            """
            # ２回目以降のエントリーの場合
            else:
                # 現在の証拠金から購入済枚数費用を引いた額
                # 証拠金 - 枚数に必要な証拠金数 / レバレッジ
                balance = round( balance - flag["position"]["price"] * flag["position"]["lot"] / levarage )
            """

            # 証拠金から購入可能な上限を得る
            max_size = round( ( balance_tether * self.leverage  * 100 / price / 100 ) , 7 )
            # 分割サイズを購入可能上限未満にする
            position_size = min(max_size, tmp_size)
            # クラスに記憶
            self.position_size = position_size
            # 購入可能上限に分割数をかけたものが総購入サイズ
            self.total_size = position_size * self.entry_times

        return position_size

if __name__ == "__main__":
    # RiskManagement クラスの初期化
    exchange = BybitExchange(Config.get_api_key(), Config.get_api_secret())
    price_data_management = PriceDataManagement()
    risk_manager = RiskManagement(price_data_management)

    # 最新の値を取得
    price = exchange.fetch_ticker()
    # 最新の口座を取得
    balance = exchange.get_account_balance()
    # BTCのused、free、total情報を表示
    #usd_balance = balance['BTC']['free']
    #balance_tether = balance * price 
    balance_tether = 200

    # 取引情報を決定
    price_data_management.update_price_data()

    # ポジションサイズを計算
    position_size = risk_manager.calculate_position_size(balance_tether, price)
    print(f'Position Size: {position_size}')
