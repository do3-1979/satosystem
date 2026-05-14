#!/usr/bin/env python3
"""
H-044: 残高上限サイジング（Cap Balance Sizing）パラメータスイープ

仮説: risk_pct × min(balance, cap) でサイジングし、残高が大きくなっても
      絶対ポジションサイズを上限制限 → 後半大損失トレードのサイズを抑制 → MaxDD低減

ベースライン(H-042後): PnL=+2197.0 USD / MaxDD=48.2%
採用基準: PnL > +1200 USD かつ MaxDD < 40.0%
"""

import subprocess
import configparser
import json
import os
import re
from datetime import datetime

CONFIG_PATH = "src/config.ini"
BASELINE_PNL = 2197.0
BASELINE_MAXDD = 48.2
ADOPT_PNL_THRESHOLD = 1200.0
ADOPT_MAXDD_THRESHOLD = 40.0

# スイープグリッド
CAP_VALUES = [300.0, 500.0, 750.0, 1000.0, 1500.0, 2000.0, 3000.0]

def read_config():
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_PATH)
    return cfg

def write_config(cfg):
    with open(CONFIG_PATH, 'w') as f:
        cfg.write(f)

def set_cap_sizing(enabled: int, cap_usd: float):
    cfg = read_config()
    cfg['CapSizing']['cap_sizing_enabled'] = str(enabled)
    cfg['CapSizing']['cap_sizing_max_balance_usd'] = str(cap_usd)
    write_config(cfg)

def restore_default():
    cfg = read_config()
    cfg['CapSizing']['cap_sizing_enabled'] = '0'
    cfg['CapSizing']['cap_sizing_max_balance_usd'] = '1000.0'
    write_config(cfg)

def run_backtest():
    result = subprocess.run(
        ["python3", "bot.py"],
        capture_output=True,
        text=True,
        cwd="src"
    )
    return result.stdout + result.stderr

def parse_results(output: str):
    pnl    = None
    max_dd = None
    trades = None

    # PnL パターン（H-042スイープと同様の日本語フォーマット対応）
    for pattern in [
        r"最終損益:\s*([+-]?[\d,]+\.?\d*)\s*\[",
        r"損益累計:([+-]?[\d,]+\.?\d*)\s*\[",
        r"PnL[:\s]+([+-]?\d+\.?\d*)",
        r"total_pnl[:\s]+([+-]?\d+\.?\d*)",
    ]:
        m = re.search(pattern, output)
        if m:
            try:
                pnl = float(m.group(1).replace(',', ''))
                break
            except ValueError:
                pass

    # MaxDD パターン
    for pattern in [
        r"最大ドローダウン率:\s*([0-9]+\.?[0-9]*)\s*\[%\]",
        r"最大ドローダウン率[:\s]+([0-9]+\.?[0-9]*)\s*%",
        r"最大DD[:\s]+([0-9]+\.?[0-9]*)\s*%",
        r"MaxDD[:\s]+([0-9]+\.?[0-9]*)\s*%",
        r"max_drawdown_pct[:\s]+([0-9]+\.?[0-9]*)",
    ]:
        m = re.search(pattern, output)
        if m:
            max_dd = float(m.group(1))
            break

    # trades
    for pattern in [
        r"総数=(\d+)",
        r"Trades:\s*(\d+)",
        r"トレード数[:\s]+(\d+)",
    ]:
        m = re.search(pattern, output)
        if m:
            try:
                trades = int(m.group(1))
                break
            except ValueError:
                pass

    return pnl, max_dd, trades

