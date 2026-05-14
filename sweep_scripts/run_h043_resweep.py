"""
H-043 再スイープ（H-044採用後ベースラインで評価）
PnL率分析から：低資本期（残高100-450 USD）に大損失率が集中
→ DD早期縮小（start_pct=5-10%）が有効かを再検証

ベースライン: PnL=+2617 USD, MaxDD=23.3%（H-044 cap=1500採用後）
採用基準: PnL>+2617 かつ MaxDD<23.3%
"""
import subprocess, re, itertools, json
from datetime import datetime

BASE_CONFIG = 'src/config.ini'

BASELINE_PNL = 2617.0
BASELINE_DD  = 23.3

def read_config():
    with open(BASE_CONFIG) as f:
        return f.read()

def write_config(content):
    with open(BASE_CONFIG, 'w') as f:
        f.write(content)

def run_backtest(config_content: str) -> dict:
    orig = read_config()
    write_config(config_content)
    try:
        result = subprocess.run(
            ['python3', 'bot.py'],
            cwd='src',
            capture_output=True,
            text=True,
            timeout=300
        )
    finally:
        write_config(orig)

    output = result.stderr + result.stdout
    pnl_m   = re.search(r'最終損益:\s*([+-]?[\d,]+)\s*\[BTC', output)
    dd_m    = re.search(r'最大ドローダウン率:\s*([\d.]+)\s*\[%\]', output)
    trade_m = re.search(r'Trades:\s*(\d+)', output)

    return {
        'pnl':    float(pnl_m.group(1).replace(',', ''))  if pnl_m   else None,
        'max_dd': float(dd_m.group(1))                    if dd_m    else None,
        'trades': int(trade_m.group(1))                   if trade_m else None,
        'raw':    output[-2000:],
    }

def make_config(start_pct: float, min_ratio: float) -> str:
    content = read_config()
    content = re.sub(r'start_time\s*=.*',             'start_time = 2024/01/01 00:00', content)
    content = re.sub(r'end_time\s*=.*',               'end_time = 2026/05/08 23:59',   content)
    content = re.sub(r'dd_sizing_enabled\s*=.*',      'dd_sizing_enabled = 1',         content)
    content = re.sub(r'dd_sizing_start_pct\s*=.*',    f'dd_sizing_start_pct = {start_pct}', content)
    content = re.sub(r'dd_sizing_min_ratio\s*=.*',    f'dd_sizing_min_ratio = {min_ratio}', content)
    content = re.sub(r'adx_upper_filter_enabled\s*=.*', 'adx_upper_filter_enabled = 0', content)
    return content

# ベースライン計測（H-043無効、H-044のみ）
print("=" * 70)
print("H-043 再スイープ（H-044採用後ベースライン）")
print(f"採用基準: PnL > {BASELINE_PNL} USD かつ MaxDD < {BASELINE_DD}%")
print("=" * 70)

print("\n[BASE] H-043=OFF, H-044=ON（ベースライン確認）...")
base_config = read_config()
base_config_mod = re.sub(r'start_time\s*=.*', 'start_time = 2024/01/01 00:00', base_config)
base_config_mod = re.sub(r'end_time\s*=.*',   'end_time = 2026/05/08 23:59',   base_config_mod)
base_config_mod = re.sub(r'adx_upper_filter_enabled\s*=.*', 'adx_upper_filter_enabled = 0', base_config_mod)
base_result = run_backtest(base_config_mod)
print(f"  PnL={base_result['pnl']:+.2f} USD  MaxDD={base_result['max_dd']:.1f}%  Trades={base_result['trades']}")

# パラメータ組み合わせ
# start_pct: DDが何%を超えたら縮小開始
# min_ratio: 最大縮小後の倍率（0.25=25%サイズ, 0.5=50%, 0.75=75%）
START_PCTS  = [5.0, 8.0, 10.0, 12.0, 15.0]
MIN_RATIOS  = [0.25, 0.40, 0.50, 0.75]

results = []
total = len(START_PCTS) * len(MIN_RATIOS)
done = 0

print(f"\n{total}パターンをスイープ中...\n")
print(f"{'start%':>7}  {'min_r':>6}  {'PnL':>10}  {'MaxDD':>7}  {'Trades':>7}  {'判定'}")
print("-" * 55)

for start_pct, min_ratio in itertools.product(START_PCTS, MIN_RATIOS):
    cfg = make_config(start_pct, min_ratio)
    r = run_backtest(cfg)
    done += 1

    pnl_ok = r['pnl'] is not None and r['pnl'] > BASELINE_PNL
    dd_ok  = r['max_dd'] is not None and r['max_dd'] < BASELINE_DD
    judge  = "✅ PASS" if (pnl_ok and dd_ok) else ("⚠️ PnL+" if pnl_ok else ("⚠️ DD-" if dd_ok else "❌"))

    results.append({
        'start_pct': start_pct, 'min_ratio': min_ratio,
        'pnl': r['pnl'], 'max_dd': r['max_dd'], 'trades': r['trades'],
        'pass': pnl_ok and dd_ok
    })

    pnl_str  = f"{r['pnl']:+.2f}" if r['pnl']    is not None else "ERR"
    dd_str   = f"{r['max_dd']:.1f}%" if r['max_dd'] is not None else "ERR"
    tr_str   = str(r['trades']) if r['trades'] is not None else "ERR"
    print(f"{start_pct:>7.1f}  {min_ratio:>6.2f}  {pnl_str:>10}  {dd_str:>7}  {tr_str:>7}  {judge}  ({done}/{total})")

# サマリー
pass_results = [r for r in results if r['pass']]
print("\n" + "=" * 70)
print(f"合格パターン: {len(pass_results)}/{total}")
if pass_results:
    best = max(pass_results, key=lambda x: x['pnl'])
    print(f"\n最良パターン:")
    print(f"  start_pct={best['start_pct']:.1f}%  min_ratio={best['min_ratio']:.2f}")
    print(f"  PnL={best['pnl']:+.2f} USD (Δ{best['pnl']-BASELINE_PNL:+.2f})")
    print(f"  MaxDD={best['max_dd']:.1f}% (Δ{best['max_dd']-BASELINE_DD:+.1f}%)")
    print(f"  Trades={best['trades']}")

# JSON保存
ts = datetime.now().strftime('%Y%m%d_%H%M%S')
out_path = f'sweep_results/h043_resweep_{ts}.json'
with open(out_path, 'w') as f:
    json.dump({'baseline': base_result, 'results': results}, f, indent=2)
print(f"\n✅ 結果保存: {out_path}")
