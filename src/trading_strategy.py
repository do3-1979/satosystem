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
        # H-042: スケールアウト状態管理
        self._scale_out_done  = False   # 1トレードにつき1回のみ
        self._entry_risk_usd  = 0.0     # エントリー時の初期リスク(USD)
        
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
        
        # 確認バー（Donchian Breakout Confirmation）
        self.donchian_confirmation_enabled = Config.get_config_bool('EntryFilters', 'donchian_confirmation_enabled', 0)
        self.donchian_confirmation_bars = Config.get_config_int('EntryFilters', 'donchian_confirmation_bars', 1)
        self.pending_breakout = None  # {'side': 'BUY'/'SELL', 'bars_waited': 0}
        
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

        # H-013: 時間帯フィルター (Session Filter)
        # close_time_dtはJST表示なので、UTCエポックからJST時刻に変換してブロック
        if Config.get_session_filter_enabled():
            try:
                epoch = self.price_data_management.get_latest_close_time()
                block_hours = Config.get_session_filter_block_hours()
                close_hour_jst = (datetime.utcfromtimestamp(epoch).hour + 9) % 24
                if close_hour_jst in block_hours:
                    self.logger.log(f"[時間帯フィルター] JST {close_hour_jst:02d}:00 のエントリーをスキップ")
                    return
            except Exception as e:
                self.logger.log(f"[時間帯フィルターエラー] {str(e)}")

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
                    
                    # === 確認バーフィルター ===
                    if self.donchian_confirmation_enabled:
                        if self.pending_breakout is None:
                            # 初回ブレイク検出 → 待機開始
                            self.pending_breakout = {'side': desired_side, 'bars_waited': 0}
                            self.logger.log(f"[確認バー] {desired_side} ブレイク検出 → {self.donchian_confirmation_bars}本待機")
                            allow_entry = False
                        elif self.pending_breakout['side'] != desired_side:
                            # 方向転換 → リセットして新方向で待機開始
                            self.pending_breakout = {'side': desired_side, 'bars_waited': 0}
                            self.logger.log(f"[確認バー] 方向転換 → {desired_side} で待機リセット")
                            allow_entry = False
                        elif self.pending_breakout['bars_waited'] < self.donchian_confirmation_bars:
                            # 待機中
                            self.pending_breakout['bars_waited'] += 1
                            if self.pending_breakout['bars_waited'] >= self.donchian_confirmation_bars:
                                # 確認完了
                                self.logger.log(f"[確認バー] ✓ {desired_side} 確認完了 → エントリー")
                                self.pending_breakout = None
                            else:
                                self.logger.log(f"[確認バー] 待機中 ({self.pending_breakout['bars_waited']}/{self.donchian_confirmation_bars})")
                                allow_entry = False
                        else:
                            # 確認済み（bars_waited >= confirmation_bars）
                            self.logger.log(f"[確認バー] ✓ {desired_side} 確認完了 → エントリー")
                            self.pending_breakout = None
                    
                    # === Range Breakout Enhanced (Task 38c) ===
                    enable_rbe = Config.get_enable_range_breakout_enhanced()
                    if enable_rbe:
                        # ブレイク強度確認（シグナル生成と同じ4H/buy_term期間のチャネル値を使用）
                        current_price = self.price_data_management.get_ticker()
                        donchian_high = signals["donchian"]["info"]["highest"]
                        donchian_low = signals["donchian"]["info"]["lowest"]
                        
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
                else:
                    # ブレイクアウトなし → pending確認バーをリセット
                    if self.donchian_confirmation_enabled and self.pending_breakout is not None:
                        self.logger.log(f"[確認バー] シグナル消滅 → 待機リセット")
                        self.pending_breakout = None
            
            # ========================================
            # 新指標チェック（Donchian使用時のみ）
            # ========================================
            if not enable_mr and allow_entry:
                if use_new_strategy:
                    if strategy_side is None:
                        # H-022: strategy_A が NONE = 方向性不明 → エントリー禁止
                        conditions_list.append(f"新指標: NONE （✗方向性不明）")
                        allow_entry = False
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

                # H-040: ATRブレイクアウト強度フィルター
                # 仮説: ブレイク幅 < ATR×ratio の弱いブレイクはフォールスブレイクアウト
                if Config.get_atr_breakout_filter_enabled() and desired_side and allow_entry:
                    try:
                        atr_period = Config.get_atr_breakout_period()
                        min_ratio  = Config.get_atr_breakout_min_ratio()
                        atr_ohlcv  = ohlcv_data if ohlcv_data else []
                        if len(atr_ohlcv) >= atr_period:
                            trs = [max(
                                atr_ohlcv[i]['high_price'] - atr_ohlcv[i]['low_price'],
                                abs(atr_ohlcv[i]['high_price'] - atr_ohlcv[i-1]['close_price']),
                                abs(atr_ohlcv[i]['low_price']  - atr_ohlcv[i-1]['close_price'])
                            ) for i in range(-atr_period, 0)]
                            atr_val = sum(trs) / len(trs)
                            dc_info = signals['donchian']['info']
                            cur_close = self.price_data_management.get_ticker()
                            if desired_side == 'BUY':
                                break_size = cur_close - dc_info.get('highest', cur_close)
                            else:
                                break_size = dc_info.get('lowest', cur_close) - cur_close
                            threshold = atr_val * min_ratio
                            if break_size < threshold:
                                filter_results.append(
                                    f"ATRBreakout: ✗ 弱いブレイク(幅={break_size:.0f} < ATR×{min_ratio}={threshold:.0f})"
                                )
                                allow_entry = False
                            else:
                                filter_results.append(
                                    f"ATRBreakout: ✓ (幅={break_size:.0f} >= ATR×{min_ratio}={threshold:.0f})"
                                )
                        else:
                            filter_results.append(f"ATRBreakout: ⚠ データ不足({len(atr_ohlcv)}<{atr_period})")
                    except Exception as e:
                        filter_results.append(f"ATRBreakout: ⚠ エラー({str(e)[:30]})")

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

                # H-006b: 日足MTFフィルター (Multi-Timeframe Regime Detection)
                # 原理: 4H足OHLCVを6本集約→日足ADX計算。日足ADX<threshold=レンジ相場→エントリー禁止
                # 参考: Elder "Trading for a Living" (1993) - MTFアプローチ
                if Config.get_mtf_daily_filter_enabled() and desired_side and allow_entry:
                    try:
                        daily_adx_threshold = Config.get_mtf_daily_adx_threshold()
                        adx_period = Config.get_mtf_daily_adx_period()
                        bars_per_day = 6  # 4H足×6本=24H
                        needed_4h = (adx_period * 2 + 1) * bars_per_day  # Wilder smoothing用に余裕を持つ
                        raw_ohlcv = ohlcv_data if ohlcv_data else []
                        if len(raw_ohlcv) >= needed_4h:
                            # 4H足→日足OHLCV集約（high_price/low_price/close_priceをfloat変換）
                            daily_candles = []
                            start = len(raw_ohlcv) % bars_per_day  # 端数を除いて整列
                            for i in range(start, len(raw_ohlcv) - bars_per_day + 1, bars_per_day):
                                chunk = raw_ohlcv[i:i + bars_per_day]
                                daily_candles.append({
                                    'high': max(float(c['high_price']) for c in chunk),
                                    'low': min(float(c['low_price']) for c in chunk),
                                    'close': float(chunk[-1]['close_price'])
                                })
                            if len(daily_candles) >= adx_period + 1:
                                highs = [c['high'] for c in daily_candles]
                                lows = [c['low'] for c in daily_candles]
                                closes = [c['close'] for c in daily_candles]
                                # True Range / Directional Movement 計算
                                trs, plus_dms, minus_dms = [], [], []
                                for j in range(1, len(daily_candles)):
                                    tr = max(highs[j] - lows[j],
                                             abs(highs[j] - closes[j-1]),
                                             abs(lows[j] - closes[j-1]))
                                    up = highs[j] - highs[j-1]
                                    dn = lows[j-1] - lows[j]
                                    trs.append(tr)
                                    plus_dms.append(up if up > dn and up > 0 else 0)
                                    minus_dms.append(dn if dn > up and dn > 0 else 0)
                                # Wilder平滑化（ATR/DM用）: 初期値は合計
                                def _wilder(data, n):
                                    if len(data) < n:
                                        return []
                                    s = [sum(data[:n])]
                                    for v in data[n:]:
                                        s.append(s[-1] - s[-1] / n + v)
                                    return s
                                atr14 = _wilder(trs, adx_period)
                                pdm14 = _wilder(plus_dms, adx_period)
                                mdm14 = _wilder(minus_dms, adx_period)
                                dx_list = []
                                for j in range(len(atr14)):
                                    if atr14[j] > 0:
                                        pdi = 100 * pdm14[j] / atr14[j]
                                        mdi = 100 * mdm14[j] / atr14[j]
                                        dx_list.append(100 * abs(pdi - mdi) / (pdi + mdi) if (pdi + mdi) > 0 else 0)
                                # ADX計算: DXのWilderスムージング（初期値は平均、以降はEMA alpha=1/n）
                                if len(dx_list) >= adx_period:
                                    adx14 = [sum(dx_list[:adx_period]) / adx_period]
                                    for v in dx_list[adx_period:]:
                                        adx14.append(adx14[-1] - adx14[-1] / adx_period + v / adx_period)
                                else:
                                    adx14 = []
                                if adx14:
                                    daily_adx = adx14[-1]
                                    if daily_adx < daily_adx_threshold:
                                        filter_results.append(f"MTF日足ADX: ✗ レンジ(日足ADX={daily_adx:.1f}<{daily_adx_threshold:.0f})")
                                        allow_entry = False
                                    else:
                                        filter_results.append(f"MTF日足ADX: ✓ トレンド(日足ADX={daily_adx:.1f}>={daily_adx_threshold:.0f})")
                                else:
                                    filter_results.append(f"MTF日足ADX: ⚠ ADX計算失敗")
                            else:
                                filter_results.append(f"MTF日足ADX: ⚠ 日足本数不足({len(daily_candles)}<{adx_period+1})")
                        else:
                            filter_results.append(f"MTF日足ADX: ⚠ 4H足不足({len(raw_ohlcv)}<{needed_4h})")
                    except Exception as e:
                        filter_results.append(f"MTF日足ADX: ⚠ エラー({str(e)[:30]})")

                # H-006c: ハースト指数フィルター (R/S Analysis - Mandelbrot 1972)
                # 原理: H < threshold = 平均回帰相場（レンジ） → エントリー禁止
                #       H >= threshold = トレンド持続性あり → エントリー許可
                # H = 0.5: ランダムウォーク, H > 0.5: トレンド持続, H < 0.5: 平均回帰
                if Config.get_hurst_filter_enabled() and desired_side and allow_entry:
                    try:
                        lookback = Config.get_hurst_lookback()
                        h_threshold = Config.get_hurst_threshold()
                        closes_raw = ohlcv_data if ohlcv_data else []
                        if len(closes_raw) >= lookback + 1:
                            px = [float(c['close_price']) for c in closes_raw[-(lookback + 1):]]
                            # log収益率系列
                            import math as _math
                            log_rets = [_math.log(px[i] / px[i-1]) for i in range(1, len(px)) if px[i-1] > 0]
                            n = len(log_rets)
                            if n >= 20:
                                # R/S解析: 複数のサブ期間長でスケーリング則を推定
                                def _rs(series):
                                    m = sum(series) / len(series)
                                    dev = [x - m for x in series]
                                    cum = [sum(dev[:i+1]) for i in range(len(dev))]
                                    r = max(cum) - min(cum)
                                    s = (sum((x - m)**2 for x in series) / len(series)) ** 0.5
                                    return r / s if s > 0 else 0
                                # スケール長: 10, 20, n//2 の3点
                                scales = sorted({max(10, n // 4), max(15, n // 3), max(20, n // 2)})
                                log_scales, log_rs = [], []
                                for sc in scales:
                                    if n >= sc:
                                        chunks = [log_rets[i:i+sc] for i in range(0, n - sc + 1, sc)]
                                        if chunks:
                                            avg_rs = sum(_rs(c) for c in chunks) / len(chunks)
                                            if avg_rs > 0:
                                                log_scales.append(_math.log(sc))
                                                log_rs.append(_math.log(avg_rs))
                                if len(log_scales) >= 2:
                                    # 最小二乗でハースト指数を推定
                                    xs, ys = log_scales, log_rs
                                    n_pts = len(xs)
                                    sx = sum(xs); sy = sum(ys)
                                    sxx = sum(x*x for x in xs); sxy = sum(x*y for x, y in zip(xs, ys))
                                    hurst = (n_pts * sxy - sx * sy) / (n_pts * sxx - sx * sx) if (n_pts * sxx - sx * sx) != 0 else 0.5
                                    hurst = max(0.0, min(1.0, hurst))  # [0, 1]にクリップ
                                    if hurst < h_threshold:
                                        filter_results.append(f"Hurst: ✗ 平均回帰(H={hurst:.3f}<{h_threshold:.2f})")
                                        allow_entry = False
                                    else:
                                        filter_results.append(f"Hurst: ✓ トレンド(H={hurst:.3f}>={h_threshold:.2f})")
                                else:
                                    filter_results.append(f"Hurst: ⚠ スケール不足")
                            else:
                                filter_results.append(f"Hurst: ⚠ データ不足({n}<20)")
                        else:
                            filter_results.append(f"Hurst: ⚠ OHLCV不足({len(closes_raw)}<{lookback+1})")
                    except Exception as e:
                        filter_results.append(f"Hurst: ⚠ エラー({str(e)[:30]})")

                # H-011: ADX適応型ポジションサイズ調整
                # ADX弱い（31〜38）→ weak_multiplier倍, ADX強い（≥38）→ 通常サイズ
                if Config.get_adx_size_scaling_enabled() and desired_side and allow_entry:
                    try:
                        strong_thresh = Config.get_adx_size_strong_threshold()
                        weak_mult = Config.get_adx_size_weak_multiplier()
                        adx_for_size = self.risk_manager.get_adx() if hasattr(self.risk_manager, 'get_adx') else 0
                        if adx_for_size < strong_thresh:
                            position_size_ratio *= weak_mult
                            filter_results.append(f"ADXサイズ調整: {weak_mult:.1%}(ADX={adx_for_size:.1f}<{strong_thresh:.0f})")
                        else:
                            filter_results.append(f"ADXサイズ調整: 100%(ADX={adx_for_size:.1f}>={strong_thresh:.0f})")
                    except Exception as e:
                        filter_results.append(f"ADXサイズ調整: ⚠ エラー({str(e)[:30]})")

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
                'entry_time': current_price.get('timestamp') or current_price.get('close_time', 0),
                'entry_atr': self.price_data_management.get_volatility(),  # H-014: ATR初期ストップ用
                'strategy_result': strategy_result,
            }
            # H-042: スケールアウト状態リセット
            self._scale_out_done = False
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

    def _evaluate_scale_out(self, current_price):
        """
        H-042: 未実現利益スケールアウト（部分利確）判定

        エントリー後、未実現利益が「初期リスク × trigger_multiplier」を
        超えたら scale_out_quantity_pct 割合で部分決済する。
        1 トレードにつき 1 回のみ発動。

        Returns:
            bool: True=SCALE_OUT 発動（trade_decision セット済み）, False=発動なし
        """
        enabled = Config.get_scale_out_enabled()
        # 回帰テストでは Config が MagicMock の場合があるため、非プリミティブは無効扱いにする
        if isinstance(enabled, bool):
            enabled_flag = enabled
        elif isinstance(enabled, (int, float)):
            enabled_flag = int(enabled) == 1
        elif isinstance(enabled, str):
            enabled_flag = enabled.strip() in ('1', 'true', 'True')
        else:
            enabled_flag = False

        if not enabled_flag:
            return False
        if self._scale_out_done:
            return False

        position_side = self.portfolio.get_position_side()
        if position_side not in ('BUY', 'SELL'):
            return False

        # 未実現損益を計算
        try:
            entry_price = float(self.portfolio.get_position_price() or 0)
        except (TypeError, ValueError):
            return False

        pos = self.portfolio.get_position_quantity()
        if not isinstance(pos, dict):
            return False
        try:
            quantity = float(pos.get('quantity', 0) or 0)
        except (TypeError, ValueError):
            return False

        try:
            current_price = float(current_price)
        except (TypeError, ValueError):
            return False

        if quantity <= 0 or entry_price <= 0:
            return False

        if position_side == 'BUY':
            unrealized_pnl = (current_price - entry_price) * quantity
        else:
            unrealized_pnl = (entry_price - current_price) * quantity

        # ATRベース価格移動トリガー（再設計: _entry_risk_usd 依存を廃止）
        # トリガー条件: (現在価格 - エントリー価格) >= entry_atr × trigger_multiplier
        entry_atr = 0.0
        if hasattr(self, 'entry_record') and self.entry_record:
            try:
                entry_atr = float(self.entry_record.get('entry_atr', 0) or 0)
            except (TypeError, ValueError):
                entry_atr = 0.0
        if entry_atr <= 0:
            return False

        try:
            trigger_multiplier = float(Config.get_scale_out_trigger_multiplier())
        except (TypeError, ValueError):
            return False

        trigger_price_move = entry_atr * trigger_multiplier  # ATRの何倍動いたら発動

        if position_side == 'BUY':
            price_diff = current_price - entry_price
        else:
            price_diff = entry_price - current_price

        if price_diff >= trigger_price_move:
            self._scale_out_done = True
            self.trade_decision["decision"] = "SCALE_OUT"
            self.trade_decision["side"]     = position_side
            try:
                qty_pct = float(Config.get_scale_out_quantity_pct())
            except (TypeError, ValueError):
                qty_pct = 0.5
            self.trade_decision["scale_out_qty_pct"] = min(max(qty_pct, 0.0), 1.0)
            self.logger.log(
                f"[H-042 ScaleOut] 発動: 価格移動={price_diff:.2f} USD >= "
                f"閾値={trigger_price_move:.2f} USD (ATR={entry_atr:.2f} × {trigger_multiplier}倍)  "
                f"未実現利益={unrealized_pnl:.2f} USD  "
                f"利確割合={self.trade_decision['scale_out_qty_pct']:.0%}"
            )
            return True

        return False

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
        
        # timestampがない場合やNoneの場合はclose_timeをtimestampとして設定（Time-Based Exit用）
        if not current_ohlcv.get('timestamp') and 'close_time' in current_ohlcv:
            current_ohlcv['timestamp'] = current_ohlcv['close_time']
        
        #-------------------------------------------------------
        # 優先度0：Time-Based Exit（長期ポジションの強制決済）
        #-------------------------------------------------------
        # ストップロスより優先して、保有時間制限をチェック
        try:
            position_info = {
                # NOTE: entry_price は TBE 用に実際のエントリー価格を使用（TBE無効の場合はこのブロック未到達）
                # Chandelier/PSL用の entry_price は各ブロック内で get_position_price() を使用
                'entry_price': self.portfolio.get_position_price() or 0,
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

        #-------------------------------------------------------
        # 優先度0.9：H-014 ATR初期ストップロス（固定ストップ）
        # エントリー時ATR×multiplierで固定ストップを設定
        # PSARはトレーリングするが、初期ストップはATR×2.0(=PSAR初期値)と同等
        # multiplier < 2.0（例:1.5）で「PSARより締まった固定ストップ」として機能
        # → エントリー後に価格が上がらず下落したケースで早期損切りして損失削減
        #-------------------------------------------------------
        if Config.get_atr_initial_stop_enabled():
            try:
                entry_atr = float(self.entry_record.get('entry_atr', 0) or 0)
                entry_price = float(self.entry_record.get('entry_price', 0) or 0)
                multiplier = Config.get_atr_initial_stop_multiplier()
                if entry_atr > 0 and entry_price > 0:
                    if position_side == 'BUY':
                        atr_stop = entry_price - multiplier * entry_atr
                        if low_price <= atr_stop:
                            executed_price = atr_stop * 0.995
                            self.logger.log(f"[条件判定:EXIT] ATR初期ストップ: 安値{low_price:.2f}≤ATR_SL{atr_stop:.2f}(ep={entry_price:.0f}-{multiplier}×ATR{entry_atr:.0f})")
                            side = "SELL"
                            decision = "EXIT"
                            exit_reason = "ATR_INITIAL_STOP"
                            self.trade_decision["side"] = side
                            self.trade_decision["decision"] = decision
                            self.trade_decision["exit_reason"] = exit_reason
                            self.trade_decision["exec_price"] = executed_price
                            return
                    elif position_side == 'SELL':
                        atr_stop = entry_price + multiplier * entry_atr
                        if high_price >= atr_stop:
                            executed_price = atr_stop * 1.005
                            self.logger.log(f"[条件判定:EXIT] ATR初期ストップ: 高値{high_price:.2f}≥ATR_SL{atr_stop:.2f}(ep={entry_price:.0f}+{multiplier}×ATR{entry_atr:.0f})")
                            side = "BUY"
                            decision = "EXIT"
                            exit_reason = "ATR_INITIAL_STOP"
                            self.trade_decision["side"] = side
                            self.trade_decision["decision"] = decision
                            self.trade_decision["exit_reason"] = exit_reason
                            self.trade_decision["exec_price"] = executed_price
                            return
            except Exception as e:
                self.logger.log(f"[WARNING] ATR初期ストップチェックエラー: {e}")

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
            
            # H-042: スケールアウト判定（エグジット評価より優先）
            if self._evaluate_scale_out(price):
                return self.trade_decision

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

