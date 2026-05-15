"""
H-039 スキャン: ドンチャンチャネル期間最適化
現状: buy_term=25, sell_term=25
仮説: 期間を短縮するとブレイクアウト頻度が増加し、
      より早いエントリーでPnL改善またはDD分散が見込める

評価: 通年（2024/01/01〜2026/05/08）
採用基準: MaxDD < 65% かつ PnL > +1,200（ベースライン+1571/75.7%比で改善）
"""
import configparser, subprocess, re
from datetime import datetime
from pathlib import Path

WORKSPACE   = Path(__file__).parent.parent
CONFIG_PATH = WORKSPACE / "src/config.ini"

YEAR_START = "2024/01/01 00:00"
YEAR_END   = "2026/05/08 23:59"

# buy_term と sell_term を同期スキャン（対称ブレイクアウト）
TERMS = [10, 15, 18, 20, 22, 25, 30, 35]  # 25=現状


def apply_config(term):
    c = configparser.ConfigParser()
    c.read(CONFIG_PATH)
    c['Period']['start_time']    = YEAR_START
    c['Period']['end_time']      = YEAR_END
    c['Strategy']['donchian_buy_term']  = str(term)
    c['Strategy']['donchian_sell_term'] = str(term)
    with open(CONFIG_PATH, 'w') as f:
        c.write(f)


def restore_config():
    c = configparser.ConfigParser()
    c.read(CONFIG_PATH)
    c['Period']['start_time']    = '2026/01/01 00:00'
    c['Period']['end_time']      = '2026/03/31 23:59'
    c['Strategy']['donchian_buy_term']  = '25'
    c['Strategy']['donchian_sell_term'] = '25'
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
    print("H-039 スキャン: ドンチャン期間最適化（buy_term = sell_term）")
    print("ベースライン(term=25): PnL=+1571 / MaxDD=75.7% / Trades=43")
    print("採用基準: MaxDD < 65% かつ PnL > +1,200")
    print("=" * 68)

    results = []
    for i, term in enumerate(TERMS, 1):
        apply_config(term)
        label = f"term={term}" + (" (現状)" if term == 25 else "")
        print(f"\n[{i}/{len(TERMS)}] {label}  ", end="", flush=True)

        out = run_backtest()
        pnl, maxdd, trades = parse(out)
        eff = pnl / maxdd if maxdd and maxdd > 0 else 0
        ok  = maxdd is not None and maxdd < 65.0 and pnl is not None and pnl > 1200.0
        flag = "✅" if ok else ""
        print(f"PnL={pnl:+.0f}  MaxDD={maxdd:.1f}%  PnL/DD={eff:.1f}  trades={trades}  {flag}")

        results.append({'term': term, 'label': label,
                        'pnl': pnl, 'maxdd': maxdd, 'trades': trades,
                        'eff': eff, 'pass': ok})

    restore_config()

    print("\n\n" + "=" * 68)
    print("H-039 スキャン結果サマリー")
    print("=" * 68)
    print(f"{'条件':<18} {'PnL':>10} {'MaxDD':>8} {'PnL/DD':>8} {'Trades':>7}  判定")
    print("-" * 68)
    for r in results:
        pnl_s = f"{r['pnl']:+.0f}" if r['pnl'] is not None else "N/A"
        dd_s  = f"{r['maxdd']:.1f}%" if r['maxdd'] is not None else "N/A"
        ef_s  = f"{r['eff']:.1f}" if r['eff'] else "N/A"
        tr_s  = str(r['trades']) if r['trades'] is not None else "N/A"
        flag  = "✅" if r['pass'] else ""
        print(f"{r['label']:<18} {pnl_s:>10} {dd_s:>8} {ef_s:>8} {tr_s:>7}  {flag}")

    ok_list = [r for r in results if r['pass']]
    if ok_list:
        best = max(ok_list, key=lambda r: r['eff'])
        print(f"\n採用候補: {len(ok_list)}件")
        print(f"  最高効率: {best['label']}  PnL={best['pnl']:+.0f}  MaxDD={best['maxdd']:.1f}%  PnL/DD={best['eff']:.1f}")
    else:
        print("\n採用基準（MaxDD<65% かつ PnL>+1,200）を満たす候補なし → H-039 見送り")

    print(f"\n完了: {datetime.now():%Y-%m-%d %H:%M:%S}")


if __name__ == "__main__":
    main()
