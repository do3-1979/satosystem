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
from logger import Logger
from config import Config
from price_data_management import PriceDataManagement
from risk_management import RiskManagement
from portfolio import Portfolio
from exit_strategy_v2 import ExitStrategyV2
from market_regime_detector import MarketRegimeDetector
from vcp_strategy import VCPStrategy
from mean_reversion_strategy import MeanReversionStrategy
from new_indicators import NewIndicators
from datetime import datetime

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

    def __init__(self, price_data_management, risk_manager, portfolio):
        self.logger = Logger()
        self.trade_decision = ()
        self.price_data_management = price_data_management
        self.risk_manager = risk_manager
        self.portfolio = portfolio
        self.exit_strategy_v2 = ExitStrategyV2()  # ExitStrategyV2を初期化
        self.exit_strategy_v2.load_config(Config)  # Config設定をロード（Task 39d）
        self.entry_record = {}  # エントリー時の指標情報を記録
        
        # 市場体制判定の初期化
        self.market_regime_detector = MarketRegimeDetector(
            atr_period=Config.get_atr_period(),
            atr_ma_period=Config.get_atr_ma_period(),
            lookback_period=Config.get_swing_lookback_period()
        )
        self.current_market_regime = 'TRANSITION'  # 現在の市場体制
        self.market_regime_confidence = 0.0
        self.current_market_regime_reason = ''  # 判定理由
        
        # VCP戦略の初期化
        self.vcp_strategy = VCPStrategy()
        self.vcp_signal_latest = 0
        self.vcp_confidence_latest = 0.0
        self.vcp_reason_latest = ''
        
        # Mean Reversion戦略の初期化
        self.mean_reversion_strategy = MeanReversionStrategy()
        self.mr_signal_latest = False
        self.mr_bb_position_latest = 0.0
        self.mr_rsi_latest = None
        self.mr_reason_latest = ''
        
        # Strategy Signal の状態保持（トレードログ記録用）
        self.current_strategy_signal = 'NONE'  # 現在の Strategy Signal (BUY/SELL/NONE)
        self.current_strategy_name = 'NONE'     # 現在の Strategy 名 (A/B/C/NONE)
        self.current_strategy_confidence = 0.0  # 現在の Strategy の信頼度
        
        # 新指標の状態変化を追跡（ログ重複排除用）
        self.last_strategy_signal = None  # 前回のstrategy signal
        
        self.initialize_trade_decision()
 
    def initialize_trade_decision(self):
        """
        trade_decision 辞書を初期化します。
        """
        self.trade_decision = {
            "side": "NONE",
            "decision": "NONE",
            "position_size_ratio": 1.0,
            "order_type": "market"
        }

    def evaluate_entry(self):
        """
        エントリー条件を評価し、エントリーするかどうかを決定します。

        条件:
        1. ポジションを保有していない
        2. ドンチャンチャネルブレイクが発生
        3. PVOが閾値範囲内
        
        Phase 22a-22c: 複数のStrategyから最適なものを選択
        
        フィルター機能:
        - enable_pvo_filter: PVO > 0 を必須条件として追加
        - enable_adx_filter: ADX > threshold を必須条件として追加
        """
        side = 'NONE'
        decision = 'NONE'
        position_size_ratio = 1.0  # Phase 0: 常に100%

        # シグナルをチェック
        signals = self.price_data_management.get_signals()

        # =========== 週末エントリー回避フィルター ===========
        if Config.get_weekend_filter_enabled():
            try:
                epoch = self.price_data_management.get_latest_close_time()
                weekday = datetime.utcfromtimestamp(epoch).weekday()  # 0=Mon, 5=Sat, 6=Sun
                if weekday >= 5:
                    day_name = 'Saturday' if weekday == 5 else 'Sunday'
                    self.logger.log(f"[週末フィルター] {day_name} のエントリーをスキップ")
                    return
            except Exception as e:
                self.logger.log(f"[週末フィルターエラー] {str(e)}")

        # 新指標ベースのStrategyを評価
        strategy_result = self._evaluate_new_indicator_strategy()
        use_new_strategy = any([
            getattr(self.risk_manager, 'enable_strategy_a_adx', False),
            getattr(self.risk_manager, 'enable_strategy_b_bb_rsi_sma', False),
            getattr(self.risk_manager, 'enable_strategy_c_combined', False),
        ])
        strategy_side = None
        if strategy_result:
            # Strategy Signal の状態を保持（トレードログ記録用）
            self.current_strategy_signal = strategy_result.get('signal', 'NONE')
            self.current_strategy_name = strategy_result.get('strategy', 'NONE')
            self.current_strategy_confidence = strategy_result.get('confidence', 0.0)
            
            raw_signal = strategy_result.get('signal', 'NONE')
            if raw_signal in ['BUY', 'SELL']:
                strategy_side = raw_signal
            elif raw_signal == 'BULL':
                strategy_side = 'BUY'
            elif raw_signal == 'BEAR':
                strategy_side = 'SELL'
        else:
            # Strategy Signal が NONE の場合
            self.current_strategy_signal = 'NONE'
            self.current_strategy_name = 'NONE'
            self.current_strategy_confidence = 0.0
        
        # PVO有効範囲チェック
        if signals["pvo"]["signal"] == True:
            
            # =========== VCP戦略シグナル評価（Donchian判定前に実行） ===========
            # OHLCV データを取得
            try:
                ohlcv_data = self.price_data_management.get_ohlcv_data_by_time_frame(
                    Config.get_time_frame()
                )
                
                donchian_high = self.risk_manager.get_donchian_high()
                donchian_low = self.risk_manager.get_donchian_low()
                current_price = self.price_data_management.get_ticker()
                
                vcp_result = self.vcp_strategy.evaluate_entry(
                    candles=ohlcv_data if ohlcv_data else [],
                    donchian_high=donchian_high,
                    donchian_low=donchian_low,
                    current_price=current_price
                )
                
                # VCP結果をstrategyに保存（bot.pyからアクセスするため）
                self.vcp_signal_latest = vcp_result['signal']
                self.vcp_confidence_latest = vcp_result['confidence']
                self.vcp_reason_latest = vcp_result['reason']
                
                if vcp_result['signal'] != 0:
                    self.logger.log(f"[VCP戦略] シグナル={vcp_result['signal']}, 信頼度={vcp_result['confidence']:.2f}, 理由={vcp_result['reason']}")
            except Exception as e:
                self.logger.log(f"[VCP戦略エラー] {str(e)}")
                self.vcp_signal_latest = 0
                self.vcp_confidence_latest = 0.0
                self.vcp_reason_latest = ''
            
            # ========================================
            # 共通初期化
            # ========================================
            allow_entry = False
            desired_side = None
            conditions_list = []
            
            # ========================================
            # Mean Reversion 戦略評価 (Phase 1評価中)
            # ========================================
            enable_mr = Config.get_enable_mean_reversion_strategy()
            if enable_mr:
                try:
                    ohlcv_data = self.price_data_management.get_ohlcv_data_by_time_frame(
                        Config.get_time_frame()
                    )
                    current_price = self.price_data_management.get_ticker()
                    
                    mr_result = self.mean_reversion_strategy.evaluate_entry(
                        candles=ohlcv_data if ohlcv_data else [],
                        current_price=current_price
                    )
                    
                    # Mean Reversion結果をstrategyに保存（bot.pyからアクセスするため）
                    self.mr_signal_latest = mr_result['signal']
                    self.mr_bb_position_latest = mr_result['bb_position']
                    self.mr_rsi_latest = mr_result['rsi']
                    self.mr_reason_latest = mr_result['reason']
                    
                    # ⚠️ Phase 1評価中: Mean ReversionシグナルがTrueの場合はエントリー
                    if mr_result['signal']:
                        self.logger.log(
                            f"[Mean Reversion戦略] ✅ エントリーシグナル: {mr_result['reason']}"
                        )
                        # DonchianではなくMean Reversionをメインシグナルとして使用
                        # 逆張りエントリー = BUYのみ (BB下限到達時)
                        desired_side = "BUY"
                        allow_entry = True
                        
                        # Mean Reversion専用条件チェック
                        conditions_list = [
                            f"PVO信号: ✓",
                            f"Mean Reversion: ✓ (BB={mr_result['bb_position']:.2f}, RSI={mr_result['rsi']:.1f})"
                        ]
                except Exception as e:
                    self.logger.log(f"[Mean Reversion戦略エラー] {str(e)}")
                    self.mr_signal_latest = False
                    self.mr_bb_position_latest = 0.0
                    self.mr_rsi_latest = None
                    self.mr_reason_latest = ''
            
            # ========================================
            # Donchian ブレイクアウト戦略
            # ========================================
            # ⚠️ Phase 1評価中: Mean Reversionが有効な場合はDonchianを無効化
            else:
                # ドンチャンチャネルブレイク発生
                if signals["donchian"]["signal"] == True:
                    desired_side = signals["donchian"]["side"]
                    allow_entry = True
                    
                    # === Range Breakout Enhanced (Task 38c) ===
                    enable_rbe = Config.get_enable_range_breakout_enhanced()
                    if enable_rbe:
                        # ブレイク強度確認
                        current_price = self.price_data_management.get_ticker()
                        donchian_high = self.risk_manager.get_donchian_high()
                        donchian_low = self.risk_manager.get_donchian_low()
                        
                        breakout_valid = self._validate_breakout_strength(
                            current_price, donchian_high, donchian_low, desired_side
                        )
                        
                        if not breakout_valid:
                            allow_entry = False
                            self.logger.log(f"[Range Breakout Enhanced] ✗ ブレイク強度不足")
                        
                        # 相対出来高確認
                        if allow_entry:
                            volume_valid = self._validate_relative_volume()
                            if not volume_valid:
                                allow_entry = False
                                self.logger.log(f"[Range Breakout Enhanced] ✗ 出来高不足")
                    
                    # === 【条件一覧】===
                    conditions_list = []
                    conditions_list.append(f"PVO信号: ✓")
                    if enable_rbe and allow_entry:
                        conditions_list.append(f"Donchian: {desired_side} (Enhanced ✓)")
                    else:
                        conditions_list.append(f"Donchian: {desired_side}")
            
            # ========================================
            # 新指標チェック（Donchian使用時のみ）
            # ========================================
            if not enable_mr and allow_entry:
                if use_new_strategy:
                    if strategy_side is None:
                        conditions_list.append(f"新指標: なし（ベースライン許可）")
                    elif strategy_side == desired_side:
                        conditions_list.append(f"新指標: {strategy_side} （✓一致）")
                    else:
                        conditions_list.append(f"新指標: {strategy_side} （✗矛盾）")
                        allow_entry = False
            
            # ========================================
            # 市場体制判定とフィルター（Mean Reversion/Donchian共通）
            # ========================================
            if allow_entry:
                # =========== 市場体制判定（常に実行してログ記録、フィルタは別制御） ===========
                # OHLCV データを取得
                try:
                    ohlcv_data = self.price_data_management.get_ohlcv_data_by_time_frame(
                        Config.get_time_frame()
                    )
                    
                    if ohlcv_data and len(ohlcv_data) >= 40:  # 最小40本必要
                        # シンプルなボックス相場判定（レンジ幅で判定）
                        regime_result = self.market_regime_detector.detect_regime_simple(
                            ohlcv_data, 
                            lookback_period=Config.get_swing_lookback_period()
                        )
                        
                        self.current_market_regime = regime_result['regime']
                        self.market_regime_confidence = regime_result['confidence']
                        self.current_market_regime_reason = regime_result['reason']  # reason も保存
                        
                        self.logger.log(f"[市場体制判定] {self.current_market_regime} (信頼度={self.market_regime_confidence:.2f}, {regime_result['reason']})")
                    else:
                        # データ不足時はデフォルト値
                        self.current_market_regime = 'UNKNOWN'
                        self.market_regime_confidence = 0.0
                        self.current_market_regime_reason = 'データ不足'
                # =========== 市場体制判定エラーはログするが、エントリー判定は続行 ===========
                except Exception as e:
                    # 市場体制判定エラーはログするが、エントリー判定は続行
                    self.logger.log(f"[市場体制判定エラー] {str(e)}")
                    self.current_market_regime = 'ERROR'
                    self.market_regime_confidence = 0.0
                    self.current_market_regime_reason = str(e)
                
                # =========== 市場体制判定に基づくフィルタリング（有効時のみ） ===========
                enable_market_regime_detection = Config.get_enable_market_regime_detection()
                if allow_entry and enable_market_regime_detection:
                    # ボックス相場判定時の条件強化
                    enable_strictness = Config.get_enable_entry_condition_strictness_on_range()
                    if self.current_market_regime == 'RANGING' and enable_strictness:
                        # ボックス相場時：Volume + ADXフィルタを必須化
                        self.logger.log(f"[市場体制フィルタ] ボックス相場検出 → エントリー条件を強化します")
                        
                        # Volume フィルター強制有効化
                        volume_value = self.price_data_management.get_latest_volume()
                        volume_threshold = Config.get_volume_filter_threshold()
                        if volume_value < volume_threshold:
                            self.logger.log(f"[市場体制フィルタ:ボックス] Volume不足で除外 (Volume={volume_value:.0f} < {volume_threshold:.0f})")
                            allow_entry = False
                        else:
                            self.logger.log(f"[市場体制フィルタ:ボックス] Volume OK (Volume={volume_value:.0f} >= {volume_threshold:.0f})")
                        
                        # ADX フィルター強制有効化
                        if allow_entry:
                            adx_value = self.risk_manager.get_adx() if hasattr(self.risk_manager, 'get_adx') else 0
                            adx_threshold = Config.get_adx_filter_threshold()
                            if adx_value < adx_threshold:
                                self.logger.log(f"[市場体制フィルタ:ボックス] ADX不足で除外 (ADX={adx_value:.2f} < {adx_threshold})")
                                allow_entry = False
                            else:
                                self.logger.log(f"[市場体制フィルタ:ボックス] ADX OK (ADX={adx_value:.2f} >= {adx_threshold})")
                        
                        # ポジションサイズ削減
                        if allow_entry:
                            ranging_multiplier = Config.get_ranging_position_size_multiplier()
                            position_size_ratio *= ranging_multiplier
                            self.logger.log(f"[市場体制フィルタ:ボックス] ポジションサイズを {ranging_multiplier:.1%} に削減")
                    
                    elif self.current_market_regime in ['TRENDING_UP', 'TRENDING_DOWN']:
                        self.logger.log(f"[市場体制フィルタ] トレンド相場 → 通常エントリー条件で進行")

                # =========== フィルター機能 ===========
                filter_results = []
                
                # PVO フィルター
                enable_pvo_filter = Config.get_enable_pvo_filter()
                if enable_pvo_filter:
                    pvo_value = signals["pvo"]["info"].get("value", 0)
                    pvo_threshold = Config.get_pvo_threshold()
                    if pvo_value <= pvo_threshold:
                        filter_results.append(f"PVO: ✗ ({pvo_value:.4f} <= {pvo_threshold})")
                        if allow_entry:
                            allow_entry = False
                    else:
                        filter_results.append(f"PVO: ✓ ({pvo_value:.4f} > {pvo_threshold})")
                
                # ADX フィルター
                enable_adx_filter = Config.get_enable_adx_filter()
                adx_threshold = Config.get_adx_filter_threshold()
                if enable_adx_filter:
                    adx_value = self.risk_manager.get_adx() if hasattr(self.risk_manager, 'get_adx') else 0
                    if adx_value < adx_threshold:
                        filter_results.append(f"ADX: ✗ ({adx_value:.2f} < {adx_threshold})")
                        if allow_entry:
                            allow_entry = False
                    else:
                        filter_results.append(f"ADX: ✓ ({adx_value:.2f} >= {adx_threshold})")
                
                # Volume フィルター
                enable_volume_filter = Config.get_enable_volume_filter()
                volume_threshold = Config.get_volume_filter_threshold()
                if enable_volume_filter:
                    volume_value = self.price_data_management.get_latest_volume()
                    if volume_value < volume_threshold:
                        filter_results.append(f"Volume: ✗ ({volume_value:.0f} < {volume_threshold:.0f})")
                        if allow_entry:
                            allow_entry = False
                    else:
                        filter_results.append(f"Volume: ✓ ({volume_value:.0f} >= {volume_threshold:.0f})")
                
                # Volatility フィルター
                enable_volatility_filter = Config.get_enable_volatility_filter()
                volatility_threshold = Config.get_volatility_filter_threshold()
                if enable_volatility_filter:
                    volatility_value = self.price_data_management.get_volatility()
                    if volatility_value > volatility_threshold:
                        filter_results.append(f"Volatility: ✗ ({volatility_value:.2f} > {volatility_threshold:.2f})")
                        if allow_entry:
                            allow_entry = False
                    else:
                        filter_results.append(f"Volatility: ✓ ({volatility_value:.2f} <= {volatility_threshold:.2f})")

                # =========== 方向性フィルター群（論文ベース） ===========
                # desired_side が確定している場合のみ評価
                if desired_side and (Config.get_sma_direction_filter_enabled() or
                                     Config.get_rsi_direction_filter_enabled() or
                                     Config.get_macd_direction_filter_enabled() or
                                     Config.get_tsmom_filter_enabled()):
                    try:
                        dir_ohlcv = ohlcv_data if ohlcv_data else []
                        dir_closes = [c['close_price'] for c in dir_ohlcv]
                        dir_ind = NewIndicators()

                        # SMA方向性フィルター (Brock, Lakonishok, LeBaron 1992 JF; Faber 2007 JOIM)
                        # 原理: 価格>SMA(N)=上昇トレンド → BUYエントリーを許可
                        if Config.get_sma_direction_filter_enabled() and dir_closes:
                            sma_period = Config.get_sma_direction_filter_period()
                            if len(dir_closes) >= sma_period:
                                sma_val = sum(dir_closes[-sma_period:]) / sma_period
                                cur_px = self.price_data_management.get_ticker()
                                above = cur_px > sma_val
                                if desired_side == "BUY" and not above:
                                    filter_results.append(f"SMA方向: ✗ BUY却下(現値<SMA{sma_period}={sma_val:.0f})")
                                    allow_entry = False
                                elif desired_side == "SELL" and above:
                                    filter_results.append(f"SMA方向: ✗ SELL却下(現値>SMA{sma_period}={sma_val:.0f})")
                                    allow_entry = False
                                else:
                                    filter_results.append(f"SMA方向: ✓ ({desired_side}, SMA{sma_period}={sma_val:.0f})")
                            else:
                                filter_results.append(f"SMA方向: ⚠ データ不足({len(dir_closes)}<{sma_period})")

                        # RSI方向性フィルター (Wilder 1978; Liu & Tsyvinski 2021 RFS)
                        # 原理: RSI>50=上昇モメンタム → BUYのみ / RSI<50=下降 → SELLのみ
                        if Config.get_rsi_direction_filter_enabled() and dir_closes:
                            rsi_period = Config.get_rsi_direction_filter_period()
                            rsi_val = dir_ind.calc_rsi(dir_closes, rsi_period)
                            if rsi_val is not None:
                                if desired_side == "BUY" and rsi_val < 50:
                                    filter_results.append(f"RSI方向: ✗ BUY却下(RSI={rsi_val:.1f}<50)")
                                    allow_entry = False
                                elif desired_side == "SELL" and rsi_val > 50:
                                    filter_results.append(f"RSI方向: ✗ SELL却下(RSI={rsi_val:.1f}>50)")
                                    allow_entry = False
                                else:
                                    filter_results.append(f"RSI方向: ✓ ({desired_side}, RSI={rsi_val:.1f})")
                            else:
                                filter_results.append(f"RSI方向: ⚠ 計算失敗")

                        # MACD方向性フィルター (Appel 1985; Murphy 1999)
                        # 原理: MACD>Signal=上昇局面 → BUYのみ / MACD<Signal=下降 → SELLのみ
                        if Config.get_macd_direction_filter_enabled() and dir_closes:
                            macd_val, macd_sig, _ = dir_ind.calc_macd(dir_closes, 12, 26, 9)
                            if macd_val is not None and macd_sig is not None:
                                macd_bull = macd_val > macd_sig
                                if desired_side == "BUY" and not macd_bull:
                                    filter_results.append(f"MACD方向: ✗ BUY却下(MACD={macd_val:.0f}≤Sig={macd_sig:.0f})")
                                    allow_entry = False
                                elif desired_side == "SELL" and macd_bull:
                                    filter_results.append(f"MACD方向: ✗ SELL却下(MACD={macd_val:.0f}>Sig={macd_sig:.0f})")
                                    allow_entry = False
                                else:
                                    filter_results.append(f"MACD方向: ✓ ({desired_side}, MACD={macd_val:.0f})")
                            else:
                                filter_results.append(f"MACD方向: ⚠ データ不足")

                        # 時系列モメンタムフィルター TSMOM (Moskowitz, Ooi, Pedersen 2012 JFE)
                        # 原理: N期間前比リターン>0=上昇モメンタム → BUYのみ
                        if Config.get_tsmom_filter_enabled() and dir_closes:
                            lb = Config.get_tsmom_filter_lookback()
                            if len(dir_closes) > lb:
                                past_px = dir_closes[-(lb + 1)]
                                now_px = dir_closes[-1]
                                tsmom_ret = (now_px / past_px - 1) * 100 if past_px > 0 else 0
                                positive = tsmom_ret > 0
                                if desired_side == "BUY" and not positive:
                                    filter_results.append(f"TSMOM: ✗ BUY却下({lb}期前比{tsmom_ret:.1f}%)")
                                    allow_entry = False
                                elif desired_side == "SELL" and positive:
                                    filter_results.append(f"TSMOM: ✗ SELL却下({lb}期前比{tsmom_ret:.1f}%)")
                                    allow_entry = False
                                else:
                                    filter_results.append(f"TSMOM: ✓ ({desired_side}, {lb}期前比{tsmom_ret:.1f}%)")
                            else:
                                filter_results.append(f"TSMOM: ⚠ データ不足({len(dir_closes)}<={lb})")

                        # ADXスロープフィルター (Elder 1993 "Trading for a Living")
                        # 原理: ADX上昇中 = トレンド強化 = エントリー良好
                        #       ADX下落中 = トレンド弱体化 = エントリー不良
                        if Config.get_adx_slope_filter_enabled():
                            adx_list = getattr(self.risk_manager, 'adx', [])
                            lb = Config.get_adx_slope_filter_lookback()
                            if len(adx_list) > lb:
                                current_adx = adx_list[-1]
                                past_adx = adx_list[-(lb + 1)]
                                adx_rising = current_adx > past_adx
                                if not adx_rising:
                                    filter_results.append(f"ADXスロープ: ✗ 下落中({current_adx:.1f}<{past_adx:.1f})")
                                    allow_entry = False
                                else:
                                    filter_results.append(f"ADXスロープ: ✓ 上昇中({current_adx:.1f}>{past_adx:.1f})")
                            else:
                                filter_results.append(f"ADXスロープ: ⚠ データ不足({len(adx_list)}<={lb})")

                    except Exception as e:
                        self.logger.log(f"[方向性フィルターエラー] {str(e)}")

                # Funding Rate フィルター (Funding Rate過熱によるエントリー抑制)
                if Config.get_funding_rate_filter_enabled() and desired_side and allow_entry:
                    try:
                        current_epoch = self.price_data_management.get_latest_close_time()
                        fr_value = self.price_data_management.get_funding_rate(current_epoch)
                        buy_threshold = Config.get_funding_rate_buy_threshold()
                        sell_threshold = Config.get_funding_rate_sell_threshold()
                        if desired_side == "BUY" and fr_value >= buy_threshold:
                            filter_results.append(f"FundingRate: ✗ BUY却下(FR={fr_value*100:.4f}%>={buy_threshold*100:.4f}%)")
                            allow_entry = False
                        elif desired_side == "SELL" and fr_value <= sell_threshold:
                            filter_results.append(f"FundingRate: ✗ SELL却下(FR={fr_value*100:.4f}%<={sell_threshold*100:.4f}%)")
                            allow_entry = False
                        else:
                            filter_results.append(f"FundingRate: ✓ ({desired_side}, FR={fr_value*100:.4f}%)")
                    except Exception as e:
                        self.logger.log(f"[Funding Rateフィルターエラー] {str(e)}")

                # フィルター結果を出力
                if filter_results:
                    self.logger.log(f"[フィルタ一覧] " + " | ".join(filter_results))
                
                # 最終判定を出力（条件一覧 + フィルタ一覧 の総合判定）
                self.logger.log(f"[条件一覧] " + " | ".join(conditions_list))
                if allow_entry:
                    self.logger.log(f"[最終判定] ✅ エントリー許可 ({desired_side})")
                    side = desired_side
                    decision = "ENTRY"
                else:
                    # 見送り理由を判定
                    if not strategy_result or (use_new_strategy and strategy_side and strategy_side != desired_side):
                        reason = "新指標が逆方向"
                    elif filter_results and any("✗" in f for f in filter_results):
                        reason = "フィルター不合格"
                    else:
                        reason = "その他"
                    self.logger.log(f"[最終判定] ✗ エントリー見送り（{reason}）")

        # エントリ条件がない場合はNONEで初期化する
        self.trade_decision["side"] = side
        self.trade_decision["decision"] = decision
        self.trade_decision["position_size_ratio"] = position_size_ratio
        
        # エントリー時の指標を記録（ExitStrategyV2用）
        if decision == "ENTRY":
            current_price = self.price_data_management.get_latest_ohlcv()
            self.entry_record = {
                'entry_price': current_price.get('close_price', 0),
                'entry_adx': self.risk_manager.get_adx(),
                'entry_pvo': current_price.get('pvo_val', 0) or current_price.get('pvo', 0),
                'entry_time': current_price.get('timestamp', 0),  # タイムスタンプ（数値）を記録
                'strategy_result': strategy_result,  # Strategy結果も記録
            }
            # self.logger.log(f"[DEBUG ENTRY RECORD] entry_record保存: entry_time={self.entry_record['entry_time']}, entry_price={self.entry_record['entry_price']}")
            
        return
    
    def _evaluate_new_indicator_strategy(self):
        """
        新指標ベースのStrategy（A/B/C）を評価
        
        戻り値:
            dict: {'signal': 'BUY'/'SELL'/'NONE', 'strategy': 'A'/'B'/'C', 'confidence': 0-1}
        """
        try:
            # すべてのStrategyを評価
            all_strategies = self.risk_manager.evaluate_all_strategies()
            
            if not all_strategies:
                return None
            
            # どのStrategyが最初に有効なシグナルを出しているか確認
            for strategy_name in ['strategy_c', 'strategy_b', 'strategy_a']:
                if strategy_name in all_strategies:
                    result = all_strategies[strategy_name]
                    signal = result.get('signal', 'NONE')
                    normalized = None
                    if signal in ['BUY', 'SELL']:
                        normalized = signal
                    elif signal == 'BULL':
                        normalized = 'BUY'
                    elif signal == 'BEAR':
                        normalized = 'SELL'
                    
                    if normalized:
                        # 状態が変化した場合のみログ出力（重複排除）
                        signal_key = f"{strategy_name}:{normalized}"
                        if signal_key != self.last_strategy_signal:
                            strategy_name_display = strategy_name.split('_')[1].upper()
                            # 条件の詳細を抽出して表示
                            conditions = result.get('conditions', {})
                            condition_str = ", ".join([f"{k}={v}" for k, v in conditions.items()]) if conditions else ""
                            if condition_str:
                                self.logger.log(f"[新指標] strategy_{strategy_name_display}: {signal} ({condition_str})")
                            else:
                                self.logger.log(f"[新指標] strategy_{strategy_name_display}: {signal}")
                            self.last_strategy_signal = signal_key
                        
                        return {
                            'signal': normalized,
                            'raw_signal': signal,
                            'strategy': strategy_name.split('_')[1].upper(),
                            'confidence': 0.7 if normalized != 'NONE' else 0.0,
                            'details': result
                        }
            
            # すべてのStrategyがNONEの場合、状態を記録
            if self.last_strategy_signal is not None:
                self.logger.log(f"[新指標] 全Strategy: NONE（シグナル消滅）")
                self.last_strategy_signal = None
            
            return None
            
        except Exception as e:
            self.logger.log(f"[新指標評価エラー] {str(e)}")
            return None
    
    def evaluate_add(self, price):
        """
        ピラミッド条件を評価し、買い増しするかどうかを決定します。

        条件:
        1. ポジションを保有している
        2. 追加レンジ幅が前回取得値を超過
        """
        side = 'NONE'
        decision = 'NONE'
  
        # 保有状態を確認 
        position_side = self.portfolio.get_position_side()
        
        if position_side != 'NONE':
            
            # 追加レンジ幅を取得
            range = self.risk_manager.get_add_range()
            # 前回取得値を取得
            last_entry_price = self.risk_manager.get_last_entry_price()
            
            # 価格がエントリー方向に基準レンジ分だけ進んだか判定する
            # TODO rangeはprice x ボラ x 2の値。妥当？
            if position_side == "BUY" and (price - last_entry_price) > range:
                self.logger.log(f"[条件判定:ADD] 価格変動 {(price - last_entry_price):.2f} が変動幅 {range:.2f} を超過しました")
                side = "BUY"
                decision = "ADD"
                self.trade_decision["side"] = side
                self.trade_decision["decision"] = decision

            elif position_side == "SELL" and (last_entry_price - price) > range:
                self.logger.log(f"[条件判定:ADD] 価格変動 {(last_entry_price - price):.2f} が変動幅 {range:.2f} を超過しました")
                side = "SELL"
                decision = "ADD"
                self.trade_decision["side"] = side
                self.trade_decision["decision"] = decision

        return

    def evaluate_exit(self):
        """
        エグジット条件を評価し、ポジションをクローズするかどうかを決定します。
        ハイブリッド方式：
        1. 従来のストップロス判定（優先度最高）
        2. ExitStrategyV2（複合シグナル）で補助的に判定
        """
        side = 'NONE'
        decision = 'NONE'
        exit_reason = 'NONE'
        
        position_side = self.portfolio.get_position_side()
        
        # ポジションがない場合はスキップ
        if position_side == 'NONE':
            self.trade_decision["side"] = side
            self.trade_decision["decision"] = decision
            return
        
        # 現在のOHLCVと指標を取得
        current_ohlcv = self.price_data_management.get_latest_ohlcv()
        
        # timestampがない場合はclose_timeをtimestampとして設定（Time-Based Exit用）
        if 'timestamp' not in current_ohlcv and 'close_time' in current_ohlcv:
            current_ohlcv['timestamp'] = current_ohlcv['close_time']
        
        #-------------------------------------------------------
        # 優先度0：Time-Based Exit（長期ポジションの強制決済）
        #-------------------------------------------------------
        # ストップロスより優先して、保有時間制限をチェック
        try:
            position_info = {
                # NOTE: entry_price=0 はベースライン互換のため意図的（0の場合TBEは P&L判定をスキップしてshould_exit=False）
                # Chandelier/PSL用の entry_price は各ブロック内で get_position_price() を使用
                'entry_price': 0,
                'quantity': self.portfolio.get_position_quantity(),
                'side': position_side,
            }
            
            # Time-Based Exitのみをチェック（他のExitStrategyV2ロジックは優先度2で実行）
            if self.exit_strategy_v2.time_based_exit_enabled:
                entry_time = self.entry_record.get('entry_time', 0)
                current_time = current_ohlcv.get('timestamp', 0)
                
                # デバッグ出力
                # self.logger.log(f"[DEBUG TBE] entry_time={entry_time}, current_time={current_time}")
                
                time_check = self.exit_strategy_v2._check_time_based_exit(
                    current_time,
                    entry_time,
                    current_ohlcv.get('close_price', 0),
                    position_info.get('entry_price', 0)
                )
                if time_check.get('should_exit', False):
                    decision = "EXIT"
                    exit_reason = time_check.get('exit_reason', 'TIME_LIMIT')
                    
                    if position_side == "BUY":
                        side = "SELL"
                    elif position_side == "SELL":
                        side = "BUY"
                    
                    self.logger.log(f"[条件判定:EXIT] Time-Based Exit: {time_check.get('description', '72時間超過')}")
                    self.trade_decision["side"] = side
                    self.trade_decision["decision"] = decision
                    self.trade_decision["exit_reason"] = exit_reason
                    return
        except Exception as e:
            self.logger.log(f"[WARNING] Time-Based Exitチェックエラー: {e}")

        #-------------------------------------------------------
        # 優先度0.5：Chandelier Exit（Task 44a）
        # - 従来型ATRストップより先に発動する可能性のあるトレイリングストップ
        # - Chandelier Stop > 従来型ストップ（ロング）の場合により高い価格でEXIT
        #-------------------------------------------------------
        try:
            if self.exit_strategy_v2.chandelier_exit_enabled:
                entry_price_for_chandelier = self.portfolio.get_position_price()
                chandelier_position_info = {
                    'entry_price': entry_price_for_chandelier,
                    'quantity': self.portfolio.get_position_quantity(),
                    'side': position_side,
                }
                chandelier_result = self.exit_strategy_v2._check_chandelier_exit(
                    current_price=current_ohlcv.get('close_price', 0),
                    current_high=current_ohlcv.get('high_price', 0),
                    current_low=current_ohlcv.get('low_price', 0),
                    current_atr=current_ohlcv.get('volatility', 0),
                    entry_price=entry_price_for_chandelier,
                    position_info=chandelier_position_info,
                    entry_info=self.entry_record,
                )
                if chandelier_result.get('should_exit', False):
                    chandelier_stop = chandelier_result.get('chandelier_stop', 0)
                    replaces_psar = getattr(self.exit_strategy_v2, 'chandelier_replaces_psar', False)
                    if replaces_psar:
                        # PSARを置換モード: Chandelier Stopを無条件採用
                        exec_chandelier = True
                    else:
                        # 併用モード: Chandelier StopがPSARより有利な場合のみ採用
                        stop_price_check = self.risk_manager.get_stop_price()
                        exec_chandelier = (
                            (position_side == "BUY"  and chandelier_stop > stop_price_check) or
                            (position_side == "SELL" and chandelier_stop < stop_price_check)
                        )
                    if exec_chandelier:
                        side = "SELL" if position_side == "BUY" else "BUY"
                        decision = "EXIT"
                        exit_reason = "CHANDELIER_STOP"
                        self.logger.log(f"[条件判定:EXIT] Chandelier Exit: stop={chandelier_stop:.2f} (replaces_psar={replaces_psar})")
                        self.trade_decision["side"] = side
                        self.trade_decision["decision"] = decision
                        self.trade_decision["exit_reason"] = exit_reason
                        return
        except Exception as e:
            self.logger.log(f"[WARNING] Chandelier Exitチェックエラー: {e}")

        #-------------------------------------------------------
        # 優先度0.6：Profit Step Lock（Task 44b）
        # - 含み益が目標に達した後、大きく引き込んだら利益確定
        #-------------------------------------------------------
        try:
            if self.exit_strategy_v2.profit_step_lock_enabled:
                entry_price_for_psl = self.portfolio.get_position_price()
                psl_position_info = {
                    'entry_price': entry_price_for_psl,
                    'quantity': self.portfolio.get_position_quantity(),
                    'side': position_side,
                }
                psl_result = self.exit_strategy_v2._check_profit_step_lock(
                    current_price=current_ohlcv.get('close_price', 0),
                    entry_price=entry_price_for_psl,
                    position_info=psl_position_info,
                )
                if psl_result.get('should_exit', False):
                    side = "SELL" if position_side == "BUY" else "BUY"
                    decision = "EXIT"
                    exit_reason = psl_result.get('exit_reason', 'PROFIT_LOCK')
                    tier_name = psl_result.get('tier', '?')
                    mfe_pct = psl_result.get('mfe_pct', 0) * 100
                    cur_pct = psl_result.get('current_pnl_pct', 0) * 100
                    self.logger.log(f"[条件判定:EXIT] Profit Step Lock {tier_name}: MFE={mfe_pct:.1f}% → 現在={cur_pct:.1f}%")
                    self.trade_decision["side"] = side
                    self.trade_decision["decision"] = decision
                    self.trade_decision["exit_reason"] = exit_reason
                    return
        except Exception as e:
            self.logger.log(f"[WARNING] Profit Step Lockチェックエラー: {e}")

        #-------------------------------------------------------
        # 優先度0.7：Volume Climax Exit（Task 44d）
        # - 出来高急増（クライマックス）時、含み益があれば利確EXIT
        #-------------------------------------------------------
        try:
            if getattr(self.exit_strategy_v2, 'volume_climax_exit_enabled', False):
                vce_entry_price = self.portfolio.get_position_price()
                vce_position_info = {
                    'entry_price': vce_entry_price,
                    'quantity': self.portfolio.get_position_quantity(),
                    'side': position_side,
                }
                vce_result = self.exit_strategy_v2._check_volume_climax_exit(
                    current_volume=current_ohlcv.get('Volume', 0),  # 大文字V
                    current_price=current_ohlcv.get('close_price', 0),
                    entry_price=vce_entry_price,
                    position_info=vce_position_info,
                )
                if vce_result.get('should_exit', False):
                    side = "SELL" if position_side == "BUY" else "BUY"
                    decision = "EXIT"
                    exit_reason = vce_result.get('exit_reason', 'VOLUME_CLIMAX')
                    vol_ratio = vce_result.get('volume_ratio', 0)
                    pnl_pct = vce_result.get('pnl_pct', 0) * 100
                    self.logger.log(f"[条件判定:EXIT] Volume Climax Exit: 出来高比={vol_ratio:.1f}x, 含み益={pnl_pct:.1f}%")
                    self.trade_decision["side"] = side
                    self.trade_decision["decision"] = decision
                    self.trade_decision["exit_reason"] = exit_reason
                    return
        except Exception as e:
            self.logger.log(f"[WARNING] Volume Climax Exitチェックエラー: {e}")

        #-------------------------------------------------------
        # 優先度0.8：Composite Score Exit（Task 44e）
        # - ADX低下・PVO低下・Volume低下の複合スコアでトレンド失速を検出
        #-------------------------------------------------------
        try:
            if getattr(self.exit_strategy_v2, 'composite_score_exit_enabled', False):
                cse_entry_price = self.portfolio.get_position_price()
                cse_position_info = {
                    'entry_price': cse_entry_price,
                    'quantity': self.portfolio.get_position_quantity(),
                    'side': position_side,
                }
                cse_result = self.exit_strategy_v2._check_composite_score_exit(
                    current_adx=current_ohlcv.get('adx', 0),
                    current_pvo=current_ohlcv.get('pvo_val', 0),
                    current_volume=current_ohlcv.get('Volume', 0),
                    entry_adx=self.entry_record.get('entry_adx', 0),
                    entry_price=cse_entry_price,
                    current_price=current_ohlcv.get('close_price', 0),
                    position_info=cse_position_info,
                )
                if cse_result.get('should_exit', False):
                    side = "SELL" if position_side == "BUY" else "BUY"
                    decision = "EXIT"
                    exit_reason = cse_result.get('exit_reason', 'COMPOSITE_SCORE_EXIT')
                    score = cse_result.get('score', 0)
                    reasons = cse_result.get('reasons', [])
                    pnl_pct = cse_result.get('pnl_pct', 0) * 100
                    self.logger.log(f"[条件判定:EXIT] Composite Score Exit: スコア={score}/3, 含み益={pnl_pct:.1f}%, {reasons}")
                    self.trade_decision["side"] = side
                    self.trade_decision["decision"] = decision
                    self.trade_decision["exit_reason"] = exit_reason
                    return
        except Exception as e:
            self.logger.log(f"[WARNING] Composite Score Exitチェックエラー: {e}")

        #-------------------------------------------------------
        # 優先度1：従来のストップロス判定
        # chandelier_replaces_psar=True のときはスキップ（Chandelierが代替）
        #-------------------------------------------------------
        _skip_psar = getattr(self.exit_strategy_v2, 'chandelier_exit_enabled', False) and \
                     getattr(self.exit_strategy_v2, 'chandelier_replaces_psar', False)
        stop_price = self.risk_manager.get_stop_price()
        high_price = current_ohlcv.get('high_price', 0)
        low_price = current_ohlcv.get('low_price', 0)
        close_price = current_ohlcv.get('close_price', 0)

        if position_side == "BUY":
            if not _skip_psar and low_price <= stop_price:
                executed_price = stop_price * 0.995  # スリッページ考慮
                self.logger.log(f"[条件判定:EXIT] 従来型ストップロス: 2h安値 {low_price:.2f} がストップ値 {stop_price:.2f} を割り込みました")
                side = "SELL"
                decision = "EXIT"
                exit_reason = "STOP_LOSS"
                self.trade_decision["side"] = side
                self.trade_decision["decision"] = decision
                self.trade_decision["exit_reason"] = exit_reason
                self.trade_decision["exec_price"] = executed_price
                return
        
        elif position_side == "SELL":
            if not _skip_psar and high_price >= stop_price:
                executed_price = stop_price * 1.005  # スリッページ考慮
                self.logger.log(f"[条件判定:EXIT] 従来型ストップロス: 2h高値 {high_price:.2f} がストップ値 {stop_price:.2f} を超過しました")
                side = "BUY"
                decision = "EXIT"
                exit_reason = "STOP_LOSS"
                self.trade_decision["side"] = side
                self.trade_decision["decision"] = decision
                self.trade_decision["exit_reason"] = exit_reason
                self.trade_decision["exec_price"] = executed_price
                return
        
        #-------------------------------------------------------
        # 優先度2：ExitStrategyV2で補助判定
        #-------------------------------------------------------
        try:
            position_info = {
                'entry_price': self.portfolio.get_position_price(),
                'quantity': self.portfolio.get_position_quantity(),
                'side': position_side,
            }
            
            exit_decision = self.exit_strategy_v2.evaluate_exit_condition(
                current_ohlcv=current_ohlcv,
                position_info=position_info,
                entry_info=self.entry_record
            )
            
            if exit_decision.get('should_exit', False):
                decision = "EXIT"
                exit_reason = exit_decision.get('exit_reason', 'UNKNOWN')
                stage = exit_decision.get('stage', 'N/A')
                
                if position_side == "BUY":
                    side = "SELL"
                elif position_side == "SELL":
                    side = "BUY"
                
                self.logger.log(f"[条件判定:EXIT] ExitStrategyV2: {exit_reason} (Stage: {stage})")
        
        except Exception as e:
            # ExitStrategyV2でエラーが発生しても、従来の判定は完了している
            self.logger.log(f"[WARNING] ExitStrategyV2エラー: {e}")
        
        self.trade_decision["side"] = side
        self.trade_decision["decision"] = decision
        self.trade_decision["exit_reason"] = exit_reason
        
        return

    def make_trade_decision(self):
        """
        トレードの実行判断を行います。

        """
        portfolio = self.portfolio.get_position_quantity()
        
        # ポートフォリオが辞書でない場合は初期化（ポジションなし）
        if not isinstance(portfolio, dict):
            portfolio = {"quantity": 0, "side": None, "position_price": 0}
        
        # エントリ・買い増し直後に離脱しないように
        if portfolio.get("quantity", 0) == 0:        
            self.evaluate_entry()
        else:
            price = self.price_data_management.get_ticker()
            
            self.evaluate_add(price)
            self.evaluate_exit()
 
        return self.trade_decision
    
    # ========================================
    # Range Breakout Enhanced メソッド (Task 38c)
    # ========================================
    
    def _validate_breakout_strength(self, current_price, donchian_high, donchian_low, side):
        """
        ブレイク強度を検証します.
        
        Args:
            current_price: 現在価格
            donchian_high: Donchian高値
            donchian_low: Donchian安値
            side: エントリー方向 ('BUY' or 'SELL')
        
        Returns:
            bool: ブレイクが有効な場合True
        """
        threshold_percent = Config.get_breakout_threshold_percent()
        
        if side == "BUY":
            # 高値ブレイク: 現在価格がDonchian高値の threshold_percent 以上上にある
            breakout_distance = (current_price - donchian_high) / donchian_high * 100
            is_valid = breakout_distance >= threshold_percent
            
            if is_valid:
                self.logger.log(
                    f"[Breakout強度] ✓ BUY: {breakout_distance:.2f}% (閾値: {threshold_percent}%)"
                )
            else:
                self.logger.log(
                    f"[Breakout強度] ✗ BUY: {breakout_distance:.2f}% < {threshold_percent}%"
                )
            
            return is_valid
            
        elif side == "SELL":
            # 安値ブレイク: 現在価格がDonchian安値の threshold_percent 以上下にある
            breakout_distance = (donchian_low - current_price) / donchian_low * 100
            is_valid = breakout_distance >= threshold_percent
            
            if is_valid:
                self.logger.log(
                    f"[Breakout強度] ✓ SELL: {breakout_distance:.2f}% (閾値: {threshold_percent}%)"
                )
            else:
                self.logger.log(
                    f"[Breakout強度] ✗ SELL: {breakout_distance:.2f}% < {threshold_percent}%"
                )
            
            return is_valid
        
        return False
    
    def _validate_relative_volume(self):
        """
        相対出来高を検証します.
        
        Returns:
            bool: 相対出来高が閾値以上の場合True
        """
        try:
            # 現在の出来高を取得
            current_ohlcv = self.price_data_management.get_latest_ohlcv()
            current_volume = current_ohlcv.get('Volume', 0)  # 大文字V
            
            if current_volume == 0:
                self.logger.log(f"[相対出来高] ✗ 現在出来高がゼロ")
                return False
            
            # 過去N期間のOHLCVデータを取得
            lookback = Config.get_relative_volume_lookback()
            ohlcv_data = self.price_data_management.get_ohlcv_data_by_time_frame(
                Config.get_time_frame()
            )
            
            if not ohlcv_data or len(ohlcv_data) < lookback:
                self.logger.log(f"[相対出来高] ⚠️ データ不足（期間={len(ohlcv_data) if ohlcv_data else 0}）")
                return True  # データ不足時は通過させる
            
            # 平均出来高を計算
            recent_volumes = [candle.get('Volume', 0) for candle in ohlcv_data[-lookback:]]  # 大文字V
            avg_volume = sum(recent_volumes) / len(recent_volumes)
            
            if avg_volume == 0:
                self.logger.log(f"[相対出来高] ⚠️ 平均出来高がゼロ")
                return True
            
            # 相対出来高を計算
            relative_volume = current_volume / avg_volume
            threshold = Config.get_relative_volume_threshold()
            
            is_valid = relative_volume >= threshold
            
            if is_valid:
                self.logger.log(
                    f"[相対出来高] ✓ {relative_volume:.2f}x (閾値: {threshold}x)"
                )
            else:
                self.logger.log(
                    f"[相対出来高] ✗ {relative_volume:.2f}x < {threshold}x"
                )
            
            return is_valid
            
        except Exception as e:
            self.logger.log(f"[相対出来高エラー] {str(e)}")
            return True  # エラー時は通過させる
    
    # ========================================
    # 既存メソッド
    # ========================================
    
    def _evaluate_box_market_entry(self):
        """
        Box市場 (ADX < 20) 向けの平均回帰エントリーシグナル生成
        
        Donchian Channel 逆張り + Bollinger Bands補助戦略
        
        Returns:
            dict: {'signal': 'LONG'/'SHORT', 'reason': 'Donchian_High_Touch'等, 'position_size_ratio': 0.6}
                  または None (エントリーなし)
        """
        current_price = self.price_data_management.get_ticker()
        
        # Donchian Channel取得
        donchian_high = self.risk_manager.get_donchian_high(period=20)
        donchian_low = self.risk_manager.get_donchian_low(period=20)
        
        # 逆張りシグナル判定：Donchian 極値タッチ (98%/102% マージン付き)
        if current_price >= donchian_high * 0.98:
            # 高値タッチ → 売りシグナル (下向き平均回帰期待)
            return {
                'signal': 'SELL',
                'reason': 'Donchian_High_Touch',
                'position_size_ratio': 0.6
            }
        
        elif current_price <= donchian_low * 1.02:
            # 安値タッチ → 買いシグナル (上向き平均回帰期待)
            return {
                'signal': 'BUY',
                'reason': 'Donchian_Low_Touch',
                'position_size_ratio': 0.6
            }
        
        # Donchian シグナルなし → Bollinger Bands 補助シグナル確認
        bb_signal, reason, ratio = self._evaluate_bollinger_signal()
        if bb_signal:
            return {
                'signal': bb_signal,
                'reason': reason,
                'position_size_ratio': ratio
            }
        
        # どちらのシグナルもなし
        return None
    
    def _evaluate_bollinger_signal(self):
        """
        Bollinger Bands 2σ 外部接触での逆張りシグナル生成 (Donchian補助用)
        
        Returns:
            tuple: (signal, reason, position_size_ratio)
                   signal: 'LONG'/'SHORT' または None
                   reason: 'BB_Upper_Touch' など
                   position_size_ratio: 0.4 (保守的)
        """
        current_price = self.price_data_management.get_ticker()
        
        # Bollinger Bands取得
        bb_upper = self.risk_manager.get_bb_upper(period=20, sigma=2.0)
        bb_lower = self.risk_manager.get_bb_lower(period=20, sigma=2.0)
        
        # BB 2σ外接触での逆張り
        if current_price > bb_upper:
            # 上限外 → 売りシグナル
            return ('SELL', 'BB_Upper_Touch', 0.4)
        
        elif current_price < bb_lower:
            # 下限外 → 買いシグナル
            return ('BUY', 'BB_Lower_Touch', 0.4)
        
        # シグナルなし
        return (None, None, 0)
    
    def __str__(self):
        return f"Trade Decision: Decision = {self.trade_decision['decision']}, Side = {self.trade_decision['side']}, Order Type = {self.trade_decision['order_type']}"

if __name__ == "__main__":
    # TradingStrategyクラスの初期化
    portfolio = Portfolio()
    price_data_management = PriceDataManagement()
    risk_manager = RiskManagement(price_data_management, portfolio)
    strategy = TradingStrategy(price_data_management, risk_manager, portfolio)

    # 取引情報を決定
    print(strategy)

