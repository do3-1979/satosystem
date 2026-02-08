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


def _max_drawdown(pnl_history: List[float]) -> float:
    peak = -1e18
    max_dd = 0.0
    for v in pnl_history:
        if v > peak:
            peak = v
        dd = peak - v
        if dd > max_dd:
            max_dd = dd
    return max_dd


def _max_drawdown_rate(pnl_history: List[float], initial_balance: float) -> float:
    """
    最大ドローダウン率を計算（初期資本を考慮）
    
    Args:
        pnl_history: 累積損益の履歴
        initial_balance: 初期資本
    
    Returns:
        最大ドローダウン率（%）
    """
    if not pnl_history or initial_balance <= 0:
        return 0.0
    
    peak_balance = initial_balance  # 資産のピーク（初期資本から開始）
    max_dd_rate = 0.0
    
    for pnl in pnl_history:
        current_balance = initial_balance + pnl  # 現在の資産
        
        if current_balance > peak_balance:
            peak_balance = current_balance  # ピーク更新
        
        # ドローダウン率 = (ピーク - 現在) / ピーク
        dd_rate = ((peak_balance - current_balance) / peak_balance * 100) if peak_balance > 0 else 0.0
        
        if dd_rate > max_dd_rate:
            max_dd_rate = dd_rate
    
    return max_dd_rate


def compute_metrics(pnl_history: List[float], trade_results: List[bool], initial_balance: float = 100.0) -> Dict[str, float]:
def compute_metrics(pnl_history: List[float], trade_results: List[bool], initial_balance: float = 100.0) -> Dict[str, float]:
    total_pnl = pnl_history[-1] if pnl_history else 0.0
    returns = _incremental_returns(pnl_history)
    sharpe = _sharpe(returns)
    max_dd = _max_drawdown(pnl_history) if pnl_history else 0.0
    max_dd_rate = _max_drawdown_rate(pnl_history, initial_balance)

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
        "sharpe": round(sharpe, 6),
        "win_rate": round(win_rate, 6),
        "trades": trades,
        "samples": len(returns)
    }

if __name__ == "__main__":
    # Simple self-test
    example = [0, 10, 5, 15, 12, 25]
    trades = [True, False, True]
    print(compute_metrics(example, trades))
