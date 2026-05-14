"""
H-056: スケールイン（追加エントリー）最適化スイープ
スケールアウト後にトレンド継続確認でポジション追加

ベースライン: PnL=+2617, MaxDD=23.30%, Trades=43
採用基準: PnL > +2617 AND MaxDD < 23.30%
四半期基準: > +2265.44 USD (ベースライン+2384.67 × 0.95)
"""

import subprocess
import re
import itertools

TRIGGER_MULTIPLIERS = [1.0, 1.5, 2.0, 2.5]
QUANTITY_PCTS       = [0.3, 0.5]

CONFIG_PATH = "src/config.ini"
BASELINE_PNL   = 2617
BASELINE_MAXDD = 23.30

def read_config():
    with open(CONFIG_PATH, "r") as f:
        return f.read()

def write_config(content):
    with open(CONFIG_PATH, "w") as f:
        f.write(content)

def set_param(content, key, value):
    pattern = rf"^({key}\s*=\s*).*$"
    if not re.search(pattern, content, flags=re.MULTILINE):
        raise ValueError(f"キー '{key}' がconfig.iniに見つかりません")
    return re.sub(pattern, rf"\g<1>{value}", content, flags=re.MULTILINE)

def run_backtest():
    result = subprocess.run(
        ["python3", "bot.py"],
        cwd="src",
        capture_output=True,
        text=True,
        timeout=300,
    )
    output = result.stdout + result.stderr
    pnl_m    = re.search(r"最終損益:\s*([+-]?[\d,]+)\s*\[BTC", output)
    dd_m     = re.search(r"最大ドローダウン率:\s*([\d.]+)\s*\[%\]", output)
    trades_m = re.search(r"Trades:\s*(\d+)", output)
    pnl    = int(pnl_m.group(1).replace(",", "")) if pnl_m    else None
    dd     = float(dd_m.group(1))                  if dd_m    else None
    trades = int(trades_m.group(1))                if trades_m else None
    return pnl, dd, trades

def main():
    original = read_config()

    # 通年期間が設定されているか確認
    if "2026/01/01" in original and "2026/03/31" in original:
        raise RuntimeError("config.iniの期間が短期間(2026/01-03)です。通年(2024/01/01〜2026/05/08)に修正してからスイープを実行してください。")

    combos = list(itertools.product(TRIGGER_MULTIPLIERS, QUANTITY_PCTS))
    total  = len(combos)
    print(f"\n=== H-056 ScaleIn スイープ ({total}パターン) ===")
    print(f"ベースライン: PnL=+{BASELINE_PNL}, MaxDD={BASELINE_MAXDD}%")
    print(f"条件: スケールアウト後 (scale_out_done=True) かつ trigger×ATR到達後に追加\n")
    print(f"{'trigger':>8} {'qty_pct':>8} {'PnL':>10} {'MaxDD':>8} {'Trades':>7}  判定")
    print("-" * 68)

    results = []
    try:
        for i, (trigger, qty_pct) in enumerate(combos, 1):
            config = original
            config = set_param(config, "scale_in_enabled",            "1")
            config = set_param(config, "scale_in_trigger_multiplier", trigger)
            config = set_param(config, "scale_in_quantity_pct",       qty_pct)
            write_config(config)

            pnl, dd, trades = run_backtest()

            if pnl is None or dd is None:
                verdict = "❌ エラー"
            elif pnl > BASELINE_PNL and dd < BASELINE_MAXDD:
                verdict = "✅ 採用候補"
            elif pnl > BASELINE_PNL:
                verdict = "⚠️ PnL改善(DD悪化)"
            elif dd < BASELINE_MAXDD:
                verdict = "⚠️ DD改善(PnL悪化)"
            else:
                verdict = "❌"

            print(f"{trigger:>8.1f} {qty_pct:>8.1f} {pnl:>+10,} {dd:>7.2f}%  {trades:>6}    {verdict}  ({i}/{total})")
            results.append((trigger, qty_pct, pnl, dd, trades, verdict))

    finally:
        write_config(original)
        print("\n設定を元に戻しました")

    valid = [(t, q, p, d, tr, v) for t, q, p, d, tr, v in results
             if p is not None and p > BASELINE_PNL and d < BASELINE_MAXDD]
    print(f"\n=== 採用候補 ({len(valid)}件) ===")
    if valid:
        for t, q, p, d, tr, v in sorted(valid, key=lambda x: x[2], reverse=True):
            print(f"  trigger={t:.1f}, qty_pct={q:.1f}  →  PnL=+{p:,}, MaxDD={d:.2f}%, Trades={tr}")
        print(f"\n次: 採用候補について四半期テスト実行（基準: >+2265.44 USD）")
    else:
        print("  なし（ベースライン超えパターン不在）")

if __name__ == "__main__":
    main()
