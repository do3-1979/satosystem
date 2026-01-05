"""
Config クラス:

ボットの設定情報を格納するクラスです。APIキー、トレードの間隔、戦略の選択などの設定を保持します。

このサンプルコードでは、Config クラスが設定ファイル（config.ini など）から
APIキー、APIシークレット、および他の設定情報を読み込むメソッドを提供しています。
設定情報の読み込みには Python の標準ライブラリである configparser を使用しています。
"""

import configparser
from datetime import datetime
import pytz
import os
import json

class Config:
    config = configparser.ConfigParser()
    # config.ini のパスを動的に決定（スクリプトのディレクトリを基準）
    config_path = os.path.join(os.path.dirname(__file__), 'config.ini')
    config.read(config_path, encoding="utf-8_sig")
    
    # .api_key ファイルからAPIキーを読み込む
    api_keys = {}
    api_key_path = os.path.join(os.path.dirname(__file__), '.api_key')
    if os.path.exists(api_key_path):
        try:
            with open(api_key_path, 'r', encoding='utf-8') as f:
                api_keys = json.load(f)
        except Exception as e:
            print(f"⚠️  .api_key ファイルの読み込みエラー: {e}")
            api_keys = {}

    @classmethod
    def get_api_key(cls):
        """
        APIキーを取得します (後方互換性のため、Bitgetキーを返す).
        .api_key から優先的に読み込み、なければ config.ini から読み込む.

        Returns:
            str: APIキー
        """
        if cls.api_keys and 'api_bitget_key' in cls.api_keys:
            return cls.api_keys['api_bitget_key']
        return cls.config['API'].get('api_bitget_key', cls.config['API'].get('api_key', ''))

    @classmethod
    def get_api_secret(cls):
        """
        APIシークレットを取得します (後方互換性のため、Bitgetシークレットを返す).
        .api_key から優先的に読み込み、なければ config.ini から読み込む.

        Returns:
            str: APIシークレット
        """
        if cls.api_keys and 'api_bitget_secret' in cls.api_keys:
            return cls.api_keys['api_bitget_secret']
        return cls.config['API'].get('api_bitget_secret', cls.config['API'].get('api_secret', ''))

    @classmethod
    def get_api_passphrase(cls):
        """
        APIパスフレーズを取得します (Bitget用).
        .api_key から優先的に読み込み、なければ config.ini から読み込む.

        Returns:
            str: APIパスフレーズ
        """
        if cls.api_keys and 'api_bitget_passphrase' in cls.api_keys:
            return cls.api_keys['api_bitget_passphrase']
        return cls.config['API'].get('api_bitget_passphrase', cls.config['API'].get('api_passphrase', ''))
    
    @classmethod
    def get_bitget_api_key(cls):
        """
        Bitget APIキーを取得します.
        .api_key から優先的に読み込み、なければ config.ini から読み込む.

        Returns:
            str: Bitget APIキー
        """
        if cls.api_keys and 'api_bitget_key' in cls.api_keys:
            return cls.api_keys['api_bitget_key']
        return cls.config['API'].get('api_bitget_key', '')
    
    @classmethod
    def get_bitget_api_secret(cls):
        """
        Bitget APIシークレットを取得します.
        .api_key から優先的に読み込み、なければ config.ini から読み込む.

        Returns:
            str: Bitget APIシークレット
        """
        if cls.api_keys and 'api_bitget_secret' in cls.api_keys:
            return cls.api_keys['api_bitget_secret']
        return cls.config['API'].get('api_bitget_secret', '')
    
    @classmethod
    def get_bitget_api_passphrase(cls):
        """
        Bitget APIパスフレーズを取得します.
        .api_key から優先的に読み込み、なければ config.ini から読み込む.

        Returns:
            str: Bitget APIパスフレーズ
        """
        if cls.api_keys and 'api_bitget_passphrase' in cls.api_keys:
            return cls.api_keys['api_bitget_passphrase']
        return cls.config['API'].get('api_bitget_passphrase', '')
    
    @classmethod
    def get_bybit_api_key(cls):
        """
        Bybit APIキーを取得します.
        .api_key から優先的に読み込み、なければ config.ini から読み込む.

        Returns:
            str: Bybit APIキー
        """
        if cls.api_keys and 'api_bybit_key' in cls.api_keys:
            return cls.api_keys['api_bybit_key']
        return cls.config['API'].get('api_bybit_key', '')
    
    @classmethod
    def get_bybit_api_secret(cls):
        """
        Bybit APIシークレットを取得します.
        .api_key から優先的に読み込み、なければ config.ini から読み込む.

        Returns:
            str: Bybit APIシークレット
        """
        if cls.api_keys and 'api_bybit_secret' in cls.api_keys:
            return cls.api_keys['api_bybit_secret']
        return cls.config['API'].get('api_bybit_secret', '')

    @classmethod
    def get_exchange(cls):
        """
        使用する取引所を取得します (後方互換性のため).

        Returns:
            str: 取引所名 ('bybit' または 'bitget')
        """
        return cls.config['API'].get('exchange_trade', cls.config['API'].get('exchange', 'bybit'))
    
    @classmethod
    def get_exchange_data(cls):
        """
        価格データ取得用の取引所を取得します.

        Returns:
            str: 取引所名 ('bybit' または 'bitget')
        """
        return cls.config['API'].get('exchange_data', 'bybit')
    
    @classmethod
    def get_exchange_trade(cls):
        """
        注文執行用の取引所を取得します.

        Returns:
            str: 取引所名 ('bybit' または 'bitget')
        """
        return cls.config['API'].get('exchange_trade', 'bitget')

    @classmethod
    def get_risk_percentage(cls):
        """
        リスク割合を取得します.

        Returns:
            float: リスク割合
        """
        return float(cls.config['RiskManagement']['risk_percentage'])
    
    @classmethod
    def get_account_balance(cls):
        """
        アカウント残高を取得します.

        Returns:
            float: アカウント残高
        """
        return float(cls.config['RiskManagement']['account_balance'])
    
    @classmethod
    def get_leverage(cls):
        """
        レバレッジを取得します.

        Returns:
            int: レバレッジ
        """
        return int(cls.config['RiskManagement']['leverage'])

    @classmethod
    def get_entry_times(cls):
        """
        エントリー回数を取得します.

        Returns:
            int: エントリー回数
        """
        return int(cls.config['RiskManagement']['entry_times'])

    @classmethod
    def get_entry_range(cls):
        """
        エントリー範囲を取得します.

        Returns:
            float: エントリー範囲
        """
        return float(cls.config['RiskManagement']['entry_range'])

    @classmethod
    def get_stop_range(cls):
        """
        ストップ範囲を取得します.

        Returns:
            float: ストップ範囲
        """
        return float(cls.config['RiskManagement']['stop_range'])

    @classmethod
    def get_stop_AF(cls):
        """
        ストップアンドリバースファクター（AF）を取得します.

        Returns:
            float: ストップアンドリバースファクター（AF）
        """
        return float(cls.config['RiskManagement']['stop_AF'])

    @classmethod
    def get_stop_AF_add(cls):
        """
        ストップアンドリバースファクター（AF）の追加値を取得します.

        Returns:
            float: ストップアンドリバースファクター（AF）の追加値
        """
        return float(cls.config['RiskManagement']['stop_AF_add'])

    @classmethod
    def get_stop_AF_max(cls):
        """
        ストップアンドリバースファクター（AF）の最大値を取得します.

        Returns:
            float: ストップアンドリバースファクター（AF）の最大値
        """
        return float(cls.config['RiskManagement']['stop_AF_max'])

    @classmethod
    def get_surge_follow_price_ratio(cls):
        """
        ストップ近傍のレートを取得します.

        Returns:
            float: ストップ近傍のレート
        """
        return float(cls.config['RiskManagement']['surge_follow_price_ratio'])

    @classmethod
    def get_psar_time_frame(cls):
        """
        PSAR用の時間軸を取得します.

        Returns:
            int: 時間軸[分]
        """
        return int(cls.config['RiskManagement']['psar_time_frame'])

    @classmethod
    def get_market(cls):
        """
        マーケットを取得します.

        Returns:
            str: マーケット情報
        """
        return str(cls.config['Market']['market'])

    @classmethod
    def get_market_unit_pair(cls):
        """
        マーケットからユニットペアを取得します.

        Returns:
            str: マーケット情報から取得したユニットペア
        """
        market_info = cls.config['Market']['market']
        unit_pair = market_info[:3]  # マーケット情報から先頭の3文字を取得
        return unit_pair

    @classmethod
    def get_time_frame(cls):
        """
        時間軸を取得します.

        Returns:
            int: 時間軸[分]
        """
        return int(cls.config['Market']['time_frame'])

    @classmethod
    def get_start_time(cls):
        """
        開始時刻を取得します.

        Returns:
            str: 開始時刻 (フォーマット: "YYYY/M/D H:mm")
        """
        return cls.config['Period']['start_time']

    @classmethod
    def get_end_time(cls):
        """
        終了時刻を取得します.

        Returns:
            str: 終了時刻 (フォーマット: "YYYY/M/D H:mm")
        """
        return cls.config['Period']['end_time']

    @classmethod
    def get_start_epoch(cls):
        """
        開始時刻をepoch時間で取得します.

        Returns:
            datetime: 開始時刻 (epoch)
        """
        start_time_str = cls.config['Period']['start_time']
        start_time = datetime.strptime(start_time_str, "%Y/%m/%d %H:%M")
        #start_time = pytz.timezone('epoch').localize(start_time)
        start_unix = int(start_time.timestamp())
        return start_unix

    @classmethod
    def get_end_epoch(cls):
        """
        終了時刻をepoch時間で取得します.

        Returns:
            datetime: 終了時刻 (epoch)
        """
        end_unix = 9999999999
        end_time_str = cls.config['Period']['end_time']

        if (end_time_str == "None") or (end_time_str == ""):
            pass
        else:
            end_time = datetime.strptime(end_time_str, "%Y/%m/%d %H:%M")
            #end_time = pytz.timezone('epoch').localize(end_time)
            end_unix = int(end_time.timestamp())

        return end_unix
    
    @classmethod
    def get_volatility_term(cls):
        """
        ボラティリティ期間を取得します.

        Returns:
            int: ボラティリティ期間
        """
        return int(cls.config['Strategy']['volatility_term'])

    @classmethod
    def get_donchian_buy_term(cls):
        """
        ドンチャン買い期間を取得します.

        Returns:
            int: ドンチャン買い期間
        """
        return int(cls.config['Strategy']['donchian_buy_term'])

    @classmethod
    def get_donchian_sell_term(cls):
        """
        ドンチャン売り期間を取得します.

        Returns:
            int: ドンチャン売り期間
        """
        return int(cls.config['Strategy']['donchian_sell_term'])

    @classmethod
    def get_pvo_s_term(cls):
        """
        PVO短期間を取得します.

        Returns:
            int: PVO短期間
        """
        return int(cls.config['Strategy']['pvo_s_term'])

    @classmethod
    def get_pvo_l_term(cls):
        """
        PVO長期間を取得します.

        Returns:
            int: PVO長期間
        """
        return int(cls.config['Strategy']['pvo_l_term'])

    @classmethod
    def get_pvo_threshold(cls):
        """
        PVO閾値を取得します.

        Returns:
            int: PVO閾値
        """
        return int(cls.config['Strategy']['pvo_threshold'])

    @classmethod
    def get_volatility_max(cls):
        """
        Volatility上限を取得します.

        Returns:
            int: Volatility上限（デフォルト: 9999）
        """
        return int(cls.config['Strategy'].get('volatility_max', 9999))

    @classmethod
    def get_lot_limit_lower(cls):
        """
        最小ロット数計算倍率を取得します.

        Returns:
            float: 最小ロット数計算倍率
        """
        return float(cls.config['Potfolio']['lot_limit_lower'])

    @classmethod
    def get_balance_tether_limit(cls):
        """
        最小証拠金を取得します.

        Returns:
            float: 最小証拠金
        """
        return float(cls.config['Potfolio']['balance_tether_limit'])

    @classmethod
    def get_server_retry_wait(cls):
        """
        サーバーのリトライ待機時間を取得します.

        Returns:
            int: リトライ待機時間 (秒)
        """
        return int(cls.config['Setting']['server_retry_wait'])

    @classmethod
    def get_bot_operation_cycle(cls):
        """
        ボットの動作サイクル時間を取得します.

        Returns:
            int: ボットの動作サイクル時間 (秒)
        """
        cyctime = int(cls.config['Setting']['bot_operation_cycle'])
        
        return cyctime
    
    @classmethod
    def get_test_initial_max_term(cls):
        """
        テストに必要な初期化期間を取得します
        PSAR の正しいトレンド形成のため、十分な履歴データが必要

        Returns:
            int: 期間
        """
        v_term = int(cls.config['Strategy']['volatility_term'])
        d_b_term = int(cls.config['Strategy']['donchian_buy_term'])
        d_s_term = int(cls.config['Strategy']['donchian_sell_term'])
        pv_s_term = int(cls.config['Strategy']['pvo_s_term'])
        
        # PSAR用初期化期間を取得（設定があれば）
        psar_term = None
        try:
            psar_term = int(cls.config['Strategy']['psar_lookback_term'])
        except (KeyError, ValueError):
            psar_term = None
        
        # PSAR期間がある場合はそれを優先、なければ他の指標から最大値を取得
        if psar_term is not None:
            max_term = max(v_term, d_b_term, d_s_term, pv_s_term, psar_term)
        else:
            max_term = max(v_term, d_b_term, d_s_term, pv_s_term)

        return max_term

    @classmethod
    def get_log_file_name(cls):
        """
        """
        return cls.config['Log']['log_file']
    
    @classmethod
    def get_log_dir_name(cls):
        """
        """
        return cls.config['Log']['log_directory']
    
    @classmethod
    def get_back_test_mode(cls):
        """
        バックテストモードを取得します.

        Returns:
            int: 1=バックテスト, 0=ホットテスト
        """
        return int(cls.config['Backtest']['back_test'])

    @classmethod
    def get_hot_test_dummy_mode(cls):
        """
        ホットテスト時の取引モードを取得します.

        Returns:
            int: 1=ダミー取引（ペーパーテスト）, 0=本番取引
        """
        return int(cls.config['Backtest']['hot_test_dummy_mode'])

    @classmethod
    def get_enable_pvo_filter(cls):
        """
        PVOフィルターの有効/無効を取得します.

        Returns:
            int: 1=有効, 0=無効
        """
        try:
            return int(cls.config['EntryFilters']['enable_pvo_filter'])
        except (KeyError, ValueError):
            return 0  # デフォルト: 無効

    @classmethod
    def get_enable_adx_filter(cls):
        """
        ADXフィルターの有効/無効を取得します.

        Returns:
            int: 1=有効, 0=無効
        """
        try:
            return int(cls.config['EntryFilters']['enable_adx_filter'])
        except (KeyError, ValueError):
            return 0  # デフォルト: 無効

    @classmethod
    def get_adx_filter_threshold(cls):
        """
        ADXフィルターの最小閾値を取得します.

        Returns:
            int: ADX最小値
        """
        try:
            return int(cls.config['EntryFilters']['adx_filter_threshold'])
        except (KeyError, ValueError):
            return 70  # デフォルト: 70

    @classmethod
    def get_enable_volume_filter(cls):
        """
        Volumeフィルターの有効/無効を取得します.

        Returns:
            int: 1=有効, 0=無効
        """
        try:
            return int(cls.config['EntryFilters']['enable_volume_filter'])
        except (KeyError, ValueError):
            return 0  # デフォルト: 無効

    @classmethod
    def get_volume_filter_threshold(cls):
        """
        Volumeフィルターの最小閾値を取得します.

        Returns:
            float: 出来高最小値
        """
        try:
            return float(cls.config['EntryFilters']['volume_filter_threshold'])
        except (KeyError, ValueError):
            return 15000  # デフォルト: 15000

    @classmethod
    def get_enable_volatility_filter(cls):
        """
        Volatilityフィルターの有効/無効を取得します.

        Returns:
            int: 1=有効, 0=無効
        """
        try:
            return int(cls.config['EntryFilters']['enable_volatility_filter'])
        except (KeyError, ValueError):
            return 0  # デフォルト: 無効

    @classmethod
    def get_volatility_filter_threshold(cls):
        """
        Volatilityフィルターの最大閾値を取得します.

        Returns:
            float: Volatility最大値
        """
        try:
            return float(cls.config['EntryFilters']['volatility_filter_threshold'])
        except (KeyError, ValueError):
            return 1000  # デフォルト: 1000

    # ==================== Seasonality セクション ====================

    @classmethod
    def get_enable_seasonality_based_positioning(cls):
        """
        季節性ベースのロット削減機能の有効/無効を取得します.

        Returns:
            int: 1=有効, 0=無効
        """
        try:
            return int(cls.config['Seasonality']['enable_seasonality_based_positioning'])
        except (KeyError, ValueError):
            return 0  # デフォルト: 無効

    @classmethod
    def get_seasonality_loss_quarter_multiplier(cls):
        """
        ボックス相場シーズンのロット削減倍率を取得します.

        Returns:
            float: 倍率（0.7 = 30%削減）
        """
        try:
            return float(cls.config['Seasonality']['seasonality_loss_quarter_multiplier'])
        except (KeyError, ValueError):
            return 0.7  # デフォルト: 70% (30%削減)

    @classmethod
    def get_seasonality_profit_quarter_multiplier(cls):
        """
        トレンド相場シーズンの倍率を取得します.

        Returns:
            float: 倍率（1.0 = 削減なし）
        """
        try:
            return float(cls.config['Seasonality']['seasonality_profit_quarter_multiplier'])
        except (KeyError, ValueError):
            return 1.0  # デフォルト: 100% (削減なし)

    # ==================== MarketRegime セクション ====================

    @classmethod
    def get_enable_market_regime_detection(cls):
        """
        市場体制判定機能の有効/無効を取得します.

        Returns:
            int: 1=有効, 0=無効
        """
        try:
            return int(cls.config['MarketRegime']['enable_market_regime_detection'])
        except (KeyError, ValueError):
            return 0  # デフォルト: 無効

    @classmethod
    def get_atr_range_threshold_lower(cls):
        """
        ATR比較のボックス判定下限倍率を取得します.

        Returns:
            float: 倍率（デフォルト0.75）
        """
        try:
            return float(cls.config['MarketRegime']['atr_range_threshold_lower'])
        except (KeyError, ValueError):
            return 0.75

    @classmethod
    def get_atr_range_threshold_upper(cls):
        """
        ATR比較のトレンド判定上限倍率を取得します.

        Returns:
            float: 倍率（デフォルト1.25）
        """
        try:
            return float(cls.config['MarketRegime']['atr_range_threshold_upper'])
        except (KeyError, ValueError):
            return 1.25

    @classmethod
    def get_atr_period(cls):
        """
        ATR計算期間を取得します.

        Returns:
            int: 期間（デフォルト14）
        """
        try:
            return int(cls.config['MarketRegime']['atr_period'])
        except (KeyError, ValueError):
            return 14

    @classmethod
    def get_atr_ma_period(cls):
        """
        ATR移動平均期間を取得します.

        Returns:
            int: 期間（デフォルト28）
        """
        try:
            return int(cls.config['MarketRegime']['atr_ma_period'])
        except (KeyError, ValueError):
            return 28

    @classmethod
    def get_swing_lookback_period(cls):
        """
        スイング判定の遡り期間を取得します.

        Returns:
            int: 期間（デフォルト20）
        """
        try:
            return int(cls.config['MarketRegime']['swing_lookback_period'])
        except (KeyError, ValueError):
            return 20

    @classmethod
    def get_enable_entry_condition_strictness_on_range(cls):
        """
        ボックス相場時のエントリー条件強化の有効/無効を取得します.

        Returns:
            int: 1=有効, 0=無効
        """
        try:
            return int(cls.config['MarketRegime']['enable_entry_condition_strictness_on_range'])
        except (KeyError, ValueError):
            return 1  # デフォルト: 有効

    @classmethod
    def get_ranging_position_size_multiplier(cls):
        """
        ボックス相場時のポジションサイズ倍率を取得します.

        Returns:
            float: 倍率（0.7 = 30%削減）
        """
        try:
            return float(cls.config['MarketRegime']['ranging_position_size_multiplier'])
        except (KeyError, ValueError):
            return 0.7  # デフォルト: 30%削減（70%のサイズ）

    @classmethod
    def get_entry_slippage(cls):
        """
        エントリー時の基本スリッページを取得します（%）.

        Returns:
            float: スリッページ（%）
        """
        try:
            return float(cls.config['OrderExecution']['entry_slippage'])
        except (KeyError, ValueError):
            return 0.5  # デフォルト値

    @classmethod
    def get_slippage_multiplier(cls):
        """
        スリッページ増加の倍率を取得します.

        Returns:
            float: 倍率
        """
        try:
            return float(cls.config['OrderExecution']['slippage_multiplier'])
        except (KeyError, ValueError):
            return 1.5  # デフォルト値

    @classmethod
    def get_max_entry_retries(cls):
        """
        エントリー時の最大リトライ回数を取得します.

        Returns:
            int: リトライ回数
        """
        try:
            return int(cls.config['OrderExecution']['max_entry_retries'])
        except (KeyError, ValueError):
            return 4  # デフォルト値

    @classmethod
    def get_max_exit_retries(cls):
        """
        決済時の最大リトライ回数を取得します.

        Returns:
            int: リトライ回数
        """
        try:
            return int(cls.config['OrderExecution']['max_exit_retries'])
        except (KeyError, ValueError):
            return 3  # デフォルト値

    @classmethod
    def get_order_timeout(cls):
        """
        注文タイムアウト時間を取得します（秒）.

        Returns:
            int: タイムアウト時間（秒）
        """
        try:
            return int(cls.config['OrderExecution']['order_timeout'])
        except (KeyError, ValueError):
            return 30  # デフォルト値

    @classmethod
    def is_dummy_mode(cls):
        """
        現在がダミーモード（ペーパートレード）かを判定します.

        ダミーモード判定ロジック：
        - back_test = 1 → ダミーモード（バックテスト）
        - back_test = 0 かつ hot_test_dummy_mode = 1 → ダミーモード（ペーパートレード）
        - back_test = 0 かつ hot_test_dummy_mode = 0 → 本番取引

        Returns:
            bool: True = ダミーモード、False = 本番取引
        """
        try:
            back_test_mode = int(cls.config['Backtest']['back_test'])
            hot_test_dummy_mode = int(cls.config['Backtest']['hot_test_dummy_mode'])
            
            # バックテスト時は常にダミーモード
            if back_test_mode == 1:
                return True
            # バックテスト以外でもペーパートレードはダミーモード
            if back_test_mode == 0 and hot_test_dummy_mode == 1:
                return True
            # それ以外は本番取引
            return False
        except (KeyError, ValueError):
            # デフォルトは安全のためダミーモード
            return True

    def __str__(self):
        """
        コンフィグ内容を可読性よく文字列として表現するメソッドです。
        """
        config_str = f"\nRisk Percentage: {self.get_risk_percentage()}\r\n"
        config_str += f"Account Balance: {self.get_account_balance()}\r\n"
        config_str += f"Leverage: {self.get_leverage()}\r\n"
        config_str += f"Entry Times: {self.get_entry_times()}\r\n"
        config_str += f"Entry Range: {self.get_entry_range()}\r\n"
        config_str += f"Stop Range: {self.get_stop_range()}\r\n"
        config_str += f"Stop AF: {self.get_stop_AF()}\r\n"
        config_str += f"Stop AF Add: {self.get_stop_AF_add()}\r\n"
        config_str += f"Stop AF Max: {self.get_stop_AF_max()}\r\n"
        config_str += f"surge follow price ratio: {self.get_surge_follow_price_ratio()}\r\n"
        config_str += f"Lot Limit Lower: {self.get_lot_limit_lower()}\r\n"
        config_str += f"Balance Tether Limit: {self.get_balance_tether_limit()}\r\n"
        config_str += f"Psar Time Frame: {self.get_psar_time_frame()}\r\n"
        config_str += f"Market: {self.get_market()}\r\n"
        config_str += f"Market Unit: {self.get_market_unit_pair()}\r\n"
        config_str += f"Time Frame: {self.get_time_frame()}\r\n"
        config_str += f"Start Time: {self.get_start_time()}\r\n"
        config_str += f"End Time: {self.get_end_time()}\r\n"
        config_str += f"Start Time (epoch): {self.get_start_epoch()}\r\n"
        config_str += f"End Time (epoch): {self.get_end_epoch()}\r\n"
        config_str += f"Volatility Term: {self.get_volatility_term()}\r\n"
        config_str += f"Donchian Buy Term: {self.get_donchian_buy_term()}\r\n"
        config_str += f"Donchian Sell Term: {self.get_donchian_sell_term()}\r\n"
        config_str += f"PVO Short Term: {self.get_pvo_s_term()}\r\n"
        config_str += f"PVO Long Term: {self.get_pvo_l_term()}\r\n"
        config_str += f"PVO Threshold: {self.get_pvo_threshold()}\r\n"
        config_str += f"Server Retry Wait: {self.get_server_retry_wait()}\r\n"
        config_str += f"Bot Operation Cycle: {self.get_bot_operation_cycle()}\r\n"
        config_str += f"Back Test Mode: {self.get_back_test_mode()}"

        return config_str

    def to_dict(self):
        """
        Convert Config parameters to a dictionary.
        """
        return {
            "Risk Percentage": self.get_risk_percentage(),
            "Account Balance": self.get_account_balance(),
            "Leverage": self.get_leverage(),
            "Entry Times": self.get_entry_times(),
            "Entry Range": self.get_entry_range(),
            "Stop Range": self.get_stop_range(),
            "Stop AF": self.get_stop_AF(),
            "Stop AF Add": self.get_stop_AF_add(),
            "Stop AF Max": self.get_stop_AF_max(),
            "surge follow price ratio": self.get_surge_follow_price_ratio(),
            "Lot Limit Lower": self.get_lot_limit_lower(),
            "Balance Tether Limit": self.get_balance_tether_limit(),
            "Psar Time Frame": self.get_psar_time_frame(),
            "Market": self.get_market(),
            "Market Unit": self.get_market_unit_pair(),
            "Time Frame": self.get_time_frame(),
            "Start Time": self.get_start_time(),
            "End Time": self.get_end_time(),
            "Start Time (epoch)": self.get_start_epoch(),
            "End Time (epoch)": self.get_end_epoch(),
            "Volatility Term": self.get_volatility_term(),
            "Donchian Buy Term": self.get_donchian_buy_term(),
            "Donchian Sell Term": self.get_donchian_sell_term(),
            "PVO Short Term": self.get_pvo_s_term(),
            "PVO Long Term": self.get_pvo_l_term(),
            "PVO Threshold": self.get_pvo_threshold(),
            "Server Retry Wait": self.get_server_retry_wait(),
            "Bot Operation Cycle": self.get_bot_operation_cycle(),
            "Back Test Mode": self.get_back_test_mode()
        }

    @classmethod
    def get_config_bool(cls, section, key, default=False):
        """
        コンフィグから論理値を取得します.

        Args:
            section (str): セクション名
            key (str): キー名
            default (bool): デフォルト値

        Returns:
            bool: 設定値
        """
        try:
            value = cls.config.get(section, key)
            return value.lower() in ('1', 'true', 'yes', 'on')
        except:
            return default

    @classmethod
    def get_config_int(cls, section, key, default=0):
        """
        コンフィグから整数値を取得します.

        Args:
            section (str): セクション名
            key (str): キー名
            default (int): デフォルト値

        Returns:
            int: 設定値
        """
        try:
            return int(cls.config.get(section, key))
        except:
            return default

    @classmethod
    def get_config_float(cls, section, key, default=0.0):
        """
        コンフィグから浮動小数点数を取得します.

        Args:
            section (str): セクション名
            key (str): キー名
            default (float): デフォルト値

        Returns:
            float: 設定値
        """
        try:
            return float(cls.config.get(section, key))
        except:
            return default

