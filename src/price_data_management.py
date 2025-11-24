from datetime import datetime
from datetime import timedelta
from config import Config
from logger import Logger
from bybit_exchange import BybitExchange
# from indicator_service import IndicatorService  # 削除済み、不要
import pprint
import json
import os
from ohlcv_cache import OHLCVCache
from regime_detector import RegimeDetector

class PriceDataManagement:
    # クラス変数として唯一のインスタンスを保持
    _instance = None
    
    @classmethod
    def reset_instance(cls):
        """シングルトンインスタンスをリセット（backtest用）"""
        cls._instance = None
    
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
    def __new__(cls, indicator_service=None):
        if cls._instance is None:
            cls._instance = super(PriceDataManagement, cls).__new__(cls)
            cls._instance._initialized = False
            cls._instance.initialize(indicator_service=indicator_service)
            cls._instance._initialized = True
        else:
            # 既存インスタンスの場合、indicator_serviceが渡されていれば更新
            if indicator_service is not None:
                cls._instance.indicator_service = indicator_service
        return cls._instance

    def initialize(self, indicator_service=None):
        self.exchange = BybitExchange(Config.get_api_key(), Config.get_api_secret())
        self.logger = Logger()
        # IndicatorServiceを外部から受け取るか、新規作成
        # self.indicator_service = indicator_service if indicator_service is not None else IndicatorService()
        self.indicator_service = indicator_service  # 削除済みのため、Noneで初期化
        
        # RegimeDetectorを初期化
        self.regime_detector = RegimeDetector()
        
        main_time_frame = Config.get_time_frame()
        psar_time_frame = Config.get_psar_time_frame()
        
        self.ohlcv_data = [
                {"time_frame": main_time_frame, "data": []},
                {"time_frame": psar_time_frame, "data": []}
            ]
        self.latest_ohlcv_data = [] # 未確定の最新値
        self.ticker = 0
        self.volume = 0
        self.time_frame = main_time_frame # 主軸タイムフレーム
        self.psar_time_frame = psar_time_frame # PSAR用タイムフレーム
        self.signals = {
            'donchian': {'signal': False, 'side': None, 'info': {'highest': 0, 'lowest': 0}},
            'pvo': {'signal': False, 'side': None, 'info': {'value': 0}},
            'keltner': {'signal': False, 'side': None, 'info': {'upper': 0, 'middle': 0, 'lower': 0, 'width_expanding': False}},
            'regime_stats': {'current_regime': 'NEUTRAL', 'regime_percentages': {}}
        }
        self.volatility = 0
        self.prev_close_time = 0
        # PVOヒット率計算用カウンタ
        self._donchian_pvo_candidates = 0  # Donchianブレイクが発生したバー数
        self._donchian_pvo_passes = 0      # そのうちPVO閾値を同時に満たしたバー数
        
        # Pullback state (Phase B)
        self.pullback_state = 'none'  # 'none', 'breakout', 'pullback', 'ready'
        self.pullback_donchian_highest = 0
        
        if Config.get_back_test_mode() == 1:
            self.back_test_ohlcv_data = [
                {"time_frame": main_time_frame, "data": [], "prev_index": 0},
                {"time_frame": psar_time_frame, "data": [], "prev_index": 0}
            ]
            self.progress_time = 0 # 処理中の時刻
            self.progress_diff = 0
            self.close_time = 0
            self.prev_high_price = 0
            self.prev_low_price = 0
            
    def get_ohlcv_data(self, time_frame):
        """
        確定済のOHLCVデータを取得するメソッドです。

        Returns:
            list: OHLCVデータのリスト
        """
        ohlcv_data = self.get_ohlcv_data_by_time_frame(time_frame)
        
        return ohlcv_data

    def get_ticker(self):
        """
        tickerデータを取得するメソッドです。

        Returns:
            int: tickerデータ
        """
        return self.ticker

    def get_latest_close_time(self):
        """
        close_timeデータを取得するメソッドです。

        Returns:
            int: close_time
        """
        return self.close_time
    
    def get_latest_close_time_dt(self):
        """
        close_timeデータを取得するメソッドです。

        Returns:
            int: close_time
        """
        return datetime.fromtimestamp(self.close_time).strftime('%Y/%m/%d %H:%M')

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
        return self.indicator_service.calculate_volatility(ohlcv_data)

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
        # 価格データ更新フラグ
        is_update_ohlcv_1 = False
        is_update_ohlcv_2 = False

        # 価格データの更新
        start_epoch = Config.get_start_epoch()
        end_epoch = 0
        # --------------------------------------------
        # Back test 用には、start時間から必要な期間を遡ってデータを取得する
        # --------------------------------------------
        if self.progress_time == 0:
            #print("###START")
            # 初回のend時間はstart時間に合わせる
            end_epoch = Config.get_start_epoch()
            self.progress_time = end_epoch
            # 初期分析に必要な時間を計算
            initial_term = Config.get_test_initial_max_term()
            diff_time = initial_term * self.time_frame
            td = timedelta(minutes=diff_time)
            # 指定のstart時間から遡った時間を取得
            org_start_time = datetime.strptime(Config.get_start_time(), "%Y/%m/%d %H:%M")
            start_time = org_start_time - td
            # 秒を切り捨て
            start_time = start_time.replace(second=0)
            # print(f"1:start_time : {start_time}")
            # epoch時間に変換
            start_epoch = int(start_time.timestamp())

        # --------------------------------------------
        # バックテストの終端を検出してステータスを更新し処理を中断
        elif self.progress_time == -1:
            #print("###END")
            return True
        # --------------------------------------------
        # バックテスト用に終端時間を次の時間にする
        else:
            end_epoch = self.progress_time

        # --------------------------------------------
        # 初回の値取得
        if self.prev_close_time == 0:
            # バックテストモード: 既に初期化済みのback_test_ohlcv_dataから取得
            back_test_mode = Config.get_back_test_mode()
            if back_test_mode == 1:
                # back_test_ohlcv_data から初期値を取得
                tmp_ohlcv_data = self.get_back_test_ohlcv_data_by_time_frame(self.time_frame)
                if not tmp_ohlcv_data:
                    self.logger.log_error("バックテスト用OHLCVデータが未初期化です")
                    return True
                
                last_ohlcv_data = tmp_ohlcv_data[-1]
                self.prev_close_time = last_ohlcv_data['close_time']
                
                # 初回のみ初期化
                self.set_ohlcv_data_by_time_frame(tmp_ohlcv_data, self.time_frame)
                self.volatility = self.calcurate_volatility(tmp_ohlcv_data)
                self.latest_ohlcv_data = []
                latest_ohlcv_data = self.get_ohlcv_data_by_time_frame(self.time_frame)
                self.latest_ohlcv_data.append(latest_ohlcv_data[-1])
                
                # PSAR用データも同様
                tmp_ohlcv_data_psar = self.get_back_test_ohlcv_data_by_time_frame(self.psar_time_frame)
                self.set_ohlcv_data_by_time_frame(tmp_ohlcv_data_psar, self.psar_time_frame)
                
                return False
            else:
                # 本番モード: サーバから取得
                tmp_ohlcv_data = self.exchange.fetch_ohlcv(start_epoch, end_epoch, self.time_frame)
                last_ohlcv_data = tmp_ohlcv_data[-1]

                self.prev_close_time = last_ohlcv_data['close_time']

                # 初回のみ初期化
                self.set_ohlcv_data_by_time_frame(tmp_ohlcv_data, self.time_frame)
                self.volatility = self.calcurate_volatility(tmp_ohlcv_data)
                self.latest_ohlcv_data = []
                latest_ohlcv_data = self.get_ohlcv_data_by_time_frame(self.time_frame)
                self.latest_ohlcv_data.append(latest_ohlcv_data[-1])
                # pprint.pprint(self.latest_ohlcv_data)

                # PSAR用データをサーバから取得
                tmp_ohlcv_data = self.exchange.fetch_ohlcv(start_epoch, end_epoch, self.psar_time_frame)
                self.set_ohlcv_data_by_time_frame(tmp_ohlcv_data, self.psar_time_frame)

                return False

        # --------------------------------------------
        # 最新値の更新（性能改善: 1分刻み→時間足刻み）
        # --------------------------------------------
        # 2時間足単位で progress_time を直接進め、不要な 1 分ステップを排除し大幅高速化
        # 進行時間が初期化済みの場合のみ進める
        ptime = self.progress_time
        # 2時間( time_frame 分 )進行
        ptime += self.time_frame * 60
        self.progress_time = ptime
        # フラグは毎ステップで再計算対象（時間足更新）
        is_update_ohlcv_1 = True
        # PSAR側も時間足が一致する場合は同時更新
        if (self.psar_time_frame == self.time_frame):
            is_update_ohlcv_2 = True

        # 2時間足終値をそのままtickerとして採用
        ohlcv_by_timeframe = self.get_back_test_ohlcv_data(ptime, self.time_frame)
        self.ticker = ohlcv_by_timeframe['close_price']
        self.close_time = ohlcv_by_timeframe['close_time']

        # 管理領域の最新値を更新（既存メソッド参照）
        latest_ohlcv_data_tmp  = self.get_back_test_ohlcv_data(self.progress_time, self.time_frame)
        # close_price は2h足終値
        latest_ohlcv_data_tmp['close_price'] = ohlcv_by_timeframe['close_price']
        """
        # TODO 最高値、最安値を更新を1分足で行うとボラティリティが小さくなりポジションサイズが変わる不具合
        if is_update_ohlcv == True:
            # 初回はclose_priceで初期化
            self.prev_high_price = ohlcv_by_minutes['high_price']
            self.prev_low_price = ohlcv_by_minutes['low_price']
            latest_ohlcv_data_tmp['high_price'] = ohlcv_by_minutes['high_price']
            latest_ohlcv_data_tmp['low_price'] = ohlcv_by_minutes['low_price']
        else:
            # 上回ったら更新
            # 最高値
            latest_ohlcv_data_tmp['high_price'] = max(self.prev_high_price, ohlcv_by_minutes['high_price'])
            self.prev_high_price = latest_ohlcv_data_tmp['high_price']
            # 最安値
            latest_ohlcv_data_tmp['low_price'] = min(self.prev_low_price, ohlcv_by_minutes['low_price'])
            self.prev_low_price = latest_ohlcv_data_tmp['low_price']
        """
        self.latest_ohlcv_data = []
        self.latest_ohlcv_data.append(latest_ohlcv_data_tmp)

        # donchianシグナル演算
        ohlcv_data = self.get_ohlcv_data_by_time_frame(self.time_frame)
        dc, high, low = self.__evaluate_donchian(ohlcv_data, self.ticker)
        
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

        # Keltnerシグナル演算（アクション1: Phase Bフィルタ）
        keltner_enabled = Config.get_keltner_enabled()
        if keltner_enabled:
            keltner_signal, keltner_side, keltner_info = self.__evaluate_keltner(ohlcv_data, self.ticker)
            self.signals['keltner']['signal'] = keltner_signal
            self.signals['keltner']['side'] = keltner_side
            self.signals['keltner']['info'] = keltner_info
        else:
            # Keltner無効時は常にTrue（フィルタなし）
            self.signals['keltner']['signal'] = True
            self.signals['keltner']['side'] = None

        # --------------------------------------------
        # データの更新があった場合(15分)
        # --------------------------------------------
        if is_update_ohlcv_2 == True:
            # 取得済テーブルから該当時刻データを取得
            # バックテスト時はバッファから1レコードずつ取得する
            last_ohlcv_data  = self.get_back_test_ohlcv_data(self.progress_time, self.psar_time_frame)
            # データリストに追加
            self.append_ohlcv_data_by_time_frame(last_ohlcv_data, self.psar_time_frame)
            # 最新行を追加し、最古を削除する
            self.del_ohlcv_data_by_time_frame( self.psar_time_frame )   
            # シグナル更新フラグ初期化
            is_update_ohlcv_2 = False

        # --------------------------------------------
        # データの更新があった場合(120分)
        # --------------------------------------------
        if is_update_ohlcv_1 == True:
            # 取得済テーブルから該当時刻データを取得
            # バックテスト時はバッファから1レコードずつ取得する
            last_ohlcv_data  = self.get_back_test_ohlcv_data(self.progress_time, self.time_frame)
            # 出来高を更新    
            self.volume = last_ohlcv_data['Volume']
            last_time = last_ohlcv_data['close_time']
            
            # PVO update
            volume = last_ohlcv_data['Volume']
            pvo, value = self.__evaluate_pvo(ohlcv_data, volume)
            self.signals['pvo']['signal'] = pvo
            self.signals['pvo']['info']['value'] = value
            
            # Regime stats update (Phase 1: アダプティブ)
            regime_detection_enabled = bool(Config.config['Strategy'].getboolean('regime_detection_enabled', fallback=False))
            if regime_detection_enabled:
                current_regime = self.regime_detector.detect_regime(self)
                regime_stats = self.regime_detector.get_regime_stats()
                self.signals['regime_stats'] = {
                    'current_regime': current_regime,
                    'regime_percentages': regime_stats.get('regime_percentages', {}),
                    'volatility_ratio': regime_stats.get('avg_volatility_ratio', 1.0),
                    'trend_strength': regime_stats.get('avg_trend_strength', 0.5)
                }
            
            # DonchianシグナルとPVOシグナルの同時発生を記録
            # ✅ 修正: Donchian発生時にPVOも同時にTRUEの場合だけカウント
            donchian_signal = self.signals['donchian']['signal']
            pvo_signal = self.signals['pvo']['signal']
            
            if donchian_signal:
                self._donchian_pvo_candidates += 1
                # AND条件: 両方がTrue の時だけ「パス」
                if pvo_signal:
                    self._donchian_pvo_passes += 1
            # update volatility
            self.volatility = self.calcurate_volatility(ohlcv_data)

            # update last data
            self.prev_close_time = last_time
            self.append_ohlcv_data_by_time_frame( last_ohlcv_data, self.time_frame )
            # 最新行を追加し、最古を削除する
            self.del_ohlcv_data_by_time_frame( self.time_frame )   

            # シグナル更新フラグ初期化
            is_update_ohlcv_1 = False

            # --------------------------------------------
            # 終端判断
            # --------------------------------------------
            # epoch時間に変換

            next_epoch = last_time + self.time_frame * 60
            end_ohlcv_data = self.get_back_test_ohlcv_data_by_time_frame(self.time_frame)
            end_epoch = end_ohlcv_data[-1]['close_time']
            #nep = datetime.fromtimestamp(next_epoch).strftime('%Y/%m/%d %H:%M:%S')
            #eep = datetime.fromtimestamp(end_epoch).strftime('%Y/%m/%d %H:%M:%S')
            #print(f"next_epoch : {nep} end_epoch : {eep}")
            if next_epoch >= end_epoch:
                # 次のデータ時間を更新
                self.progress_time = -1

        return False

    def update_price_data(self):
        """
        価格データとトレードシグナルを更新するメソッドです。
        """

        # 価格データの更新
        # TODO 本番では開始・終端時間はコンフィグ取得ではなく自動計算　終端は今　開始は必要期間をさかのぼって取得
        start_epoch = Config.get_start_epoch()
        end_epoch = Config.get_end_epoch()
        
        # --------------------------------------------
        # データの更新(15分) ※常に最新で入れ替える
        # --------------------------------------------
        tmp_ohlcv_data_2 = self.exchange.fetch_latest_ohlcv(self.psar_time_frame)
        self.set_ohlcv_data_by_time_frame(tmp_ohlcv_data_2,self.psar_time_frame)

        # --------------------------------------------
        # データの更新(120分)
        # --------------------------------------------
        # 確定した最新値を取得
        tmp_ohlcv_data_1 = self.exchange.fetch_ohlcv(start_epoch, end_epoch, self.time_frame)
        last_ohlcv_data = tmp_ohlcv_data_1[-1]

        # 最新値を取得
        self.latest_ohlcv_data = self.exchange.fetch_latest_ohlcv(self.time_frame)
        self.ticker = self.exchange.fetch_ticker()
        self.volume = self.latest_ohlcv_data[0]['Volume']

        # 初回の処理
        if self.prev_close_time == 0:            
            self.prev_close_time = last_ohlcv_data['close_time']
            # 初回のみ初期化
            self.set_ohlcv_data_by_time_frame(tmp_ohlcv_data_1, self.time_frame)
            self.volatility = self.calcurate_volatility(tmp_ohlcv_data_1)
            return

        # donchianシグナル演算は常時実施
        ohlcv_data = self.get_ohlcv_data_by_time_frame(self.time_frame)
        dc, high, low = self.__evaluate_donchian(ohlcv_data, self.ticker)
        
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

        # データの更新時
        if self.prev_close_time < last_ohlcv_data['close_time']:

            # PVO update
            volume = last_ohlcv_data['Volume']
            ohlcv_data = self.get_ohlcv_data_by_time_frame(self.time_frame)
            pvo, value = self.__evaluate_pvo(ohlcv_data, volume)
            self.signals['pvo']['signal'] = pvo
            self.signals['pvo']['info']['value'] = value
            
            # DonchianシグナルとPVOシグナルの同時発生を記録
            # ✅ 修正: Donchian発生時にPVOも同時にTRUEの場合だけカウント
            donchian_signal = self.signals['donchian']['signal']
            pvo_signal = self.signals['pvo']['signal']
            
            if donchian_signal:
                self._donchian_pvo_candidates += 1
                # AND条件: 両方がTrue の時だけ「パス」
                if pvo_signal:
                    self._donchian_pvo_passes += 1
            # update volatility
            self.volatility = self.calcurate_volatility(tmp_ohlcv_data_1)
            # update last data
            self.prev_close_time = last_ohlcv_data['close_time']
            # 最新行を追加し、最古を削除する
            # バックテストの場合は、2h経過時にデータ一覧を追加してからシグナル再計算する
            self.append_ohlcv_data_by_time_frame(last_ohlcv_data, self.time_frame)
            # 最新行を追加し、最古を削除する
            self.del_ohlcv_data_by_time_frame(self.time_frame)   

        return

    def initialise_back_test_ohlcv_data(self):
        """
        バックテスト用取引データ初期化
        """
        cache = OHLCVCache()
        # 指定された期間のバックテストデータを取得
        start_epoch = Config.get_start_epoch()
        # 初期分析に必要な時間を計算
        initial_term = Config.get_test_initial_max_term()
        diff_time = initial_term * self.time_frame
        td = timedelta(minutes=diff_time)
        # 指定のstart時間から遡った時間を取得
        org_start_time = datetime.strptime(Config.get_start_time(), "%Y/%m/%d %H:%M")
        start_time = org_start_time - td
        # 秒を切り捨て
        start_time = start_time.replace(second=0)
        # epoch時間に変換
        start_epoch = int(start_time.timestamp())

        # 時間足データ初期化（キャッシュを優先。既存JSONがあれば取り込み）
        for data_dict in self.back_test_ohlcv_data:
            time_frame = data_dict["time_frame"]
            end_epoch = Config.get_end_epoch() + time_frame * 60
            self.logger.log(f"時間足データ {time_frame} 分 初期化")

            symbol = Config.get_market()

            # 互換: 旧JSONキャッシュを優先取り込み（2箇所パスを探索）
            legacy_files = [
                f"ohlcv_data/ohlcv_data_{start_epoch}_{end_epoch}_{time_frame}.json",
                f"logs/ohlcv_data/ohlcv_data_{start_epoch}_{end_epoch}_{time_frame}.json",
            ]
            legacy_loaded = False
            for lf in legacy_files:
                if os.path.exists(lf):
                    try:
                        self.logger.log(f"既存ファイル {lf} を取り込み -> DB 反映")
                        with open(lf, "r") as f:
                            legacy_data = json.load(f)
                        # DB に流し込む（不足分のみ Upsert）
                        cache.upsert_candles(symbol, time_frame, legacy_data)
                        legacy_loaded = True
                        break
                    except Exception as e:
                        self.logger.log_error(f"旧キャッシュ取り込み失敗: {lf} err={e}")

            # DB に十分なデータがあればそのまま使用。なければサーバから不足分取得
            if not cache.has_sufficient_cache(symbol, time_frame, start_epoch, end_epoch):
                self.logger.log("キャッシュ不足 -> サーバから取得しDBに格納")
                try:
                    fetched = self.exchange.fetch_ohlcv(start_epoch, end_epoch, time_frame)
                    cache.upsert_candles(symbol, time_frame, fetched)
                except Exception as e:
                    # バックテストモード時のAPIエラーはログして継続
                    # キャッシュにあるデータで進行
                    self.logger.log_error(f"キャッシュ不足かつAPI取得失敗（続行）: {e}")
                    self.logger.log(f"既存キャッシュから利用可能なデータを使用します")

            # DB から最終的な範囲データを復元
            data = cache.get_range(symbol, time_frame, start_epoch, end_epoch)
            data_dict["data"] = data

            # 互換: 旧ファイル名でもJSONを残しておく（後方互換・解析用途）
            try:
                os.makedirs("ohlcv_data", exist_ok=True)
                compat_file = f"ohlcv_data/ohlcv_data_{start_epoch}_{end_epoch}_{time_frame}.json"
                with open(compat_file, "w") as wf:
                    json.dump(data, wf)
            except Exception as e:
                self.logger.log_error(f"互換JSON保存失敗: {e}")

        self.logger.log("時間足データ初期化 done")

        return

    def del_ohlcv_data_by_time_frame(self, target_time_frame):
        """
        指定されたtime_frameの先頭行を削除する
        """
        for data_dict in self.ohlcv_data:
            if data_dict["time_frame"] == target_time_frame:
                ohlcv_data = data_dict["data"]
                del ohlcv_data[0]
        return None

    def append_ohlcv_data_by_time_frame(self, ohlcv_data, target_time_frame):
        """
        指定されたtime_frameの終端にデータを追加する
        """
        for data_dict in self.ohlcv_data:
            if data_dict["time_frame"] == target_time_frame:
                tmp_ohlcv_data = data_dict["data"]
                tmp_ohlcv_data.append(ohlcv_data)
        return None

    def set_ohlcv_data_by_time_frame(self, ohlcv_data, target_time_frame):
        """
        指定されたtime_frameのデータに、指定データリストを置き換える
        """
        for data_dict in self.ohlcv_data:
            if data_dict["time_frame"] == target_time_frame:
                data_dict["data"] = ohlcv_data.copy()
        
        return None

    def get_ohlcv_data_by_time_frame(self, target_time_frame):
        """
        指定されたtime_frameのデータリストを取得する
        """
        for data_dict in self.ohlcv_data:
            if data_dict["time_frame"] == target_time_frame:
                return data_dict["data"]
        return None

    def get_back_test_ohlcv_data_by_time_frame(self, target_time_frame):
        """
        （バックテスト用）指定されたtime_frameのデータを取得
        """
        for data_dict in self.back_test_ohlcv_data:
            if data_dict["time_frame"] == target_time_frame:
                return data_dict["data"]
        return None

    def get_back_test_ohlcv_data(self, target_unix_time, time_frame):
        """
        （バックテスト用）指定されたtime_frameのデータで、指定されたunix_timeのデータを取得
        """
        closest_data = None
        time_difference = float('inf')  # 初期値を無限大に設定

        ohlcv_data_entry = next(entry for entry in self.back_test_ohlcv_data if entry["time_frame"] == time_frame)
        ohlcv_data = ohlcv_data_entry["data"]

        # 前回の検索終了点から再開するように修正
        start_index = ohlcv_data_entry["prev_index"]

        # 秒を切り捨て
        target_time = datetime.fromtimestamp(target_unix_time)
        target_time = target_time.replace(second=0)
        target_unix_time_aligned = int(target_time.timestamp())

        # YMDDBG
        #leno = len(ohlcv_data)
        #print(f"start_index: {start_index} len(ohlcv_data): {leno}")

        for i in range(start_index, len(ohlcv_data)):
            data = ohlcv_data[i]
            data_unix_time = data['close_time']

            if (data_unix_time + time_frame * 60) >= target_unix_time:
                # 目標UNIX時間を超えているデータの場合
                current_difference = data_unix_time - target_unix_time_aligned
                if current_difference < time_difference:
                    # より近いデータを見つけた場合
                    time_difference = current_difference
                    closest_data = data
                    # 保存したインデックスの次から開始
                    ohlcv_data_entry["prev_index"] = i
                    break

        # 最初から保存したインデックスまでを探す
        for i in range(start_index):
            data = ohlcv_data[i]
            data_unix_time = data['close_time']

            if (data_unix_time + time_frame * 60) >= target_unix_time:
                # 目標UNIX時間を超えているデータの場合
                current_difference = data_unix_time - target_unix_time_aligned
                if current_difference < time_difference:
                    # より近いデータを見つけた場合
                    closest_data = data

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
        return self.indicator_service.calculate_donchian(ohlcv_data, price)

    def __calc_ema(self, term, data):
        """
        Exponential Moving Average（指数平滑移動平均）を計算するメソッドです。
        DEPRECATED: Use indicator_service.calculate_ema() instead.

        Args:
            term (int): 移動平均の期間
            data (list): 価格データのリスト

        Returns:
            float: EMAの値
        """
        return self.indicator_service.calculate_ema(term, data)

    def __calcurate_pvo(self, ohlcv_data, volume):
        """
        Price Volume Oscillator（PVO）を計算するメソッドです。
        DEPRECATED: Use indicator_service.calculate_pvo() instead.

        Args:
            ohlcv_data (list): OHLCVデータのリスト
            volume (float): 出来高

        Returns:
            float: PVOの値
        """
        return self.indicator_service.calculate_pvo(ohlcv_data, volume)

    def __evaluate_pvo(self, ohlcv_data, volume):
        """
        PVOに基づくトレードシグナルを評価するメソッドです。

        Args:
            ohlcv_data (list): OHLCVデータのリスト
            volume (float): 出来高

        Returns:
            bool: トレードシグナル (True, False)
        """
        pvo_value = self.indicator_service.calculate_pvo(ohlcv_data, volume)
        judge = self.indicator_service.evaluate_pvo(pvo_value)
        return judge, pvo_value

    def __evaluate_keltner(self, ohlcv_data, current_price):
        """
        Keltnerチャネルに基づくトレードシグナルを評価するメソッドです（だまし回避フィルタ）。
        
        判定ロジック（シンプル版）:
        1. Keltner幅（ボラティリティ）をチェック
        2. 幅が十分広い（= トレンド強い）ときのみENTRY許可
        3. 幅が狭い（= レンジ相場）ときはENTRY拒否（だまし回避）
        
        ※ドンチャンブレイク方向との整合性は trading_strategy.py で判定
        
        Args:
            ohlcv_data (list): OHLCVデータのリスト
            current_price (float): 現在価格

        Returns:
                        tuple: (volatility_ok: bool, side: str, info: dict)
                                     volatility_ok: ボラティリティ条件を満たすか（True=幅広い）
                                     side: ブレイクアウト方向 ('BUY'/'SELL'/None) ※価格位置で判定
        """
        if len(ohlcv_data) < Config.get_keltner_ema_period():
            return False, None, {'upper': 0, 'middle': 0, 'lower': 0, 'width_expanding': False}
        
        # Keltnerチャネル計算
        ema_period = Config.get_keltner_ema_period()
        atr_multiplier = Config.get_keltner_atr_multiplier()
        middle, upper, lower = self.indicator_service.calculate_keltner_channel(
            ohlcv_data, 
            ema_period=ema_period, 
            atr_multiplier=atr_multiplier
        )
        
        # None チェック
        if middle is None or upper is None or lower is None:
            return False, None, {'upper': 0, 'middle': 0, 'lower': 0, 'width_expanding': False}
        
        # 1. ボラティリティチェック（Keltner幅 >= ATR × 閾値倍率）
        width_current = upper - lower
        atr = self.indicator_service.calculate_atr(ohlcv_data, term=ema_period)
        # ATR倍率設定値をそのまま閾値として使用（例: 2.0倍なら width >= ATR×2.0）
        volatility_ok = width_current >= (atr * atr_multiplier * 0.8)  # 80%緩和
        
        # 2. 価格位置でブレイクアウト方向を判定
        side = None
        if current_price > upper:
            side = 'BUY'  # 上限突破
        elif current_price < lower:
            side = 'SELL'  # 下限突破
        
        info = {
            'upper': upper,
            'middle': middle,
            'lower': lower,
            'width_expanding': volatility_ok,
            'atr': atr,
            'width': width_current,
            'volatility_ok': volatility_ok
        }
        
        return volatility_ok, side, info

    # ========================================
    # PVOヒット率メトリクス
    # ========================================
    def get_pvo_donchian_metrics(self):
        """Donchian候補バー数とPVO通過バー数からヒット率を返す。

        Returns:
            dict: {'donchian_candidates': int, 'pvo_passes': int, 'pvo_pass_ratio': float}
        """
        if self._donchian_pvo_candidates > 0:
            ratio = self._donchian_pvo_passes / self._donchian_pvo_candidates
        else:
            ratio = 0.0
        return {
            'donchian_candidates': self._donchian_pvo_candidates,
            'pvo_passes': self._donchian_pvo_passes,
            'pvo_pass_ratio': ratio
        }

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

