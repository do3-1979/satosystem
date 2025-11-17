"""Indicator calculation service for trading bot.

Centralizes all technical indicator calculations (Donchian, PVO, PSAR, ADX, Volatility)
to improve maintainability, testability, and enable future performance optimizations.
"""
from config import Config
import numpy as np
import collections


class IndicatorService:
    """Service class for calculating technical indicators."""

    def __init__(self, adx_term=14, adx_continue_num=3, adx_bull_threshold=25, adx_bear_threshold=20):
        """Initialize indicator service.
        
        Args:
            adx_term (int): ADX period. Default 14.
            adx_continue_num (int): ADX continuation count. Default 3.
            adx_bull_threshold (float): ADX bullish threshold. Default 25.
            adx_bear_threshold (float): ADX bearish threshold. Default 20.
        """
        # PSAR state
        self.psar = []
        self.psarbull = []
        self.psarbear = []
        # ADX state
        self.adx = []
        self.adx_bull = False
        self.adx_bear = False
        # Configuration
        self.stop_AF_add = Config.get_stop_AF_add()
        self.stop_AF_max = Config.get_stop_AF_max()
        self.adx_term = adx_term
        self.adx_continue_num = adx_continue_num
        self.adx_bull_threshold = adx_bull_threshold
        self.adx_bear_threshold = adx_bear_threshold
        # Donchian incremental cache (monotonic deques)
        self._donchian_cache = {
            'last_len': 0,
            'buy_deque': collections.deque(),  # stores (index, high_price) in decreasing order
            'sell_deque': collections.deque(), # stores (index, low_price) in increasing order
            'buy_term': None,
            'sell_term': None
        }

    # ========================================
    # Donchian Channel
    # ========================================
    def calculate_donchian(self, ohlcv_data, price, buy_term=None, sell_term=None):
        """Calculate Donchian Channel breakout signal.

        Args:
            ohlcv_data (list): List of OHLCV dicts with 'high_price', 'low_price'
            price (float): Current price to check for breakout
            buy_term (int, optional): Period for buy signal. Defaults to config.
            sell_term (int, optional): Period for sell signal. Defaults to config.

        Returns:
            tuple: (side, highest, lowest) where side is 'BUY', 'SELL', or 'None'
        """
        if buy_term is None:
            buy_term = Config.get_donchian_buy_term()
        if sell_term is None:
            sell_term = Config.get_donchian_sell_term()

        # For small window sizes the original simple slicing is faster.
        if buy_term < 50 and sell_term < 50:
            side = 'None'
            highest = max(i['high_price'] for i in ohlcv_data[(-1 * buy_term):])
            if price > highest:
                side = 'BUY'
            lowest = min(i['low_price'] for i in ohlcv_data[(-1 * sell_term):])
            if price < lowest:
                side = 'SELL'
            return side, highest, lowest

        side = 'None'
        data_len = len(ohlcv_data)
        cache = self._donchian_cache
        if (cache['buy_term'] != buy_term or cache['sell_term'] != sell_term or cache['last_len'] > data_len):
            cache['buy_deque'].clear(); cache['sell_deque'].clear(); cache['last_len'] = 0; cache['buy_term'] = buy_term; cache['sell_term'] = sell_term
        start_index = cache['last_len']
        if start_index < data_len:
            buy_deque = cache['buy_deque']; sell_deque = cache['sell_deque']
            for idx in range(start_index, data_len):
                bar = ohlcv_data[idx]; high = bar['high_price']; low = bar['low_price']
                while buy_deque and buy_deque[-1][1] <= high: buy_deque.pop()
                buy_deque.append((idx, high))
                while buy_deque and idx - buy_deque[0][0] >= buy_term: buy_deque.popleft()
                while sell_deque and sell_deque[-1][1] >= low: sell_deque.pop()
                sell_deque.append((idx, low))
                while sell_deque and idx - sell_deque[0][0] >= sell_term: sell_deque.popleft()
            cache['last_len'] = data_len
        if data_len < buy_term:
            highest = max(i['high_price'] for i in ohlcv_data)
        else:
            highest = cache['buy_deque'][0][1] if cache['buy_deque'] else max(i['high_price'] for i in ohlcv_data[-buy_term:])
        if data_len < sell_term:
            lowest = min(i['low_price'] for i in ohlcv_data)
        else:
            lowest = cache['sell_deque'][0][1] if cache['sell_deque'] else min(i['low_price'] for i in ohlcv_data[-sell_term:])
        if price > highest: side = 'BUY'
        elif price < lowest: side = 'SELL'
        return side, highest, lowest

    # ========================================
    # PVO (Price Volume Oscillator)
    # ========================================
    def calculate_ema(self, term, data):
        """Calculate Exponential Moving Average.

        Args:
            term (int): EMA period
            data (list): Price or volume data

        Returns:
            float: EMA value
        """
        if not data or len(data) == 0:
            return 0.0

        result = []
        for p in data:
            i = len(result)
            if i <= (term - 1):
                chk_1_sum = sum(result)
                chk_1 = (float(chk_1_sum) + float(p)) / (i + 1)
                result.append(chk_1)
            else:
                et_1 = result[-1]
                result.append(float(et_1 + 2 / (term + 1) * (float(p) - et_1)))
        return result[-1]

    def calculate_pvo(self, ohlcv_data, current_volume, short_term=None, long_term=None):
        """Calculate Price Volume Oscillator.

        Args:
            ohlcv_data (list): List of OHLCV dicts with 'Volume'
            current_volume (float): Current bar volume
            short_term (int, optional): Short EMA period. Defaults to config.
            long_term (int, optional): Long EMA period. Defaults to config.

        Returns:
            float: PVO value (percentage)
        """
        if short_term is None:
            short_term = Config.get_pvo_s_term()
        if long_term is None:
            long_term = Config.get_pvo_l_term()

        volume_data = []
        data_len = max(short_term, long_term)
        for i in ohlcv_data[(-1 * data_len):]:
            volume_data.append(i['Volume'])

        volume_data.append(current_volume)
        short_ema = self.calculate_ema(short_term, volume_data)
        long_ema = self.calculate_ema(long_term, volume_data)

        if long_ema == 0:
            return 0.0

        pvo_value = ((short_ema - long_ema) * 100 / long_ema)
        return pvo_value

    def evaluate_pvo(self, pvo_value, threshold=None):
        """Evaluate PVO signal.

        Args:
            pvo_value (float): PVO value
            threshold (float, optional): PVO threshold. Defaults to config.

        Returns:
            bool: True if PVO is above threshold
        """
        if threshold is None:
            threshold = Config.get_pvo_threshold()
        return pvo_value > threshold

    # ========================================
    # Volatility (ATR-based)
    # ========================================
    def calculate_atr(self, ohlcv_data, term=None):
        """Calculate Average True Range (ATR).
        
        True Range is the maximum of:
        - Current High - Current Low
        - abs(Current High - Previous Close)
        - abs(Current Low - Previous Close)
        
        ATR is the moving average of True Range over the specified period.

        Args:
            ohlcv_data (list): List of OHLCV dicts with 'high_price', 'low_price', 'close_price'
            term (int, optional): ATR period. Defaults to config volatility_term.

        Returns:
            float: ATR value
        """
        if term is None:
            term = Config.get_volatility_term()

        if not ohlcv_data or len(ohlcv_data) < 2:
            return 0.0

        # Calculate True Range for each bar
        true_ranges = []
        for i in range(1, len(ohlcv_data)):
            high = ohlcv_data[i]['high_price']
            low = ohlcv_data[i]['low_price']
            prev_close = ohlcv_data[i-1]['close_price']
            
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            true_ranges.append(tr)
        
        if len(true_ranges) < term:
            # Not enough data, return simple average of available TRs
            return sum(true_ranges) / len(true_ranges) if true_ranges else 0.0
        
        # Calculate ATR as average of last 'term' True Ranges
        atr = sum(true_ranges[-term:]) / term
        return atr

    def calculate_volatility(self, ohlcv_data, term=None):
        """Calculate volatility using ATR method.
        
        This method now delegates to calculate_atr for improved accuracy.
        Kept for backward compatibility.

        Args:
            ohlcv_data (list): List of OHLCV dicts
            term (int, optional): Volatility period. Defaults to config.

        Returns:
            float: Volatility value (ATR)
        """
        return self.calculate_atr(ohlcv_data, term)

    # ========================================
    # Parabolic SAR
    # ========================================
    def calculate_parabolic_sar(self, ohlcv_data):
        """Calculate Parabolic SAR indicator.

        Args:
            ohlcv_data (list): List of OHLCV dicts with 'high_price', 'low_price', 'close_price'

        Returns:
            None (updates internal state: self.psar, self.psarbull, self.psarbear)
        """
        iaf = self.stop_AF_add
        maxaf = self.stop_AF_max

        # Extract price arrays
        high = [item['high_price'] for item in ohlcv_data]
        low = [item['low_price'] for item in ohlcv_data]
        close = [item['close_price'] for item in ohlcv_data]

        length = len(close)
        if length < 3:
            return

        psar = [None] * length

        # Initialize PSAR
        if not self.psar:
            psar[0] = close[0]
            psar[1] = close[0]
        else:
            for i in range(min(length, len(self.psar))):
                psar[i] = self.psar[i]

        psarbull = [None] * length
        psarbear = [None] * length
        bull = True
        af = iaf
        ep = low[0]
        hp = high[0]
        lp = low[0]

        # Calculate PSAR from historical data
        for i in range(2, length):
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

        self.psar = psar
        self.psarbull = psarbull
        self.psarbear = psarbear

    def get_psar(self):
        """Get latest PSAR value."""
        if not self.psar or len(self.psar) == 0:
            return None
        return self.psar[-1]

    def get_psarbull(self):
        """Get latest PSAR bull value."""
        if not self.psarbull or len(self.psarbull) == 0:
            return None
        return self.psarbull[-1]

    def get_psarbear(self):
        """Get latest PSAR bear value."""
        if not self.psarbear or len(self.psarbear) == 0:
            return None
        return self.psarbear[-1]

    # ========================================
    # ADX (Average Directional Index)
    # ========================================
    def calculate_adx(self, ohlcv_data, period=None):
        """Calculate ADX indicator.

        Args:
            ohlcv_data (list): List of OHLCV dicts
            period (int, optional): ADX period. Defaults to 14.

        Returns:
            None (updates internal state: self.adx, self.adx_bull, self.adx_bear)
        """
        if period is None:
            period = self.adx_term

        continue_num = self.adx_continue_num
        bull_threshold = self.adx_bull_threshold
        bear_threshold = self.adx_bear_threshold

        high = [item['high_price'] for item in ohlcv_data]
        low = [item['low_price'] for item in ohlcv_data]
        close = [item['close_price'] for item in ohlcv_data]
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

        if length < period * 2:
            # Insufficient data
            self.adx = [0] * length
            self.adx_bull = False
            self.adx_bear = False
            return

        tr_smooth[period - 1] = sum(tr[1:period])
        plus_dm_smooth[period - 1] = sum(plus_dm[1:period])
        minus_dm_smooth[period - 1] = sum(minus_dm[1:period])

        for i in range(period, length):
            tr_smooth[i] = tr_smooth[i - 1] - (tr_smooth[i - 1] / period) + tr[i]
            plus_dm_smooth[i] = plus_dm_smooth[i - 1] - (plus_dm_smooth[i - 1] / period) + plus_dm[i]
            minus_dm_smooth[i] = minus_dm_smooth[i - 1] - (minus_dm_smooth[i - 1] / period) + minus_dm[i]

        # Prevent division by zero
        with np.errstate(divide='ignore', invalid='ignore'):
            plus_di = np.where(tr_smooth != 0, 100 * (plus_dm_smooth / tr_smooth), 0)
            minus_di = np.where(tr_smooth != 0, 100 * (minus_dm_smooth / tr_smooth), 0)
            dx = np.where((plus_di + minus_di) != 0,
                         100 * np.abs((plus_di - minus_di) / (plus_di + minus_di)),
                         0)

        adx = np.zeros(length)
        adx[period - 1] = sum(dx[period - 1:2 * period - 1]) / period

        for i in range(period, length):
            adx[i] = ((adx[i - 1] * (period - 1)) + dx[i]) / period

        self.adx = adx.tolist()

        self.adx_bull = all(adx[i] > bull_threshold for i in range(-continue_num, 0))
        self.adx_bear = all(adx[i] < bear_threshold for i in range(-continue_num, 0))

    def get_adx(self):
        """Get latest ADX value."""
        if not self.adx or len(self.adx) == 0:
            return 0
        return self.adx[-1]

    def get_adx_bull(self):
        """Check if ADX indicates bullish trend."""
        return self.adx_bull

    def get_adx_bear(self):
        """Check if ADX indicates bearish trend."""
        return self.adx_bear


# Singleton instance (optional, for shared state)
_indicator_service_instance = None


def get_indicator_service():
    """Get or create singleton instance of IndicatorService."""
    global _indicator_service_instance
    if _indicator_service_instance is None:
        _indicator_service_instance = IndicatorService()
    return _indicator_service_instance