def main():
    print("=" * 70)
    print("H-044 残高上限サイジング（Cap Balance Sizing）パラメータスイープ")
    print(f"グリッド: cap_max_balance_usd × {CAP_VALUES}")
    print(f"ベースライン(H-042後): PnL=+{BASELINE_PNL} USD / MaxDD={BASELINE_MAXDD}%")
    print(f"採用基準: PnL > +{ADOPT_PNL_THRESHOLD} USD かつ MaxDD < {ADOPT_MAXDD_THRESHOLD}%")
    print("=" * 70)
    print()

    results = []
    total = len(CAP_VALUES)

    for i, cap in enumerate(CAP_VALUES, 1):
        print(f"[{i:2d}/{total}] cap={cap:.0f} USD  実行中...")
        set_cap_sizing(1, cap)
        output = run_backtest()
        pnl, max_dd, trades = parse_results(output)

        if pnl is None or max_dd is None:
            print(f"  ⚠️  パース失敗 — 出力末尾:")
            for line in output.splitlines()[-15:]:
                print(f"    {line.strip()}")
            pnl = pnl if pnl is not None else 0
            max_dd = max_dd if max_dd is not None else 0
            trades = trades if trades is not None else 0

        delta_pnl = pnl - BASELINE_PNL
        delta_dd = max_dd - BASELINE_MAXDD
        adopted = pnl > ADOPT_PNL_THRESHOLD and max_dd < ADOPT_MAXDD_THRESHOLD
        tag = "✅ 採用候補" if adopted else ("⚠️ PnL低" if pnl <= ADOPT_PNL_THRESHOLD else "⚠️ DD高")

        results.append({
            "cap_usd": cap,
            "pnl": pnl,
            "delta_pnl": delta_pnl,
            "max_dd": max_dd,
            "delta_dd": delta_dd,
            "trades": trades or 0,
            "adopted": adopted
        })

        print(f"  → PnL={pnl:.2f} USD (Δ{delta_pnl:+.2f})  MaxDD={max_dd:.2f}% (Δ{delta_dd:+6.2f})  trades={trades}  {tag}")

    restore_default()
    print(f"\n✅ config.ini を元の設定に復元しました")

    # 結果サマリー
    print()
    print("=" * 70)
    print("スキャン結果サマリー")
    print("=" * 70)
    sorted_results = sorted(results, key=lambda x: (-x["pnl"] if x["max_dd"] < ADOPT_MAXDD_THRESHOLD else -9999))
    header = f"{'cap(USD)':>10}  {'PnL(USD)':>10}  {'ΔPNL':>10}  {'MaxDD':>8}  {'ΔDD':>8}  adopted"
    print(header)
    print("-" * 70)
    for r in sorted_results:
        adopted_str = "✅" if r["adopted"] else "❌"
        print(f"{r['cap_usd']:>10.0f}  {r['pnl']:>10.2f}  {r['delta_pnl']:>+10.2f}  {r['max_dd']:>7.2f}%  {r['delta_dd']:>+7.2f}  {adopted_str}")

    # 採用候補
    candidates = [r for r in results if r["adopted"]]
    if candidates:
        best = max(candidates, key=lambda x: x["pnl"])
        print()
        print("🏆 最良採用候補:")
        print(f"   cap={best['cap_usd']:.0f} USD  PnL={best['pnl']:.2f} USD (Δ{best['delta_pnl']:+.2f})  MaxDD={best['max_dd']:.2f}% (Δ{best['delta_dd']:+.2f})")
    else:
        print()
        print("❌ 採用基準を満たすパラメータなし → H-044不採用")

    # 結果保存
    os.makedirs("sweep_results", exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"sweep_results/h044_sweep_{ts}.json"
    with open(fname, "w") as f:
        json.dump({
            "hypothesis": "H-044",
            "description": "残高上限サイジング（Cap Balance Sizing）",
            "baseline_pnl": BASELINE_PNL,
            "baseline_maxdd": BASELINE_MAXDD,
            "adopt_pnl_threshold": ADOPT_PNL_THRESHOLD,
            "adopt_maxdd_threshold": ADOPT_MAXDD_THRESHOLD,
            "results": results,
            "best": best if candidates else None
        }, f, indent=2, ensure_ascii=False)
    print(f"\n📄 結果保存: {fname}")

if __name__ == "__main__":
    main()
