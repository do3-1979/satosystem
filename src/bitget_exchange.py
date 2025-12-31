"""
BitgetExchange クラス (Exchange クラスを継承):

Bitget 取引所との連携を行うためのクラスです。Exchange クラスを継承し、Bitget 取引所に特有の設定や操作を追加しています。

Attributes:
    api_key (str): ユーザーごとの API キー
    api_secret (str): ユーザーごとの API シークレット
    passphrase (str): Bitget API用パスフレーズ
    exchange (ccxt.Exchange): ccxt ライブラリの Bitget 取引所インスタンス

Methods:
    get_account_balance(self):
        口座の残高情報を取得します。

    execute_order(self, symbol, side, quantity, price, order_type):
        注文を発行します。

Raises:
    ValueError: 無効な order_type が指定された場合に発生します。

Usage:
    # ユーザーごとの API キーと API シークレット、パスフレーズを設定
    api_key = 'YOUR_API_KEY'
    api_secret = 'YOUR_API_SECRET'
    passphrase = 'YOUR_PASSPHRASE'

    # BitgetExchange クラスを初期化
    exchange = BitgetExchange(api_key, api_secret, passphrase)

    # 口座残高情報を取得
    balance = exchange.get_account_balance()
    print("口座残高:", balance)

    # 注文を発行 (例: BTC/USDT マーケットで0.001BTC を買う)
    order_response = exchange.execute_order('buy', 0.001, None, 'market')
    print("注文結果:", order_response)
"""

import ccxt
import time
import random
from datetime import datetime
from datetime import timedelta
from config import Config
from logger import Logger
from exchange import Exchange

