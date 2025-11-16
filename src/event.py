"""
Event クラス:

イベント駆動型の設計をサポートするためのクラスです。新しい取引データが入力されたときやトレードが実行されたときにイベントを生成し、
それに基づいてボットが反応することができます。

このサンプルコードでは、Event クラスがイベントのタイプと関連データを保持するために使用されます。
イベントのタイプは文字列で指定され、関連データは任意の形式で設定できます。
このクラスを使用することで、トレーディングボット内でさまざまなイベントを生成し、処理できます。

トレーディングボット内でイベントを作成し、他のコンポーネントに通知するために使用できます。
たとえば、エントリーシグナルが発生したときにエントリーイベントを生成し、ポジション管理モジュールに通知するなどの用途に利用できます。
"""
from typing import Callable, Dict, List, Any


class Event:
    def __init__(self, event_type, data=None):
        """
        イベントクラスを初期化
        :param event_type: イベントのタイプ（例: "ENTRY_SIGNAL", "EXIT_SIGNAL", "ORDER_EXECUTED"）
        :param data: イベントに関連するデータ
        """
        self.event_type = event_type
        self.data = data


class EventType:
    TICK = "TICK"
    ENTRY_SIGNAL = "ENTRY_SIGNAL"
    ADD_SIGNAL = "ADD_SIGNAL"
    EXIT_SIGNAL = "EXIT_SIGNAL"
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    ORDER_EXECUTED = "ORDER_EXECUTED"
    PORTFOLIO_UPDATED = "PORTFOLIO_UPDATED"
    RISK_UPDATED = "RISK_UPDATED"
    LOOP_ERROR = "LOOP_ERROR"


class EventBus:
    """
    シンプルなPub/Sub。副作用を避けるため同期呼び出しのみ。
    """
    def __init__(self):
        self._handlers: Dict[str, List[Callable[[Event], None]]] = {}

    def subscribe(self, event_type: str, handler: Callable[[Event], None]):
        self._handlers.setdefault(event_type, []).append(handler)

    def unsubscribe(self, event_type: str, handler: Callable[[Event], None]):
        if event_type in self._handlers:
            self._handlers[event_type] = [h for h in self._handlers[event_type] if h != handler]
            if not self._handlers[event_type]:
                del self._handlers[event_type]

    def emit(self, event_type: str, data: Any = None):
        if event_type not in self._handlers:
            return
        ev = Event(event_type, data)
        for h in list(self._handlers[event_type]):
            try:
                h(ev)
            except Exception:
                # サイレントに失敗を飲み込む（本体の挙動に影響しないため）
                pass

if __name__ == "__main__":
    # イベントの作成
    entry_signal_event = Event("ENTRY_SIGNAL", {"symbol": "BTC/USD", "price": 10000})
    exit_signal_event = Event("EXIT_SIGNAL", {"symbol": "BTC/USD", "price": 10500})
    order_executed_event = Event("ORDER_EXECUTED", {"order_id": "12345", "filled_quantity": 5})

    # イベントの表示
    print(f"Entry Signal Event: {entry_signal_event.event_type}")
    print(f"Entry Signal Data: {entry_signal_event.data}")

    print(f"Exit Signal Event: {exit_signal_event.event_type}")
    print(f"Exit Signal Data: {exit_signal_event.data}")

    print(f"Order Executed Event: {order_executed_event.event_type}")
    print(f"Order Executed Data: {order_executed_event.data}")
