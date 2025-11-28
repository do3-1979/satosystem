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
import pandas as pd
from indicator_service import IndicatorService
import numpy as np

class RiskManagement:
    def __init__(self, price_data_management, portfolio, indicator_service=None):
        """
        リスク管理クラスを初期化します。

        Args:
            price_data_management: PriceDataManagement instance
            portfolio: Portfolio instance
            indicator_service: IndicatorService instance (shared with PriceDataManagement)
        """
        self.logger = Logger()
        
        # ADX parameters (initialize before IndicatorService)
        self.adx_term = 14
        self.adx_continue_num = 3
        self.adx_bull_threshold = 25
        self.adx_bear_threshold = 20
        
        # Use shared IndicatorService or create new one with ADX parameters
        if indicator_service is not None:
            self.indicator_service = indicator_service
            # Update ADX parameters in shared instance
            if indicator_service is not None:
                self.indicator_service.adx_term = self.adx_term
                self.indicator_service.adx_continue_num = self.adx_continue_num
                self.indicator_service.adx_bull_threshold = self.adx_bull_threshold
                self.indicator_service.adx_bear_threshold = self.adx_bear_threshold
        else:
            # Initialize IndicatorService with ADX parameters
            self.indicator_service = IndicatorService(
                adx_term=self.adx_term,
                adx_continue_num=self.adx_continue_num,
                adx_bull_threshold=self.adx_bull_threshold,
                adx_bear_threshold=self.adx_bear_threshold
            )
        
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
        self.surge_follow_price_ratio = Config.get_surge_follow_price_ratio()
        self.stop_ATR = 0

        # PSAR (state will be synced from indicator_service)
        self.psar = []
        self.psarbull = []
        self.psarbear = []

        # ADX (state will be synced from indicator_service)
        self.adx = []
        self.adx_bull = False
        self.adx_bear = False

        # ストップ値
        self.stop_offset = 0 # 価格ベース
        self.stop_price = 0 # 価格ベース
        self.last_entry_price = 0 # 価格ベース
        self.psar_stop_offset = 0 # PSAR ストップオフセット
        self.price_surge_stop_offset = 0 # サージフォロー用ストップオフセット
        
        # Phase 2: 段階的ポジションサイジング用のレジーム情報
        self.current_regime = "NEUTRAL"
        self.graduated_sizing_enabled = Config.get_graduated_sizing_enabled()
        self.sideways_multiplier = Config.get_sideways_position_multiplier()
        self.weak_trend_multiplier = Config.get_weak_trend_position_multiplier()
        self.strong_trend_multiplier = Config.get_strong_trend_position_multiplier()
    
    def get_entry_range(self):
        return self.entry_range

    def get_add_range(self):
        return self.add_range

    def get_last_entry_price(self):
        return self.last_entry_price

    def update_last_entry_price(self, price):
        self.last_entry_price = price
        return
    
    def reset_position_tracking(self):
        """
        ポジション決済後の状態リセット
        次のエントリーに備えて内部状態をクリアする
        """
        self.last_entry_price = 0
        self.stop_price = 0
        self.stop_offset = 0
        self.psar_stop_offset = 0
        self.price_surge_stop_offset = 0
        self.add_range = 0
        self.logger.log(f"[リセット] ポジション追跡状態を初期化 (last_entry_price=0, stop_price=0)")
        return

    def update_risk_status(self):
        self.__update_stop_price()
        return

    def get_stop_price(self):
        return self.stop_price
    
    def get_position_size(self):
        # Phase 2: 段階的ポジションサイジング
        position_size = self.position_size
        if self.graduated_sizing_enabled and self.current_regime != "NEUTRAL":
            multiplier = self._get_regime_multiplier()
            position_size = position_size * multiplier
        return position_size
    
    def _get_regime_multiplier(self):
        """レジーム別のポジションサイズ乗数を返す"""
        if self.current_regime == "SIDEWAYS":
            return self.sideways_multiplier
        elif self.current_regime == "WEAK_TREND":
            return self.weak_trend_multiplier
        elif self.current_regime == "STRONG_TREND":
            return self.strong_trend_multiplier
        return 1.0  # デフォルト
    
    def set_regime_info(self, regime_stats):
        """取引戦略からレジーム情報を受け取る"""
        if regime_stats:
            self.current_regime = regime_stats.get("current_regime", "NEUTRAL")
        return
        
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

    def get_psar_stop_offset(self):
        return self.psar_stop_offset
    
    def get_price_surge_stop_offset(self):
        return self.price_surge_stop_offset

    # パラボリックSARを計算する関数
    def __calc_parabolic_sar(self, data):
        """IndicatorServiceに委譲してPSAR計算を実行"""
        self.indicator_service.calculate_parabolic_sar(data)
        
        # indicator_serviceから計算結果を取得
        self.psar = self.indicator_service.psar
        self.psarbull = self.indicator_service.psarbull
        self.psarbear = self.indicator_service.psarbear
        
        return

    def __calc_adx(self, data):
        """IndicatorServiceに委譲してADX計算を実行"""
        adx_period = self.adx_term
        self.indicator_service.calculate_adx(data, adx_period)
        
        # indicator_serviceから計算結果を取得
        self.adx = self.indicator_service.adx
        self.adx_bull = self.indicator_service.adx_bull
        self.adx_bear = self.indicator_service.adx_bear
        
        return

    def __calc_stop_psar(self):
        """
        ストップ値をパラボリックSARにする関数
        
        ポジションのBUY/SELLに応じてパラボリックSARの値をストップポジションとする
        ストップオフセットは常に正の値（絶対値）
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

        # BUYの時は現在値からpsarbullの差をstopとする。SELLはpsarbear
        # ストップオフセットは常に正の値（絶対値）
        if self.portfolio.get_position_side() == "BUY" and psarbull is not None:
            tmp_stop_offset = abs(round(position_price - psarbull))

        if self.portfolio.get_position_side() == "SELL" and psarbear is not None:
            tmp_stop_offset = abs(round(psarbear - position_price))

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

        # パラボリックSAR計算（高速モード時はスキップ）
        fast_summary_mode = Config.get_fast_summary_mode()
        if fast_summary_mode == 0:
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

            # PSAR値をそのままストップとして記録（ログ出力用）
            # psarbull: BUY時のストップ（SAR値）/ psarbear: SELL時のストップ（SAR値）
            if side == "BUY":
                # ストップ値再計算
                tmp_stop_price = position_price - self.stop_offset
                self.stop_price = max(tmp_stop_price, prev_stop_price)
                # PSAR が有効なら使用
                psar_applied = False
                try:
                    psar_val = self.psarbear
                    if isinstance(psar_val, (list, pd.Series)):
                        psar_val = psar_val.iloc[0] if isinstance(psar_val, pd.Series) else psar_val[0]
                    if psar_val is not None and psar_val != 0 and psar_val == psar_val:  # NaN check
                        self.stop_price = float(psar_val)
                        psar_applied = True
                except:
                    pass
                # PSAR計算がスキップされた場合は stop_offset ベースの値を使用
                if not psar_applied and (self.stop_price == 0 or self.stop_price != self.stop_price):  # NaN check
                    self.stop_price = tmp_stop_price
            elif side == "SELL":
                # ストップ値再計算
                tmp_stop_price = position_price + self.stop_offset
                self.stop_price = min(tmp_stop_price, prev_stop_price)
                # PSAR が有効なら使用
                psar_applied = False
                try:
                    psar_val = self.psarbull
                    if isinstance(psar_val, (list, pd.Series)):
                        psar_val = psar_val.iloc[0] if isinstance(psar_val, pd.Series) else psar_val[0]
                    if psar_val is not None and psar_val != 0 and psar_val == psar_val:  # NaN check
                        self.stop_price = float(psar_val)
                        psar_applied = True
                except:
                    pass
                # PSAR計算がスキップされた場合は stop_offset ベースの値を使用
                if not psar_applied and (self.stop_price == 0 or self.stop_price != self.stop_price):  # NaN check
                    self.stop_price = tmp_stop_price
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
            
            # =====================================================================
            # 【修正】ボラティリティがゼロまたは無効な場合の対応
            # =====================================================================
            # ボラティリティがゼロまたは計算不可の場合はデフォルト値を使用
            if volatility == 0 or volatility is None or (isinstance(volatility, float) and (np.isnan(volatility) or np.isinf(volatility))):
                # デフォルトボラティリティ: 0.5%（低ボラティリティ環境での安全マージン）
                # ただし、最初のENTRY実行時はボラティリティ計算失敗が多いため
                # より保守的に 1.0% を使用
                volatility = 1.0
                self.logger.log(f"[警告] ボラティリティ計算不可: デフォルト値 {volatility}% を使用")
            
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
            
            # =====================================================================
            # 【追加ログ】計算の透明化
            # =====================================================================
            self.logger.log(f"[ポジションサイズ計算] volatility={volatility:.2f}%, stop_range={stop_range:.2f}, "
                           f"balance={balance_tether:.2f}, position_size={position_size:.7f} ({position_size*price:.2f}USD)")

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