class BitgetExchange(Exchange):
    def __init__(self, api_key, api_secret, passphrase=None):
        """
        BitgetExchange クラスの初期化

        Args:
            api_key (str): ユーザーごとの API キー
            api_secret (str): ユーザーごとの API シークレット
            passphrase (str): Bitget API用パスフレーズ (必須)
        """
        super().__init__(api_key, api_secret)

        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.logger = Logger()
        
        # ダミー取引モード判定
        # back_test = 1 の場合はバックテストモード（ダミー価格・ダミー取引）
        # back_test = 0 の場合はホットテスト（実API価格を使用）
        # - hot_test_dummy_mode = 1: ペーパートレード（実API価格でダミー取引）
        # - hot_test_dummy_mode = 0: 本番取引（実API価格で実取引）
        back_test_mode = Config.get_back_test_mode()
        hot_test_dummy_mode = Config.get_hot_test_dummy_mode()
        
        # 価格データについて: バックテストのみ、fetch_latest_ohlcv/fetch_tickerがダミー値を返す
        # ホットテスト（ペーパートレード含む）は常に実API価格を使用
        self.is_dummy_mode = (back_test_mode == 1)  # バックテスト＝ダミー価格
        self.is_backtest_mode = (back_test_mode == 1)  # バックテストモードのみ
        self.is_papertrading_mode = (back_test_mode == 0 and hot_test_dummy_mode == 1)  # ペーパートレード識別
        self.is_live_trading_mode = (back_test_mode == 0 and hot_test_dummy_mode == 0)  # 本番取引識別
        self.dummy_balance = 100.0  # ダミー口座残高
        self.dummy_orders = {}  # ダミー注文履歴
        self.dummy_order_id = 0  # 注文ID カウンタ

        # 設定可能なパラメタ：1,3,5,15,30,60,120,240,360,720,D,M,W
        time_frame = Config.get_time_frame()
        if time_frame == 60:
            self.timeframe = '1h'
        elif time_frame == 120:
            self.timeframe = '2h'

        # マーケット変換 (Bitget用)
        market_type = Config.get_market()
        if market_type == 'BTC/USD':
            self.market = "BTC/USDT"  # BitgetはUSD建てがないのでUSDT建てに統一
        elif market_type == 'BTC/USDT':
            self.market = "BTC/USDT"
        elif market_type == 'ETH/USD':
            self.market = "ETH/USDT"  # BitgetはUSD建てがないのでUSDT建てに統一
        elif market_type == 'ETH/USDT':
            self.market = "ETH/USDT"

        # バックテスト時のみ exchange を初期化しない
        # ペーパートレード時は本番と同等の exchange を初期化
        if self.is_backtest_mode:
            # バックテストでもキャッシュからデータ取得のため exchange を初期化する
            # (実際の API 呼び出しは行わない、キャッシュ機構が優先的に使用される)
            self.exchange = ccxt.bitget({
                'apiKey': api_key if api_key != 'YOUR_API_KEY' else '',
                'secret': api_secret if api_secret != 'YOUR_API_SECRET' else '',
                'password': passphrase if passphrase else '',
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'swap',  # 先物取引
                }
            })
            self.logger.log(f"🎭 バックテストモード ON（balance: {self.dummy_balance} USD）")
        else:
            self.exchange = ccxt.bitget({
                'apiKey': api_key,
                'secret': api_secret,
                'password': passphrase,
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'swap',  # 先物取引
                }
            })
            if self.is_papertrading_mode:
                self.logger.log(f"🎭 ペーパートレード（ダミー取引）モード ON（balance: {self.dummy_balance} USD）")

    def get_account_balance(self):
        """
        口座の残高情報を取得します.

        Returns:
            dict: 口座の残高情報
        """
        # バックテスト・ペーパートレード時のダミー残高
        if self.is_backtest_mode or self.is_papertrading_mode:
            return {
                'USDT': {
                    'total': self.dummy_balance,
                    'used': 0,
                    'free': self.dummy_balance
                }
            }
        
        server_retry_wait = Config.get_server_retry_wait()
        err_occuerd = False
        
        while True:
            try:
                balance = self.exchange.fetchBalance()
                break
            except ccxt.BaseError as e:
                if err_occuerd == False:
                    self.logger.log_error(f"口座の残高情報エラー:{str(e)}")
                    err_occuerd = True
                time.sleep(server_retry_wait)

        if err_occuerd == True:
            self.logger.log_error("口座の残高情報エラー復帰")

        return balance
    
    def get_account_balance_total(self):
        """
        口座上の使用可能な証拠金残高を取得します.

        Returns:
            int: 口座上の使用可能な証拠金残高
        """
        # バックテスト・ペーパートレード時のダミー残高
        if self.is_backtest_mode or self.is_papertrading_mode:
            return self.dummy_balance
        
        server_retry_wait = Config.get_server_retry_wait()
        err_occuerd = False
        
        while True:
            try:
                balance = self.exchange.fetchBalance()
                break
            except ccxt.BaseError as e:
                if err_occuerd == False:
                    self.logger.log_error(f"口座の使用可能な証拠金残高エラー:{str(e)}")
                    err_occuerd = True
                time.sleep(server_retry_wait)

        if err_occuerd == True:
            self.logger.log_error("口座の使用可能な証拠金残高エラー復帰")

        # Bitget の場合は USDT 残高を取得
        usdt_balance = balance['USDT']['total']

        return usdt_balance

    def get_market_symbol(self) -> str:
        """
        現在の取引シンボルを返す（例: BTC/USDT, ETH/USDT）

        Returns:
            str: 取引シンボル
        """
        return self.market

    def execute_order(self, side, quantity, price, order_type):
        """
        注文を発行します.

        Args:
            side (str): 注文のタイプ ('buy' または 'sell')
            quantity (float): 注文数量
            price (float or None): 注文価格 (市場注文の場合は None)
            order_type (str): 注文タイプ ('limit' または 'market')

        Returns:
            dict: 注文の実行結果
        """
        # ダミーモード対応
        if self.is_dummy_mode:
            self.dummy_order_id += 1
            order_result = {
                'id': str(self.dummy_order_id),
                'symbol': self.market,
                'side': side,
                'type': order_type,
                'amount': quantity,
                'price': price if price else 0,
                'timestamp': int(time.time() * 1000),
                'status': 'closed',
                'info': {}
            }
            self.dummy_orders[str(self.dummy_order_id)] = order_result
            self.logger.log(f"🎭 ダミー注文: {side.upper()} {quantity} @ {price or 'MARKET'} (ID: {self.dummy_order_id})")
            return True
        
        server_retry_wait = Config.get_server_retry_wait()
        err_occuerd = False
        
        if order_type == 'limit':
            while True:
                try:
                    order = self.exchange.create_limit_order(
                        symbol=self.market,
                        side=side,
                        amount=quantity,
                        price=price
                    )
                    break
                except ccxt.BaseError as e:
                    if err_occuerd == False:
                        self.logger.log_error(f"指値注文エラー:{str(e)}")
                        err_occuerd = True
                    time.sleep(server_retry_wait)

            if err_occuerd == True:
                self.logger.log_error("指値注文エラー復帰")

        elif order_type == 'market':
            while True:
                try:
                    order = self.exchange.create_market_order(
                        symbol=self.market,
                        side=side,
                        amount=quantity
                    )
                    break
                except ccxt.BaseError as e:
                    if err_occuerd == False:
                        self.logger.log_error(f"成行注文エラー:{str(e)}")
                        err_occuerd = True
                    time.sleep(server_retry_wait)

            if err_occuerd == True:
                self.logger.log_error("成行注文エラー復帰")

        else:
            raise ValueError("Invalid order_type. Use 'limit' or 'market'.")

        # テストでは常に成功
        if Config.get_back_test_mode() == 1:
            response = True
        else:
            response = self.exchange.create_order(
                symbol=order['symbol'],
                side=order['side'],
                type=order['type'],
                quantity=order['amount'],
                price=order['price']
            )

        return response

    def _calculate_entry_price(self, side, current_price, slippage_percent):
        """
        エントリー指値価格を計算します（スリッページを考慮）
        
        Args:
            side (str): 'buy' または 'sell'
            current_price (float): 現在値
            slippage_percent (float): スリッページ率（%）
            
        Returns:
            float: 指値価格
        """
        if side == 'buy':
            # 買いは下に（安く買いたい）
            return current_price * (1 - slippage_percent / 100)
        else:
            # 売りは上に（高く売りたい）
            return current_price * (1 + slippage_percent / 100)

    def _calculate_exit_price(self, side, current_price, slippage_percent):
        """
        決済指値価格を計算します（少しでも良い値で）
        
        Args:
            side (str): 'buy' または 'sell' (現在のポジション側)
            current_price (float): 現在値
            slippage_percent (float): スリッページ率（%）
            
        Returns:
            float: 指値価格
        """
        if side == 'sell':
            # ショート決済（買い戻し）= 安く買い戻す
            return current_price * (1 - slippage_percent / 100)
        else:
            # ロング決済（売却）= 高く売る
            return current_price * (1 + slippage_percent / 100)

    def _execute_market_order(self, side, quantity):
        """
        成行注文を実行します（リトライなし）
        
        Args:
            side (str): 'buy' または 'sell'
            quantity (float): 数量
            
        Returns:
            dict or bool: 注文結果
        """
        try:
            order = self.exchange.create_market_order(
                symbol=self.market,
                side=side,
                amount=quantity,
                params={'timeout': 10000}
            )
            self.logger.log(f"✅ 成行注文成功: {side} {quantity}")
            return order
        except (ccxt.BaseError, TimeoutError) as e:
            self.logger.log_error(f"成行注文失敗: {str(e)}")
            raise

    def _execute_market_order_final(self, side, quantity):
        """
        最後のフォールバック成行注文を実行します
        
        Args:
            side (str): 'buy' または 'sell'
            quantity (float): 数量
            
        Returns:
            dict or bool: 注文結果
        """
        max_retries = 2
        for attempt in range(max_retries):
            try:
                order = self.exchange.create_market_order(
                    symbol=self.market,
                    side=side,
                    amount=quantity,
                    params={'timeout': 10000}
                )
                self.logger.log(f"✅ 最終成行成功 (試行 {attempt+1}/{max_retries}): {side} {quantity}")
                return order
            except (ccxt.BaseError, TimeoutError) as e:
                if attempt == max_retries - 1:
                    self.logger.log_error(f"❌ 最終成行失敗 (全リトライ完了): {str(e)}")
                    raise
                else:
                    self.logger.log(f"⚠️ 最終成行失敗 (試行 {attempt+1}/{max_retries}), リトライ中...")
                    time.sleep(1)

    def execute_entry_order(self, side, quantity, current_price):
        """
        エントリー注文を指値で実行します
        
        指値で約定を狙い、失敗時は動的にスリッページを拡大してリトライ。
        全て失敗時は成行で約定します。
        
        注意: 現時点では成行注文を優先的に使用しています。
        将来的には以下の指値リトライロジックを有効化できます。
        
        Args:
            side (str): 'buy' または 'sell'
            quantity (float): 注文数量
            current_price (float): 現在値
            
        Returns:
            dict or bool: 注文結果
        """
        # バックテスト時のみダミー注文
        if self.is_backtest_mode:
            return self._dummy_entry_order(side, quantity, current_price)
        
        # 現時点では成行注文を優先（早期約定を重視）
        try:
            return self._execute_market_order(side, quantity)
        except Exception as e:
            self.logger.log(f"⚠️ 成行失敗: {str(e)} → 指値にフォールバック")
            return self._execute_entry_order_with_limit_retry(side, quantity, current_price)
    
    def _execute_entry_order_with_limit_retry(self, side, quantity, current_price):
        """
        指値リトライロジック（約定確認とキャンセル処理付き）
        
        将来的にこのロジックを有効化することで、より低い手数料での約定を狙えます。
        
        Args:
            side (str): 'buy' または 'sell'
            quantity (float): 注文数量
            current_price (float): 現在値
            
        Returns:
            dict or bool: 注文結果
        """
        # パラメータ取得
        base_slippage = Config.get_entry_slippage()  # デフォルト 0.5%
        slippage_multiplier = Config.get_slippage_multiplier()  # デフォルト 1.5
        max_retries = Config.get_max_entry_retries()  # デフォルト 4
        
        previous_order_id = None
        
        # 指値注文をリトライ
        for attempt in range(max_retries):
            # 前の注文がまだ未決済ならキャンセル
            if previous_order_id:
                try:
                    self.exchange.cancel_order(previous_order_id, self.market)
                    self.logger.log(f"✅ 前の注文をキャンセル: {previous_order_id}")
                except Exception as e:
                    self.logger.log(f"⚠️ キャンセル失敗 (注文が既に約定した可能性): {str(e)}")
                time.sleep(0.5)
            
            adjusted_slippage = base_slippage * (slippage_multiplier ** attempt)
            limit_price = self._calculate_entry_price(side, current_price, adjusted_slippage)
            
            try:
                order = self.exchange.create_limit_order(
                    symbol=self.market,
                    side=side,
                    amount=quantity,
                    price=limit_price,
                    params={'timeout': 10000}
                )
                order_id = order.get('id')
                previous_order_id = order_id
                
                self.logger.log(f"📝 指値注文発注 (試行 {attempt+1}/{max_retries}): {side} {quantity} @ {limit_price:.2f} USD (注文ID: {order_id})")
                
                # 短時間で約定したか確認（500ms待機）
                time.sleep(0.5)
                
                try:
                    filled_order = self.exchange.fetch_order(order_id, self.market)
                    order_status = filled_order.get('status', 'unknown')
                    
                    if order_status == 'closed':
                        self.logger.log(f"✅ 指値約定成功 (試行 {attempt+1}/{max_retries}): {side} {quantity} @ {limit_price:.2f} USD")
                        return filled_order
                    else:
                        self.logger.log(f"⚠️ 指値未約定 (試行 {attempt+1}/{max_retries}), リトライ中...")
                        
                        
                except Exception as e:
                    self.logger.log(f"⚠️ 注文状態確認失敗: {str(e)}")
                    continue
                    
            except (ccxt.BaseError, TimeoutError) as e:
                self.logger.log(f"⚠️ 指値発注失敗 (試行 {attempt+1}/{max_retries}): {str(e)}")
                if attempt == max_retries - 1:
                    # 最後のリトライ失敗 → 成行へ
                    self.logger.log(f"⚠️ 指値全て失敗 → 成行で約定を試みる")
                    try:
                        return self._execute_market_order_final(side, quantity)
                    except Exception as e_market:
                        self.logger.log_error(f"❌ 成行も失敗: {str(e_market)}")
                        raise
                time.sleep(1)

    def execute_exit_order(self, side, quantity):
        """
        決済注文を成行で実行します
        
        現時点では成行注文を優先（早期約定を重視）。
        成行失敗時は指値でリトライします。
        
        Args:
            side (str): 'buy' または 'sell' (ポジション反対側)
            quantity (float): 注文数量
            
        Returns:
            dict or bool: 注文結果
        """
        # バックテスト時のみダミー取引
        if self.is_backtest_mode:
            return self._dummy_exit_order(side, quantity)
        
        # 現時点では成行注文を優先（早期約定を重視）
        try:
            order = self.exchange.create_market_order(
                symbol=self.market,
                side=side,
                amount=quantity,
                params={'timeout': 10000}
            )
            self.logger.log(f"✅ 決済成功 (成行): {side} {quantity}")
            return order
        except (ccxt.BaseError, TimeoutError) as e:
            self.logger.log(f"⚠️ 成行失敗: {str(e)} → 指値にフォールバック")
            return self._execute_exit_order_with_limit_retry(side, quantity)
    
    def _execute_exit_order_with_limit_retry(self, side, quantity):
        """
        決済注文の指値リトライロジック（約定確認とキャンセル処理付き）
        
        成行失敗時のフォールバック処理。
        
        Args:
            side (str): 'buy' または 'sell' (ポジション反対側)
            quantity (float): 注文数量
            
        Returns:
            dict or bool: 注文結果
        """
        max_exit_retries = Config.get_max_exit_retries()  # デフォルト 3
        current_price = self.fetch_ticker()
        previous_order_id = None
        
        # 指値のリトライ
        for attempt in range(max_exit_retries):
            # 前の注文がまだ未決済ならキャンセル
            if previous_order_id:
                try:
                    self.exchange.cancel_order(previous_order_id, self.market)
                    self.logger.log(f"✅ 前の決済注文をキャンセル: {previous_order_id}")
                except Exception as e:
                    self.logger.log(f"⚠️ キャンセル失敗 (注文が既に約定した可能性): {str(e)}")
                time.sleep(0.5)
            
            slippage = 0.1 * (attempt + 1)  # 0.1%, 0.2%, 0.3%
            limit_price = self._calculate_exit_price(side, current_price, slippage)
            
            try:
                order = self.exchange.create_limit_order(
                    symbol=self.market,
                    side=side,
                    amount=quantity,
                    price=limit_price,
                    params={'timeout': 10000}
                )
                order_id = order.get('id')
                previous_order_id = order_id
                
                self.logger.log(f"📝 決済指値注文発注 (試行 {attempt+1}/{max_exit_retries}): {side} {quantity} @ {limit_price:.2f} USD (注文ID: {order_id})")
                
                # 短時間で約定したか確認（500ms待機）
                time.sleep(0.5)
                
                try:
                    filled_order = self.exchange.fetch_order(order_id, self.market)
                    order_status = filled_order.get('status', 'unknown')
                    
                    if order_status == 'closed':
                        self.logger.log(f"✅ 決済指値約定成功 (試行 {attempt+1}/{max_exit_retries}): {side} {quantity} @ {limit_price:.2f} USD")
                        return filled_order
                    else:
                        self.logger.log(f"⚠️ 決済指値未約定 (試行 {attempt+1}/{max_exit_retries}), リトライ中...")
                        
                        
                except Exception as e:
                    self.logger.log(f"⚠️ 決済注文状態確認失敗: {str(e)}")
                    continue
                    
            except (ccxt.BaseError, TimeoutError) as e_limit:
                self.logger.log(f"⚠️ 決済指値失敗 (試行 {attempt+1}/{max_exit_retries}): {str(e_limit)}")
                if attempt == max_exit_retries - 1:
                    self.logger.log(f"⚠️ 決済指値全て失敗 → 成行で約定を試みる")
                    try:
                        return self._execute_market_order_final(side, quantity)
                    except Exception as e_market:
                        self.logger.log_error(f"❌ 決済成行も失敗: {str(e_market)}")
                        raise
                time.sleep(1)

    def _dummy_entry_order(self, side, quantity, current_price):
        """
        ダミーエントリー注文を実行します
        
        Args:
            side (str): 'buy' または 'sell'
            quantity (float): 注文数量
            current_price (float): 現在値
            
        Returns:
            bool: True（常に成功）
        """
        base_slippage = Config.get_entry_slippage() / 100
        entry_price = self._calculate_entry_price(side, current_price, base_slippage * 100)
        self.dummy_balance -= quantity * entry_price
        self.logger.log(f"🎭 ダミーエントリー: {side} {quantity} @ {entry_price:.2f} USD")
        return True

    def _dummy_exit_order(self, side, quantity):
        """
        ダミー決済注文を実行します
        
        Args:
            side (str): 'buy' または 'sell'
            quantity (float): 注文数量
            
        Returns:
            bool: True（常に成功）
        """
        # ダミー価格生成
        base_price = 100000
        exit_price = base_price + random.uniform(-500, 500)
        self.dummy_balance += quantity * exit_price
        self.logger.log(f"🎭 ダミー決済: {side} {quantity} @ {exit_price:.2f} USD")
        return True

    def get_nearest_epoch_time(self, end_epoch):
        """
        指定されたepoch時間に最も近い2時間足の時刻を取得

        Args:
            end_epoch (int): 終了epoch時間

        Returns:
            int: 最も近い2時間足のepoch時間
        """
        # 現在のローカル時刻を取得
        current_local_time = datetime.now()
        current_local_epoch = int(current_local_time.timestamp())
        
        # 古い時刻を採用
        if end_epoch < current_local_epoch:
            target_epoch = end_epoch
            target_time = datetime.fromtimestamp(target_epoch)
        else:
            target_epoch = current_local_epoch
            target_time = current_local_time
        
        # 指定された時刻リスト
        target_near_times = [1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23]
        
        # 現在の時刻から分と秒を0に設定
        target_time = target_time.replace(minute=0, second=0)
        
        # 最も近い時刻を選択
        year = target_time.year
        month = target_time.month
        
        for i in range(len(target_near_times)):
            if target_time.hour == 23:
                nearest_time = 23
                day = target_time.day
                break
            elif target_time.hour == 0:
                nearest_time = 23
                day = (target_time - timedelta(days=1)).day
                year = (target_time - timedelta(days=1)).year
                month = (target_time - timedelta(days=1)).month
                break
            else:
                if target_time.hour < target_near_times[i]:
                    nearest_time = target_near_times[i - 1]
                    day = target_time.day
                    break
        
        # 選択した時刻でepoch時間を作成
        epoch_time_str = datetime(year, month, day, nearest_time, 0, 0)
        epoch_time = int(epoch_time_str.timestamp())

        return epoch_time

    def fetch_ohlcv(self, start_epoch, end_epoch, time_frame):
        """
        取引情報を取得

        Returns:
            list: 価格データのリスト
        """
        err_occuerd = False
        ohlcv_data = []

        back_test_mode = Config.get_back_test_mode()
        server_retry_wait = Config.get_server_retry_wait()
        
        # 終端時間の計算
        end_epoch_fixed = self.get_nearest_epoch_time(end_epoch)
        total_progress = int((end_epoch_fixed - start_epoch) / 60) + 1  # 1分足なので1分ごとに進捗

        get_time = start_epoch
        while get_time < end_epoch_fixed:
            # 価格取得
            max_retries = 3
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    ohlcv = self.exchange.fetch_ohlcv(
                        symbol = self.market,
                        timeframe = self.timeframe,
                        since = int(get_time * 1000),
                        params={'timeout': 10000}
                    )
                    break
                except (ccxt.BaseError, TimeoutError) as e:
                    retry_count += 1
                    if retry_count >= max_retries:
                        self.logger.log_error(f"価格取得エラー(最大リトライ達成):{str(e)}")
                        err_occuerd = True
                    else:
                        if err_occuerd == False:
                            self.logger.log_error(f"価格取得エラー:{str(e)}")
                            err_occuerd = True
                        time.sleep(server_retry_wait)

            if retry_count >= max_retries:
                # 最大リトライに達した場合、スキップして次の時間へ
                get_time += time_frame * 60  # 次のタイムフレームへ移動
                continue

            if err_occuerd == True and retry_count < max_retries:
                self.logger.log_error("価格取得エラー復帰")
            # データ成型
            for i in range(len(ohlcv)):
                # 終端時間を超えないかぎり取得
                # volumeは0もありうるので除外する
                tmp_time = ohlcv[i][0] / 1000 
                if tmp_time < end_epoch_fixed:
                    ohlcv_data.append({ "close_time" : tmp_time,
                        "close_time_dt" : datetime.fromtimestamp(tmp_time).strftime('%Y/%m/%d %H:%M'),
                        "open_price" : ohlcv[i][1],
                        "high_price" : ohlcv[i][2],
                        "low_price" : ohlcv[i][3],
                        "close_price": ohlcv[i][4],
                        "Volume" : ohlcv[i][5]})
                else:
                    break
            get_time = tmp_time
            
            if back_test_mode == 1:
                progress = int((get_time - start_epoch) / 60)
                start_date = datetime.fromtimestamp(start_epoch).strftime('%Y/%m/%d %H:%M:%S')
                end_date = datetime.fromtimestamp(end_epoch_fixed).strftime('%Y/%m/%d %H:%M:%S')
                get_date = datetime.fromtimestamp(get_time).strftime('%Y/%m/%d %H:%M:%S')
                print(f"進捗：{progress}/{total_progress} 開始: {start_date} 終了：{end_date} 処理中: {get_date}", end='\r')

        if back_test_mode == 1:
            print("")
        # TODO 取得データ確認（抜け漏れ、ダブり）

        return ohlcv_data

    def fetch_latest_ohlcv(self, time_frame):
        """
        最新取引情報を取得

        Returns:
            list: 価格データのリスト
        """
        # バックテスト時のみダミー価格を返す
        # ホットテスト（ペーパートレード含む）は常に実API価格を使用
        if self.is_backtest_mode:
            # ダミー価格生成
            base_price = 100000  # ダミー基準価格
            random_price = base_price + random.uniform(-1000, 1000)
            tmp_time = int(time.time())
            return [{
                "close_time": tmp_time,
                "close_time_dt": datetime.fromtimestamp(tmp_time).strftime('%Y/%m/%d %H:%M'),
                "open_price": random_price - 100,
                "high_price": random_price + 200,
                "low_price": random_price - 200,
                "close_price": random_price,
                "Volume": random.uniform(1000, 10000)
            }]
        
        err_occuerd = False
        ohlcv_data = []

        server_retry_wait = Config.get_server_retry_wait()
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                ohlcv = self.exchange.fetch_ohlcv(
                    symbol = self.market,
                    timeframe = time_frame,
                    params={'timeout': 10000}
                )
                break
            except (ccxt.BaseError, TimeoutError) as e:
                retry_count += 1
                if retry_count >= max_retries:
                    self.logger.log_error(f"最新価格取得エラー(最大リトライ達成):{str(e)}")
                    err_occuerd = True
                else:
                    if err_occuerd == False:
                        self.logger.log_error(f"最新価格取得エラー:{str(e)}")
                        err_occuerd = True
                    time.sleep(server_retry_wait)

        if err_occuerd == True:
            self.logger.log_error("最新価格取得エラー復帰")
        
        latest_ohlcv = ohlcv[-1]
        tmp_time = latest_ohlcv[0] / 1000 
        ohlcv_data.append({ "close_time" : tmp_time,
            "close_time_dt" : datetime.fromtimestamp(tmp_time).strftime('%Y/%m/%d %H:%M'),
            "open_price" : latest_ohlcv[1],
            "high_price" : latest_ohlcv[2],
            "low_price" : latest_ohlcv[3],
            "close_price": latest_ohlcv[4],
            "Volume" : latest_ohlcv[5]})
        
        return ohlcv_data

    def fetch_ticker(self, symbol=None, params=None):
        """
        指定されたペアの最新の価格情報を取得します.

        Args:
            symbol (str): 取得するペアのシンボル (例: 'BTC/USDT'、デフォルトはconfig.iniの設定)
            params (dict): 追加パラメータ (オプション)

        Returns:
            float or dict: 引数なしの場合は価格（float）、引数ありの場合はticker辞書
        """
        # 引数なしで呼ばれた場合は価格のみ返す（後方互換性）
        return_price_only = (symbol is None and params is None)
        
        if params is None:
            params = {}
            
        # バックテスト時はダミーticker辞書を返す
        # ホットテスト（ペーパートレード含む）は常に実API価格を使用
        if self.is_backtest_mode:
            # ダミー価格生成（ticker辞書形式で返す）
            dummy_price = 100000 + random.uniform(-1000, 1000)
            ticker = {
                'symbol': 'BTC/USDT:USDT',
                'timestamp': int(time.time() * 1000),
                'datetime': datetime.now().isoformat(),
                'high': dummy_price * 1.01,
                'low': dummy_price * 0.99,
                'bid': dummy_price * 0.999,
                'ask': dummy_price * 1.001,
                'last': dummy_price,
                'close': dummy_price,
                'baseVolume': 1000,
                'quoteVolume': dummy_price * 1000,
                'info': {}
            }
            return dummy_price if return_price_only else ticker
        
        # シンボルが指定されていない場合はconfigから取得
        if symbol is None:
            # マーケット変換
            market_type = Config.get_market()
            if market_type == 'BTC/USD':
                symbol = "BTC/USDT"  # BitgetはUSD建てがない
            elif market_type == 'BTC/USDT':
                symbol = "BTC/USDT"
            elif market_type == 'ETH/USD':
                symbol = "ETH/USDT"  # BitgetはUSD建てがない
            elif market_type == 'ETH/USDT':
                symbol = "ETH/USDT"
            else:
                symbol = "BTC/USDT"  # デフォルト
        
        max_retries = 3
        retry_count = 0
        
        # タイムアウト設定
        if 'timeout' not in params:
            params['timeout'] = 10000
        
        while retry_count < max_retries:
            try:
                ticker = self.exchange.fetch_ticker(symbol, params=params)
                # 引数なしの場合は価格のみ、ありの場合はticker辞書全体を返す
                return ticker['last'] if return_price_only else ticker
            except (ccxt.BaseError, TimeoutError) as e:
                retry_count += 1
                if retry_count >= max_retries:
                    self.logger.log_error(f"Ticker取得エラー(最大リトライ達成):{str(e)}")
                    raise
                else:
                    self.logger.log(f"⚠️ Ticker取得リトライ ({retry_count}/{max_retries}): {str(e)}")
                    time.sleep(1)
    
    def fetch_open_orders(self, symbol=None, params=None):
        """
        未決済注文を取得します.

        Args:
            symbol (str): 取得するペアのシンボル (例: 'BTC/USDT:USDT'、オプション)
            params (dict): 追加パラメータ (オプション)

        Returns:
            list: 未決済注文のリスト
        """
        if params is None:
            params = {}
            
        # バックテスト・ペーパートレード時はダミー注文を返す
        if self.is_backtest_mode or self.is_papertrading_mode:
            return [order for order in self.dummy_orders.values() if order['status'] == 'open']
        
        # シンボルが指定されていない場合はconfigから取得
        if symbol is None:
            market_type = Config.get_market()
            if market_type == 'BTC/USD':
                symbol = "BTC/USDT:USDT"
            elif market_type == 'BTC/USDT':
                symbol = "BTC/USDT:USDT"
            elif market_type == 'ETH/USD':
                symbol = "ETH/USDT:USDT"
            elif market_type == 'ETH/USDT':
                symbol = "ETH/USDT:USDT"
            else:
                symbol = "BTC/USDT:USDT"
        
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                orders = self.exchange.fetch_open_orders(symbol, params=params)
                return orders
            except (ccxt.BaseError, TimeoutError) as e:
                retry_count += 1
                if retry_count >= max_retries:
                    self.logger.log_error(f"未決済注文取得エラー(最大リトライ達成):{str(e)}")
                    raise
                else:
                    self.logger.log(f"⚠️ 未決済注文取得リトライ ({retry_count}/{max_retries}): {str(e)}")
                    time.sleep(1)
    
    def create_limit_order(self, symbol, side, amount, price, params=None):
        """
        指値注文を作成します.

        Args:
            symbol (str): 取引ペアのシンボル (例: 'BTC/USDT:USDT')
            side (str): 'buy' または 'sell'
            amount (float): 注文数量
            price (float): 指値価格
            params (dict): 追加パラメータ (オプション)

        Returns:
            dict: 注文情報
        """
        if params is None:
            params = {}
            
        # バックテスト・ペーパートレード時はダミー注文を作成
        if self.is_backtest_mode or self.is_papertrading_mode:
            self.dummy_order_id += 1
            order = {
                'id': f'dummy_{self.dummy_order_id}',
                'symbol': symbol,
                'type': 'limit',
                'side': side,
                'amount': amount,
                'price': price,
                'status': 'open',
                'timestamp': int(time.time() * 1000),
                'datetime': datetime.now().isoformat(),
                'filled': 0,
                'remaining': amount,
                'cost': 0,
                'fee': {'cost': 0, 'currency': 'USDT'},
                'info': {}
            }
            self.dummy_orders[order['id']] = order
            self.logger.log(f"🎭 ダミー注文作成: ID={order['id']}, {side.upper()}, 数量={amount}, 価格={price:.2f}")
            return order
        
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                order = self.exchange.create_limit_order(symbol, side, amount, price, params=params)
                self.logger.log(f"✅ 注文作成成功: ID={order['id']}, {side.upper()}, 数量={amount}, 価格={price:.2f}")
                return order
            except (ccxt.BaseError, TimeoutError) as e:
                retry_count += 1
                if retry_count >= max_retries:
                    self.logger.log_error(f"注文作成エラー(最大リトライ達成):{str(e)}")
                    raise
                else:
                    self.logger.log(f"⚠️ 注文作成リトライ ({retry_count}/{max_retries}): {str(e)}")
                    time.sleep(1)
    
    def cancel_order(self, order_id, symbol=None, params=None):
        """
        注文をキャンセルします.

        Args:
            order_id (str): キャンセルする注文のID
            symbol (str): 取引ペアのシンボル (例: 'BTC/USDT:USDT', オプション)
            params (dict): 追加パラメータ (オプション)

        Returns:
            dict: キャンセル結果
        """
        if params is None:
            params = {}
            
        # バックテスト・ペーパートレード時はダミー注文をキャンセル
        if self.is_backtest_mode or self.is_papertrading_mode:
            if order_id in self.dummy_orders:
                self.dummy_orders[order_id]['status'] = 'canceled'
                self.logger.log(f"🎭 ダミー注文キャンセル: ID={order_id}")
                return self.dummy_orders[order_id]
            else:
                raise Exception(f"Order {order_id} not found")
        
        # シンボルが指定されていない場合はconfigから取得
        if symbol is None:
            market_type = Config.get_market()
            if market_type == 'BTC/USD':
                symbol = "BTC/USDT:USDT"
            elif market_type == 'BTC/USDT':
                symbol = "BTC/USDT:USDT"
            elif market_type == 'ETH/USD':
                symbol = "ETH/USDT:USDT"
            elif market_type == 'ETH/USDT':
                symbol = "ETH/USDT:USDT"
            else:
                symbol = "BTC/USDT:USDT"
        
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                result = self.exchange.cancel_order(order_id, symbol, params=params)
                self.logger.log(f"✅ 注文キャンセル成功: ID={order_id}")
                return result
            except (ccxt.BaseError, TimeoutError) as e:
                retry_count += 1
                if retry_count >= max_retries:
                    self.logger.log_error(f"注文キャンセルエラー(最大リトライ達成):{str(e)}")
                    raise
                else:
                    self.logger.log(f"⚠️ 注文キャンセルリトライ ({retry_count}/{max_retries}): {str(e)}")
                    time.sleep(1)


