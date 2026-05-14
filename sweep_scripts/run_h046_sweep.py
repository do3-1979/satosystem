#!/usr/bin/env python3
"""
H-046: 連続損失後ポジションサイズ縮小 パラメータスイープ

仮説: N連続損失後の次エントリーでサイズを縮小 → 同一下落局面への
     連続突撃による大損失を抑制する。勝ちトレードでカウントリセット。

ベースライン(H-044 cap=1500/taper=0.0): PnL=+2617.0 USD / MaxDD=23.3%
採用基準: PnL > +2617 USD かつ MaxDD < 23.3%
"""

import subprocess
import configparser
import re
import json
import os
from datetime import datetime

CONFIG_PATH = "src/config.ini"
BASELINE_PNL   = 2617.0
BASELINE_MAXDD = 23.3
ADOPT_PNL_THRESHOLD  = 2617.0
ADOPT_MAXDD_THRESHOLD = 23.3

TRIGGERS    = [1, 2, 3]
MIN_RATIOS  = [0.25, 0.5, 0.75]


def read_config():
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_PATH)
    return cfg

def write_config(cfg):
    with open(CONFIG_PATH, 'w') as f:
        cfg.write(f)

def set_consq(enabled, trigger, min_ratio):
    cfg = read_config()
    cfg['ConseqSizing']['consq_sizing_enabled']   = str(enabled)
    cfg['ConseqSizing']['consq_sizing_trigger']   = str(trigger)
    cfg['ConseqSizing']['consq_sizing_min_ratio'] = str(min_ratio)
    write_config(cfg)

def restore_default():
    cfg = read_config()
    cfg['ConseqSizing']['consq_sizing_enabled']   = '0'
    cfg['ConseqSizing']['consq_sizing_trigger']   = '2'
    cfg['ConseqSizing']['consq_sizing_min_ratio'] = '0.5'
    write_config(cfg)

def run_backtest():
    result = subprocess.run(
        ["python3", "bot.py"],
        capture_output=True, text=True, cwd="src"
    )
    return result.stdout + result.stderr

def parse_results(output):
    pnl = max_dd = trades = None
    for pattern in [
        r"最終損益:\s*([+-]?[\d,]+\.?\d*)\s*\[",
        r"損益累計:([+-]?[\d,]+\.?\d*)\s*\[",
    ]:
        m = re.search(pattern, output)
        if m:
            try:
                pnl = float(m.group(1).replace(',', ''))
                break
            except ValueError:
                pass
    for pattern in [
        r"最大ドローダウン率:\s*([0-9]+\.?[0-9]*)\s*\[%\]",
        r"最大ドローダウン率[:\s]+([0-9]+\.?[0-9]*)",
    ]:
        m = re.search(pattern, output)
        if m:
            max_dd = float(m.group(1))
            break
    m = re.search(r"Trades:\s*(\d+)", output)
    if m:
        trades = int(m.group(1))
    return pnl, max_dd, trades


def main():
    grid = [(t, r) for t in TRIGGERS for r in MIN_RATIOS]
    total = len(grid)

    print("=" * 68)
    print("H-046 連続損失後ポジションサイズ縮小 パラメータスイープ")
    print(f"グリッド: trigger×{TRIGGERS} / min_ratio×{MIN_RATIOS}")
    print(f"ベースライン: PnL=+{BASELINE_PNL} USD / MaxDD={BASELINE_MAXDD}%")
    print(f"採用基準: PnL > +{ADOPT_PNL_THRESHOLD} USD かつ MaxDD < {ADOPT_MAXDD_THRESHOLD}%")
    print("=" * 68)
    print()

    results = []
    for i, (trigger, min_r) in enumerate(grid, 1):
        label = f"trigger={trigger}/min_ratio={min_r}"
        print(f"[{i:2d}/{total}] {label:<28}  実行中...")
        set_consq(1, trigger, min_r)
        out = run_backtest()
        pnl, max_dd, trades = parse_results(out)
        if pnl is None or max_dd is None:
            print(f"  ⚠️  パース失敗:")
            for line in out.splitlines()[-10:]:
                print(f"    {line.strip()}")
            pnl = pnl or 0
            max_dd = max_dd or 0
            trades = trades or 0

        d_pnl = pnl - BASELINE_PNL
        d_dd  = max_dd - BASELINE_MAXDD
        adopted = pnl > ADOPT_PNL_THRESHOLD and max_dd < ADOPT_MAXDD_THRESHOLD
        tag = "✅ 採用候補" if adopted else ("⚠️ PnL低" if pnl <= ADOPT_PNL_THRESHOLD else "⚠️ DD高")
        results.append(dict(trigger=trigger, min_ratio=min_r, pnl=pnl, delta_pnl=d_pnl,
                            max_dd=max_dd, delta_dd=d_dd, trades=trades, adopted=adopted))
        print(f"  → PnL={pnl:.2f} (Δ{d_pnl:+.2f})  MaxDD={max_dd:.2f}% (Δ{d_dd:+.2f})  trades={trades}  {tag}")

    restore_default()
    print(f"\n✅ config.ini を元の設定に復元しました")

    print()
    print("=" * 68)
    print("スキャン結果サマリー（PnL降順）")
    print("=" * 68)
    sorted_r = sorted(results, key=lambda x: x['pnl'], reverse=True)
    print(f"{'trigger':>8} {'min_r':>6}  {'PnL':>9}  {'ΔPnL':>8}  {'MaxDD':>7}  {'ΔDD':>7}  adopted")
    print("-" * 68)
    for r in sorted_r:
        ad = "✅" if r['adopted'] else "❌"
        print(f"{r['trigger']:>8} {r['min_ratio']:>6.2f}  {r['pnl']:>9.2f}  {r['delta_pnl']:>+8.2f}  "
              f"{r['max_dd']:>6.2f}%  {r['delta_dd']:>+6.2f}  {ad}")

    candidates = [r for r in results if r['adopted']]
    best = None
    if candidates:
        best = max(candidates, key=lambda x: x['pnl'])
        print()
        print("🏆 最良採用候補:")
        print(f"   trigger={best['trigger']}/min_ratio={best['min_ratio']}  "
              f"PnL={best['pnl']:.2f} (Δ{best['delta_pnl']:+.2f})  "
              f"MaxDD={best['max_dd']:.2f}% (Δ{best['delta_dd']:+.2f})")
    else:
        print()
        print("❌ 採用基準を満たすパラメータなし → H-046不採用")

    os.makedirs("sweep_results", exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"sweep_results/h046_sweep_{ts}.json"
    with open(fname, 'w') as f:
        json.dump(dict(hypothesis="H-046",
                       description="連続損失後ポジションサイズ縮小",
                       baseline_pnl=BASELINE_PNL, baseline_maxdd=BASELINE_MAXDD,
                       results=results, best=best), f, indent=2, ensure_ascii=False)
    print(f"\n📄 結果保存: {fname}")


if __name__ == "__main__":
    main()
