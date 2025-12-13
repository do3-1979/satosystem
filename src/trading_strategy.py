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
        self.initialize_trade_decision()
 
    def initialize_trade_decision(self):
        """
        trade_decision 辞書を初期化します。
        """
        self.trade_decision = {'decision': 'NONE', 'side': 'NONE', 'order_type': 'market'}
 
    def evaluate_entry(self):
        """
        エントリー条件を評価し、エントリーするかどうかを決定します。

        条件:
        1. ポジションを保有していない
        2. ドンチャンチャネルブレイクが発生
        3. PVOが閾値範囲内
        
        Phase 22a-22c: 複数のStrategyから最適なものを選択
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
        
        # エントリ・買い増し直後に離脱しないように
        if portfolio["quantity"] == 0:        
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