if __name__ == "__main__":
    # BitgetExchange クラスを初期化
    exchange = BitgetExchange(Config.get_api_key(), Config.get_api_secret(), Config.get_api_passphrase())

    print("----------")
    print("口座残高情報を取得")
    print("----------")
    start_balance_time = time.time()
    balance = exchange.get_account_balance()
    end_balance_time = time.time()
    # 統合口座のused、free、total情報を表示
    print(f"balance : {balance}")
    usdt_balance = balance['USDT']
    print("USDT Used: ", usdt_balance['used'])
    print("USDT Free: ", usdt_balance['free'])
    print("USDT Total: ", usdt_balance['total'])
    
    print("----------")
    print("口座残高総合取得")
    print("----------")
    balance = exchange.get_account_balance_total()
    print(f"balance : {balance}")

    print(f"{Config.get_market()} の最新価格情報")
    price = exchange.fetch_ticker()
    print(f"価格: {price}")
    print("----------")

    print("最新価格データ 2h を取得")
    print("----------")
    start_price_time = time.time()
    ohlcv_data = exchange.fetch_latest_ohlcv(120)
    end_price_time = time.time()
    entry = ohlcv_data[0]
    print(f"生データ: {ohlcv_data}")
    print(f"時刻: {entry['close_time_dt']}")
    print(f"開始価格: {entry['open_price']}")
    print(f"最高価格: {entry['high_price']}")
    print(f"最低価格: {entry['low_price']}")
    print(f"終値: {entry['close_price']}")
    print(f"出来高: {entry['Volume']}")
    print("----------")

    print("口座残高情報取得にかかった時間: {:.2f}秒".format(end_balance_time - start_balance_time))
    print("価格データ取得にかかった時間: {:.2f}秒".format(end_price_time - start_price_time))
