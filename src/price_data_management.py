from datetime import datetime
from datetime import timedelta
from config import Config
from logger import Logger
from bybit_exchange import BybitExchange

class PriceDataManagement:
    # クラス変数として唯一のインスタンスを保持
    _instance = None
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
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PriceDataManagement, cls).__new__(cls)
            cls._instance.initialize()
        return cls._instance

    def initialize(self):
        self.exchange = BybitExchange(Config.get_api_key(), Config.get_api_secret())
        self.logger = Logger()
        self.ohlcv_data = [] # 確定済のデータテーブル
        self.latest_ohlcv_data = [] # 未確定の最新値
        self.ticker = 0
        self.volume = 0
        self.signals = {'donchian': {'signal': False, 'side': None, 'info': {'highest': 0, 'lowest': 0} }, 'pvo': {'signal': False, 'side': None, 'info':{'value': 0} }}
        self.volatility = 0
        self.prev_close_time = 0
        
        if Config.get_back_test_mode() == 1:
            self.back_test_ohlcv_data = [] # バックテスト用のデータテーブルバッファ
            self.progress_time = 0 # 処理中の時刻
            
    def get_ohlcv_data(self):
        """
        確定済のOHLCVデータを取得するメソッドです。

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

    def get_latest_ohlcv(self):
        """
        最新の未確定のOHLCVデータを表示するメソッドです。
        """
        return self.latest_ohlcv_data[-1]

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
        high_sum = sum(i['high_price'] for i in ohlcv_data[-1 * volatility_term :])
        low_sum = sum(i['low_price'] for i in ohlcv_data[-1 * volatility_term :])
        volatility = (high_sum - low_sum) / volatility_term
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
            f"  出来高: {latest_ohlcv_data['Volume']}"
        )

    def show_latest_signals(self):
        """
        最新のトレードシグナルを表示するメソッドです。
        """
        self.logger.log("トレードシグナル:")
        for signal_type, signal_info in self.signals.items():
            self.logger.log(f"{signal_type}: Signal = {signal_info['signal']}, Side = {signal_info['side']}, Info = {signal_info['info']}")

    def get_signals(self):
        """
        トレードシグナルを取得するメソッドです。

        Returns:
            dict: トレードシグナルの辞書
        """
        return self.signals
    
    def update_price_data_backtest(self):
        """
        バックテスト用に価格データとトレードシグナルを更新するメソッドです。
        """

        # 価格データの更新
        start_epoch = Config.get_start_epoch()
        end_epoch = 0
        # --------------------------------------------
        # Back test 用には、指定時間＋解析に必要な期間のみ追加する
        # --------------------------------------------
        # 初期化時
        if self.progress_time == 0:
            #print("###START")
            # 初期分析に必要な時間を計算
            initial_term = Config.get_test_initial_max_term()
            diff_time = initial_term * Config.get_time_frame()
            td = timedelta(minutes=diff_time)
            start_time = datetime.strptime(Config.get_start_time(), "%Y/%m/%d %H:%M")
            end_time = start_time + td
            # epoch時間に変換
            end_epoch = int(end_time.timestamp())
            self.progress_time = end_epoch
        # --------------------------------------------
        # バックテストの終端を検出してステータスを更新し処理を中断
        elif self.progress_time == -1:
            #print("###END")
            return True
        # --------------------------------------------
        # バックテスト用に終端時間を次の時間にする
        else:
            tmp_time = self.progress_time        
            #print(f"###PROGRESS {tmp_time}")
            end_epoch = self.progress_time

        # --------------------------------------------
        # 初回の値取得
        if self.prev_close_time == 0:
            # 初期機関をサーバから取得 TODO 取得済テーブルから取得
            tmp_ohlcv_data = self.exchange.fetch_ohlcv(start_epoch, end_epoch)
            last_ohlcv_data = tmp_ohlcv_data[-1]

            self.prev_close_time = last_ohlcv_data['close_time']
            # 初回のみ初期化
            self.ohlcv_data = tmp_ohlcv_data
            self.volatility = self.calcurate_volatility(tmp_ohlcv_data)
            self.latest_ohlcv_data = []
            self.latest_ohlcv_data.append(self.ohlcv_data[-1])
            return False

        # --------------------------------------------
        # 最新値の更新
        # --------------------------------------------
        # バックテスト時はバッファから1レコードずつ取得する
        # 指定した時間の次のデータを取得する　同時に次のデータ時間も取得する
        # TODO nextの時間は次の配列に頼らず自分で作るしかないのでは 
        # end_epochを超えるまで次の配列を得る
        tmp_data  = self.get_back_test_ohlcv_data(self.progress_time)
        #tmp_time = tmp_data['close_time']
        #print(f"---ROGRESS data_time {tmp_time} self.progress_time {self.progress_time}")
        self.latest_ohlcv_data = []
        self.latest_ohlcv_data.append(tmp_data)

        
        # 最新の値は最新のclose時間とする
        # TODO 60秒のデータの組み合わせ
        self.ticker = self.latest_ohlcv_data[0]['close_price']
        self.volume = self.latest_ohlcv_data[0]['Volume']
        last_ohlcv_data = self.latest_ohlcv_data[0]

        # 終端判断
        last_time = last_ohlcv_data['close_time']
        diff_time = Config.get_time_frame() * 60
        # epoch時間に変換
        next_epoch = last_time + diff_time
        end_epoch = self.back_test_ohlcv_data[-1]['close_time']
        #print(f"next_apoch {next_epoch} end_epoch {end_epoch}")
        if next_epoch >= end_epoch:
            # 次のデータ時間を更新
            self.progress_time = -1
        else:
            # 次のデータ時間を更新
            self.progress_time = next_epoch

        # --------------------------------------------
        # データの更新があった場合
        # --------------------------------------------
        if self.prev_close_time < last_time:
            # donchian update
            dc, high, low = self.__evaluate_donchian(self.ohlcv_data, self.ticker)
            
            if dc == 'BUY':
                self.signals['donchian']['signal'] = True
                self.signals['donchian']['side'] = 'BUY'
            elif dc == 'SELL':
                self.signals['donchian']['signal'] = True
                self.signals['donchian']['side'] = 'SELL'
            else:
                self.signals['donchian']['signal'] = False
                self.signals['donchian']['side'] = 'None'

            self.signals['donchian']['info']['highest'] = high
            self.signals['donchian']['info']['lowest'] = low

            # PVO update
            volume = last_ohlcv_data['Volume']
            pvo, value = self.__evaluate_pvo(self.ohlcv_data, volume)
            self.signals['pvo']['signal'] = pvo
            self.signals['pvo']['info']['value'] = value
            # update volatility
            self.volatility = self.calcurate_volatility(self.ohlcv_data)
            # update last data
            self.prev_close_time = last_time
            # 最新行を追加し、最古を削除する
            self.ohlcv_data.append( last_ohlcv_data )
            del self.ohlcv_data[0]
            
        return False

    def update_price_data(self):
        """
        価格データとトレードシグナルを更新するメソッドです。
        """

        # 価格データの更新
        start_epoch = Config.get_start_epoch()
        end_epoch = Config.get_end_epoch()
        # 確定した最新値を取得
        tmp_ohlcv_data = self.exchange.fetch_ohlcv(start_epoch, end_epoch)
        last_ohlcv_data = tmp_ohlcv_data[-1]

        # --------------------------------------------
        # 最新値の更新
        # --------------------------------------------
        # 最新値を取得
        self.latest_ohlcv_data = self.exchange.fetch_latest_ohlcv()
        self.ticker = self.exchange.fetch_ticker()
        self.volume = self.latest_ohlcv_data[0]['Volume']

        # 初回の処理
        if self.prev_close_time == 0:            
            self.prev_close_time = last_ohlcv_data['close_time']
            # 初回のみ初期化
            self.ohlcv_data = tmp_ohlcv_data
            self.volatility = self.calcurate_volatility(tmp_ohlcv_data)
            return

        # --------------------------------------------
        # データの更新があった場合
        # --------------------------------------------
        elif self.prev_close_time < last_ohlcv_data['close_time']:
            # donchian update
            dc, high, low = self.__evaluate_donchian(self.ohlcv_data, self.ticker)
            
            if dc == 'BUY':
                self.signals['donchian']['signal'] = True
                self.signals['donchian']['side'] = 'BUY'
            elif dc == 'SELL':
                self.signals['donchian']['signal'] = True
                self.signals['donchian']['side'] = 'SELL'
            else:
                self.signals['donchian']['signal'] = False
                self.signals['donchian']['side'] = 'None'

            self.signals['donchian']['info']['highest'] = high
            self.signals['donchian']['info']['lowest'] = low

            # PVO update
            volume = last_ohlcv_data['Volume']
            pvo, value = self.__evaluate_pvo(self.ohlcv_data, volume)
            self.signals['pvo']['signal'] = pvo
            self.signals['pvo']['info']['value'] = value
            # update volatility
            self.volatility = self.calcurate_volatility(tmp_ohlcv_data)
            # update last data
            self.prev_close_time = last_ohlcv_data['close_time']
            # 最新行を追加し、最古を削除する
            self.ohlcv_data.append( last_ohlcv_data )
            del self.ohlcv_data[0]
            
        return

    def initialise_back_test_ohlcv_data(self):
        """
        バックテスト用取引データ初期化
        """
        # 指定された期間のバックテストデータを取得
        start_epoch = Config.get_start_epoch()
        end_epoch = Config.get_end_epoch()
        self.back_test_ohlcv_data = self.exchange.fetch_ohlcv(start_epoch, end_epoch)
        return

    def get_back_test_ohlcv_data(self, target_unix_time):
        """
        指定された時間のデータと、次のデータを返す
        """
        closest_data = None
        time_difference = float('inf')  # 初期値を無限大に設定

        ohlcv_data = self.back_test_ohlcv_data

        for i, data in enumerate(ohlcv_data):
            data_unix_time = data['close_time']
            if data_unix_time >= target_unix_time:
                # 目標UNIX時間を超えているデータの場合
                current_difference = data_unix_time - target_unix_time
                if current_difference < time_difference:
                    # より近いデータを見つけた場合
                    time_difference = current_difference
                    closest_data = data
                    tmp_time = closest_data['close_time']
                    #print(f"closet_data time {tmp_time} target_unix_time {target_unix_time}")

        return closest_data

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
        side = 'None'

        highest = max(i['high_price'] for i in ohlcv_data[(-1 * buy_term) :])
        if price > highest:
            side = 'BUY'

        lowest = min(i['low_price'] for i in ohlcv_data[(-1 * sell_term) :])
        if price < lowest:
            side = 'SELL'

        return side, highest, lowest

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
            volume_data.append(i['Volume'])

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

        return judge, pvo_value

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

