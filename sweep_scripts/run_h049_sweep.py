"""
H-049: ATRブレイクアウト強度フィルター スイープ
既存実装（atr_breakout_filter_enabled）を活用。
「ブレイク幅 < ATR×N」なら弱いブレイクとしてエントリー拒否。

ターゲット損失:
  T41(2026/04/14): -176 USD  entry=74384
  T42(2026/05/04): -326 USD  entry=80280
  T43(2026/05/06): -345 USD  entry=82486
  T24(2025/04/02): -751 USD  entry=86699
  T28(2025/06/10): -266 USD  entry=110220

ベースライン: PnL=+2617 USD / MaxDD=23.3% / trades=43
採用基準: PnL > 2617 かつ MaxDD < 23.3%  （両方同時改善）
"""

import subprocess
import re
import configparser
import os
import sys

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "src", "config.ini")

def run_backtest():
    result = subprocess.run(
        [sys.executable, "bot.py"],
        capture_output=True, text=True,
        cwd=os.path.join(os.path.dirname(__file__), "src")
    )
    output = result.stdout + result.stderr
    pnl_match = re.search(r"最終損益:\s*([+-]?[\d,]+\.?\d*)\s*\[", output)
    dd_match   = re.search(r"最大ドローダウン率:\s*([0-9]+\.?[0-9]*)\s*\[%\]", output)
    tr_match   = re.search(r"Trades:\s*(\d+)", output)
    pnl    = float(pnl_match.group(1).replace(",", "")) if pnl_match else None
    maxdd  = float(dd_match.group(1))  if dd_match  else None
    trades = int(tr_match.group(1))    if tr_match  else None
    return pnl, maxdd, trades

def set_config(min_ratio: float, enabled: int = 1):
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_PATH)
    cfg["EntryFilters"]["atr_breakout_filter_enabled"] = str(enabled)
    cfg["EntryFilters"]["atr_breakout_min_ratio"]      = str(min_ratio)
    cfg["EntryFilters"]["atr_breakout_period"]         = "14"
    with open(CONFIG_PATH, "w") as f:
        cfg.write(f)

def restore_baseline():
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_PATH)
    cfg["EntryFilters"]["atr_breakout_filter_enabled"] = "0"
    cfg["EntryFilters"]["atr_breakout_min_ratio"]      = "0.3"
    with open(CONFIG_PATH, "w") as f:
        cfg.write(f)

BASELINE_PNL   = 2617.0
BASELINE_MAXDD = 23.3

# スイープ範囲: 弱→強
# ATR(14)の N倍 がブレイクアウト幅の最小要件
# 4H足BTCのATR≒1000-2000 USD → min_ratio=0.3 → 閾値≒300-600 USD
MIN_RATIOS = [0.05, 0.10, 0.15, 0.20, 0.30, 0.50, 0.80, 1.00]

results = []

print("=" * 72)
print("H-049: ATRブレイクアウト強度フィルター スイープ")
print(f"ベースライン: PnL=+{BASELINE_PNL:.1f} USD / MaxDD={BASELINE_MAXDD}%")
print("=" * 72)

# ベースライン確認
restore_baseline()
b_pnl, b_dd, b_tr = run_backtest()
print(f"[ベースライン確認] PnL={b_pnl:+.1f} / MaxDD={b_dd:.1f}% / Trades={b_tr}")
print()

for ratio in MIN_RATIOS:
    set_config(min_ratio=ratio, enabled=1)
    pnl, dd, tr = run_backtest()

    delta_pnl = (pnl - BASELINE_PNL) if pnl is not None else None
    delta_dd  = (dd  - BASELINE_MAXDD) if dd  is not None else None

    both_better = (pnl is not None and dd is not None and
                   pnl > BASELINE_PNL and dd < BASELINE_MAXDD)
    pnl_only    = (pnl is not None and pnl > BASELINE_PNL and not both_better)
    mark = "✅ 両方改善" if both_better else ("📈 PnL改善" if pnl_only else "❌")

    print(f"ratio={ratio:.2f}: PnL={pnl:+8.1f} (Δ{delta_pnl:+.1f})  "
          f"MaxDD={dd:.1f}% (Δ{delta_dd:+.1f}%)  Trades={tr:2d}  {mark}")
    results.append({
        "ratio": ratio, "pnl": pnl, "maxdd": dd, "trades": tr,
        "delta_pnl": delta_pnl, "delta_dd": delta_dd,
        "both_better": both_better,
    })

restore_baseline()

print()
print("=" * 72)
print("結果サマリー")
print("=" * 72)

adopted = [r for r in results if r["both_better"]]
if adopted:
    print("🎯 採用候補（PnL>2617 かつ MaxDD<23.3%）:")
    for r in adopted:
        print(f"  ratio={r['ratio']:.2f}: PnL={r['pnl']:+.1f} (Δ{r['delta_pnl']:+.1f})  "
              f"MaxDD={r['maxdd']:.1f}% (Δ{r['delta_dd']:+.1f}%)  Trades={r['trades']}")
    best = max(adopted, key=lambda r: r["pnl"])
    print(f"\n最良パターン: ratio={best['ratio']:.2f}")
else:
    print("採用候補なし（両方同時改善なし）")
    # PnL改善のみ
    pnl_up = [r for r in results if r["pnl"] and r["pnl"] > BASELINE_PNL]
    if pnl_up:
        print("PnL改善のみ（MaxDD悪化）:")
        for r in pnl_up:
            print(f"  ratio={r['ratio']:.2f}: PnL={r['pnl']:+.1f} (Δ{r['delta_pnl']:+.1f})  "
                  f"MaxDD={r['maxdd']:.1f}% (Δ{r['delta_dd']:+.1f}%)  Trades={r['trades']}")
    # DD改善のみ
    dd_down = [r for r in results if r["maxdd"] and r["maxdd"] < BASELINE_MAXDD and r["pnl"] and r["pnl"] < BASELINE_PNL]
    if dd_down:
        print("MaxDD改善のみ（PnL減少）:")
        for r in dd_down:
            print(f"  ratio={r['ratio']:.2f}: PnL={r['pnl']:+.1f} (Δ{r['delta_pnl']:+.1f})  "
                  f"MaxDD={r['maxdd']:.1f}% (Δ{r['delta_dd']:+.1f}%)  Trades={r['trades']}")
