from datetime import datetime
from config import Config
from logger import Logger
from bybit_exchange import BybitExchange

class PriceDataManagement:
    """
    価格データとトレードシグナルを管理するクラスです。

    Attributes:
        exchange (BybitExchange): BybitのAPIとの通信を担当するExchangeクラスのインスタンス
        logger (Logger): ログを出力するためのLoggerクラスのインスタンス
        ohlcv_data (list): OHLCVデータのリスト
        ticker (float): 最新のティッカー価格
        signals (dict): トレードシグナルの辞書
            - signals["donchian"]: ドンチャンチャネルに基づくトレードシグナル
            - signals["pvo"]: PVOに基づくトレードシグナル
        volatility (int): 価格データのボラティリティ
        prev_close_time (int): 前回の終値時間

    Methods:
        get_ohlcv_data(self): OHLCVデータを取得します。
        get_volatility(self): 価格データのボラティリティを取得します。
        calcurate_volatility(self, ohlcv_data): ボラティリティを計算します。
        show_latest_ticker(self): 最新のティッカー価格を表示します。
        show_latest_ohlcv(self): 最新のOHLCVデータを表示します。
        show_latest_signals(self): 最新のトレードシグナルを表示します。
        get_signals(self): トレードシグナルを取得します。
        update_price_data(self): 価格データとトレードシグナルを更新します。
    """

    def __init__(self):
        self.exchange = BybitExchange(Config.get_api_key(), Config.get_api_secret())
        self.logger = Logger()
        self.ohlcv_data = []
        self.latest_ohlcv_data = []
        self.ticker = 0
        self.volume = 0
        self.signals = {"donchian": {"signal": False, "side": None }, "pvo": {"signal": False, "side": None }}
        self.volatility = 0
        self.prev_close_time = 0

    def get_ohlcv_data(self):
        """
        OHLCVデータを取得するメソッドです。
        このメソッドは実際のデータを取得するロジックを追加してください。

        Returns:
            list: OHLCVデータのリスト
        """
        return self.ohlcv_data

    def get_ticker(self):
        """
        tickerデータを取得するメソッドです。

        Returns:
            int: tickerデータ
        """
        return self.ticker

    def get_latest_volume(self):
        """
        最新の出来高を取得するメソッドです。
        """
        return self.volume

    def get_volatility(self):
        """
        価格データのボラティリティを取得するメソッドです。
        このメソッドは実際のデータを取得するロジックを追加してください。

        Returns:
            int: 価格データのボラティリティ
        """
        return self.volatility

    def calcurate_volatility(self, ohlcv_data):
        """
        ボラティリティを計算するメソッドです。

        Args:
            ohlcv_data (list): OHLCVデータのリスト

        Returns:
            int: ボラティリティ
        """
        volatility_term = Config.get_volatility_term()
        high_sum = sum(i["high_price"] for i in ohlcv_data[-1 * volatility_term :])
        low_sum = sum(i["low_price"] for i in ohlcv_data[-1 * volatility_term :])
        volatility = round((high_sum - low_sum) / volatility_term)
        return volatility

    def show_latest_ticker(self):
        """
        最新のティッカー価格を表示するメソッドです。
        """
        self.logger.log(f"ティッカー値: {self.ticker}")

    def show_latest_volume(self):
        """
        最新の出来高を表示するメソッドです。
        """
        self.logger.log(f"出来高: {self.volume}")

    def show_latest_ohlcv(self):
        """
        最新の未確定のOHLCVデータを表示するメソッドです。
        """
        latest_ohlcv_data = self.latest_ohlcv_data[-1]
        self.logger.log(
            f"終値時間: {datetime.fromtimestamp(latest_ohlcv_data['close_time']).strftime('%Y/%m/%d %H:%M')}"
            f"  高値: {round(latest_ohlcv_data['high_price'])}"
            f"  安値: {round(latest_ohlcv_data['low_price'])}"
            f"  終値: {round(latest_ohlcv_data['close_price'])}"
            f"  出来高: {round(latest_ohlcv_data['Volume'])}"
        )

    def show_latest_signals(self):
        """
        最新のトレードシグナルを表示するメソッドです。
        """
        self.logger.log("トレードシグナル:")
        for signal_type, signal_info in self.signals.items():
            self.logger.log(f"{signal_type}: Signal = {signal_info['signal']}, Side = {signal_info['side']}")

    def get_signals(self):
        """
        トレードシグナルを取得するメソッドです。

        Returns:
            dict: トレードシグナルの辞書
        """
        return self.signals

    def update_price_data(self):
        """
        価格データとトレードシグナルを更新するメソッドです。
        """
        # 最新値の更新
        self.latest_ohlcv_data = self.exchange.fetch_latest_ohlcv()
        self.volume = self.latest_ohlcv_data[0]["Volume"]
        self.ticker = self.exchange.fetch_ticker()

        # 価格データの更新
        tmp_ohlcv_data = self.exchange.fetch_ohlcv()
        last_ohlcv_data = tmp_ohlcv_data[-1]

        # 初回の処理
        if self.prev_close_time == 0:
            self.prev_close_time = last_ohlcv_data['close_time']
            self.ohlcv_data = tmp_ohlcv_data
            self.volatility = self.calcurate_volatility(tmp_ohlcv_data)
            return

        # 価格更新時
        elif self.prev_close_time < last_ohlcv_data['close_time']:
            # donchian update
            dc = self.__evaluate_donchian(self.ohlcv_data, self.ticker)
            if dc == "BUY":
                self.signals["donchian"]["signal"] = True
                self.signals["donchian"]["side"] = "BUY"
            elif dc == "SELL":
                self.signals["donchian"]["signal"] = True
                self.signals["donchian"]["side"] = "SELL"
            else:
                self.signals["donchian"]["signal"] = False
                self.signals["donchian"]["side"] = "None"
            # PVO update
            volume = last_ohlcv_data["Volume"]
            self.signals["pvo"]["signal"] = self.__evaluate_pvo(self.ohlcv_data, volume)
            # update volatility
            self.volatility = self.calcurate_volatility(tmp_ohlcv_data)
            # update last data
            self.prev_close_time = last_ohlcv_data["close_time"]
            self.ohlcv_data = tmp_ohlcv_data

        return

    def __evaluate_donchian(self, ohlcv_data, price):
        """
        ドンチャンチャネルに基づくトレードシグナルを評価するメソッドです。

        Args:
            ohlcv_data (list): OHLCVデータのリスト
            price (float): 現在の価格

        Returns:
            str: トレードシグナル ('BUY', 'SELL', 'None')
        """
        buy_term = Config.get_donchian_buy_term()
        sell_term = Config.get_donchian_sell_term()
        side = "None"

        highest = max(i["high_price"] for i in ohlcv_data[(-1 * buy_term) :])
        if price > highest:
            side = "BUY"

        lowest = min(i["low_price"] for i in ohlcv_data[(-1 * sell_term) :])
        if price < lowest:
            side = "SELL"

        return side

    def __calc_ema(self, term, data):
        """
        Exponential Moving Average（指数平滑移動平均）を計算するメソッドです。

        Args:
            term (int): 移動平均の期間
            data (list): 価格データのリスト

        Returns:
            float: EMAの値
        """
        i = 0
        chk_1 = 0
        chk_1_sum = 0
        et_1 = 0
        result = []
        for p in data:
            i = len(result)
            if i <= (term - 1):
                chk_1_sum = sum(result)
                chk_1 = (float(chk_1_sum) + float(p)) / (i + 1)
                result += [chk_1]
            else:
                et_1 = result[-1]
                result += [float(et_1 + 2 / (term + 1) * (float(p) - et_1))]
        return result[-1]

    def __calcurate_pvo(self, ohlcv_data, volume):
        """
        Price Volume Oscillator（PVO）を計算するメソッドです。

        Args:
            ohlcv_data (list): OHLCVデータのリスト
            volume (float): 出来高

        Returns:
            float: PVOの値
        """
        pvo_s_term = Config.get_pvo_s_term()
        pvo_l_term = Config.get_pvo_l_term()
        volume_data = []

        data_len = max(pvo_s_term, pvo_l_term)
        for i in ohlcv_data[(-1 * data_len) :]:
            volume_data.append(i["Volume"])

        volume_data.append(volume)
        short_ema = self.__calc_ema(pvo_s_term, volume_data)
        long_ema = self.__calc_ema(pvo_l_term, volume_data)
        pvo_value = ((short_ema - long_ema) * 100 / long_ema)

        return pvo_value

    def __evaluate_pvo(self, ohlcv_data, volume):
        """
        PVOに基づくトレードシグナルを評価するメソッドです。

        Args:
            ohlcv_data (list): OHLCVデータのリスト
            volume (float): 出来高

        Returns:
            bool: トレードシグナル (True, False)
        """
        pvo_threshold = Config.get_pvo_threshold()
        pvo_value = self.__calcurate_pvo(ohlcv_data, volume)
        if pvo_value <= pvo_threshold:
            judge = False
        else:
            judge = True

        return judge

if __name__ == "__main__":
    # PriceDataManagement
    price_data_management = PriceDataManagement()

    print("----------")
    print("価格データとトレードシグナルを更新")
    price_data_management.update_price_data()

    # 最新のOHLCVデータを表示
    price_data_management.show_latest_ohlcv()

    # 最新のティッカー価格を表示
    price_data_management.show_latest_ticker()

    # 最新の出来高を表示
    price_data_management.show_latest_volume()

    # 最新のトレードシグナルを表示
    price_data_management.show_latest_signals()
