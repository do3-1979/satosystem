"""Metrics calculation utilities for backtest performance evaluation.

Functions:
    compute_metrics(pnl_history, trade_results, initial_balance, trade_pnls) -> dict

Metrics:
- total_pnl: 累積損益 (USD)
- profit_factor: プロフィットファクター (総利益/総損失)
- max_drawdown: 最大ドローダウン (USD)
- max_drawdown_rate: 最大ドローダウン率 (%)
- sharpe: シャープレシオ
- win_rate: 勝率 (%)
- trades: 総トレード数
- samples: バーサンプル数
- sortino: ソルティノレシオ (下方偏差のみ使用)
- recovery_factor: リカバリーファクター (総損益/最大DD)
- payoff_ratio: ペイオフレシオ (平均利益/平均損失)
- expectancy: 期待値 (1トレード当たり期待損益 USD)
- max_consec_losses: 最大連続損失回数

Notes:
- pnl_history: list of cumulative PnL values (can be negative). Assumed chronological.
- trade_results: list of booleans for each closed trade (True=win, False=loss).
- trade_pnls: list of per-trade PnL amounts (USD). Optional.
- Sharpe/Sortino ratio is computed on incremental returns. Risk-free rate assumed 0.
- Max Drawdown computed from cumulative PnL peak to trough.
"""
from __future__ import annotations
from typing import List, Dict, Optional
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


def _sortino(returns: List[float]) -> float:
    """ソルティノレシオ: 下方偏差（マイナスリターンのみ）を使ったリスク調整済みリターン"""
    if len(returns) < 2:
        return 0.0
    mean_ret = sum(returns) / len(returns)
    downside_returns = [r for r in returns if r < 0]
    if len(downside_returns) < 2:
        # 損失なしの場合は正の無限大相当（良いパフォーマンス）→上限キャップ
        return 3.0 if mean_ret > 0 else 0.0
    downside_variance = sum(r ** 2 for r in downside_returns) / len(downside_returns)
    downside_std = math.sqrt(downside_variance) if downside_variance > 0 else 0.0
    if downside_std == 0:
        return 0.0
    return mean_ret / downside_std * math.sqrt(len(returns))


def _max_consec_losses(trade_results: List[bool]) -> int:
    """最大連続損失回数を計算"""
    max_consec = 0
    current_consec = 0
    for result in trade_results:
        if not result:  # loss
            current_consec += 1
            max_consec = max(max_consec, current_consec)
        else:
            current_consec = 0
    return max_consec


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


def compute_metrics(pnl_history: List[float], trade_results: List[bool], initial_balance: float, trade_pnls: Optional[List[float]] = None) -> Dict[str, float]:
    """
    バックテスト結果のメトリクスを計算
    
    Args:
        pnl_history: 累積損益の履歴
        trade_results: トレード結果のリスト（True=勝ち, False=負け）
        initial_balance: 初期資本（必須）
        trade_pnls: per-tradeの損益リスト（USD）。指定時に期待値・RR比率を計算
    
    Returns:
        メトリクス辞書
    """
    total_pnl = pnl_history[-1] if pnl_history else 0.0
    returns = _incremental_returns(pnl_history)
    sharpe = _sharpe(returns)
    sortino = _sortino(returns)
    max_dd = _max_drawdown(pnl_history) if pnl_history else 0.0
    max_dd_rate = _max_drawdown_rate(pnl_history, initial_balance)

    trades = len(trade_results)
    wins = sum(1 for r in trade_results if r)
    losses = trades - wins
    win_rate = (wins / trades * 100) if trades > 0 else 0.0

    profit_factor = (sum(r for r in returns if r > 0) / abs(sum(r for r in returns if r < 0))) if any(r < 0 for r in returns) else 0.0

    # Recovery Factor: 総損益/最大DD
    recovery_factor = round(total_pnl / max_dd, 6) if max_dd > 0 else 0.0

    # Max Consecutive Losses
    max_consec_losses = _max_consec_losses(trade_results)

    # Per-trade metrics (trade_pnlsが必要)
    payoff_ratio = 0.0
    expectancy = 0.0
    avg_win = 0.0
    avg_loss = 0.0
    if trade_pnls and len(trade_pnls) > 0:
        win_pnls = [p for p in trade_pnls if p >= 0]
        loss_pnls = [p for p in trade_pnls if p < 0]
        avg_win = sum(win_pnls) / len(win_pnls) if win_pnls else 0.0
        avg_loss = abs(sum(loss_pnls) / len(loss_pnls)) if loss_pnls else 0.0
        payoff_ratio = round(avg_win / avg_loss, 6) if avg_loss > 0 else 0.0
        win_rate_dec = win_rate / 100.0
        loss_rate_dec = 1.0 - win_rate_dec
        expectancy = round(win_rate_dec * avg_win - loss_rate_dec * avg_loss, 6)

    return {
        "total_pnl": round(total_pnl, 6),
        "profit_factor": round(profit_factor, 6),
        "max_drawdown": round(max_dd, 6),
        "max_drawdown_rate": round(max_dd_rate, 6),
        "sharpe": round(sharpe, 6),
        "sortino": round(sortino, 6),
        "recovery_factor": round(recovery_factor, 6),
        "win_rate": round(win_rate, 6),
        "payoff_ratio": round(payoff_ratio, 6),
        "expectancy": round(expectancy, 6),
        "max_consec_losses": max_consec_losses,
        "trades": trades,
        "samples": len(returns)
    }

if __name__ == "__main__":
    # Simple self-test
    example = [0, 10, 5, 15, 12, 25]
    trades = [True, False, True]
    print(compute_metrics(example, trades))
