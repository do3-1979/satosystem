from enum import Enum


class Side(Enum):
    BUY = "BUY"
    SELL = "SELL"
    NONE = "NONE"


def normalize_side(value):
    """
    任意の表記 ('buy'/'sell'/'BUY'/'SELL'/Side) を内部表記 ('BUY'/'SELL'/'NONE') に正規化。
    """
    if isinstance(value, Side):
        return value.value
    if not isinstance(value, str):
        return Side.NONE.value
    v = value.strip().upper()
    if v in (Side.BUY.value, Side.SELL.value, Side.NONE.value):
        return v
    # 低リスクに NONE にフォールバック
    return Side.NONE.value


def to_exchange_side(value):
    """
    取引所API向けに 'buy'/'sell' の lower-case へ変換。
    内部 'NONE' はそのまま 'none' を返す（未使用想定）。
    """
    v = normalize_side(value)
    if v == Side.BUY.value:
        return "buy"
    if v == Side.SELL.value:
        return "sell"
    return "none"
