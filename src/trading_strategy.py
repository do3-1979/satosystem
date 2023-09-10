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
from config import Config
from logger import Logger
from bybit_exchange import BybitExchange

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

    def __init__(self):
        self.position = None
        self.exchange = BybitExchange(Config.get_api_key(), Config.get_api_secret())
        self.logger = Logger()
        self.ohlcv_data = []
        # BUY/SELL/None
        self.signal_donchian = "None"
        # True / False
        self.signal_pvo = False
        self.volatility = 0
        self.prev_close_time = 0
 
    def evaluate_entry(self, price_data):
        """
        エントリー条件を評価し、エントリーするかどうかを決定します。

        Args:
            price_data (dict): 価格データ

        Returns:
            bool: エントリーが成功した場合はTrue、それ以外はFalse

        """
        if self.entry_condition(price_data):
            self.position = {"entry_price": price_data["close_price"]}
            return True
        return False

    def evaluate_add(self, price_data):
        """
        ピラミッディング条件を評価し、ピラミッディングするかどうかを決定します。

        Args:
            price_data (dict): 価格データ

        Returns:
            bool: ピラミッディングが成功した場合はTrue、それ以外はFalse

        """
        if self.add_condition(price_data):
            # ピラミッディングの条件を満たす場合の処理
            return True
        return False

    def evaluate_exit(self, price_data):
        """
        エグジット条件を評価し、ポジションをクローズするかどうかを決定します。

        Args:
            price_data (dict): 価格データ

        Returns:
            bool: エグジットが成功した場合はTrue、それ以外はFalse

        """
        if self.exit_condition(price_data):
            self.position = None
            return True
        return False

    def get_ohlcv_data(self):
        """
        価格データを取得するメソッドです。
        このメソッドは実際のデータを取得するロジックを追加してください。

        Returns:
            list: 価格データのリスト

        """
        return self.ohlcv_data

    def get_volatility(self):
        """
        価格データのボラティリティを取得するメソッドです。
        このメソッドは実際のデータを取得するロジックを追加してください。

        Returns:
            int: 価格データのボラティリティ

        """
        return self.volatility


    def calcurate_volatility(self, ohlcv_data):
        """_summary_

        Args:
            ohlcv_data (_type_): _description_
            price (_type_): _description_

        Returns:
            _type_: _description_
        """
        volatility_term = Config.get_volatility_term()
        high_sum = sum(i["high_price"] for i in ohlcv_data[-1 * volatility_term :])
        low_sum	 = sum(i["low_price"]  for i in ohlcv_data[-1 * volatility_term :])
        volatility = round((high_sum - low_sum) / volatility_term)
        self.volatility = volatility
        return volatility

    def make_trade_decision(self, balance):
        """
        トレードの実行判断を行います。

        Args:
            action (str): トレードアクション ('buy' または 'sell')
            price_data (dict): 価格データ

        """
        tmp_ohlcv_data = []
        
        # 価格を取得
        tmp_ohlcv_data = self.exchange.fetch_ohlcv()
        price = self.exchange.fetch_ticker()
        
        # 初回は値更新のみ
        if self.prev_close_time == 0:
            # 価格データを更新
            self.prev_close_time = tmp_ohlcv_data[-1]["close_time"]
            self.ohlcv_data = tmp_ohlcv_data
            self.volatility = self.calcurate_volatility(tmp_ohlcv_data)

            return
        # 価格データ更新があれば
        elif self.prev_close_time < tmp_ohlcv_data[-1]["close_time"]:
            # トレード判断に必要な情報を更新
            self.signal_donchian = self.__evaluate_donchian(self.ohlcv_data, price)
            volume = tmp_ohlcv_data[-1]["Volume"]
            self.signal_pvo = self.__evaluate_pvo(self.ohlcv_data, volume)
            
            self.logger.log(f"donchian : {self.signal_donchian}")
            self.logger.log(f"pvo : {self.signal_pvo}")
            # 価格データを更新
            self.prev_close_time = tmp_ohlcv_data[-1]["close_time"]
            self.ohlcv_data = tmp_ohlcv_data
            self.volatility = self.calcurate_volatility(tmp_ohlcv_data)
            
        # トレードの実行判断
        # オーダーサイズ、サイドを返す
        # self.evaluate_entry()
        # self.evaluate_add()
        # self.evaluate_exit()

        return None

    def __evaluate_donchian(self, ohlcv_data, price):
        """_summary_

        Args:
            ohlcv_data (_type_): _description_
            price (_type_): _description_

        Returns:
            _type_: _description_
        """
        buy_term = Config.get_donchian_buy_term()
        sell_term = Config.get_donchian_sell_term()
        side = "None"

        highest = max(i["high_price"] for i in ohlcv_data[ (-1* buy_term): ])
        if price > highest:
            side = "BUY"

        lowest = min(i["low_price"] for i in ohlcv_data[ (-1* sell_term): ])
        if price < lowest:
            side = "SELL"

        return side

    def __calc_ema(self, term, data):
        """
        EMAを計算する

        Exponential Moving Average（指数平滑移動平均）。MACDを算出する際に使ったり結構多用します。
        過去よりも現在の方が影響が強いという考えを入れた移動平均値で、現在に近いレートほど重みをつけて計算します。
        計算式は
        E(t) = E(t-1) + 2/(n+1)(直近の終値 – E(t-1))
        data : price list
        n    : period

        Args:
            term (_type_): _description_
            data (_type_): _description_

        Returns:
            _type_: _description_
        """
        i=0
        chk_1=0
        chk_1_sum=0
        et_1=0
        result = []
        for p in data:
            i = len(result)
            if i <= (term - 1):
                #SMA
                chk_1_sum = sum(result)
                chk_1 = (float(chk_1_sum) + float(p)) / (i + 1)
                result += [chk_1]
            else:
                #EMA
                et_1 = result[-1]
                result += [float(et_1 + 2 / (term + 1) * (float(p) - et_1))]
        return result[-1]

    def __calcurate_pvo(self, ohlcv_data, volume):
        """_summary_

        Args:
            ohlcv_data (_type_): _description_
            volume (_type_): _description_

        Returns:
            _type_: _description_
        """
        pvo_s_term = Config.get_pvo_s_term()
        pvo_l_term = Config.get_pvo_l_term()
        volume_data = []
        
        data_len = max( pvo_s_term, pvo_l_term )
        # 出来高の必要数を配列に格納
        for i in ohlcv_data[ (-1* data_len): ]:
            volume_data.append(i["Volume"])
        
        # 最新の値も追加する
        volume_data.append(volume)
        # 短いほうのEMAを計算
        short_ema = self.__calc_ema( pvo_s_term, volume_data )
        # 長いほうのEMAを計算
        long_ema = self.__calc_ema( pvo_l_term, volume_data )
        # PVOを計算
        pvo_value = ( ( short_ema - long_ema ) * 100 / long_ema )
        
        return pvo_value

    def __evaluate_pvo(self, ohlcv_data, volume):
        """_summary_

        Args:
            ohlcv_data (_type_): _description_
            volume (_type_): _description_

        Returns:
            _type_: _description_
        """
        pvo_threshold = Config.get_pvo_threshold()
        pvo_value = self.__calcurate_pvo(ohlcv_data, volume)
        # PVOの閾値チェック
        if pvo_value <= pvo_threshold:
            judge = False
        else:
            judge = True

        return judge

if __name__ == "__main__":
    # TradingStrategyクラスの初期化
    strategy = TradingStrategy()

    balance = 10000

    # 取引情報を決定
    strategy.make_trade_decision(balance)
    print(f"volatirity : {strategy.volatility}")
        
    # 価格データのサンプル
    ohlcv_data = strategy.get_ohlcv_data()
