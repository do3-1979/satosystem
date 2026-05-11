#!/usr/bin/env python3
"""
H-043 DDサイジング パラメータスイープ

dd_sizing_start_pct × dd_sizing_min_ratio のグリッドを通年バックテスト
(2024/01/01 〜 2026/05/08) で評価し、ベースラインと比較する。

【H-043 ロジック】
  - ドローダウンが start_pct% を超えたらポジションサイズを縮小
  - start_pct 〜 (start_pct+20)% の範囲で 1.0 → min_ratio に線形補間
  - (start_pct+20)% 以上では min_ratio 固定

ベースライン(H-042後): PnL=+2197 USD / MaxDD=48.2%
採用基準:
  - 通年 PnL > +1200 USD  (ベースライン比 -45% 以内)
  - 通年 MaxDD < 40%      (ベースライン 48.2% から改善)
  ※ MaxDD改善優先のため、PnL基準をやや緩める（実稼働は通年連続）

使い方:
  cd /home/satoshi/work/satosystem
  python3 run_h043_sweep.py
"""

import subprocess
import sys
import os
import re
import itertools
from datetime import datetime

# ──────────────────────────────────────────────
# グリッド定義
# start_pct: DDがこの%を超えたら縮小開始
# min_ratio: 最大縮小時のサイズ倍率
# ──────────────────────────────────────────────
START_PCTS  = [5.0, 10.0, 15.0, 20.0]
MIN_RATIOS  = [0.25, 0.50, 0.75]

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "src", "config.ini")

# ──────────────────────────────────────────────
# ベースライン（H-042採用後）
# ──────────────────────────────────────────────
BASELINE_PNL   = 2197.0   # USD
BASELINE_MAXDD = 48.2     # %

# ──────────────────────────────────────────────
# ユーティリティ
# ──────────────────────────────────────────────
def read_config():
    with open(CONFIG_PATH, "r") as f:
        return f.read()

def write_config(text):
    with open(CONFIG_PATH, "w") as f:
        f.write(text)

def set_param(text, key, value):
    pattern = rf"^({re.escape(key)}\s*=\s*).*$"
    return re.sub(pattern, rf"\g<1>{value}", text, flags=re.MULTILINE)

def run_backtest():
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, "bot.py"],
        cwd=os.path.join(os.path.dirname(__file__), "src"),
        capture_output=True, text=True,
        env=env,
        timeout=600,
    )
    return result.stdout + result.stderr

def parse_result(output):
    pnl = maxdd = trades = None
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
        r"最大ドローダウン率[:\s]+([0-9]+\.?[0-9]*)\s*%",
        r"MaxDD[:\s]+([0-9]+\.?[0-9]*)\s*%",
    ]:
        m = re.search(pattern, output)
        if m:
            maxdd = float(m.group(1))
            break
    m = re.search(r"総数=(\d+)", output)
    if m:
        trades = int(m.group(1))
    return pnl, maxdd, trades

def fmt(v, decimals=2):
    return "N/A" if v is None else f"{v:.{decimals}f}"

def fmt_diff(v, decimals=2):
    if v is None:
        return "N/A"
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.{decimals}f}"

