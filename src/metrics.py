"""Metrics calculation utilities for backtest performance evaluation.

Functions:
    compute_metrics(pnl_history, trade_results) -> dict

Notes:
- pnl_history: list of cumulative PnL values (can be negative). Assumed chronological.
- trade_results: list of booleans for each closed trade (True=win, False=loss).
- Sharpe ratio is computed on incremental returns (diffs of cumulative PnL). Risk-free rate assumed 0.
- Max Drawdown computed from cumulative PnL peak to trough.
"""
from __future__ import annotations
from typing import List, Dict
import math


def _incremental_returns(pnl_history: List[float]) -> List[float]:
    if len(pnl_history) < 2:
        return []
    returns = []
    prev = pnl_history[0]
    for v in pnl_history[1:]:
        returns.append(v - prev)
        prev = v
    return returns


def _sharpe(returns: List[float]) -> float:
    if len(returns) < 2:
        return 0.0
    mean_ret = sum(returns) / len(returns)
    # population std dev not appropriate; use sample
    variance = sum((r - mean_ret) ** 2 for r in returns) / (len(returns) - 1)
    std_dev = math.sqrt(variance) if variance > 0 else 0.0
    if std_dev == 0:
        return 0.0
    # scale by sqrt(n) (no time normalization since interval uniform per loop iteration)
    return mean_ret / std_dev * math.sqrt(len(returns))


def _max_drawdown(pnl_history: List[float], initial_equity: float = 100.0) -> tuple:
    """最大ドローダウンとドローダウン率を計算する。
    累積PnLのみが与えられる前提のため、初期証拠金(initial_equity)を仮定して
    有効ピーク資産 = peak_at_max_dd + initial_equity を分母に用いる。

    極小のピーク値(例: 数ドル)で大きな下落が起きると従来実装では >100% が発生。
    これは初期資本を考慮していないためで、その補正を行う。
    Returns: (max_drawdown_value, max_drawdown_rate_percent, trough_index, peak_index, effective_peak_equity)
    """
    if not pnl_history:
        return 0.0, 0.0, -1, -1, initial_equity

    peak = pnl_history[0]
    max_dd = 0.0
    peak_at_max_dd = peak
    peak_idx = 0
    trough_idx = 0

    for i, v in enumerate(pnl_history):
        if v > peak:
            peak = v
            peak_idx = i
        dd = peak - v
        if dd > max_dd:
            max_dd = dd
            peak_at_max_dd = peak
            trough_idx = i

    effective_peak_equity = peak_at_max_dd + initial_equity
    if effective_peak_equity <= 0:
        max_dd_rate = 0.0
    else:
        max_dd_rate = (max_dd / effective_peak_equity) * 100

    return max_dd, max_dd_rate, trough_idx, peak_idx, effective_peak_equity


def _recovery_days(pnl_history: List[float], trough_idx: int) -> int:
    """
    Compute recovery period (number of iterations/bars) from maximum drawdown trough.
    Returns: number of iterations from trough to recovery (or -1 if not recovered)
    """
    if trough_idx < 0 or trough_idx >= len(pnl_history):
        return 0
    
    # Find the peak value at trough
    peak_before_trough = pnl_history[0]
    for i in range(trough_idx + 1):
        if pnl_history[i] > peak_before_trough:
            peak_before_trough = pnl_history[i]
    
    # Find when PnL recovers to peak_before_trough
    for i in range(trough_idx + 1, len(pnl_history)):
        if pnl_history[i] >= peak_before_trough:
            return i - trough_idx
    
    # Not recovered yet
    return -1


def compute_metrics(pnl_history: List[float], trade_results: List[bool]) -> Dict[str, float]:
    total_pnl = pnl_history[-1] if pnl_history else 0.0
    returns = _incremental_returns(pnl_history)
    sharpe = _sharpe(returns)
    # initial_equity は現状ハードコード。将来的に設定/引数化可能。
    max_dd, max_dd_rate, trough_idx, peak_idx, effective_peak_equity = _max_drawdown(pnl_history) if pnl_history else (0.0, 0.0, -1, -1, 100.0)
    recovery_period = _recovery_days(pnl_history, trough_idx) if pnl_history else 0

    trades = len(trade_results)
    wins = sum(1 for r in trade_results if r)
    losses = trades - wins
    win_rate = (wins / trades * 100) if trades > 0 else 0.0

    profit_factor = (sum(r for r in returns if r > 0) / abs(sum(r for r in returns if r < 0))) if any(r < 0 for r in returns) else 0.0

    return {
        "total_pnl": round(total_pnl, 6),
        "profit_factor": round(profit_factor, 6),
        "max_drawdown": round(max_dd, 6),
        "max_drawdown_rate": round(max_dd_rate, 6),
        "effective_peak_equity": round(effective_peak_equity, 6),
        "sharpe": round(sharpe, 6),
        "win_rate": round(win_rate, 6),
        "trades": trades,
        "samples": len(returns),
        "recovery_period": recovery_period
    }

if __name__ == "__main__":
    # Simple self-test
    example = [0, 10, 5, 15, 12, 25]
    trades = [True, False, True]
    print(compute_metrics(example, trades))