if __name__ == "__main__":
    # APIキーとAPIシークレットを取得
    api_key = Config.get_api_key()
    api_secret = Config.get_api_secret()

    print(f'API Key: {api_key}')
    print(f'API Secret: {api_secret}')

    # 他の設定情報を取得
    risk_percentage = Config.get_risk_percentage()
    account_balance = Config.get_account_balance()
    leverage = Config.get_leverage()
    entry_times = Config.get_entry_times()
    entry_range = Config.get_entry_range()
    stop_range = Config.get_stop_range()
    stop_AF = Config.get_stop_AF()
    stop_AF_add = Config.get_stop_AF_add()
    stop_AF_max = Config.get_stop_AF_max()
    surge_follow_price_ratio = Config.get_surge_follow_price_ratio()
    lot_limit_lower = Config.get_lot_limit_lower()
    balance_tether_limit = Config.get_balance_tether_limit()
    psar_time_frame = Config.get_psar_time_frame()
    print(f'Risk Percentage: {risk_percentage}')
    print(f'Account Balance: {account_balance}')
    print(f'Leverage: {leverage}')
    print(f'Entry Times: {entry_times}')
    print(f'Entry Range: {entry_range}')
    print(f'Stop Range: {stop_range}')
    print(f'Stop AF: {stop_AF}')
    print(f'Stop AF Add: {stop_AF_add}')
    print(f'Stop AF Max: {stop_AF_max}')
    print(f'surge follow price ratio: {surge_follow_price_ratio}')
    print(f'Lot Limit Lower: {lot_limit_lower}')
    print(f'Balance Thther Limit: {balance_tether_limit}')
    print(f'Psar Time Frame: {psar_time_frame}')

    # Market セクションの情報を取得
    market = Config.get_market()
    time_frame = Config.get_time_frame()
    market_unit_pair = Config.get_market_unit_pair()
    print(f'Market: {market}')
    print(f'Market Unit: {market_unit_pair}')
    print(f'Time Frame: {time_frame}')

    # Period セクションの情報を取得
    start_time = Config.get_start_time()
    end_time = Config.get_end_time()
    print(f'Start Time: {start_time}')
    print(f'End Time: {end_time}')

    # Period セクションの情報を取得 (epoch時間)
    start_epoch = Config.get_start_epoch()
    end_epoch = Config.get_end_epoch()
    print(f'Start Time (epoch): {start_epoch}')
    print(f'End Time (epoch): {end_epoch}')

    # Strategy セクションの情報を取得
    volatility_term = Config.get_volatility_term()
    donchian_buy_term = Config.get_donchian_buy_term()
    donchian_sell_term = Config.get_donchian_sell_term()
    pvo_s_term = Config.get_pvo_s_term()
    pvo_l_term = Config.get_pvo_l_term()
    pvo_threshold = Config.get_pvo_threshold()
    max_term = Config.get_test_initial_max_term()
    print(f'Volatility Term: {volatility_term}')
    print(f'Donchian Buy Term: {donchian_buy_term}')
    print(f'Donchian Sell Term: {donchian_sell_term}')
    print(f'PVO Short Term: {pvo_s_term}')
    print(f'PVO Long Term: {pvo_l_term}')
    print(f'PVO Threshold: {pvo_threshold}')
    print(f'[Test] Max_term: {max_term}')

    # Setting セクションの情報を取得
    server_retry_wait = Config.get_server_retry_wait()
    bot_operation_cycle = Config.get_bot_operation_cycle()
    print(f'Server Retry Wait: {server_retry_wait}')
    print(f'Bot Operation Cycle: {bot_operation_cycle}')

    # コンフィグ一覧表示
    config_instance = Config()
    print("----------")
    print(str(config_instance))
