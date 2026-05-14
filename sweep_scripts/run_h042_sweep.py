#!/usr/bin/env python3
"""
H-042 スケールアウト パラメータスイープ（再設計版）

trigger_multiplier × quantity_pct のグリッドを通年バックテスト
(2024/01/01 〜 2026/05/08) で評価し、ベースラインと比較する。

【再設計】トリガー: 価格移動 >= entry_atr × trigger_multiplier
  - 旧実装: _entry_risk_usd が常に0 → スケールアウト未発動
  - 新実装: entry_record['entry_atr'] を直接使用 → ATRベース価格移動トリガー

ベースライン: PnL=+1571 USD / MaxDD=75.7% (scale_out_enabled=0)
採用基準:
  - 通年 PnL > +1200 USD  (ベースライン比 -25% 以内)
  - 通年 MaxDD < 65%

使い方:
  cd /home/satoshi/work/satosystem
  python3 run_h042_sweep.py
"""

import subprocess
import sys
import os
import re
import itertools
import json
from datetime import datetime

# ──────────────────────────────────────────────
# グリッド定義（ATRベース再設計版）
# trigger_multiplier: entry_atr の何倍の価格移動でスケールアウト
# BTC 4H ATR ≈ 1000〜3000 USD 程度
# 例) ATR=2000, trigger=2.0 → 4000 USD 価格移動でスケールアウト
# ──────────────────────────────────────────────
TRIGGER_MULTIPLIERS = [1.0, 1.5, 2.0, 3.0, 4.0]
QUANTITY_PCTS       = [0.25, 0.50, 0.75]

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "src", "config.ini")

# ──────────────────────────────────────────────
# ベースライン（scale_out_enabled=0 の通年結果）
# ──────────────────────────────────────────────
BASELINE_PNL   = 1571.0   # USD
BASELINE_MAXDD = 75.7     # %

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
    """config.ini の [ScaleOut] セクションのキーを更新"""
    pattern = rf"^({re.escape(key)}\s*=\s*).*$"
    replacement = rf"\g<1>{value}"
    new_text = re.sub(pattern, replacement, text, flags=re.MULTILINE)
    if key not in new_text:
        raise ValueError(f"キー '{key}' が config.ini に見つかりません")
    return new_text

def run_backtest():
    """通年バックテストを実行して結果を返す"""
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    result = subprocess.run(
        [sys.executable, "bot.py"],
        cwd=os.path.join(os.path.dirname(__file__), "src"),
        capture_output=True, text=True,
        env=env,
        timeout=600,
    )
    output = result.stdout + result.stderr
    return output

def parse_result(output):
    """バックテスト出力から PnL と MaxDD を抽出"""
    pnl    = None
    maxdd  = None
    trades = None

    # 損益累計 (例: "最終損益: 1571 [BTC/USD]" / "損益累計:1571.23 [BTC/USDT]" )
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

    # MaxDD — ドローダウン率 (例: "最大ドローダウン率: 75.70 [%]" / "MaxDD: 75.7%")
    for pattern in [
        r"最大ドローダウン率:\s*([0-9]+\.?[0-9]*)\s*\[%\]",
        r"最大ドローダウン率[:\s]+([0-9]+\.?[0-9]*)\s*%",
        r"最大DD[:\s]+([0-9]+\.?[0-9]*)\s*%",
        r"MaxDD[:\s]+([0-9]+\.?[0-9]*)\s*%",
        r"max_drawdown_pct[:\s]+([0-9]+\.?[0-9]*)",
    ]:
        m = re.search(pattern, output)
        if m:
            maxdd = float(m.group(1))
            break

    # trades (例: "トレード統計: 総数=43,")
    for pattern in [
        r"総数=(\d+)",
        r"トレード数[:\s]+(\d+)",
        r"trades[:\s]+(\d+)",
        r"Total trades[:\s]+(\d+)",
    ]:
        m = re.search(pattern, output)
        if m:
            try:
                trades = int(m.group(1))
                break
            except ValueError:
                pass

    return pnl, maxdd, trades

