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
        self.entry_record = {}  # エントリー時の指標情報を記録
        
        # 市場体制判定の初期化
        self.market_regime_detector = MarketRegimeDetector(
            atr_period=Config.get_atr_period(),
            atr_ma_period=Config.get_atr_ma_period(),
            lookback_period=Config.get_swing_lookback_period()
        )
        self.current_market_regime = 'TRANSITION'  # 現在の市場体制
        self.market_regime_confidence = 0.0
        
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

    def _get_current_quarter_and_year(self, timestamp):
        """
        タイムスタンプから現在のQ(四半期)と年を取得する
        
        Args:
            timestamp: datetime object
            
        Returns:
            tuple: (year, quarter_name) e.g., (2025, 'Q1')
        """
        if not isinstance(timestamp, datetime):
            return None, None
        
        year = timestamp.year
        month = timestamp.month
        
        if month <= 3:
            quarter = 'Q1'
        elif month <= 6:
            quarter = 'Q2'
        elif month <= 9:
            quarter = 'Q3'
        else:
            quarter = 'Q4'
        
        return year, quarter

    def _apply_seasonality_positioning(self, current_timestamp, position_size_ratio):
        """
        季節性ベースのロット調整を適用する
        
        損失が多い四半期（Q2, Q3, Q1-2025+）ではロットを削減
        利益が多い四半期（Q1, Q4）では通常のロット
        
        Args:
            current_timestamp: 現在のタイムスタンプ (datetime)
            position_size_ratio: 現在のポジションサイズ比率
            
        Returns:
            float: 調整後のポジションサイズ比率
        """
        if not Config.get_enable_seasonality_based_positioning():
            return position_size_ratio
        
        year, quarter = self._get_current_quarter_and_year(current_timestamp)
        if year is None or quarter is None:
            return position_size_ratio
        
        # 損失が多い四半期の判定
        loss_quarters = ['Q2', 'Q3']  # Q2, Q3 は箱相場で損失が多い
        is_loss_quarter_2025_plus = (quarter == 'Q1' and year >= 2025)  # 2025年以降のQ1も損失
        
        if quarter in loss_quarters or is_loss_quarter_2025_plus:
            seasonality_multiplier = Config.get_seasonality_loss_quarter_multiplier()
            original_ratio = position_size_ratio
            position_size_ratio *= seasonality_multiplier
            self.logger.log(
                f"[季節性:ロット調整] {year}{quarter} → 損失四半期で {seasonality_multiplier:.1%} に削減 "
                f"({original_ratio:.2f} → {position_size_ratio:.2f})"
            )
        else:
            seasonality_multiplier = Config.get_seasonality_profit_quarter_multiplier()
            self.logger.log(
                f"[季節性:ロット調整] {year}{quarter} → 利益四半期で {seasonality_multiplier:.1%} 適用 "
                f"(位置サイズ={position_size_ratio:.2f})"
            )
        
        return position_size_ratio

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

        # 新指標ベースのStrategyを評価
        strategy_result = self._evaluate_new_indicator_strategy()
        use_new_strategy = any([
            getattr(self.risk_manager, 'enable_strategy_a_adx', False),
            getattr(self.risk_manager, 'enable_strategy_b_bb_rsi_sma', False),
            getattr(self.risk_manager, 'enable_strategy_c_combined', False),
        ])
        strategy_side = None
        if strategy_result:
            raw_signal = strategy_result.get('signal', 'NONE')
            if raw_signal in ['BUY', 'SELL']:
                strategy_side = raw_signal
            elif raw_signal == 'BULL':
                strategy_side = 'BUY'
            elif raw_signal == 'BEAR':
                strategy_side = 'SELL'
        
        # PVO有効範囲チェック
        if signals["pvo"]["signal"] == True:
            # ドンチャンチャネルブレイク発生
            if signals["donchian"]["signal"] == True:
                desired_side = signals["donchian"]["side"]
                allow_entry = True

                if use_new_strategy:
                    if strategy_side is None:
                        # 新指標が沈黙ならベースライン許可（フィルタのみとして扱う）
                        self.logger.log(f"[条件判定:ENTRY] 新指標シグナルなし→ベースライン許可 (donchian={desired_side})")
                    elif strategy_side == desired_side:
                        self.logger.log(f"[条件判定:ENTRY] {desired_side} エントリー条件成立（新指標一致）")
                    else:
                        self.logger.log(f"[条件判定:ENTRY] 新指標が逆方向のためエントリー見送り (donchian={desired_side}, strategy={strategy_side})")
                        allow_entry = False
                else:
                    self.logger.log(f"[条件判定:ENTRY] {desired_side} のエントリー条件成立しました")

                # =========== 市場体制判定 ===========
                enable_market_regime_detection = Config.get_enable_market_regime_detection()
                if allow_entry and enable_market_regime_detection:
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
                            
                            self.logger.log(f"[市場体制判定] {self.current_market_regime} (信頼度={self.market_regime_confidence:.2f}, {regime_result['reason']})")
                            
                            # ボックス相場判定時の条件強化
                            enable_strictness = Config.get_enable_entry_condition_strictness_on_range()
                            if self.current_market_regime == 'RANGING' and enable_strictness:
                                # ボックス相場時：Volume + ADXフィルタを必須化
                                self.logger.log(f"[市場体制判定] ボックス相場検出 → エントリー条件を強化します")
                                
                                # Volume フィルター強制有効化
                                volume_value = self.price_data_management.get_latest_volume()
                                volume_threshold = Config.get_volume_filter_threshold()
                                if volume_value < volume_threshold:
                                    self.logger.log(f"[市場体制:ボックス] Volume不足で除外 (Volume={volume_value:.0f} < {volume_threshold:.0f})")
                                    allow_entry = False
                                else:
                                    self.logger.log(f"[市場体制:ボックス] Volume OK (Volume={volume_value:.0f} >= {volume_threshold:.0f})")
                                
                                # ADX フィルター強制有効化
                                if allow_entry:
                                    adx_value = self.risk_manager.get_adx() if hasattr(self.risk_manager, 'get_adx') else 0
                                    adx_threshold = Config.get_adx_filter_threshold()
                                    if adx_value < adx_threshold:
                                        self.logger.log(f"[市場体制:ボックス] ADX不足で除外 (ADX={adx_value:.2f} < {adx_threshold})")
                                        allow_entry = False
                                    else:
                                        self.logger.log(f"[市場体制:ボックス] ADX OK (ADX={adx_value:.2f} >= {adx_threshold})")
                                
                                # ポジションサイズ削減
                                if allow_entry:
                                    ranging_multiplier = Config.get_ranging_position_size_multiplier()
                                    position_size_ratio *= ranging_multiplier
                                    self.logger.log(f"[市場体制:ボックス] ポジションサイズを {ranging_multiplier:.1%} に削減")
                            
                            elif self.current_market_regime in ['TRENDING_UP', 'TRENDING_DOWN']:
                                self.logger.log(f"[市場体制判定] トレンド相場 → 通常エントリー条件で進行")
                    except Exception as e:
                        # 市場体制判定エラーはログするが、エントリー判定は続行
                        self.logger.log(f"[市場体制判定エラー] {str(e)}")

                # =========== 季節性ベースのロット調整 ===========
                # 損失が多い四半期ではロットを削減、利益が多い四半期では通常のロット
                if allow_entry:
                    try:
                        current_ohlcv = self.price_data_management.get_latest_ohlcv()
                        if current_ohlcv and 'real_time_dt' in current_ohlcv:
                            current_timestamp = current_ohlcv['real_time_dt']
                            if isinstance(current_timestamp, datetime):
                                year, quarter = self._get_current_quarter_and_year(current_timestamp)
                                if year is not None and quarter is not None:
                                    # 季節性判定
                                    loss_quarters = ['Q2', 'Q3']
                                    is_loss_quarter = (quarter in loss_quarters or (quarter == 'Q1' and year >= 2025))
                                    
                                    if is_loss_quarter and Config.get_enable_seasonality_based_positioning():
                                        # 損失四半期では、より厳格な条件を強制（Volume + ADXフィルタ）
                                        seasonality_multiplier = Config.get_seasonality_loss_quarter_multiplier()
                                        self.logger.log(
                                            f"[季節性判定] {year}{quarter} → 損失四半期検出 ({seasonality_multiplier:.0%} の適用)"
                                        )
                                        
                                        # Volume フィルター強制有効化
                                        volume_value = self.price_data_management.get_latest_volume()
                                        volume_threshold = Config.get_volume_filter_threshold()
                                        if volume_value < volume_threshold:
                                            self.logger.log(
                                                f"[季節性:損失四半期] Volume不足で除外 "
                                                f"(Volume={volume_value:.0f} < {volume_threshold:.0f})"
                                            )
                                            allow_entry = False
                                        
                                        # ADX フィルター強制有効化
                                        if allow_entry:
                                            adx_value = self.risk_manager.get_adx() if hasattr(self.risk_manager, 'get_adx') else 0
                                            adx_threshold = Config.get_adx_filter_threshold()
                                            if adx_value < adx_threshold:
                                                self.logger.log(
                                                    f"[季節性:損失四半期] ADX不足で除外 (ADX={adx_value:.2f} < {adx_threshold})"
                                                )
                                                allow_entry = False
                                        
                                        # エントリーが許可されていればポジションサイズ削減
                                        if allow_entry:
                                            position_size_ratio *= seasonality_multiplier
                                            self.logger.log(
                                                f"[季節性:損失四半期] ポジションサイズを {seasonality_multiplier:.0%} に削減"
                                            )
                    except Exception as e:
                        self.logger.log(f"[季節性調整エラー] {str(e)}")

                # =========== フィルター機能 ===========
                # PVO フィルター
                enable_pvo_filter = Config.get_enable_pvo_filter()
                if allow_entry and enable_pvo_filter:
                    pvo_value = signals["pvo"]["info"].get("value", 0)
                    pvo_threshold = Config.get_pvo_threshold()
                    if pvo_value <= pvo_threshold:
                        self.logger.log(f"[フィルター:ENTRY] PVO フィルター失敗 (PVO={pvo_value:.4f} <= {pvo_threshold})")
                        allow_entry = False
                    else:
                        self.logger.log(f"[フィルター:ENTRY] PVO フィルター成功 (PVO={pvo_value:.4f} > {pvo_threshold})")
                
                # ADX フィルター
                enable_adx_filter = Config.get_enable_adx_filter()
                adx_threshold = Config.get_adx_filter_threshold()
                if allow_entry and enable_adx_filter:
                    adx_value = self.risk_manager.get_adx() if hasattr(self.risk_manager, 'get_adx') else 0
                    if adx_value < adx_threshold:
                        self.logger.log(f"[フィルター:ENTRY] ADX フィルター失敗 (ADX={adx_value:.2f} < {adx_threshold})")
                        allow_entry = False
                    else:
                        self.logger.log(f"[フィルター:ENTRY] ADX フィルター成功 (ADX={adx_value:.2f} >= {adx_threshold})")
                
                # Volume フィルター
                enable_volume_filter = Config.get_enable_volume_filter()
                volume_threshold = Config.get_volume_filter_threshold()
                if allow_entry and enable_volume_filter:
                    volume_value = self.price_data_management.get_latest_volume()
                    if volume_value < volume_threshold:
                        self.logger.log(f"[フィルター:ENTRY] Volume フィルター失敗 (Volume={volume_value:.0f} < {volume_threshold:.0f})")
                        allow_entry = False
                    else:
                        self.logger.log(f"[フィルター:ENTRY] Volume フィルター成功 (Volume={volume_value:.0f} >= {volume_threshold:.0f})")
                
                # Volatility フィルター
                enable_volatility_filter = Config.get_enable_volatility_filter()
                volatility_threshold = Config.get_volatility_filter_threshold()
                if allow_entry and enable_volatility_filter:
                    volatility_value = self.price_data_management.get_latest_volatility()
                    if volatility_value > volatility_threshold:
                        self.logger.log(f"[フィルター:ENTRY] Volatility フィルター失敗 (Volatility={volatility_value:.2f} > {volatility_threshold:.2f})")
                        allow_entry = False
                    else:
                        self.logger.log(f"[フィルター:ENTRY] Volatility フィルター成功 (Volatility={volatility_value:.2f} <= {volatility_threshold:.2f})")

                if allow_entry:
                    side = desired_side
                    decision = "ENTRY"

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
                'entry_time': current_price.get('real_time_dt'),
                'strategy_result': strategy_result,  # Strategy結果も記録
            }
            
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
                        self.logger.log(f"[新指標] {strategy_name}: {signal}")
                        return {
                            'signal': normalized,
                            'raw_signal': signal,
                            'strategy': strategy_name.split('_')[1].upper(),
                            'confidence': 0.7 if normalized != 'NONE' else 0.0,
                            'details': result
                        }
            
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
        
        #-------------------------------------------------------
        # 優先度1：従来のストップロス判定
        #-------------------------------------------------------
        stop_price = self.risk_manager.get_stop_price()
        high_price = current_ohlcv.get('high_price', 0)
        low_price = current_ohlcv.get('low_price', 0)
        close_price = current_ohlcv.get('close_price', 0)
        
        if position_side == "BUY":
            if low_price <= stop_price:
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
            if high_price >= stop_price:
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
                'entry_price': self.portfolio.entry_price if hasattr(self.portfolio, 'entry_price') else 0,
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

