"""
H-048: EMAトレンドフィルター スイープ
BUYエントリー条件: close > EMA(N) （下落相場でのフォールスブレイクアウトを排除）
スイープ: ema_period = [50, 100, 150, 200]

ベースライン: PnL=+2617 USD / MaxDD=23.3% / trades=43
採用基準: PnL > 2617 かつ MaxDD < 23.3% の両方、または PnL 大幅改善
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
        capture_output=True, text=True, cwd=os.path.join(os.path.dirname(__file__), "src")
    )
    output = result.stdout + result.stderr
    pnl_match = re.search(r"最終損益:\s*([+-]?[\d,]+\.?\d*)\s*\[", output)
    dd_match  = re.search(r"最大ドローダウン率:\s*([0-9]+\.?[0-9]*)\s*\[%\]", output)
    tr_match  = re.search(r"Trades:\s*(\d+)", output)
    pnl    = float(pnl_match.group(1).replace(",", "")) if pnl_match else None
    maxdd  = float(dd_match.group(1))  if dd_match  else None
    trades = int(tr_match.group(1))    if tr_match  else None
    return pnl, maxdd, trades

def set_config(period: int, enabled: int = 1):
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_PATH)
    cfg["EntryFilters"]["ema_trend_filter_enabled"] = str(enabled)
    cfg["EntryFilters"]["ema_trend_filter_period"]  = str(period)
    with open(CONFIG_PATH, "w") as f:
        cfg.write(f)

def restore_baseline():
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_PATH)
    cfg["EntryFilters"]["ema_trend_filter_enabled"] = "0"
    cfg["EntryFilters"]["ema_trend_filter_period"]  = "200"
    with open(CONFIG_PATH, "w") as f:
        cfg.write(f)

BASELINE_PNL   = 2617.0
BASELINE_MAXDD = 23.3

# スイープパラメータ（4H足単位: 50本=8日, 100本=17日, 150本=25日, 200本=33日）
EMA_PERIODS = [50, 100, 150, 200]

results = []

print("=" * 65)
print("H-048: EMAトレンドフィルター スイープ")
print(f"ベースライン: PnL=+{BASELINE_PNL:.1f} USD / MaxDD={BASELINE_MAXDD}%")
print("=" * 65)

# ベースライン（フィルターなし）確認
restore_baseline()
b_pnl, b_dd, b_tr = run_backtest()
print(f"[ベースライン確認] PnL={b_pnl:+.1f} / MaxDD={b_dd:.1f}% / Trades={b_tr}")
print()

for period in EMA_PERIODS:
    set_config(period=period, enabled=1)
    pnl, dd, tr = run_backtest()

    delta_pnl = (pnl - BASELINE_PNL) if pnl is not None else None
    delta_dd  = (dd  - BASELINE_MAXDD) if dd  is not None else None

    both_better = (pnl is not None and dd is not None and
                   pnl > BASELINE_PNL and dd < BASELINE_MAXDD)
    mark = "✅ 両方改善" if both_better else ("📈 PnL改善のみ" if pnl and pnl > BASELINE_PNL else "❌")

    print(f"EMA({period:3d}): PnL={pnl:+8.1f} (Δ{delta_pnl:+.1f})  MaxDD={dd:.1f}% (Δ{delta_dd:+.1f}%)  Trades={tr}  {mark}")
    results.append({
        "period": period,
        "pnl": pnl,
        "maxdd": dd,
        "trades": tr,
        "delta_pnl": delta_pnl,
        "delta_dd": delta_dd,
        "both_better": both_better,
    })

restore_baseline()

print()
print("=" * 65)
print("結果サマリー")
print("=" * 65)

best = max(results, key=lambda r: (r["pnl"] or -9999))
print(f"最高PnL: EMA({best['period']}) → PnL={best['pnl']:+.1f} / MaxDD={best['maxdd']:.1f}% / Trades={best['trades']}")

best_dd = min([r for r in results if r["pnl"] and r["pnl"] > 0], key=lambda r: r["maxdd"] or 999, default=None)
if best_dd:
    print(f"最低MaxDD: EMA({best_dd['period']}) → PnL={best_dd['pnl']:+.1f} / MaxDD={best_dd['maxdd']:.1f}%")

adopted = [r for r in results if r["both_better"]]
if adopted:
    print(f"\n🎯 採用候補（PnL>{BASELINE_PNL:.0f} かつ MaxDD<{BASELINE_MAXDD}%）:")
    for r in adopted:
        print(f"  EMA({r['period']}): PnL={r['pnl']:+.1f} (Δ{r['delta_pnl']:+.1f})  MaxDD={r['maxdd']:.1f}% (Δ{r['delta_dd']:+.1f}%)")
else:
    print("\n採用候補なし（両方同時改善なし）")
    # PnL改善のみのものも表示
    pnl_improved = [r for r in results if r["pnl"] and r["pnl"] > BASELINE_PNL]
    if pnl_improved:
        print("PnL改善のみ（MaxDD未改善）:")
        for r in pnl_improved:
            print(f"  EMA({r['period']}): PnL={r['pnl']:+.1f} (Δ{r['delta_pnl']:+.1f})  MaxDD={r['maxdd']:.1f}% (Δ{r['delta_dd']:+.1f}%)")
