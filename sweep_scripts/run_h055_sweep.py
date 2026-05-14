"""
H-055: スケールアウト最適化スイープ
scale_out_trigger_multiplier × scale_out_quantity_pct の全組み合わせを通年検証

ベースライン: PnL=+2617, MaxDD=23.30%, Trades=43
採用基準: PnL > +2617 AND MaxDD < 23.30%
"""

import subprocess
import re
import itertools

# スイープ対象パラメータ
TRIGGER_MULTIPLIERS = [0.5, 0.7, 1.0, 1.5, 2.0, 2.5]
QUANTITY_PCTS       = [0.3, 0.5, 0.7]

CONFIG_PATH = "src/config.ini"
BASELINE_PNL = 2617
BASELINE_MAXDD = 23.30

def read_config():
    with open(CONFIG_PATH, "r") as f:
        return f.read()

def write_config(content):
    with open(CONFIG_PATH, "w") as f:
        f.write(content)

def set_param(content, key, value):
    """config.ini 内の key = <value> を置き換える"""
    pattern = rf"^({key}\s*=\s*).*$"
    replacement = rf"\g<1>{value}"
    if not re.search(pattern, content, flags=re.MULTILINE):
        raise ValueError(f"キー '{key}' がconfig.iniに見つかりません")
    return re.sub(pattern, replacement, content, flags=re.MULTILINE)

def run_backtest():
    result = subprocess.run(
        ["python3", "bot.py"],
        cwd="src",
        capture_output=True,
        text=True,
        timeout=300,
    )
    output = result.stdout + result.stderr

    pnl_match   = re.search(r"最終損益:\s*([+-]?[\d,]+)\s*\[BTC", output)
    dd_match    = re.search(r"最大ドローダウン率:\s*([\d.]+)\s*\[%\]", output)
    trades_match = re.search(r"Trades:\s*(\d+)", output)

    pnl    = int(pnl_match.group(1).replace(",", "")) if pnl_match else None
    dd     = float(dd_match.group(1))                  if dd_match  else None
    trades = int(trades_match.group(1))                if trades_match else None

    return pnl, dd, trades

def main():
    original_config = read_config()

    combos = list(itertools.product(TRIGGER_MULTIPLIERS, QUANTITY_PCTS))
    total = len(combos)
    print(f"\n=== H-055 ScaleOut最適化スイープ ({total}パターン) ===")
    print(f"ベースライン: PnL=+{BASELINE_PNL}, MaxDD={BASELINE_MAXDD}%\n")
    print(f"{'trigger':>8} {'qty_pct':>8} {'PnL':>10} {'MaxDD':>8} {'Trades':>7}  判定")
    print("-" * 65)

    results = []

    try:
        for i, (trigger, qty_pct) in enumerate(combos, 1):
            config = original_config
            config = set_param(config, "scale_out_trigger_multiplier", trigger)
            config = set_param(config, "scale_out_quantity_pct", qty_pct)
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

            print(f"{trigger:>8.1f} {qty_pct:>8.1f} {pnl:>+10,} {dd:>7.2f}%  {trades:>6}    {verdict}")
            results.append((trigger, qty_pct, pnl, dd, trades, verdict))

    finally:
        write_config(original_config)
        print("\n設定を元に戻しました")

    # ベスト結果サマリ
    valid = [(t, q, p, d, tr, v) for t, q, p, d, tr, v in results if p is not None and p > BASELINE_PNL and d < BASELINE_MAXDD]
    print(f"\n=== 採用候補 ({len(valid)}件) ===")
    if valid:
        valid_sorted = sorted(valid, key=lambda x: x[2], reverse=True)
        for t, q, p, d, tr, v in valid_sorted:
            print(f"  trigger={t:.1f}, qty_pct={q:.1f}  →  PnL=+{p:,}, MaxDD={d:.2f}%, Trades={tr}")
    else:
        print("  なし（ベースライン超えパラメータ不在）")

if __name__ == "__main__":
    main()
