"""exchange.py

NOTE:
- このモジュールは抽象的な Exchange 基底クラスを提供します。
- ccxt はここでは直接使用していないため、未導入環境でも import 可能なように任意依存として扱います。
- Task 40g: API障害時のリトライロジック追加
"""

import time
from functools import wraps
from typing import Callable, Any
from config import Config
from logger import Logger

try:
    import ccxt  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    ccxt = None


def retry_with_backoff(max_attempts: int = None, initial_delay: float = None, 
                      backoff_multiplier: float = None, max_delay: float = None):
    """
    API呼び出しに対する指数バックオフリトライデコレーター
    
    Args:
        max_attempts: 最大リトライ回数（Noneの場合はconfig.iniから取得）
        initial_delay: 初期待機時間（秒、Noneの場合はconfig.iniから取得）
        backoff_multiplier: バックオフ倍率（Noneの場合はconfig.iniから取得）
        max_delay: 最大待機時間（秒、Noneの場合はconfig.iniから取得）
    
    Returns:
        デコレーターされた関数
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # config.iniから設定を取得（デフォルト値）
            _max_attempts = max_attempts if max_attempts is not None else Config.get_api_retry_max_attempts()
            _initial_delay = initial_delay if initial_delay is not None else Config.get_api_retry_initial_delay()
            _backoff_multiplier = backoff_multiplier if backoff_multiplier is not None else Config.get_api_retry_backoff_multiplier()
            _max_delay = max_delay if max_delay is not None else Config.get_api_retry_max_delay()
            
            logger = Logger()
            delay = _initial_delay
            last_exception = None
            
            for attempt in range(_max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    # 最後の試行の場合は例外を投げる
                    if attempt == _max_attempts - 1:
                        logger.log(f"❌ API呼び出し失敗（{_max_attempts}回リトライ後）: {func.__name__}, エラー: {str(e)}")
                        raise
                    
                    # リトライ可能なエラーか判定
                    if not _is_retryable_error(e):
                        logger.log(f"⚠️  リトライ不可能なエラー: {func.__name__}, エラー: {str(e)}")
                        raise
                    
                    # リトライログ
                    logger.log(f"⚠️  API呼び出し失敗、{delay:.1f}秒後にリトライ（{attempt + 1}/{_max_attempts}）: {func.__name__}, エラー: {str(e)}")
                    
                    # 待機
                    time.sleep(delay)
                    
                    # 次の待機時間を計算（指数バックオフ）
                    delay = min(delay * _backoff_multiplier, _max_delay)
            
            # ここには到達しないはずだが、念のため
            raise last_exception
        
        return wrapper
    return decorator


def _is_retryable_error(error: Exception) -> bool:
    """
    エラーがリトライ可能かどうかを判定
    
    Args:
        error: 発生した例外
    
    Returns:
        bool: リトライ可能ならTrue
    """
    # リトライ可能なエラーの種類
    retryable_errors = [
        'NetworkError',
        'RequestTimeout',
        'ExchangeNotAvailable',
        'DDoSProtection',
        'RateLimitExceeded',
        'ConnectionError',
        'Timeout'
    ]

    # リトライ不可なエラー（残高不足・無効注文など、リトライしても無意味）
    non_retryable_errors = [
        'InsufficientFunds',
        'InvalidOrder',
        'BadSymbol',
        'AuthenticationError',
        'PermissionDenied',
        'AccountSuspended',
        'OrderNotFound',
        'CancelPending',
    ]
    
    error_name = type(error).__name__
    error_message = str(error).lower()

    # リトライ不可エラーを先にチェック
    if any(nr in error_name for nr in non_retryable_errors):
        return False
    # Bitget error code 43012 (Insufficient balance) をメッセージで検知
    if '43012' in error_message or 'insufficient balance' in error_message:
        return False
    
    # エラー名でチェック
    if any(retryable in error_name for retryable in retryable_errors):
        return True
    
    # エラーメッセージでチェック
    retryable_keywords = ['timeout', 'network', 'connection', 'unavailable', 'rate limit']
    if any(keyword in error_message for keyword in retryable_keywords):
        return True
    
    return False


class Exchange:
    """
    Exchangeクラス:

    このクラスは仮想通貨の取引所との通信を担当します。APIキーの認証、注文の発行、口座残高の取得などの機能を提供します。
    各取引所に対するサブクラスを作成して、取引所固有の実装を処理できます。たとえば、BinanceExchange、CoinbaseExchangeなどのサブクラスを考えることができます。
    """
    def __init__(self, api_key, api_secret):
        """
        Exchangeクラスを初期化します。

        Args:
            api_key (str): 取引所のAPIキー
            api_secret (str): 取引所のAPIシークレット
        """
        self.api_key = api_key
        self.api_secret = api_secret

    def get_account_balance(self):
        """
        口座の残高情報を取得します。
        
        Returns:
            dict: 口座の残高情報
        """
        raise NotImplementedError("Subclasses must implement this method.")

    def execute_order(self, symbol, side, quantity, price, order_type):
        """
        注文を発行します。

        Args:
            symbol (str): トレード対象の通貨ペア（例: 'BTC/USD'）
            side (str): 注文の種類（'buy'または'sell'）
            quantity (float): 注文数量
            price (float or None): 注文価格（市場価格注文の場合はNone）
            order_type (str): 注文のタイプ（'limit'または'market'）

        Returns:
            dict: 注文の実行結果
        """
        raise NotImplementedError("Subclasses must implement this method.")
