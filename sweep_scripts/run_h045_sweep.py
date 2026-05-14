#!/usr/bin/env python3
"""
H-045: スケールアウト後ブレイクイーブンストップ パラメータスイープ

仮説: スケールアウト（部分利確）発動後、残りポジションのストップを
      エントリー価格に移動 → 以後の大損失トレードを「ほぼゼロ損益」に変換

ベースライン(H-044 cap=1500/taper=0.0): PnL=+2617.0 USD / MaxDD=23.3%
H-045は ON/OFF のみ（パラメータなし）

採用基準: PnL > +2617 USD かつ MaxDD < 23.3%  （両指標改善）
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


def read_config():
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_PATH)
    return cfg

def write_config(cfg):
    with open(CONFIG_PATH, 'w') as f:
        cfg.write(f)

def set_break_even(enabled: int):
    cfg = read_config()
    cfg['ScaleOut']['break_even_after_scale_out'] = str(enabled)
    write_config(cfg)

def restore_default():
    cfg = read_config()
    cfg['ScaleOut']['break_even_after_scale_out'] = '0'
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
    print("=" * 60)
    print("H-045 スケールアウト後ブレイクイーブンストップ 検証")
    print(f"ベースライン: PnL=+{BASELINE_PNL} USD / MaxDD={BASELINE_MAXDD}%")
    print(f"採用基準: PnL > +{BASELINE_PNL} USD かつ MaxDD < {BASELINE_MAXDD}%")
    print("=" * 60)
    print()

    # break_even = 0 (ベースライン確認) と break_even = 1 の2ケースを実行
    cases = [
        (0, "OFF (ベースライン確認)"),
        (1, "ON  (H-045)"),
    ]

    results = []
    for enabled, label in cases:
        print(f"[{'ON' if enabled else 'OFF'}] break_even_after_scale_out={enabled}  ({label})")
        set_break_even(enabled)
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
        adopted = enabled == 1 and pnl > BASELINE_PNL and max_dd < BASELINE_MAXDD
        tag = "✅ 採用" if adopted else ("⚠️ 参考" if enabled == 0 else
                                         ("⚠️ PnL低" if pnl <= BASELINE_PNL else "⚠️ DD高"))
        results.append(dict(enabled=enabled, pnl=pnl, delta_pnl=d_pnl,
                            max_dd=max_dd, delta_dd=d_dd, trades=trades, adopted=adopted))
        print(f"  → PnL={pnl:.2f} (Δ{d_pnl:+.2f})  MaxDD={max_dd:.2f}% (Δ{d_dd:+.2f})  trades={trades}  {tag}")
        print()

    restore_default()
    print(f"✅ config.ini を元の設定（break_even=0）に復元しました")

    # サマリー
    print()
    print("=" * 60)
    print("結果サマリー")
    print("=" * 60)
    be_off = results[0]
    be_on  = results[1]
    print(f"{'':20}  {'OFF':>10}  {'ON (H-045)':>12}")
    print(f"{'PnL (USD)':20}  {be_off['pnl']:>10.2f}  {be_on['pnl']:>12.2f}  (Δ{be_on['delta_pnl']:+.2f})")
    print(f"{'MaxDD (%)':20}  {be_off['max_dd']:>10.2f}  {be_on['max_dd']:>12.2f}  (Δ{be_on['delta_dd']:+.2f})")
    print(f"{'Trades':20}  {be_off['trades']:>10}  {be_on['trades']:>12}")

    adopted = results[1]['adopted']
    print()
    if adopted:
        print("🏆 H-045 採用 → ブレイクイーブンストップ有効化でPnL・MaxDD両方改善")
    else:
        r = results[1]
        reason = "PnLが改善しなかった" if r['pnl'] <= BASELINE_PNL else "MaxDDが改善しなかった"
        print(f"❌ H-045 不採用 → {reason}")

    # 保存
    os.makedirs("sweep_results", exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"sweep_results/h045_sweep_{ts}.json"
    with open(fname, 'w') as f:
        json.dump(dict(hypothesis="H-045",
                       description="スケールアウト後ブレイクイーブンストップ",
                       baseline_pnl=BASELINE_PNL, baseline_maxdd=BASELINE_MAXDD,
                       results=results), f, indent=2, ensure_ascii=False)
    print(f"\n📄 結果保存: {fname}")


if __name__ == "__main__":
    main()