# ──────────────────────────────────────────────
# メイン
# ──────────────────────────────────────────────
def main():
    original_config = read_config()
    total = len(START_PCTS) * len(MIN_RATIOS)
    print("=" * 70)
    print("H-043 DDサイジング パラメータスイープ")
    print(f"グリッド: start_pct×{START_PCTS} / min_ratio×{MIN_RATIOS}")
    print(f"ベースライン(H-042後): PnL=+{BASELINE_PNL} USD / MaxDD={BASELINE_MAXDD}%")
    print(f"採用基準: PnL > +1200 USD かつ MaxDD < 40.0%")
    print("=" * 70)

    results = []
    idx = 0

    try:
        for start_pct, min_ratio in itertools.product(START_PCTS, MIN_RATIOS):
            idx += 1
            label = f"[{idx:2d}/{total}] start={start_pct:.0f}%  min_ratio={min_ratio:.2f}"
            print(f"\n{label}  実行中...", flush=True)

            try:
                cfg = read_config()
                cfg = set_param(cfg, "dd_sizing_enabled", "1")
                cfg = set_param(cfg, "dd_sizing_start_pct", str(start_pct))
                cfg = set_param(cfg, "dd_sizing_min_ratio", str(min_ratio))
                write_config(cfg)

                out = run_backtest()
                pnl, maxdd, trades = parse_result(out)

                pnl_diff   = (pnl - BASELINE_PNL)   if pnl   is not None else None
                maxdd_diff = (maxdd - BASELINE_MAXDD) if maxdd is not None else None
                ok_pnl  = (pnl   is not None and pnl   > 1200)
                ok_dd   = (maxdd is not None and maxdd < 40.0)
                adopted = ok_pnl and ok_dd

                tag = "✅ ADOPTED" if adopted else ("⚠️ PnL低" if not ok_pnl else "⚠️ DD高")
                print(
                    f"  → PnL={fmt(pnl)} USD (Δ{fmt_diff(pnl_diff):>8})  "
                    f"MaxDD={fmt(maxdd)}% (Δ{fmt_diff(maxdd_diff):>7})  "
                    f"trades={trades}  {tag}"
                )

                results.append({
                    "start_pct": start_pct,
                    "min_ratio": min_ratio,
                    "pnl": pnl,
                    "pnl_diff": pnl_diff,
                    "maxdd": maxdd,
                    "maxdd_diff": maxdd_diff,
                    "trades": trades,
                    "adopted": adopted,
                })

            except subprocess.TimeoutExpired:
                print("  → ⏰ TIMEOUT")
            except Exception as e:
                print(f"  → ❌ ERROR: {e}")

    finally:
        write_config(original_config)
        print("\n✅ config.ini を元の設定に復元しました")

    # ──────────────────────────────────────────────
    # サマリー
    # ──────────────────────────────────────────────
    print()
    print("=" * 70)
    print("スキャン結果サマリー")
    print("=" * 70)
    valid = [r for r in results if r["pnl"] is not None and r["maxdd"] is not None]
    valid.sort(key=lambda r: (-(r["adopted"]), r["maxdd"], -r["pnl"]))

    print(f"{'start':>7} {'min_r':>6}  {'PnL(USD)':>10}  {'ΔPNL':>9}  {'MaxDD':>7}  {'ΔDD':>7}  adopted")
    print("-" * 70)
    for r in valid:
        mark = "✅" if r["adopted"] else "❌"
        print(
            f"  {r['start_pct']:>4.0f}%  {r['min_ratio']:>4.2f}  "
            f"{fmt(r['pnl']):>10}  {fmt_diff(r['pnl_diff']):>9}  "
            f"{fmt(r['maxdd']):>7}%  {fmt_diff(r['maxdd_diff']):>7}  {mark}"
        )

    adopted_list = [r for r in valid if r["adopted"]]
    if adopted_list:
        best = min(adopted_list, key=lambda r: r["maxdd"])
        print(f"\n✅ 採用候補 ({len(adopted_list)}件) 最良 → "
              f" start={best['start_pct']:.0f}% / min_ratio={best['min_ratio']:.2f}"
              f"  PnL={fmt(best['pnl'])} / MaxDD={fmt(best['maxdd'])}%")
    else:
        print("\n❌ 採用基準を満たすパラメータなし → H-043不採用")

    # 結果JSON保存
    import json
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs("sweep_results", exist_ok=True)
    out_path = f"sweep_results/h043_sweep_{ts}.json"
    with open(out_path, "w") as f:
        json.dump({"results": valid, "baseline": {"pnl": BASELINE_PNL, "maxdd": BASELINE_MAXDD}}, f, indent=2)
    print(f"\n📄 結果保存: {out_path}")

if __name__ == "__main__":
    main()