def fmt(v, decimals=2):
    if v is None:
        return "N/A"
    return f"{v:.{decimals}f}"

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

    # まず scale_out_enabled=0 のベースラインを実測する
    print("=" * 70)
    print("H-042 スケールアウト パラメータスイープ")
    print(f"グリッド: trigger×{TRIGGER_MULTIPLIERS} / qty×{QUANTITY_PCTS}")
    print(f"ベースライン参照: PnL=+{BASELINE_PNL} USD / MaxDD={BASELINE_MAXDD}%")
    print("=" * 70)

    results = []
    total = len(TRIGGER_MULTIPLIERS) * len(QUANTITY_PCTS)
    idx   = 0

    for trigger, qty in itertools.product(TRIGGER_MULTIPLIERS, QUANTITY_PCTS):
        idx += 1
        label = f"[{idx:2d}/{total}] trigger={trigger:.1f}x  qty={qty:.0%}"
        print(f"\n{label}  実行中...", flush=True)

        try:
            cfg = read_config()
            cfg = set_param(cfg, "scale_out_enabled", "1")
            cfg = set_param(cfg, "scale_out_trigger_multiplier", str(trigger))
            cfg = set_param(cfg, "scale_out_quantity_pct", str(qty))
            write_config(cfg)

            out = run_backtest()
            pnl, maxdd, trades = parse_result(out)

            pnl_diff = (pnl - BASELINE_PNL) if pnl is not None else None
            ok_pnl   = (pnl is not None and pnl > 1200)
            ok_dd    = (maxdd is not None and maxdd < 65.0)
            adopted  = ok_pnl and ok_dd

            tag = "✅ ADOPTED" if adopted else "⚠️ NG"
            print(
                f"  → PnL={fmt(pnl)} USD (Δ{fmt_diff(pnl_diff):>8})  "
                f"MaxDD={fmt(maxdd)}%  trades={trades}  {tag}"
            )

            results.append({
                "trigger": trigger,
                "qty_pct": qty,
                "pnl": pnl,
                "pnl_diff": pnl_diff,
                "maxdd": maxdd,
                "trades": trades,
                "ok_pnl": ok_pnl,
                "ok_dd": ok_dd,
                "adopted": adopted,
            })

        except Exception as e:
            print(f"  → ERROR: {e}")
            results.append({
                "trigger": trigger, "qty_pct": qty,
                "pnl": None, "pnl_diff": None, "maxdd": None,
                "trades": None, "adopted": False, "error": str(e),
            })
        finally:
            write_config(original_config)

    # ──────────────────────────────────────────────
    # サマリーテーブル
    # ──────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("スキャン結果サマリー")
    print("=" * 70)
    print(f"{'trigger':>8} {'qty':>6} {'PnL(USD)':>10} {'Δ vs BL':>10} {'MaxDD':>7} {'adopted':>8}")
    print("-" * 70)

    for r in sorted(results, key=lambda x: -(x["pnl"] or -9999)):
        adopted_str = "✅" if r["adopted"] else "❌"
        print(
            f"{r['trigger']:>8.1f} {r['qty_pct']:>6.0%} "
            f"{fmt(r['pnl']):>10} {fmt_diff(r.get('pnl_diff')):>10} "
            f"{fmt(r['maxdd']):>7}% {adopted_str:>8}"
        )

    adopted_list = [r for r in results if r["adopted"]]
    print()
    if adopted_list:
        best = max(adopted_list, key=lambda x: (x["pnl"] or -9999))
        print(f"✅ 採用候補 ({len(adopted_list)}件) 最良 →  "
              f"trigger={best['trigger']}x / qty={best['qty_pct']:.0%}  "
              f"PnL={fmt(best['pnl'])} / MaxDD={fmt(best['maxdd'])}%")
    else:
        print("❌ 採用基準を満たすパラメータなし → H-042不採用")

    # JSON保存
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(os.path.dirname(__file__), f"sweep_results/h042_sweep_{ts}.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({"results": results, "baseline": {"pnl": BASELINE_PNL, "maxdd": BASELINE_MAXDD}}, f, indent=2, ensure_ascii=False)
    print(f"\n📄 結果保存: {out_path}")

    return results

if __name__ == "__main__":
    results = main()
