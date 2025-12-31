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
from bitget_exchange import BitgetExchange
from portfolio import Portfolio
from new_indicators import NewIndicators
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
        
        # 新指標（Phase 22a-22c）
        self.new_indicators = NewIndicators()
        self.enable_strategy_a_adx = Config.get_config_bool('Strategy', 'enable_strategy_a_adx', 1)
        self.enable_strategy_b_bb_rsi_sma = Config.get_config_bool('Strategy', 'enable_strategy_b_bb_rsi_sma', 0)
        self.enable_strategy_c_combined = Config.get_config_bool('Strategy', 'enable_strategy_c_combined', 0)
        
        # 新指標パラメータ
        self.bb_period = Config.get_config_int('Strategy', 'bb_period', 20)
        self.bb_std_dev = Config.get_config_float('Strategy', 'bb_std_dev', 2.0)
        self.rsi_period = Config.get_config_int('Strategy', 'rsi_period', 14)
        self.rsi_overbought = Config.get_config_int('Strategy', 'rsi_overbought', 70)
        self.rsi_oversold = Config.get_config_int('Strategy', 'rsi_oversold', 30)
        self.sma_fast_period = Config.get_config_int('Strategy', 'sma_fast_period', 50)
        self.sma_slow_period = Config.get_config_int('Strategy', 'sma_slow_period', 200)
        self.macd_fast_period = Config.get_config_int('Strategy', 'macd_fast_period', 12)
        self.macd_slow_period = Config.get_config_int('Strategy', 'macd_slow_period', 26)
        self.macd_signal_period = Config.get_config_int('Strategy', 'macd_signal_period', 9)
        
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
        self.adx_term = Config.get_config_int('Strategy', 'adx_term', 14)
        self.adx_continue_num = Config.get_config_int('Strategy', 'adx_continue_num', 3)
        self.adx_bull_threshold = Config.get_config_int('Strategy', 'adx_bull_threshold', 25)
        self.adx_bear_threshold = Config.get_config_int('Strategy', 'adx_bear_threshold', 20)

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
        if not self.psar or len(self.psar) == 0:
            return None
        return self.psar[-1]
    
    def get_psarbull(self):
        if not self.psarbull or len(self.psarbull) == 0:
            return None
        return self.psarbull[-1]
    
    def get_psarbear(self):
        if not self.psarbear or len(self.psarbear) == 0:
            return None
        return self.psarbear[-1]

    def get_adx(self):
        if not self.adx or len(self.adx) == 0:
            return 0
        return self.adx[-1]
    
    def get_adx_bull(self):
        return self.adx_bull
    
    def get_adx_bear(self):
        return self.adx_bear

    def get_donchian_high(self, period=20):
        """
        Donchian Channel の高値を取得 (N期間の最高値)
        
        Args:
            period (int): 期間（デフォルト 20）
        
        Returns:
            float: Donchian高値、データ不足時は現在値
        """
        main_time_frame = '1h'
        
        # ダミーモードの判定（バックテスト or ペーパートレード）
        is_dummy = False
        try:
            from config import Config
            is_dummy = Config.is_dummy_mode()
        except:
            pass
        
        if is_dummy:
            ohlcv_data = self.price_data_management.get_back_test_ohlcv_data_by_time_frame(main_time_frame)
        else:
            ohlcv_data = self.price_data_management.get_ohlcv_data_by_time_frame(main_time_frame)
        
        if not ohlcv_data or len(ohlcv_data) < period:
            return self.price_data_management.get_ticker()
        
        # 高値抽出（辞書形式対応）
        highs = []
        for candle in ohlcv_data[-period:]:
            if isinstance(candle, dict):
                highs.append(candle.get('high_price', candle.get('high', 0)))
            else:
                highs.append(candle[2] if len(candle) > 2 else 0)
        
        return max(highs) if highs else self.price_data_management.get_ticker()
    
    def get_donchian_low(self, period=20):
        """
        Donchian Channel の安値を取得 (N期間の最安値)
        
        Args:
            period (int): 期間（デフォルト 20）
        
        Returns:
            float: Donchian安値、データ不足時は現在値
        """
        main_time_frame = '1h'
        
        # ダミーモードの判定（バックテスト or ペーパートレード）
        is_dummy = False
        try:
            from config import Config
            is_dummy = Config.is_dummy_mode()
        except:
            pass
        
        if is_dummy:
            ohlcv_data = self.price_data_management.get_back_test_ohlcv_data_by_time_frame(main_time_frame)
        else:
            ohlcv_data = self.price_data_management.get_ohlcv_data_by_time_frame(main_time_frame)
        
        if not ohlcv_data or len(ohlcv_data) < period:
            return self.price_data_management.get_ticker()
        
        # 安値抽出（辞書形式対応）
        lows = []
        for candle in ohlcv_data[-period:]:
            if isinstance(candle, dict):
                lows.append(candle.get('low_price', candle.get('low', 0)))
            else:
                lows.append(candle[3] if len(candle) > 3 else 0)
        
        return min(lows) if lows else self.price_data_management.get_ticker()
    
    def get_bb_upper(self, period=20, sigma=2.0):
        """
        Bollinger Bands の上限を取得
        
        Args:
            period (int): 期間（デフォルト 20）
            sigma (float): シグマ倍数（デフォルト 2.0）
        
        Returns:
            float: BB上限値
        """
        main_time_frame = '1h'
        
        # ダミーモードの判定（バックテスト or ペーパートレード）
        is_dummy = False
        try:
            from config import Config
            is_dummy = Config.is_dummy_mode()
        except:
            pass
        
        if is_dummy:
            ohlcv_data = self.price_data_management.get_back_test_ohlcv_data_by_time_frame(main_time_frame)
        else:
            ohlcv_data = self.price_data_management.get_ohlcv_data_by_time_frame(main_time_frame)
        
        if not ohlcv_data or len(ohlcv_data) < period:
            return self.price_data_management.get_ticker()
        
        # 終値抽出（辞書形式対応）
        closes = []
        for candle in ohlcv_data[-period:]:
            if isinstance(candle, dict):
                closes.append(candle.get('close_price', candle.get('close', 0)))
            else:
                closes.append(candle[4] if len(candle) > 4 else 0)
        
        closes_array = np.array(closes)
        sma = np.mean(closes_array)
        std = np.std(closes_array)
        return sma + (sigma * std)
    
    def get_bb_lower(self, period=20, sigma=2.0):
        """
        Bollinger Bands の下限を取得
        
        Args:
            period (int): 期間（デフォルト 20）
            sigma (float): シグマ倍数（デフォルト 2.0）
        
        Returns:
            float: BB下限値
        """
        main_time_frame = '1h'
        
        # ダミーモードの判定（バックテスト or ペーパートレード）
        is_dummy = False
        try:
            from config import Config
            is_dummy = Config.is_dummy_mode()
        except:
            pass
        
        if is_dummy:
            ohlcv_data = self.price_data_management.get_back_test_ohlcv_data_by_time_frame(main_time_frame)
        else:
            ohlcv_data = self.price_data_management.get_ohlcv_data_by_time_frame(main_time_frame)
        
        if not ohlcv_data or len(ohlcv_data) < period:
            return self.price_data_management.get_ticker()
        
        # 終値抽出（辞書形式対応）
        closes = []
        for candle in ohlcv_data[-period:]:
            if isinstance(candle, dict):
                closes.append(candle.get('close_price', candle.get('close', 0)))
            else:
                closes.append(candle[4] if len(candle) > 4 else 0)
        
        closes_array = np.array(closes)
        sma = np.mean(closes_array)
        std = np.std(closes_array)
        return sma - (sigma * std)

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
        if length < 3:
            # データ不足の場合は計算をスキップ
            return
        
        psar = [None] * length

        # 初回のpsarの初期設定
        # 【改善】前回計算値を継承しつつ、データ長変化に対応
        if not self.psar or len(self.psar) != length:
            # 初回計算またはデータ長が変わった場合のみ初期化
            psar[0] = close[0]
            psar[1] = close[0]
        else:
            # 前回計算値を継承して連続性を保持
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

        if length < adx_period * 2:
            # データ不足の場合はデフォルト値を設定
            self.adx = [0] * length
            self.adx_bull = False
            self.adx_bear = False
            return
        
        tr_smooth[adx_period - 1] = sum(tr[1:adx_period])
        plus_dm_smooth[adx_period - 1] = sum(plus_dm[1:adx_period])
        minus_dm_smooth[adx_period - 1] = sum(minus_dm[1:adx_period])

        for i in range(adx_period, length):
            tr_smooth[i] = tr_smooth[i - 1] - (tr_smooth[i - 1] / adx_period) + tr[i]
            plus_dm_smooth[i] = plus_dm_smooth[i - 1] - (plus_dm_smooth[i - 1] / adx_period) + plus_dm[i]
            minus_dm_smooth[i] = minus_dm_smooth[i - 1] - (minus_dm_smooth[i - 1] / adx_period) + minus_dm[i]

        # ゼロ除算を防ぐ
        with np.errstate(divide='ignore', invalid='ignore'):
            plus_di = np.where(tr_smooth != 0, 100 * (plus_dm_smooth / tr_smooth), 0)
            minus_di = np.where(tr_smooth != 0, 100 * (minus_dm_smooth / tr_smooth), 0)
            dx = np.where((plus_di + minus_di) != 0, 
                         100 * np.abs((plus_di - minus_di) / (plus_di + minus_di)), 
                         0)

        adx = np.zeros(length)
        adx[adx_period - 1] = sum(dx[adx_period - 1:2 * adx_period - 1]) / adx_period

        for i in range(adx_period, length):
            adx[i] = ((adx[i - 1] * (adx_period - 1)) + dx[i]) / adx_period

        self.adx = adx.tolist()

        self.adx_bull = all(adx[i] > bull_threshold for i in range(-continue_num, 0))
        self.adx_bear = all(adx[i] < bear_threshold for i in range(-continue_num, 0))
        
        return

    def evaluate_strategy_a_adx(self):
        """
        Strategy A: ADX\u30d9\u30fc\u30b9の\u5e02\u5834\u30ec\u30b8\u30fc\u30e0\u691c\u51fa
        ADX\u304c\u6240\u5b9a\u5024\u3092\u8d85\u3048\u308b\u3068\u304d\u306fbull/bear\u3092\u8fd4\u3059\        
        """
        if not self.enable_strategy_a_adx:
            return {"signal": "NONE", "bull": False, "bear": False, "adx": 0}
        
        adx_value = self.adx[-1] if self.adx else 0
        return {
            # signal を BUY/SELL に正規化して返す（BULL/BEAR も詳細として保持）
            "signal": "BUY" if self.adx_bull else ("SELL" if self.adx_bear else "NONE"),
            "bull": self.adx_bull,
            "bear": self.adx_bear,
            "adx": adx_value
        }

    def evaluate_strategy_b_bb_rsi_sma(self):
        """
        Strategy B: Bollinger Bands + RSI + SMA\u8907\u5408\u6307\u6a19
        \u8907\u6570\u306e\u6307\u6a19\u304c\u63c3\u3063\u305f\u3068\u304d\u306esignal\u3092\u8fd4\u3059
        """
        if not self.enable_strategy_b_bb_rsi_sma:
            return {"signal": "NONE", "bb": {}, "rsi": {}, "sma": {}}
        
        try:
            main_time_frame = Config.get_time_frame()
            ohlcv_data = self.price_data_management.get_ohlcv_data(main_time_frame)
            
            if not ohlcv_data or len(ohlcv_data) < self.sma_slow_period:
                return {"signal": "NONE", "bb": {}, "rsi": {}, "sma": {}}
            
            close_prices = [item['close_price'] for item in ohlcv_data]
            current_price = self.price_data_management.get_ticker()
            
            # Bollinger Bands\u8a08\u7b97
            bb_upper, bb_middle, bb_lower = self.new_indicators.calc_bollinger_bands(
                close_prices, self.bb_period, self.bb_std_dev
            )
            
            # RSI\u8a08\u7b97
            rsi_value = self.new_indicators.calc_rsi(close_prices, self.rsi_period)
            
            # SMA\u8a08\u7b97
            sma_fast, sma_slow = self.new_indicators.calc_sma(
                close_prices, self.sma_fast_period, self.sma_slow_period
            )
            
            # Signal\u8a55\u4fa1
            bb_signal = "BUY" if current_price < bb_lower else ("SELL" if current_price > bb_upper else "NONE")
            rsi_signal = "BUY" if rsi_value < self.rsi_oversold else ("SELL" if rsi_value > self.rsi_overbought else "NONE")
            sma_signal = "BUY" if sma_fast > sma_slow else ("SELL" if sma_fast < sma_slow else "NONE")
            
            # \u8907\u5408\u30b7\u30b0\u30ca\u30eb\uff08\u8907\u6570\u4e00\u81f4\u3067BUY/SELL\uff09
            signals = [bb_signal, rsi_signal, sma_signal]
            buy_count = signals.count("BUY")
            sell_count = signals.count("SELL")
            
            combined_signal = "BUY" if buy_count >= 2 else ("SELL" if sell_count >= 2 else "NONE")
            
            return {
                "signal": combined_signal,
                "bb": {"upper": bb_upper, "middle": bb_middle, "lower": bb_lower, "signal": bb_signal},
                "rsi": {"value": rsi_value, "signal": rsi_signal},
                "sma": {"fast": sma_fast, "slow": sma_slow, "signal": sma_signal}
            }
        except Exception as e:
            self.logger.log(f"Error in Strategy B evaluation: {str(e)}")
            return {"signal": "NONE", "bb": {}, "rsi": {}, "sma": {}}

    def evaluate_strategy_c_combined(self):
        """
        Strategy C: \u5168\u6307\u6a19\u7d71\u5408 (ADX + BB + RSI + SMA)
        Strategy A\u3068B\u306e\u4e21\u65b9\u304c\u63c3\u3063\u305f\u3068\u304d\u306esignal\u3092\u8fd4\u3059
        """
        if not self.enable_strategy_c_combined:
            return {"signal": "NONE", "strategy_a": {}, "strategy_b": {}}
        
        try:
            strategy_a_result = self.evaluate_strategy_a_adx()
            strategy_b_result = self.evaluate_strategy_b_bb_rsi_sma()
            
            # \u4e21\u65b9\u304c\u63c3\u3063\u305f\u3068\u304d\u306eみbull/bear\u3092\u8a55\u4fa1
            a_signal = strategy_a_result.get("signal", "NONE")
            b_signal = strategy_b_result.get("signal", "NONE")
            
            if a_signal != "NONE" and b_signal != "NONE" and a_signal == b_signal:
                combined_signal = a_signal
            else:
                combined_signal = "NONE"
            
            return {
                "signal": combined_signal,
                "strategy_a": strategy_a_result,
                "strategy_b": strategy_b_result
            }
        except Exception as e:
            self.logger.log(f"Error in Strategy C evaluation: {str(e)}")
            return {"signal": "NONE", "strategy_a": {}, "strategy_b": {}}

    def evaluate_all_strategies(self):
        """
        \u3059\u3079\u3066\u306e\u30b9\u30c8\u30e9\u30c6\u30b8\u30fc\u3092\u8a55\u4fa1\u3057\u3001\u6709\u52b9\u306a\u3082\u306e\u3092\u8fd4\u3059
        """
        results = {
            "strategy_a": self.evaluate_strategy_a_adx(),
            "strategy_b": self.evaluate_strategy_b_bb_rsi_sma(),
            "strategy_c": self.evaluate_strategy_c_combined()
        }
        return results

    def __calc_stop_psar(self):
        """
        ストップ値をパラボリックASRにする関数
        
        ポジションのBUY/SELLに応じてパラボリックSARの値をストップポジションとする
        """

        # 現在のストップレンジ
        prev_stop_offset = self.stop_offset

        psarbull = self.get_psarbull()
        psarbear = self.get_psarbear()

        # PSAR未計算の場合は前回の値を維持
        if psarbull is None and psarbear is None:
            return prev_stop_offset

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
        
        # ポジションが辞書でない場合は初期化（ポジションなし）
        if not isinstance(position, dict):
            position = {"quantity": 0, "side": None, "position_price": 0}
        
        quantity = position.get("quantity", 0)
        side = position.get("side", None)
        position_price = position.get("position_price", 0)
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

            # ゼロ除算を防ぐ
            if stop_range == 0 or price == 0:
                self.logger.log_error(f"計算エラー: stop_range={stop_range}, price={price}")
                return 0

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
    # 注文執行用の取引所クラスを動的に選択（ハイブリッド構成）
    exchange_type = Config.get_exchange_trade()
    if exchange_type == 'bitget':
        exchange = BitgetExchange(Config.get_bitget_api_key(), Config.get_bitget_api_secret(), Config.get_bitget_api_passphrase())
    else:  # デフォルトは bybit
        exchange = BybitExchange(Config.get_bybit_api_key(), Config.get_bybit_api_secret())
    
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
