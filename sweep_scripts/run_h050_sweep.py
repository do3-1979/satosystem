"""
H-050: ADX上限フィルター スイープ
ADX >= upper_threshold でBUYエントリーを抑制（過熱トレンドのフォールスブレイクアウト排除）

分析根拠（ADX別パフォーマンス）:
  ADX 30-40: 22件, +2308 USD (平均+105) ← ゴールデンゾーン
  ADX ≥ 40:  19件, +331 USD  (平均+17)  ← 大損失集中

大損失トレードのADX:
  T24(-751): ADX=42.0
  T43(-345): ADX=40.9
  T42(-326): ADX=47.3
  T41(-176): ADX=44.2
  T32(-77):  ADX=70.3

ベースライン: PnL=+2617 USD / MaxDD=23.3% / trades=43
採用基準: PnL > 2617 かつ MaxDD < 23.3%
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

def set_config(upper_thr: float, enabled: int = 1):
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_PATH)
    cfg["EntryFilters"]["adx_upper_filter_enabled"]   = str(enabled)
    cfg["EntryFilters"]["adx_upper_filter_threshold"] = str(upper_thr)
    with open(CONFIG_PATH, "w") as f:
        cfg.write(f)

def restore_baseline():
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_PATH)
    cfg["EntryFilters"]["adx_upper_filter_enabled"]   = "0"
    cfg["EntryFilters"]["adx_upper_filter_threshold"] = "60"
    with open(CONFIG_PATH, "w") as f:
        cfg.write(f)

BASELINE_PNL   = 2617.0
BASELINE_MAXDD = 23.3

# スイープ範囲
# ADX=40がターゲット（大損失の最低ADX）なので、38以上は全て網羅
UPPER_THRESHOLDS = [38, 40, 42, 45, 50, 55, 60]

results = []

print("=" * 72)
print("H-050: ADX上限フィルター スイープ")
print(f"ベースライン: PnL=+{BASELINE_PNL:.1f} USD / MaxDD={BASELINE_MAXDD}%")
print("ADX下限=28 (既存) / 上限=N でのエントリー抑制")
print("=" * 72)

restore_baseline()
b_pnl, b_dd, b_tr = run_backtest()
print(f"[ベースライン確認] PnL={b_pnl:+.1f} / MaxDD={b_dd:.1f}% / Trades={b_tr}")
print()

for thr in UPPER_THRESHOLDS:
    set_config(upper_thr=thr, enabled=1)
    pnl, dd, tr = run_backtest()

    delta_pnl = (pnl - BASELINE_PNL) if pnl is not None else None
    delta_dd  = (dd  - BASELINE_MAXDD) if dd  is not None else None
    delta_tr  = tr - b_tr if tr is not None and b_tr is not None else None

    both_better = (pnl is not None and dd is not None and
                   pnl > BASELINE_PNL and dd < BASELINE_MAXDD)
    pnl_only    = (pnl is not None and pnl > BASELINE_PNL and not both_better)
    mark = "✅ 両方改善" if both_better else ("📈 PnL改善" if pnl_only else "❌")

    print(f"ADX<{thr:2d}: PnL={pnl:+8.1f} (Δ{delta_pnl:+.1f})  "
          f"MaxDD={dd:.1f}% (Δ{delta_dd:+.1f}%)  Trades={tr:2d} (Δ{delta_tr:+d})  {mark}")
    results.append({
        "thr": thr, "pnl": pnl, "maxdd": dd, "trades": tr,
        "delta_pnl": delta_pnl, "delta_dd": delta_dd, "delta_tr": delta_tr,
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
        print(f"  ADX<{r['thr']:2d}: PnL={r['pnl']:+.1f} (Δ{r['delta_pnl']:+.1f})  "
              f"MaxDD={r['maxdd']:.1f}% (Δ{r['delta_dd']:+.1f}%)  Trades={r['trades']}")
    best = max(adopted, key=lambda r: r["pnl"])
    print(f"\n最良パターン: ADX<{best['thr']}")
else:
    print("採用候補なし（両方同時改善なし）")
    pnl_up = [r for r in results if r["pnl"] and r["pnl"] > BASELINE_PNL]
    if pnl_up:
        print("PnL改善のみ（MaxDD悪化）:")
        for r in pnl_up:
            print(f"  ADX<{r['thr']:2d}: PnL={r['pnl']:+.1f} (Δ{r['delta_pnl']:+.1f})  "
                  f"MaxDD={r['maxdd']:.1f}% (Δ{r['delta_dd']:+.1f}%)  Trades={r['trades']}")
    dd_down = [r for r in results if r["maxdd"] and r["maxdd"] < BASELINE_MAXDD]
    if dd_down:
        print("MaxDD改善（PnL増減問わず）:")
        for r in dd_down:
            print(f"  ADX<{r['thr']:2d}: PnL={r['pnl']:+.1f} (Δ{r['delta_pnl']:+.1f})  "
                  f"MaxDD={r['maxdd']:.1f}% (Δ{r['delta_dd']:+.1f}%)  Trades={r['trades']}")
