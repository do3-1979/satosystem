#!/usr/bin/env python3
"""
H-044b: ソフトキャップ（Soft Cap Sizing）パラメータスイープ

H-044の固定キャップ問題を改善:
  固定cap → balance>cap で複利が完全停止
  ソフトキャップ → cap以上でも taper_rate 倍で緩やかに成長継続

effective_balance:
  balance <= cap: effective = balance
  balance >  cap: effective = cap + (balance - cap) * taper_rate

ベースライン(H-044: cap=1500/taper=0.0): PnL=+2617.0 USD / MaxDD=23.3%
採用基準: PnL > +2617 USD かつ MaxDD < 35.0%  （PnL改善 + MaxDD維持）
"""

import subprocess
import configparser
import json
import os
import re
from datetime import datetime

CONFIG_PATH = "src/config.ini"
BASELINE_PNL   = 2617.0
BASELINE_MAXDD = 23.3
ADOPT_PNL_THRESHOLD  = 2617.0   # H-044より改善必須
ADOPT_MAXDD_THRESHOLD = 35.0    # MaxDD多少増加は許容（複利効果のトレードオフ）

# スイープグリッド
CAP_VALUES    = [500.0, 750.0, 1000.0, 1500.0]
TAPER_RATES   = [0.0, 0.2, 0.3, 0.5, 0.7]
# taper=0.0 は固定キャップ（H-044と同等）


def read_config():
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_PATH)
    return cfg

def write_config(cfg):
    with open(CONFIG_PATH, 'w') as f:
        cfg.write(f)

def set_cap_sizing(enabled, cap_usd, taper_rate):
    cfg = read_config()
    cfg['CapSizing']['cap_sizing_enabled'] = str(enabled)
    cfg['CapSizing']['cap_sizing_max_balance_usd'] = str(cap_usd)
    cfg['CapSizing']['cap_sizing_taper_rate'] = str(taper_rate)
    write_config(cfg)

def restore_default():
    cfg = read_config()
    cfg['CapSizing']['cap_sizing_enabled'] = '1'
    cfg['CapSizing']['cap_sizing_max_balance_usd'] = '1500.0'
    cfg['CapSizing']['cap_sizing_taper_rate'] = '0.0'
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
    grid = [(c, t) for c in CAP_VALUES for t in TAPER_RATES]
    total = len(grid)

    print("=" * 72)
    print("H-044b ソフトキャップ（Soft Cap Sizing）パラメータスイープ")
    print(f"グリッド: cap×{CAP_VALUES} / taper×{TAPER_RATES}")
    print(f"ベースライン(H-044 固定cap=1500): PnL=+{BASELINE_PNL} USD / MaxDD={BASELINE_MAXDD}%")
    print(f"採用基準: PnL > +{ADOPT_PNL_THRESHOLD} USD かつ MaxDD < {ADOPT_MAXDD_THRESHOLD}%")
    print("=" * 72)
    print()

    results = []
    for i, (cap, taper) in enumerate(grid, 1):
        label = f"cap={cap:.0f}/taper={taper}"
        print(f"[{i:2d}/{total}] {label:<22}  実行中...")
        set_cap_sizing(1, cap, taper)
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
        results.append(dict(cap=cap, taper=taper, pnl=pnl, delta_pnl=d_pnl,
                            max_dd=max_dd, delta_dd=d_dd, trades=trades or 0, adopted=adopted))
        print(f"  → PnL={pnl:.2f} (Δ{d_pnl:+.2f})  MaxDD={max_dd:.2f}% (Δ{d_dd:+.2f})  {tag}")

    restore_default()
    print(f"\n✅ config.ini を元の設定（cap=1500/taper=0.0）に復元しました")

    # サマリー
    print()
    print("=" * 72)
    print("スキャン結果サマリー（PnL降順）")
    print("=" * 72)
    sorted_r = sorted(results, key=lambda x: x['pnl'], reverse=True)
    print(f"{'cap':>7} {'taper':>6}  {'PnL':>9}  {'ΔPnL':>8}  {'MaxDD':>7}  {'ΔDD':>7}  adopted")
    print("-" * 72)
    for r in sorted_r:
        ad = "✅" if r['adopted'] else "❌"
        print(f"{r['cap']:>7.0f} {r['taper']:>6.1f}  {r['pnl']:>9.2f}  {r['delta_pnl']:>+8.2f}  "
              f"{r['max_dd']:>6.2f}%  {r['delta_dd']:>+6.2f}  {ad}")

    candidates = [r for r in results if r['adopted']]
    if candidates:
        best = max(candidates, key=lambda x: x['pnl'])
        print()
        print("🏆 最良採用候補:")
        print(f"   cap={best['cap']:.0f}/taper={best['taper']}  "
              f"PnL={best['pnl']:.2f} (Δ{best['delta_pnl']:+.2f})  "
              f"MaxDD={best['max_dd']:.2f}% (Δ{best['delta_dd']:+.2f})")
    else:
        best = None
        print()
        print("❌ 採用基準を満たすパラメータなし")
        # 最良のPnL候補を表示（参考）
        best_pnl = max(results, key=lambda x: x['pnl'])
        best_dd  = min(results, key=lambda x: x['max_dd'])
        print(f"   PnL最大: cap={best_pnl['cap']:.0f}/taper={best_pnl['taper']}  "
              f"PnL={best_pnl['pnl']:.2f}  MaxDD={best_pnl['max_dd']:.2f}%")
        print(f"   DD最小:  cap={best_dd['cap']:.0f}/taper={best_dd['taper']}  "
              f"PnL={best_dd['pnl']:.2f}  MaxDD={best_dd['max_dd']:.2f}%")

    os.makedirs("sweep_results", exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"sweep_results/h044b_sweep_{ts}.json"
    with open(fname, 'w') as f:
        json.dump(dict(hypothesis="H-044b", description="ソフトキャップ（Soft Cap Sizing）",
                       baseline_pnl=BASELINE_PNL, baseline_maxdd=BASELINE_MAXDD,
                       adopt_pnl_threshold=ADOPT_PNL_THRESHOLD,
                       adopt_maxdd_threshold=ADOPT_MAXDD_THRESHOLD,
                       results=results, best=best), f, indent=2, ensure_ascii=False)
    print(f"\n📄 結果保存: {fname}")


if __name__ == "__main__":
    main()
