from datetime import datetime
from datetime import timedelta
from config import Config
from logger import Logger
from bybit_exchange import BybitExchange
from bitget_exchange import BitgetExchange
from ohlcv_cache import OHLCVCache
import pprint
import json
import os

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
        # 価格データ取得用の取引所を使用（ハイブリッド構成）
        exchange_type = Config.get_exchange_data()
        if exchange_type == 'bitget':
            self.exchange = BitgetExchange(Config.get_bitget_api_key(), Config.get_bitget_api_secret(), Config.get_bitget_api_passphrase())
        else:  # デフォルトは bybit（価格データ取得用）
            self.exchange = BybitExchange(Config.get_bybit_api_key(), Config.get_bybit_api_secret())
        
        self.logger = Logger()
        self.cache = OHLCVCache()  # OHLCVキャッシュを初期化
        
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
        self.signals = {'donchian': {'signal': False, 'side': None, 'info': {'highest': 0, 'lowest': 0} }, 'pvo': {'signal': False, 'side': None, 'info':{'value': 0} }}
        self.volatility = 0
        self.prev_close_time = 0
        
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
        volatility_term = Config.get_volatility_term()
        # 最新N期間の各足における高値と安値の差（True Range相当）の平均を計算
        tr_values = []
        for i in ohlcv_data[-1 * volatility_term:]:
            tr = i['high_price'] - i['low_price']
            tr_values.append(tr)
        
        volatility = sum(tr_values) / len(tr_values) if tr_values else 0
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
            # 120分足をサーバから取得
            # TODO 取得済テーブルから取得
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

            # 初期化時に close_time を設定（1970/01/01 対策）
            self.close_time = last_ohlcv_data['close_time']
            self.ticker = last_ohlcv_data['close_price']

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

    def _fetch_with_retry(self, func, *args, retries=3):
        """
        API呼び出しをリトライ付きで実行するメソッドです。
        
        Args:
            func: 呼び出す関数
            *args: 関数の引数
            retries: リトライ回数（デフォルト：3）
            
        Returns:
            API の戻り値
            
        Raises:
            Exception: すべてのリトライに失敗した場合
        """
        import time
        
        for attempt in range(retries):
            try:
                return func(*args)
            except Exception as e:
                if attempt == retries - 1:
                    # 最後のリトライに失敗した場合は例外を再発生
                    self.logger.log_error(f"【TIMEOUT】API呼び出し失敗（リトライ {attempt+1}/{retries} 終了）: {e}")
                    raise
                wait_time = min(2 ** attempt, 30)  # 指数バックオフ: 1秒, 2秒, 4秒...最大30秒
                self.logger.log(f"API呼び出し失敗（リトライ {attempt+1}/{retries}）: {e} → {wait_time}秒待機")
                time.sleep(wait_time)

    def update_price_data(self):
        """
        価格データとトレードシグナルを更新するメソッドです。
        リトライロジック、例外処理、バリデーション機能を備えています。
        """
        try:
            # 価格データの更新
            # ホットテスト時は現在時刻を基準に取得、バックテスト時はコンフィグから取得
            if Config.get_back_test_mode() == 0:  # ホットテスト時
                # 現在時刻
                now = int(time.time())
                # 過去N期間分のデータを取得
                # ボラティリティ計算に必要な期間（14期間）+ 安全マージン
                volatility_term = Config.get_volatility_term()
                lookback_minutes = (volatility_term + 10) * self.time_frame  # 余裕を持たせる
                start_epoch = now - (lookback_minutes * 60)
                end_epoch = now
            else:  # バックテスト時
                start_epoch = Config.get_start_epoch()
                end_epoch = Config.get_end_epoch()
            
            # --------------------------------------------
            # データの更新(15分) ※常に最新で入れ替える
            # リトライ付きで取得
            # --------------------------------------------
            try:
                tmp_ohlcv_data_2 = self._fetch_with_retry(
                    self.exchange.fetch_latest_ohlcv, 
                    self.psar_time_frame,
                    retries=3
                )
                self.set_ohlcv_data_by_time_frame(tmp_ohlcv_data_2, self.psar_time_frame)
            except Exception as e:
                self.logger.log_error(f"15分足データ取得失敗: {e}")
                return False

            # --------------------------------------------
            # データの更新(240分)
            # 確定した最新値を取得（リトライ付き）
            # ※ fetch_ohlcv()の最後のエントリは「未確定足」を含むため除外
            # --------------------------------------------
            try:
                tmp_ohlcv_data_1 = self._fetch_with_retry(
                    self.exchange.fetch_ohlcv,
                    start_epoch, end_epoch, self.time_frame,
                    retries=3
                )
                
                # 空リストチェック
                if not tmp_ohlcv_data_1:
                    self.logger.log_error("fetch_ohlcv: 空リスト返却（データがありません）")
                    return False
                
                # ✅ 修正: fetch_ohlcv()の最後のエントリ（未確定足）を除外
                # Bybit APIは現在実行中の240分足（未確定）まで含めて返す
                # → 確定足のみを使用する場合は最後から2番目を取得
                if len(tmp_ohlcv_data_1) > 1:
                    # 最新の確定足は「1つ前」
                    last_ohlcv_data = tmp_ohlcv_data_1[-2]
                    confirmed_data = tmp_ohlcv_data_1[:-1]  # 未確定足を除外
                else:
                    # データが1件のみの場合は、それが確定足と判断
                    last_ohlcv_data = tmp_ohlcv_data_1[-1]
                    confirmed_data = tmp_ohlcv_data_1
            except IndexError as e:
                self.logger.log_error(f"120分足データ取得エラー: リスト が空です: {e}")
                return False
            except Exception as e:
                self.logger.log_error(f"120分足データ取得失敗: {e}")
                return False

            # 最新値を取得（リトライ付き）
            try:
                self.latest_ohlcv_data = self._fetch_with_retry(
                    self.exchange.fetch_latest_ohlcv,
                    self.time_frame,
                    retries=3
                )
                
                if not self.latest_ohlcv_data:
                    self.logger.log_error("fetch_latest_ohlcv: 空リスト返却（データがありません）")
                    return False
                
                # ticker と volume を取得（キー存在チェック付き）
                if 'Volume' not in self.latest_ohlcv_data[0]:
                    self.logger.log_error("fetch_latest_ohlcv: 'Volume' キーが見つかりません")
                    return False
                
                self.volume = self.latest_ohlcv_data[0]['Volume']
                
            except IndexError as e:
                self.logger.log_error(f"最新足データ取得エラー: リストが空です: {e}")
                return False
            except KeyError as e:
                self.logger.log_error(f"最新足データ取得エラー: キーが見つかりません: {e}")
                return False
            except Exception as e:
                self.logger.log_error(f"最新足データ取得失敗: {e}")
                return False

            # ticker を取得（リトライ付き）
            try:
                self.ticker = self._fetch_with_retry(
                    self.exchange.fetch_ticker,
                    retries=3
                )
            except Exception as e:
                self.logger.log_error(f"ticker取得失敗: {e}")
                return False

            # 初回の処理
            if self.prev_close_time == 0:            
                self.prev_close_time = last_ohlcv_data['close_time']
                # 初回のみ初期化（確定足のみを使用）
                self.set_ohlcv_data_by_time_frame(confirmed_data, self.time_frame)
                self.volatility = self.calcurate_volatility(confirmed_data)
                return True

            # データの更新時（240分足が確定した時のみシグナル再計算）
            if self.prev_close_time < last_ohlcv_data['close_time']:
                # ✅ 修正: 確定足のみでボラティリティを計算
                self.volatility = self.calcurate_volatility(confirmed_data)
                # update last data
                self.prev_close_time = last_ohlcv_data['close_time']
                # 最新行を追加し、最古を削除する
                # バックテストの場合は、2h経過時にデータ一覧を追加してからシグナル再計算する
                self.append_ohlcv_data_by_time_frame(last_ohlcv_data, self.time_frame)
                # 最新行を追加し、最古を削除する
                self.del_ohlcv_data_by_time_frame(self.time_frame)
                
                # 確定足のリストからシグナルを計算（240分足確定時のみ）
                signal_calc_data = self.get_ohlcv_data_by_time_frame(self.time_frame)
                
                # Donchianシグナル：確定足のみから計算
                dc, high, low = self.__evaluate_donchian(signal_calc_data, self.ticker)
                
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

                # PVO：確定足のボリュームのみから計算（240分足確定時のみ）
                pvo, value = self.__evaluate_pvo(signal_calc_data, None)
                self.signals['pvo']['signal'] = pvo
                self.signals['pvo']['info']['value'] = value

            return True
            
        except Exception as e:
            # 予期しない例外をキャッチ
            self.logger.log_error(f"update_price_data メインループエラー: {e}")
            return False

    def initialise_back_test_ohlcv_data(self):
        """
        バックテスト用取引データ初期化
        """
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

        # 取引シンボルを取得
        symbol = self.exchange.get_market_symbol()

        # 時間足データ初期化
        for data_dict in self.back_test_ohlcv_data:
            time_frame = data_dict["time_frame"]
            end_epoch = Config.get_end_epoch() + time_frame * 60
            self.logger.log(f"時間足データ {time_frame} 分 初期化")

            # SQLiteキャッシュから取得を試みる（部分一致：指定期間がキャッシュに含まれているか確認）
            cached_data = self.cache.get_ohlcv_data_partial(start_epoch, end_epoch, time_frame, symbol)
            if cached_data is not None:
                self.logger.log(f"SQLiteキャッシュから {len(cached_data)} 件のデータを取得")
                data_dict["data"] = cached_data
            else:
                # サーバからデータを取得
                exchange_name = Config.get_exchange_data()
                self.logger.log(f"{exchange_name}サーバからデータを取得 (start_epoch={start_epoch}, end_epoch={end_epoch}, time_frame={time_frame})")
                data_dict["data"] = self.exchange.fetch_ohlcv(start_epoch, end_epoch, time_frame)
                # SQLiteキャッシュに保存
                if data_dict["data"]:
                    self.cache.save_ohlcv_data(data_dict["data"], start_epoch, end_epoch, time_frame, symbol)

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
        buy_term = Config.get_donchian_buy_term()
        sell_term = Config.get_donchian_sell_term()
        side = 'None'

        #print(f"ohlcv_data first: {ohlcv_data[0]}")
        #print(f"ohlcv_data last : {ohlcv_data[-1]}")

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
            ohlcv_data (list): OHLCVデータのリスト（確定足のみ）
            volume (float): 出来高（使用しません - 確定足のボリュームのみを使用）

        Returns:
            float: PVOの値
        """
        
        pvo_s_term = Config.get_pvo_s_term()
        pvo_l_term = Config.get_pvo_l_term()
        volume_data = []

        # 確定足のボリュームのみを使用
        data_len = max(pvo_s_term, pvo_l_term)
        for i in ohlcv_data[(-1 * data_len) :]:
            volume_data.append(i['Volume'])
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

