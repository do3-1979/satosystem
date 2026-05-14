"""
H-040 スキャン: ATRブレイクアウト強度フィルター（フォールスブレイクアウト排除）
仮説: ブレイク幅 < ATR×ratio の「弱いブレイク」はフォールスブレイクアウト → 排除で勝率改善

評価: 通年（2024/01/01〜2026/05/08）
採用基準: MaxDD < 65% かつ PnL > +1,200（ベースライン+1571/75.7%比で改善）
"""
import configparser, subprocess, re
from datetime import datetime
from pathlib import Path

WORKSPACE   = Path(__file__).parent
CONFIG_PATH = WORKSPACE / "src/config.ini"

YEAR_START = "2024/01/01 00:00"
YEAR_END   = "2026/05/08 23:59"

# スキャン範囲: ATR × min_ratio（0.0 = フィルター無効に相当）
RATIOS = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.7, 1.0]
ATR_PERIOD = 14  # 固定


def apply_config(ratio):
    c = configparser.ConfigParser()
    c.read(CONFIG_PATH)
    c['Period']['start_time'] = YEAR_START
    c['Period']['end_time']   = YEAR_END
    if ratio == 0.0:
        c['EntryFilters']['atr_breakout_filter_enabled'] = '0'
        c['EntryFilters']['atr_breakout_min_ratio']      = '0.3'
    else:
        c['EntryFilters']['atr_breakout_filter_enabled'] = '1'
        c['EntryFilters']['atr_breakout_min_ratio']      = str(ratio)
        c['EntryFilters']['atr_breakout_period']         = str(ATR_PERIOD)
    with open(CONFIG_PATH, 'w') as f:
        c.write(f)


def restore_config():
    c = configparser.ConfigParser()
    c.read(CONFIG_PATH)
    c['Period']['start_time'] = '2026/01/01 00:00'
    c['Period']['end_time']   = '2026/03/31 23:59'
    c['EntryFilters']['atr_breakout_filter_enabled'] = '0'
    with open(CONFIG_PATH, 'w') as f:
        c.write(f)


def run_backtest():
    r = subprocess.run(
        ["python3", "bot.py"],
        cwd=WORKSPACE / "src",
        capture_output=True, text=True, timeout=300
    )
    return r.stdout + r.stderr


def parse(output):
    pnl, maxdd, trades = None, None, None
    m = re.search(r'最終損益:\s*([+-]?\d+\.?\d*)', output)
    if m: pnl = float(m.group(1))
    m = re.search(r'最大ドローダウン率:\s*([0-9]+\.?[0-9]*)', output)
    if m: maxdd = float(m.group(1))
    m = re.search(r'Trades:\s*(\d+)', output)
    if m: trades = int(m.group(1))
    return pnl, maxdd, trades


def main():
    print("=" * 68)
    print("H-040 スキャン: ATRブレイクアウト強度フィルター")
    print(f"ATR期間={ATR_PERIOD}、ratio=ブレイク幅/ATR最小比率")
    print("ベースライン(ratio=0.0): PnL=+1571 / MaxDD=75.7%")
    print("採用基準: MaxDD < 65% かつ PnL > +1,200")
    print("=" * 68)

    results = []
    for i, ratio in enumerate(RATIOS, 1):
        apply_config(ratio)
        label = f"ratio={ratio:.1f}" if ratio > 0 else "無効(baseline)"
        print(f"\n[{i}/{len(RATIOS)}] {label}  ", end="", flush=True)

        out = run_backtest()
        pnl, maxdd, trades = parse(out)
        eff = pnl / maxdd if maxdd and maxdd > 0 else 0
        ok  = maxdd is not None and maxdd < 65.0 and pnl is not None and pnl > 1200.0
        flag = "✅" if ok else ""
        print(f"PnL={pnl:+.0f}  MaxDD={maxdd:.1f}%  PnL/DD={eff:.1f}  trades={trades}  {flag}")

        results.append({'ratio': ratio, 'label': label,
                        'pnl': pnl, 'maxdd': maxdd, 'trades': trades,
                        'eff': eff, 'pass': ok})

    restore_config()

    print("\n\n" + "=" * 68)
    print("H-040 スキャン結果サマリー")
    print("=" * 68)
    print(f"{'条件':<20} {'PnL':>10} {'MaxDD':>8} {'PnL/DD':>8} {'Trades':>7}  判定")
    print("-" * 68)
    for r in results:
        pnl_s = f"{r['pnl']:+.0f}" if r['pnl'] is not None else "N/A"
        dd_s  = f"{r['maxdd']:.1f}%" if r['maxdd'] is not None else "N/A"
        ef_s  = f"{r['eff']:.1f}" if r['eff'] else "N/A"
        tr_s  = str(r['trades']) if r['trades'] is not None else "N/A"
        flag  = "✅" if r['pass'] else ""
        print(f"{r['label']:<20} {pnl_s:>10} {dd_s:>8} {ef_s:>8} {tr_s:>7}  {flag}")

    ok_list = [r for r in results if r['pass']]
    if ok_list:
        best = max(ok_list, key=lambda r: r['eff'])
        print(f"\n採用候補: {len(ok_list)}件")
        print(f"  最高効率: {best['label']}  PnL={best['pnl']:+.0f}  MaxDD={best['maxdd']:.1f}%  PnL/DD={best['eff']:.1f}")
    else:
        print("\n採用基準（MaxDD<65% かつ PnL>+1,200）を満たす候補なし → H-040 見送り")

    print(f"\n完了: {datetime.now():%Y-%m-%d %H:%M:%S}")


if __name__ == "__main__":
    main()
