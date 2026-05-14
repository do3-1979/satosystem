#!/usr/bin/env python3
"""
H-047: 残高連動可変risk_pct パラメータスイープ

仮説: 残高が増えるにつれてrisk_pctを段階的に下げることで、
     高残高期の大損失を抑制する（H-044 cap=1500と組み合わせ）。

tier構造（固定）:
  balance <= t1=500   → t1_pct (固定 0.30)
  balance <= t2=1500  → t2_pct (スイープ)
  balance <= t3=3000  → t3_pct (スイープ)
  balance >  t3       → t4_pct (スイープ)

H-044と組み合わせ: effective_balance = min(balance, 1500)
  → balance > 1500 のトレードは t3/t4 の risk_pct でリスク計算される

ベースライン(H-044 cap=1500): PnL=+2617.0 USD / MaxDD=23.3%
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

# スイープグリッド (t1_pct=0.30 固定)
T2_PCTS = [0.20, 0.25]         # balance <= 1500 時のrisk_pct
T3_PCTS = [0.15, 0.20]         # balance <= 3000 時のrisk_pct
T4_PCTS = [0.10, 0.15]         # balance >  3000 時のrisk_pct
# 合計: 2×2×2 = 8パターン


def read_config():
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_PATH)
    return cfg

def write_config(cfg):
    with open(CONFIG_PATH, 'w') as f:
        cfg.write(f)

def set_var_risk(enabled, t2_pct, t3_pct, t4_pct):
    cfg = read_config()
    cfg['VarRisk']['var_risk_enabled'] = str(enabled)
    cfg['VarRisk']['var_risk_t2_pct']  = str(t2_pct)
    cfg['VarRisk']['var_risk_t3_pct']  = str(t3_pct)
    cfg['VarRisk']['var_risk_t4_pct']  = str(t4_pct)
    write_config(cfg)

def restore_default():
    cfg = read_config()
    cfg['VarRisk']['var_risk_enabled'] = '0'
    cfg['VarRisk']['var_risk_t2_pct']  = '0.25'
    cfg['VarRisk']['var_risk_t3_pct']  = '0.20'
    cfg['VarRisk']['var_risk_t4_pct']  = '0.15'
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
    grid = [(t2, t3, t4) for t2 in T2_PCTS for t3 in T3_PCTS for t4 in T4_PCTS]
    total = len(grid)

    print("=" * 74)
    print("H-047 残高連動可変risk_pct パラメータスイープ")
    print(f"tier構造: t1=0.30(<=500) / t2(<=1500) / t3(<=3000) / t4(>3000)")
    print(f"グリッド: t2×{T2_PCTS} / t3×{T3_PCTS} / t4×{T4_PCTS}")
    print(f"ベースライン: PnL=+{BASELINE_PNL} USD / MaxDD={BASELINE_MAXDD}%")
    print(f"採用基準: PnL > +{BASELINE_PNL} USD かつ MaxDD < {BASELINE_MAXDD}%")
    print("=" * 74)
    print()

    results = []
    for i, (t2, t3, t4) in enumerate(grid, 1):
        label = f"t2={t2:.2f}/t3={t3:.2f}/t4={t4:.2f}"
        print(f"[{i:2d}/{total}] {label:<28}  実行中...")
        set_var_risk(1, t2, t3, t4)
        out = run_backtest()
        pnl, max_dd, trades = parse_results(out)
        if pnl is None or max_dd is None:
            print(f"  ⚠️  パース失敗:")
            for line in out.splitlines()[-10:]:
                print(f"    {line.strip()}")
            pnl = pnl or 0; max_dd = max_dd or 0; trades = trades or 0

        d_pnl = pnl - BASELINE_PNL
        d_dd  = max_dd - BASELINE_MAXDD
        adopted = pnl > BASELINE_PNL and max_dd < BASELINE_MAXDD
        tag = "✅ 採用候補" if adopted else ("⚠️ PnL低" if pnl <= BASELINE_PNL else "⚠️ DD高")
        results.append(dict(t2_pct=t2, t3_pct=t3, t4_pct=t4,
                            pnl=pnl, delta_pnl=d_pnl,
                            max_dd=max_dd, delta_dd=d_dd,
                            trades=trades, adopted=adopted))
        print(f"  → PnL={pnl:.2f} (Δ{d_pnl:+.2f})  MaxDD={max_dd:.2f}% (Δ{d_dd:+.2f})  trades={trades}  {tag}")

    restore_default()
    print(f"\n✅ config.ini を元の設定に復元しました")

    print()
    print("=" * 74)
    print("スキャン結果サマリー（PnL降順）")
    print("=" * 74)
    sorted_r = sorted(results, key=lambda x: x['pnl'], reverse=True)
    print(f"{'t2':>6} {'t3':>6} {'t4':>6}  {'PnL':>9}  {'ΔPnL':>8}  {'MaxDD':>7}  {'ΔDD':>7}  adopted")
    print("-" * 74)
    for r in sorted_r:
        ad = "✅" if r['adopted'] else "❌"
        print(f"{r['t2_pct']:>6.2f} {r['t3_pct']:>6.2f} {r['t4_pct']:>6.2f}  "
              f"{r['pnl']:>9.2f}  {r['delta_pnl']:>+8.2f}  "
              f"{r['max_dd']:>6.2f}%  {r['delta_dd']:>+6.2f}  {ad}")

    candidates = [r for r in results if r['adopted']]
    best = None
    if candidates:
        best = max(candidates, key=lambda x: x['pnl'])
        print()
        print("🏆 最良採用候補:")
        print(f"   t2={best['t2_pct']:.2f}/t3={best['t3_pct']:.2f}/t4={best['t4_pct']:.2f}  "
              f"PnL={best['pnl']:.2f} (Δ{best['delta_pnl']:+.2f})  "
              f"MaxDD={best['max_dd']:.2f}% (Δ{best['delta_dd']:+.2f})")
    else:
        print()
        print("❌ 採用基準を満たすパラメータなし → H-047不採用")

    os.makedirs("sweep_results", exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"sweep_results/h047_sweep_{ts}.json"
    with open(fname, 'w') as f:
        json.dump(dict(hypothesis="H-047",
                       description="残高連動可変risk_pct",
                       baseline_pnl=BASELINE_PNL, baseline_maxdd=BASELINE_MAXDD,
                       results=results, best=best), f, indent=2, ensure_ascii=False)
    print(f"\n📄 結果保存: {fname}")


if __name__ == "__main__":
    main()
