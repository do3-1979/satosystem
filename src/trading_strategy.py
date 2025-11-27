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
        self.initialize_trade_decision()
        
        # 重複ログ抑制用フラグ
        self._add_limit_logged = False  # ADD上限到達ログ表示済みフラグ
        self._keltner_filter_counter = 0  # Keltnerフィルタログ出力カウンタ
        self._keltner_filter_interval = 600  # Keltnerフィルタログ出力間隔（600回に1回）
 
    def initialize_trade_decision(self):
        """
        trade_decision 辞書を初期化します。
        """
        self.trade_decision = {'decision': 'NONE', 'side': 'NONE', 'order_type': 'market'}
 
    def evaluate_entry(self):
        """
        エントリー条件を評価し、新規エントリーするかどうかを決定します。

        **重要**: このメソッドはポジション保有時は呼び出されません
        (make_trade_decision内で分岐制御)

        Phase B条件（新規エントリー）:
        1. ポジションを保有していない
        2. PVO > 閾値（出来高確認）
        3. Donchianブレイク発生
        
        (Keltnerフィルタ無効時):
        → ENTRY判定
        
        (Keltnerフィルタ有効時 - だまし回避):
        1. Keltner幅 >= 閾値（ボラティリティ確認 = トレンド強い）
        2. ドンチャンブレイク発生
        3. PVO > 閾値
        → ENTRY（レンジ相場のだましを除外）
        
        (レジーム検出有効時 - Phase 1):
        4. ボラティリティ比率とトレンド強度でレジーム判定
        → WEAK_TREND/SIDEWAYS判定でエントリー可否を調整
        """
        side = 'NONE'
        decision = 'NONE'

        signals = self.price_data_management.get_signals()

        # PVO有効範囲チェック
        if signals["pvo"]["signal"] == True:
            # ドンチャンチャネルブレイク発生
            if signals["donchian"]["signal"] == True:
                # Keltnerフィルタチェック（アクション1: トグル可能）
                keltner_enabled = Config.get_keltner_enabled()
                keltner_pass = True
                if keltner_enabled and "keltner" in signals:
                    # Keltnerボラティリティフィルタ
                    # signals["keltner"]["signal"] = volatility_ok (ボラ十分か)
                    volatility_ok = signals["keltner"]["signal"]
                    
                    if volatility_ok:
                        keltner_pass = True  # ボラティリティOK → ENTRY許可
                    else:
                        keltner_pass = False  # ボラティリティ不足 → だまし疑い
                        # Keltnerフィルタログは600回に1回出力（約10分に1回）
                        self._keltner_filter_counter += 1
                        if self._keltner_filter_counter >= self._keltner_filter_interval:
                            keltner_info = signals["keltner"].get("info", {})
                            self.logger.log(
                                f"[条件判定:ENTRY] Keltnerフィルタで除外 "
                                f"(volatility_ok={volatility_ok}, width={keltner_info.get('width', 0):.2f}, atr={keltner_info.get('atr', 0):.2f}) "
                                f"600回に1回表示"
                            )
                            self._keltner_filter_counter = 0

                # Phase B: Donchian + PVO + Keltner(オプション)
                if keltner_pass:
                    donchian_side = signals["donchian"]["side"]
                    if donchian_side == "BUY":
                        self.logger.log(f"[条件判定:ENTRY] BUY成立 (Donchian + PVO + Keltner={keltner_enabled})")
                        side = "BUY"
                        decision = "ENTRY"
                        # 新規エントリー時にフラグリセット
                        self._add_limit_logged = False
                    elif donchian_side == "SELL":
                        self.logger.log(f"[条件判定:ENTRY] SELL成立 (Donchian + PVO + Keltner={keltner_enabled})")
                        side = "SELL"
                        decision = "ENTRY"
                        # 新規エントリー時にフラグリセット
                        self._add_limit_logged = False

        self.trade_decision["side"] = side
        self.trade_decision["decision"] = decision
        
        # Phase 1: レジーム検出（アダプティブモード）
        regime_detection_enabled = bool(Config.config['Strategy'].getboolean('regime_detection_enabled', fallback=False))
        sideways_mode = Config.config['Strategy'].get('sideways_handling_mode', 'block')  # block or reduce
        
        if decision == "ENTRY" and regime_detection_enabled:
            regime_stats = signals.get("regime_stats", {})
            current_regime = regime_stats.get("current_regime", "NEUTRAL")
            regime_percentages = regime_stats.get("regime_percentages", {})
            self.logger.log(f"[レジーム検出] current_regime={current_regime}, mode={sideways_mode}")
            
            # Phase 2: リスク管理層にレジーム情報を渡す（段階的ポジションサイジング用）
            self.risk_manager.set_regime_info(regime_stats)
            
            # SIDEWAYS レジーム時の処理
            if current_regime == "SIDEWAYS":
                if sideways_mode == 'block':
                    # モード1: エントリーを完全にブロック
                    self.logger.log(f"[レジーム検出] SIDEWAYS → エントリーを回避")
                    decision = 'NONE'
                    side = 'NONE'
                    self.trade_decision["side"] = side
                    self.trade_decision["decision"] = decision
                elif sideways_mode == 'reduce':
                    # モード2: ポジションサイズを50%に削減して進める
                    self.logger.log(f"[レジーム検出] SIDEWAYS → ポジションサイズを50%に削減")
                    # リスク管理層でポジションサイズを調整するため、フラグを設定
                    if not hasattr(self, '_sideways_reduce_flag'):
                        self._sideways_reduce_flag = True
                    # このフラグを make_trade_decision で参照して位置サイズを調整
        else:
            # レジーム検出がOFFまたはENTRY以外の場合もレジーム情報を渡す
            regime_stats = signals.get("regime_stats", {})
            if regime_stats:
                self.risk_manager.set_regime_info(regime_stats)
            
        return
    
    def evaluate_add(self, price):
        """
        ピラミッディング（段階的ポジション増加）条件を評価します。
        
        **重要な役割**: 
        ENTRY後に再度ENTRYシグナルが発生した場合、
        ADDで対応する（単なる無視ではなく、体系的に処理）

        Phase C条件（ピラミッディング）:
        1. ポジションを保有している
        2. 追加回数が上限（entry_times）未満
        3. 価格が前回エントリー価格から add_range 以上変動
        
        **戦略目的**:
        - 保合い→トレンド転換時に段階的にポジションを増やす
        - 各追加は前回エントリーから一定変動後のみ許可
        - 回数上限で過度な積み上げを防止
        """
        side = 'NONE'
        decision = 'NONE'
  
        position_side = self.portfolio.get_position_side()
        
        if position_side != 'NONE':
            # Phase C: entry_times回上限チェック
            add_count = getattr(self.portfolio, 'add_count', 0)
            max_entries = Config.get_entry_times()
            if add_count >= max_entries:
                # 初回のみログ出力
                if not self._add_limit_logged:
                    self.logger.log(f"[条件判定:ADD] 上限到達 add_count={add_count}, max={max_entries}")
                    self._add_limit_logged = True
                return

            # 追加レンジ幅を取得
            range_val = self.risk_manager.get_add_range()
            last_entry_price = self.risk_manager.get_last_entry_price()
            
            # 価格がエントリー方向に基準レンジ分だけ進んだか判定する
            if position_side == "BUY" and (price - last_entry_price) > range_val:
                self.logger.log(f"[条件判定:ADD] 価格変動 {(price - last_entry_price):.2f} が変動幅 {range_val:.2f} を超過")
                side = "BUY"
                decision = "ADD"
                self.trade_decision["side"] = side
                self.trade_decision["decision"] = decision
                self.portfolio.add_count = add_count + 1  # Phase C: 回数カウント

            elif position_side == "SELL" and (last_entry_price - price) > range_val:
                self.logger.log(f"[条件判定:ADD] 価格変動 {(last_entry_price - price):.2f} が変動幅 {range_val:.2f} を超過")
                side = "SELL"
                decision = "ADD"
                self.trade_decision["side"] = side
                self.trade_decision["decision"] = decision
                self.portfolio.add_count = add_count + 1  # Phase C: 回数カウント

        return

    def evaluate_exit(self):
        """
        エグジット条件を評価し、ポジションをクローズするかどうかを決定します。
        
        Phase D条件:
        1. ストップロス判定（リアルタイム+2h確認のハイブリッド）
        2. 時間ベースEXIT: 最大保持バー数超過で強制決済
        3. (オプション) 部分利確: 利益率・保持バー数条件を満たしたら部分決済
        """
        side = 'NONE'
        decision = 'NONE'
        position_side = 'NONE'
        
        stop_price = self.risk_manager.get_stop_price()
        
        # リアルタイムデータを使用（ストップロス判定の高速化）
        current_price = self.price_data_management.get_ticker()
        price = self.price_data_management.get_latest_ohlcv()
        high_price = price['high_price']
        low_price = price['low_price']
        close_price = price['close_price']
        
        position_side = self.portfolio.get_position_side()
        
        # Phase C: 時間ベースEXIT (最大保持バー数チェック)
        max_hold_bars = Config.get_max_hold_bars()
        if max_hold_bars > 0 and position_side != 'NONE':
            # bot.pyのopen_tradeからバー数を取得する必要があるため、
            # portfolioに保存するか、別の方法で取得
            # 現状はbot.pyで管理されているため、ここでは判定できない
            # 代わりにbot.pyで判定する方式に変更
            pass
        
        # Phase D: 部分決済チェック (設定有効時)
        if position_side != 'NONE' and Config.get_partial_exit_enabled():
            avg_entry = self.portfolio.get_position_price()
            if avg_entry > 0:
                # 利益率計算
                if position_side == 'BUY':
                    profit_rate = (close_price - avg_entry) / avg_entry
                else:  # SELL
                    profit_rate = (avg_entry - close_price) / avg_entry
                # バー保持条件
                bars_min = Config.get_partial_exit_min_bars()
                # open_trade からバー数を取得可能なら利用（不足時は0）
                bars_held = getattr(self.portfolio, 'partial_exit_count', 0)  # 簡易: 既存partial回数を利用
                profit_thr = Config.get_partial_exit_profit_rate()
                if profit_rate >= profit_thr and bars_held >= bars_min:
                    exit_ratio = Config.get_partial_exit_ratio()
                    self.logger.log(f"[条件判定:PARTIAL_EXIT] 利益率 {profit_rate*100:.2f}% >= {profit_thr*100:.2f}% で部分決済 ratio={exit_ratio:.2f}")
                    side = 'SELL' if position_side == 'BUY' else 'BUY'
                    decision = 'PARTIAL_EXIT'
                    self.trade_decision['side'] = side
                    self.trade_decision['decision'] = decision
                    return

        #-------------------------------------------------------
        # 現在値とストップ値比較（リアルタイム判定）
        #-------------------------------------------------------
        # ストップロス判定: リアルタイム値（current_price）で判定
        # BUY: current_price <= stop でストップ成立（スリッページ -0.5%）
        # SELL: current_price >= stop でストップ成立（スリッページ +0.5%）
        executed_price = None
        if position_side == "BUY":
            if current_price <= stop_price:
                executed_price = stop_price * 0.995  # スリッページ考慮
                self.logger.log(f"[条件判定:EXIT] リアルタイム価格 {current_price:.2f} がストップ値 {stop_price:.2f} を割り込みました (実行価格 {executed_price:.2f})")
                side = "SELL"
                decision = "EXIT"
                self.trade_decision["side"] = side
                self.trade_decision["decision"] = decision
                self.trade_decision["exec_price"] = executed_price
                self._add_limit_logged = False
        elif position_side == "SELL":
            if current_price >= stop_price:
                executed_price = stop_price * 1.005  # スリッページ考慮
                self.logger.log(f"[条件判定:EXIT] リアルタイム価格 {current_price:.2f} がストップ値 {stop_price:.2f} を超過しました (実行価格 {executed_price:.2f})")
                side = "BUY"
                decision = "EXIT"
                self.trade_decision["side"] = side
                self.trade_decision["decision"] = decision
                self.trade_decision["exec_price"] = executed_price
                self._add_limit_logged = False

        return

    def make_trade_decision(self):
        """
        トレードの実行判断を行います。

        ロジック:
        1. ポジションなし → ENTRY判定のみ
        2. ポジションあり → ADD判定 → EXIT判定
        
        ※ ENTRY後に再度ENTRYシグナル発生 → ADD処理に転換
           (段階的ポジション増加 Phase C)
        """
        portfolio = self.portfolio.get_position_quantity()
        price = self.price_data_management.get_ticker()
        
        # ポジション有無で処理を分岐
        if portfolio["quantity"] == 0:        
            # ポジションなし: ENTRY判定のみ
            self.evaluate_entry()
        else:
            # ポジションあり: ADD → EXIT判定（優先度順）
            self.evaluate_add(price)
            self.evaluate_exit()
 
        return self.trade_decision
    
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

