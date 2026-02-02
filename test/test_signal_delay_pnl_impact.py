""" 
40j: 「バックテストがホット相当より古い足を参照し、売買が1本（以上）遅れる」場合の損益影響を検証する。

このスクリプトは“ホット経路の逐次更新”を厳密に再現するのではなく、
実データ（ohlcv_data/ohlcv_cache.db）の確定足系列から Donchian/PVO シグナルを計算し、
そのシグナルに対して「約定価格をlag本後ろにずらす」ことで遅延のP&L影響を直接測る。

注意:
- 本ファイルは検証用。ロジック本体は変更しない。
- 取引所手数料/スリッページ/ポジションサイズ/他フィルタは省略した簡易モデル。
"""

import os
import sys
import sqlite3
import copy
from dataclasses import dataclass
from datetime import datetime, timezone

# sys.path 設定
WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(WORKSPACE_ROOT, "src")
sys.path.insert(0, SRC_DIR)


def _dt(epoch: float) -> str:
    try:
        return datetime.fromtimestamp(float(epoch), tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return str(epoch)


def load_candles_from_sqlite(symbol: str, time_frame: int, start_epoch: int, end_epoch: int):
    db_path = os.path.join(WORKSPACE_ROOT, "ohlcv_data", "ohlcv_cache.db")
    if not os.path.exists(db_path):
        raise FileNotFoundError(db_path)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT close_time, open_price, high_price, low_price, close_price, volume
        FROM candles
        WHERE symbol = ? AND time_frame = ?
          AND close_time >= ? AND close_time <= ?
        ORDER BY close_time ASC
        """,
        (symbol, int(time_frame), float(start_epoch), float(end_epoch)),
    )

    rows = cur.fetchall()
    conn.close()

    candles = []
    for (close_time, open_price, high_price, low_price, close_price, volume) in rows:
        candles.append(
            {
                "close_time": int(close_time),
                "open_price": float(open_price),
                "high_price": float(high_price),
                "low_price": float(low_price),
                "close_price": float(close_price),
                "Volume": float(volume),
            }
        )

    return candles


@dataclass
class Step:
    close_time: int
    ticker: float
    signals: dict

def _calc_ema(term: int, data):
    """price_data_management.PriceDataManagement.__calc_ema と同等のロジック（検証用に複製）"""
    chk_1_sum = 0.0
    et_1 = 0.0
    result = []
    for p in data:
        i = len(result)
        if i <= (term - 1):
            chk_1_sum = sum(result)
            chk_1 = (float(chk_1_sum) + float(p)) / (i + 1)
            result += [chk_1]
        else:
            et_1 = result[-1]
            result += [float(et_1 + 2 / (term + 1) * (float(p) - et_1))]
    return float(result[-1]) if result else 0.0


def compute_signals_series(candles, *, donchian_buy_term: int, donchian_sell_term: int, pvo_s_term: int, pvo_l_term: int, pvo_threshold: float):
    """確定足系列だけで Donchian/PVO を計算し、各足(i)でのシグナルを返す。

    - Donchianは「直近N本（iは含めない）」の高値/安値を基準に、足iのcloseで判定。
    - PVOは「直近max(s,l)本（iは含めない）」のVolumeで算出。
    """

    series = []
    lookback = max(donchian_buy_term, donchian_sell_term, pvo_l_term, pvo_s_term) + 1
    for i in range(lookback, len(candles)):
        window = candles[i - donchian_buy_term : i]
        highest = max(x["high_price"] for x in window)
        lowest = min(x["low_price"] for x in candles[i - donchian_sell_term : i])

        price = float(candles[i]["close_price"])
        side = "None"
        if price > highest:
            side = "BUY"
        if price < lowest:
            side = "SELL"

        # PVO
        data_len = max(pvo_s_term, pvo_l_term)
        vols = [float(x["Volume"]) for x in candles[i - data_len : i]]
        short_ema = _calc_ema(pvo_s_term, vols)
        long_ema = _calc_ema(pvo_l_term, vols)
        pvo_value = ((short_ema - long_ema) * 100 / long_ema) if long_ema != 0 else 0.0
        pvo_signal = bool(pvo_value > float(pvo_threshold))

        series.append(
            Step(
                close_time=int(candles[i]["close_time"]),
                ticker=float(candles[i]["close_price"]),
                signals={
                    "donchian": {"signal": side != "None", "side": side, "info": {"highest": float(highest), "lowest": float(lowest)}},
                    "pvo": {"signal": pvo_signal, "side": None, "info": {"value": float(pvo_value)}},
                },
            )
        )
    return series


@dataclass
class TradeResult:
    total_pnl: float
    trades: int
    wins: int
    losses: int
    entries: int
    exits: int


def simulate_pnl(steps, *, use_pvo_filter: bool):
    """超シンプルな実行モデル（検証用）

    - donchian side が BUY ならロング、SELL ならショート
    - 同方向シグナルは無視
    - 反対シグナルでドテン（=決済して反転）
    - 約定価格はそのステップの ticker（= close_price相当）
    """

    position = 0  # 1: long, -1: short, 0: flat
    entry_price = None
    wins = losses = 0
    trades = 0
    entries = exits = 0
    total_pnl = 0.0

    def allowed_by_pvo(sig):
        if not use_pvo_filter:
            return True
        return bool(sig.get("pvo", {}).get("signal", False))

    for st in steps:
        s = st.signals
        dc = s.get("donchian", {})
        if not dc.get("signal", False):
            continue
        if not allowed_by_pvo(s):
            continue

        side = dc.get("side")
        if side not in ("BUY", "SELL"):
            continue

        target_pos = 1 if side == "BUY" else -1

        if position == 0:
            position = target_pos
            entry_price = st.ticker
            entries += 1
            continue

        if position == target_pos:
            continue

        # reverse (exit + entry)
        exits += 1
        pnl = (st.ticker - entry_price) * position
        total_pnl += pnl
        trades += 1
        if pnl >= 0:
            wins += 1
        else:
            losses += 1

        # new entry
        position = target_pos
        entry_price = st.ticker
        entries += 1

    # 最後はクローズせず（検証を単純化）
    return TradeResult(
        total_pnl=float(total_pnl),
        trades=int(trades),
        wins=int(wins),
        losses=int(losses),
        entries=int(entries),
        exits=int(exits),
    )


def simulate_pnl_with_execution_lag(steps, *, execution_lag_candles: int, use_pvo_filter: bool):
    """シグナルは足iで計算し、約定は足(i+lag)の価格で行う（=遅延の損益影響を評価）。"""
    lag = int(execution_lag_candles)
    if lag < 0:
        raise ValueError("execution_lag_candles must be >= 0")
    if lag == 0:
        return simulate_pnl(steps, use_pvo_filter=use_pvo_filter)

    position = 0
    entry_price = None
    wins = losses = 0
    trades = 0
    entries = exits = 0
    total_pnl = 0.0

    def allowed_by_pvo(sig):
        if not use_pvo_filter:
            return True
        return bool(sig.get("pvo", {}).get("signal", False))

    # 最終lag本は約定価格が取れないためスキップ
    for i in range(0, len(steps) - lag):
        st = steps[i]
        exec_price = float(steps[i + lag].ticker)

        s = st.signals
        dc = s.get("donchian", {})
        if not dc.get("signal", False):
            continue
        if not allowed_by_pvo(s):
            continue

        side = dc.get("side")
        if side not in ("BUY", "SELL"):
            continue
        target_pos = 1 if side == "BUY" else -1

        if position == 0:
            position = target_pos
            entry_price = exec_price
            entries += 1
            continue

        if position == target_pos:
            continue

        exits += 1
        pnl = (exec_price - entry_price) * position
        total_pnl += pnl
        trades += 1
        if pnl >= 0:
            wins += 1
        else:
            losses += 1

        position = target_pos
        entry_price = exec_price
        entries += 1

    return TradeResult(
        total_pnl=float(total_pnl),
        trades=int(trades),
        wins=int(wins),
        losses=int(losses),
        entries=int(entries),
        exits=int(exits),
    )


def main():
    # DB上は BTC/USDT:USDT, time_frame=240 のみ
    symbol = "BTC/USDT:USDT"
    tf = 240

    # 2025/Q4 を中心に検証（データが存在する想定）
    start_epoch = int(datetime(2025, 10, 1, 0, 0, tzinfo=timezone.utc).timestamp())
    end_epoch = int(datetime(2025, 12, 31, 23, 59, tzinfo=timezone.utc).timestamp())

    candles = load_candles_from_sqlite(symbol, tf, start_epoch, end_epoch)
    if len(candles) < 200:
        raise RuntimeError(f"candles too short: {len(candles)}")

    # 文字列は既存フォーマットに合わせる（Config.get_start_time は YYYY/MM/DD HH:MM）
    start_time_str = "2025/10/01 00:00"
    end_time_str = "2025/12/31 23:59"

    # まずは「確定足系列のみ」でシグナルを計算し、その上で『約定が1本遅れる』場合のP&L差を測る
    steps = compute_signals_series(
        candles,
        donchian_buy_term=30,
        donchian_sell_term=30,
        pvo_s_term=5,
        pvo_l_term=70,
        pvo_threshold=10,
    )

    # P&L（lag=0 vs lag=1）
    lag0_dc = simulate_pnl_with_execution_lag(steps, execution_lag_candles=0, use_pvo_filter=False)
    lag1_dc = simulate_pnl_with_execution_lag(steps, execution_lag_candles=1, use_pvo_filter=False)

    lag0_dcpvo = simulate_pnl_with_execution_lag(steps, execution_lag_candles=0, use_pvo_filter=True)
    lag1_dcpvo = simulate_pnl_with_execution_lag(steps, execution_lag_candles=1, use_pvo_filter=True)

    # 参考: 2〜3本遅延（以前の観測で -4h〜-12h のズレが出ていたため）
    lag2_dc = simulate_pnl_with_execution_lag(steps, execution_lag_candles=2, use_pvo_filter=False)
    lag3_dc = simulate_pnl_with_execution_lag(steps, execution_lag_candles=3, use_pvo_filter=False)
    lag2_dcpvo = simulate_pnl_with_execution_lag(steps, execution_lag_candles=2, use_pvo_filter=True)
    lag3_dcpvo = simulate_pnl_with_execution_lag(steps, execution_lag_candles=3, use_pvo_filter=True)

    print("=" * 80)
    print("📈 40j 検証: 1本遅延が損益に与える影響")
    print("=" * 80)
    print(f"dataset: {symbol} tf={tf}min candles={len(candles)} ({_dt(candles[0]['close_time'])} .. {_dt(candles[-1]['close_time'])})")
    print()

    print("🕒 遅延モデル")
    print("  - lag=0: シグナル足の終値で約定")
    print("  - lag=1: シグナル足の次の足の終値で約定（=1本遅延）")
    print()

    def show(label, a: TradeResult, b: TradeResult):
        print(label)
        print(f"  lag0: pnl={a.total_pnl:.2f} trades={a.trades} win={a.wins}/{a.trades} entries={a.entries} exits={a.exits}")
        print(f"  lag1: pnl={b.total_pnl:.2f} trades={b.trades} win={b.wins}/{b.trades} entries={b.entries} exits={b.exits}")
        print(f"  diff(lag1-lag0): pnl={b.total_pnl - a.total_pnl:.2f} trades={b.trades - a.trades}")
        print()

    show("🧪 Donchianのみ（フィルタなし）", lag0_dc, lag1_dc)
    print(f"  lag2: pnl={lag2_dc.total_pnl:.2f} trades={lag2_dc.trades} win={lag2_dc.wins}/{lag2_dc.trades}")
    print(f"  lag3: pnl={lag3_dc.total_pnl:.2f} trades={lag3_dc.trades} win={lag3_dc.wins}/{lag3_dc.trades}")
    print()
    show("🧪 Donchian + PVO（PVO閾値を適用）", lag0_dcpvo, lag1_dcpvo)
    print(f"  lag2: pnl={lag2_dcpvo.total_pnl:.2f} trades={lag2_dcpvo.trades} win={lag2_dcpvo.wins}/{lag2_dcpvo.trades}")
    print(f"  lag3: pnl={lag3_dcpvo.total_pnl:.2f} trades={lag3_dcpvo.trades} win={lag3_dcpvo.wins}/{lag3_dcpvo.trades}")
    print()


if __name__ == "__main__":
    main()
