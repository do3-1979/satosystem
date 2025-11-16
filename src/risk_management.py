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
import numpy as np

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
        self.add_range = 0
        self.position_size = 0 
        self.total_size = 0
        # ストップ制御
        self.initial_stop_range = Config.get_stop_range() # ボラを基準としたサイズ
        self.stop_AF = Config.get_stop_AF()
        self.stop_AF_add = Config.get_stop_AF_add()
        self.stop_AF_max = Config.get_stop_AF_max()
        self.stop_AF_add = Config.get_stop_AF_add()
        self.stop_AF_max = Config.get_stop_AF_max()
        self.surge_follow_price_ratio = Config.get_surge_follow_price_ratio()
        self.stop_ATR = 0

        # PSAR
        self.psar = []
        self.psarbull = []
        self.psarbear = []

        # ADX
        self.adx = []
        self.adx_bull = False
        self.adx_bear = False
        self.adx_term = 14
        self.adx_continue_num = 3
        self.adx_bull_threshold = 25
        self.adx_bear_threshold = 20

        # ストップ値
        self.stop_offset = 0 # 価格ベース
        self.stop_price = 0 # 価格ベース
        self.last_entry_price = 0 # 価格ベース
    
    def get_entry_range(self):
        return self.entry_range

    def get_add_range(self):
        return self.add_range

    def get_last_entry_price(self):
        return self.last_entry_price

    def update_last_entry_price(self, price):
        self.last_entry_price = price
        return

    def update_risk_status(self):
        self.__update_stop_price()
        return

    def get_stop_price(self):
        return self.stop_price
    
    def get_position_size(self):
        return self.position_size
        
    def get_total_size(self):
        return self.total_size

    def get_stop_offset(self):
        return self.stop_offset    

    def get_psar(self):
        return self.psar[-1]
    
    def get_psarbull(self):
        return self.psarbull[-1]
    
    def get_psarbear(self):
        return self.psarbear[-1]

    def get_adx(self):
        return self.adx[-1]
    
    def get_adx_bull(self):
        return self.adx_bull
    
    def get_adx_bear(self):
        return self.adx_bear

    def get_psar_stop_offset(self):
        return self.psar_stop_offset
    
    def get_price_surge_stop_offset(self):
        return self.price_surge_stop_offset

    # パラボリックSARを計算する関数
    def __calc_parabolic_sar(self, data):
        iaf = self.stop_AF_add
        maxaf = self.stop_AF_max

        # データ成型
        high = []
        low = []
        close = []
        datalen = len(data)

        for i in range(datalen):
            high.append(data[i]['high_price'])
            low.append(data[i]['low_price'])
            close.append(data[i]['close_price'])

        length = len(close)
        psar = [None] * length

        # 初回のpsarの初期設定
        if not self.psar:
            psar[0] = close[0]
            psar[1] = close[0]
        else:
            for i in range(min(length, len(self.psar))):
                psar[i] = self.psar[i]

        length = len(close)
        #print(f"length {length}")

        psarbull = [None] * length
        psarbear = [None] * length
        bull = True
        af = iaf
        ep = low[0]
        hp = high[0]
        lp = low[0]

        #print(f"psar[0] {psar[0]} af {af} ep {ep} hp {hp} lp {lp}")

        # 過去データからPSARを計算
        for i in range(2, length):
            if bull:
                psar[i] = psar[i - 1] + af * (hp - psar[i - 1])
            else:
                psar[i] = psar[i - 1] + af * (lp - psar[i - 1])
            #print(f"psar[{i}] {psar[i]}")

            reverse = False

            if bull:
                if low[i] < psar[i]:
                    bull = False
                    reverse = True
                    psar[i] = hp
                    lp = low[i]
                    af = iaf

                    #print(f"reverse bull psar[{i}] {psar[i]}")

            else:
                if high[i] > psar[i]:
                    bull = True
                    reverse = True
                    psar[i] = lp
                    hp = high[i]
                    af = iaf

                    #print(f"reverse bear psar[{i}] {psar[i]}")

            if not reverse:
                if bull:
                    if high[i] > hp:
                        hp = high[i]
                        af = min(af + iaf, maxaf)
                    if low[i - 1] < psar[i]:
                        psar[i] = low[i - 1]
                    if low[i - 2] < psar[i]:
                        psar[i] = low[i - 2]
                        
                    #print(f"not reverse bull psar[{i}] {psar[i]}")
                        
                else:
                    if low[i] < lp:
                        lp = low[i]
                        af = min(af + iaf, maxaf)
                    if high[i - 1] > psar[i]:
                        psar[i] = high[i - 1]
                    if high[i - 2] > psar[i]:
                        psar[i] = high[i - 2]

                    #print(f"not reverse bear psar[{i}] {psar[i]}")

            if bull:
                psarbull[i] = psar[i]
            else:
                psarbear[i] = psar[i]

        # PSAR更新
        self.psar = psar
        self.psarbull = psarbull
        self.psarbear = psarbear

        return

    def __calc_adx(self, data):
        adx_period = self.adx_term
        continue_num = self.adx_continue_num
        bull_threshold = self.adx_bull_threshold
        bear_threshold = self.adx_bear_threshold
        
        high = [item['high_price'] for item in data]
        low = [item['low_price'] for item in data]
        close = [item['close_price'] for item in data]
        length = len(close)

        plus_dm = np.zeros(length)
        minus_dm = np.zeros(length)
        tr = np.zeros(length)

        for i in range(1, length):
            high_diff = high[i] - high[i - 1]
            low_diff = low[i - 1] - low[i]

            plus_dm[i] = high_diff if high_diff > low_diff and high_diff > 0 else 0
            minus_dm[i] = low_diff if low_diff > high_diff and low_diff > 0 else 0

            tr[i] = max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1]))

        tr_smooth = np.zeros(length)
        plus_dm_smooth = np.zeros(length)
        minus_dm_smooth = np.zeros(length)

        tr_smooth[adx_period - 1] = sum(tr[1:adx_period])
        plus_dm_smooth[adx_period - 1] = sum(plus_dm[1:adx_period])
        minus_dm_smooth[adx_period - 1] = sum(minus_dm[1:adx_period])

        for i in range(adx_period, length):
            tr_smooth[i] = tr_smooth[i - 1] - (tr_smooth[i - 1] / adx_period) + tr[i]
            plus_dm_smooth[i] = plus_dm_smooth[i - 1] - (plus_dm_smooth[i - 1] / adx_period) + plus_dm[i]
            minus_dm_smooth[i] = minus_dm_smooth[i - 1] - (minus_dm_smooth[i - 1] / adx_period) + minus_dm[i]

        plus_di = 100 * (plus_dm_smooth / tr_smooth)
        minus_di = 100 * (minus_dm_smooth / tr_smooth)
        dx = 100 * np.abs((plus_di - minus_di) / (plus_di + minus_di))

        adx = np.zeros(length)
        adx[adx_period - 1] = sum(dx[adx_period - 1:2 * adx_period - 1]) / adx_period

        for i in range(adx_period, length):
            adx[i] = ((adx[i - 1] * (adx_period - 1)) + dx[i]) / adx_period

        self.adx = adx.tolist()

        self.adx_bull = all(adx[i] > bull_threshold for i in range(-continue_num, 0))
        self.adx_bear = all(adx[i] < bear_threshold for i in range(-continue_num, 0))
        
        return

    def __calc_stop_psar(self):
        """
        ストップ値をパラボリックASRにする関数
        
        ポジションのBUY/SELLに応じてパラボリックSARの値をストップポジションとする
        """

        # 現在のストップレンジ
        prev_stop_offset = self.stop_offset

        psarbull = self.get_psarbull()
        psarbear = self.get_psarbear()

        # 現在の平均取得単価
        position_price = self.portfolio.get_position_price()
        tmp_stop_offset = prev_stop_offset

        #tmp_stop_offsetb = round(position_price - psarbull)
        #tmp_stop_offsets = round(psarbear - position_price)
        #print(f"prev_stop_offset: {prev_stop_offset} position_price: {position_price} psarbull {psarbull} psarbear {psarbear} BUY diff {tmp_stop_offsetb} SELL diff {0}")
        # BUYの時は現在値からpsarbullの差をstopとする。SELLはpserbear
        if self.portfolio.get_position_side() == "BUY" and psarbull != None:
            tmp_stop_offset = round(position_price - psarbull)

        if self.portfolio.get_position_side() == "SELL" and psarbear != None:
            tmp_stop_offset = round(psarbear - position_price)

        self.psar_stop_offset = tmp_stop_offset

        # 現在のstopより大きければ維持
        stop = min( prev_stop_offset, tmp_stop_offset )

        return stop

    def __follow_price_surge(self, price):
        # ストップ値は「ポジションの取得単価」に対する差額。ポジション取得単価より高い場合は負値。
        # 現在の終値との差額を求めてから新しいストップ値を求める
        prev_stop_offset = self.stop_offset
        surge_follow_price = self.surge_follow_price_ratio * price
        position_price = self.portfolio.get_position_price()

        tmp_stop_offset = prev_stop_offset

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

    def __follow_price_range(self, price):
        # 初回購入時に設定するストップ値は、直近の最高値・最安値を上回らないようにする
        # 追加購入があった場合は、現在の取得単価 - 1レンジで追従させる

        # T.B.D.
        tmp_stop_offset = 0

        return tmp_stop_offset


    def __update_stop_price(self):

        main_time_frame = Config.get_time_frame()
        psar_time_frame = Config.get_psar_time_frame()

        position = self.portfolio.get_position_quantity()
        quantity = position["quantity"]
        side = position["side"]
        position_price = position["position_price"]
        price = self.price_data_management.get_ticker()
        #ohlcv = self.price_data_management.get_latest_ohlcv()
        
        # 未初期化の場合は初期値を設定する
        # TODO 初期ストップ値の再考慮　ボラティリティで決めていいのか
        if self.stop_offset == 0:
            self.stop_offset = self.price_data_management.get_volatility() * self.initial_stop_range

        prev_stop_offset = self.stop_offset

        if quantity != 0 and self.stop_price == 0:
            if side == "BUY":
                prev_stop_price = price - self.stop_offset
            if side == "SELL":
                prev_stop_price = price + self.stop_offset
        else:
            prev_stop_price = self.stop_price

        # パラボリックSAR計算
        psar_ohlcv_data = self.price_data_management.get_ohlcv_data(psar_time_frame)
        self.__calc_parabolic_sar(psar_ohlcv_data)

        # ADX計算
        adx_ohlcv_data = self.price_data_management.get_ohlcv_data(main_time_frame)
        self.__calc_adx(adx_ohlcv_data)

        # ポジションがある場合のみストップ値を更新
        if quantity != 0:
            # パラボリックSARストップ値計算
            psar_stop_offset = self.__calc_stop_psar()

            # 急騰時に利益が一定以上の場合は固定値で追従する
            price_surge_stop_offset = self.__follow_price_surge(price)
            self.price_surge_stop_offset = price_surge_stop_offset
            
            # 現在値からレンジ幅でストップ値を計算(負数もありうる　現在)
            new_stop_offset = min(prev_stop_offset, psar_stop_offset)
            # ストップのオフセットが更新された場合のみ、ストップ値を再評価する
            if prev_stop_offset > new_stop_offset:
                self.stop_offset = new_stop_offset

            # 前回のoffsetから変化がなかったらストップ値は変更しない
            if side == "BUY":
                # ストップ値再計算
                tmp_stop_price = position_price - self.stop_offset
                self.stop_price = max(tmp_stop_price, prev_stop_price)
                #self.logger.log(f"prev stop offset {prev_stop_offset} psar offset {psar_stop_offset} new_stop_offset {new_stop_offset} tmp_stop_price {tmp_stop_price} prev_stop_price {prev_stop_price} stop_price {self.stop_price} price {price} ")
            if side == "SELL":
                # ストップ値再計算
                tmp_stop_price = position_price + self.stop_offset
                self.stop_price = min(tmp_stop_price, prev_stop_price)
                #self.logger.log(f"prev stop offset {prev_stop_offset} psar offset {psar_stop_offset} new_stop_offset {new_stop_offset} tmp_stop_price {tmp_stop_price} prev_stop_price {prev_stop_price} stop_price {self.stop_price} price {price} ")
        else:
            self.psar_stop_offset = 0
            self.price_surge_stop_offset = 0
            self.stop_price = 0
            self.stop_offset = 0
            self.position_size = 0 
            self.add_range = 0 
            self.total_size = 0
            self.stop_ATR = 0
            self.last_entry_price = 0 # 価格ベース

    def calculate_position_size(self, balance_tether):
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
            self.logger.log_error(f"証拠金{balance_tether:.2f}が最低額{self.balance_tether_limit}を下回ったので発注できません")
            self.capital_exhausted = True
        else:
            # 初回のstop値を計算
            # ボラティリティの幅からストップ幅を計算
            volatility = self.price_data_management.get_volatility()
            price = self.price_data_management.get_ticker()
            stop_range = self.initial_stop_range * volatility

            # 総購入数は、総資産 x 失っていい割合 / ボラティリティで動きうる幅で決定
            total_size = round( ( balance_tether * 100 * self.risk_percentage / stop_range / 100 ), 7 )
            # 分割購入するので1買い当たりのサイズに変換
            tmp_size = round( ( total_size * 100 / self.entry_times / 100 ) , 7 )

            # TODO stop値計算に移動
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
            # 追加購入時の幅の計算
            self.add_range = self.get_entry_range() * volatility

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
    portfolio = Portfolio()
    price_data_management = PriceDataManagement()
    risk_manager = RiskManagement(price_data_management, portfolio)

    # 最新の値を取得
    price = exchange.fetch_ticker()
    # 最新の口座を取得
    balance = exchange.get_account_balance()
    # BTCのused、free、total情報を表示
    usd_balance = balance['USDT']['total']
    balance_tether = usd_balance
    
    # 不足する場合の救済処置
    if balance_tether < risk_manager.balance_tether_limit:
        balance_tether = risk_manager.balance_tether_limit * 2

    # 取引情報を決定
    price_data_management.update_price_data()

    # ポジションサイズを計算
    position_size = risk_manager.calculate_position_size(balance_tether)
    print(f'Position Size[USDT]: {position_size}')
