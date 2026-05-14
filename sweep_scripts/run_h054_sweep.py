"""
H-054 スイープ（ADXスロープフィルター）
既存機能 adx_slope_filter を活用する。

原理: ADX が下落中 = トレンド弱体化 = フォールスブレイクアウトリスク高
     ADX が上昇中 = トレンド強化 = エントリー良好
     Elder (1993) "Trading for a Living" の手法に基づく

仮説への根拠:
  T24 (ADX=42, -44%): ADXが強かったがトランプショックで急落
  T14 (ADX=28.7, -47%): ADXがしきい値28に近く、かつ下落中だった可能性
  T11/T12 (ADX=33-34, -36/-32%): 2024年相場転換期、ADX下落中の可能性

ベースライン: PnL=+2617 USD, MaxDD=23.3%, Trades=43（H-044 cap=1500採用後）
採用基準: PnL > +2617 USD かつ MaxDD < 23.3%
"""
import subprocess, re, json
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

def make_config(lookback: int) -> str:
    content = read_config()
    content = re.sub(r'start_time\s*=.*',                 'start_time = 2024/01/01 00:00', content)
    content = re.sub(r'end_time\s*=.*',                   'end_time = 2026/05/08 23:59',   content)
    content = re.sub(r'adx_slope_filter_enabled\s*=.*',   'adx_slope_filter_enabled = 1',  content)
    content = re.sub(r'adx_slope_filter_lookback\s*=.*',  f'adx_slope_filter_lookback = {lookback}', content)
    content = re.sub(r'psar_sizing_enabled\s*=.*',        'psar_sizing_enabled = 0',        content)
    content = re.sub(r'atr_initial_stop_enabled\s*=.*',   'atr_initial_stop_enabled = 0',   content)
    return content

# ===============================================================
print("=" * 70)
print("H-054 スイープ（ADXスロープフィルター: ADX上昇中のみエントリー）")
print(f"採用基準: PnL > {BASELINE_PNL} USD かつ MaxDD < {BASELINE_DD}%")
print("=" * 70)

# ベースライン確認
print("\n[BASE] ADXスロープ=OFF（ベースライン確認）...")
base_config = read_config()
base_mod = re.sub(r'start_time\s*=.*', 'start_time = 2024/01/01 00:00', base_config)
base_mod = re.sub(r'end_time\s*=.*',   'end_time = 2026/05/08 23:59',   base_mod)
base_mod = re.sub(r'psar_sizing_enabled\s*=.*', 'psar_sizing_enabled = 0', base_mod)
base_mod = re.sub(r'atr_initial_stop_enabled\s*=.*', 'atr_initial_stop_enabled = 0', base_mod)
base_result = run_backtest(base_mod)
print(f"  PnL={base_result['pnl']:+.2f} USD  MaxDD={base_result['max_dd']:.1f}%  Trades={base_result['trades']}")

# lookback候補
# 3: 3本前のADXと比較（最近のトレンド変化に敏感）
# 5: 中間
# 10: 現在のデフォルト
# 15: 中長期スロープ
# 20: 長期スロープ
LOOKBACKS = [2, 3, 5, 10, 15, 20]

results = []
passed = []

print(f"\n{'LB':>4} | {'PnL':>10} | {'MaxDD':>7} | {'Trades':>6} | {'PnL判定':>12} | {'DD判定':>12} | {'総合':>5}")
print("-" * 72)

for lb in LOOKBACKS:
    cfg = make_config(lb)
    r = run_backtest(cfg)
    pnl = r['pnl']
    dd  = r['max_dd']
    trades = r['trades']

    if pnl is None or dd is None:
        print(f"  lb={lb}: ⚠️ 結果取得失敗")
        print(f"    raw: {r['raw'][-300:]}")
        results.append({'lookback': lb, 'error': True})
        continue

    delta_pnl = pnl - BASELINE_PNL
    delta_dd  = dd  - BASELINE_DD

    pnl_ok = pnl > BASELINE_PNL
    dd_ok  = dd  < BASELINE_DD
    ok     = pnl_ok and dd_ok

    pnl_str = f"{'✅' if pnl_ok else '❌'} ({delta_pnl:+.0f})"
    dd_str  = f"{'✅' if dd_ok  else '❌'} ({delta_dd:+.1f}%)"
    ok_str  = "✅" if ok else "❌"

    print(f"  {lb:>3} | {pnl:>+10.2f} | {dd:>6.1f}% | {trades:>6} | {pnl_str:>14} | {dd_str:>14} | {ok_str}")

    entry = {
        'lookback': lb,
        'pnl': pnl, 'max_dd': dd, 'trades': trades,
        'delta_pnl': delta_pnl, 'delta_dd': delta_dd, 'passed': ok,
    }
    results.append(entry)
    if ok:
        passed.append(entry)

print("-" * 72)
print(f"\n合格パターン: {len(passed)}/{len(LOOKBACKS)}")

if passed:
    best = max(passed, key=lambda x: x['pnl'] - x['max_dd'] * 10)
    print(f"✅ 最良パターン: lookback={best['lookback']}  PnL={best['pnl']:+.2f} USD  MaxDD={best['max_dd']:.1f}%  Trades={best['trades']}")
    print(f"   ΔPnL={best['delta_pnl']:+.0f} USD  ΔMaxDD={best['delta_dd']:+.1f}%")
else:
    valid = [r for r in results if not r.get('error')]
    if valid:
        closest = min(valid, key=lambda x: (0 if x['pnl'] > BASELINE_PNL else BASELINE_PNL - x['pnl'],
                                             0 if x['max_dd'] < BASELINE_DD else x['max_dd'] - BASELINE_DD))
        print(f"最ベースライン近似: lookback={closest['lookback']}  PnL={closest['pnl']:+.2f} USD  MaxDD={closest['max_dd']:.1f}%")
    print("❌ H-054: 採用基準を満たすパターンなし")

# 結果保存
ts = datetime.now().strftime('%Y%m%d_%H%M%S')
out_path = f'sweep_results/h054_sweep_{ts}.json'
import os; os.makedirs('sweep_results', exist_ok=True)
with open(out_path, 'w') as f:
    json.dump({
        'meta': {
            'hypothesis': 'H-054',
            'description': 'ADXスロープフィルター（ADX上昇中のみエントリー許可）',
            'baseline_pnl': BASELINE_PNL,
            'baseline_dd': BASELINE_DD,
            'run_at': ts,
        },
        'baseline': base_result,
        'results': results,
        'passed': passed,
    }, f, indent=2, ensure_ascii=False)
print(f"✅ 結果保存: {out_path}")
