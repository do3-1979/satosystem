"""
H-051 スイープ（PSAR/ATR比フィルター）
仮説: エントリー時に |price - PSAR| / ATR > threshold の場合エントリー見送り
     → ストップが遠すぎるトレードは損失ポテンシャルが大きく、除外すべき

PnL率分析の根拠:
  T24(ADX=42, -44%): entry=86,699  PSAR距離≈3,700 / ATR≈1,152 → ratio≈3.2
  T14(ADX=28, -47%): entry=45,409  距離大 → 最悪損失率
  T11(ADX=33, -36%): 同様

ベースライン: PnL=+2617 USD, MaxDD=23.3%, Trades=43（H-044 cap=1500採用後）
採用基準: PnL > +2617 かつ MaxDD < 23.3%
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

def make_config(threshold: float) -> str:
    content = read_config()
    content = re.sub(r'start_time\s*=.*',              'start_time = 2024/01/01 00:00', content)
    content = re.sub(r'end_time\s*=.*',                'end_time = 2026/05/08 23:59',   content)
    content = re.sub(r'psar_atr_filter_enabled\s*=.*', 'psar_atr_filter_enabled = 1',   content)
    content = re.sub(r'psar_atr_filter_threshold\s*=.*', f'psar_atr_filter_threshold = {threshold}', content)
    return content

# ===============================================================
print("=" * 70)
print("H-051 スイープ（PSAR/ATR比フィルター）")
print(f"採用基準: PnL > {BASELINE_PNL} USD かつ MaxDD < {BASELINE_DD}%")
print("=" * 70)

# ベースライン確認
print("\n[BASE] H-051=OFF（ベースライン確認）...")
base_config = read_config()
base_mod = re.sub(r'start_time\s*=.*', 'start_time = 2024/01/01 00:00', base_config)
base_mod = re.sub(r'end_time\s*=.*',   'end_time = 2026/05/08 23:59',   base_mod)
base_result = run_backtest(base_mod)
print(f"  PnL={base_result['pnl']:+.2f} USD  MaxDD={base_result['max_dd']:.1f}%  Trades={base_result['trades']}")

# threshold候補: 大きいほど「ゆるい」フィルター（拒否が少ない）
# 2.0: ADX=3.2xATRのT24を確実に除外、かつ適度なトレード数維持
# 2.5: 中間（デフォルト）
# 3.0: 緩め（T24は除外、T14の一部は通過）
# 3.5: さらに緩め
# 4.0: 非常に緩め
THRESHOLDS = [1.5, 2.0, 2.5, 3.0, 3.5, 4.0]

results = []
passed = []

print(f"\n{'閾値':>6} | {'PnL':>10} | {'MaxDD':>7} | {'Trades':>6} | {'PnL判定':>8} | {'DD判定':>8} | {'総合':>5}")
print("-" * 70)

for thr in THRESHOLDS:
    cfg = make_config(thr)
    r = run_backtest(cfg)
    pnl = r['pnl']
    dd  = r['max_dd']
    trades = r['trades']

    if pnl is None or dd is None:
        print(f"  thr={thr:.1f}: ⚠️ 結果取得失敗")
        print(f"    raw: {r['raw'][-500:]}")
        results.append({'threshold': thr, 'error': True})
        continue

    pnl_ok = pnl > BASELINE_PNL
    dd_ok  = dd  < BASELINE_DD
    ok     = pnl_ok and dd_ok

    delta_pnl = pnl - BASELINE_PNL
    delta_dd  = dd  - BASELINE_DD

    pnl_str = f"{'✅' if pnl_ok else '❌'} ({delta_pnl:+.0f})"
    dd_str  = f"{'✅' if dd_ok  else '❌'} ({delta_dd:+.1f}%)"
    ok_str  = "✅" if ok else "❌"

    print(f"  {thr:>5.1f} | {pnl:>+10.2f} | {dd:>6.1f}% | {trades:>6} | {pnl_str:>12} | {dd_str:>12} | {ok_str}")

    entry = {
        'threshold': thr,
        'pnl': pnl,
        'max_dd': dd,
        'trades': trades,
        'delta_pnl': delta_pnl,
        'delta_dd': delta_dd,
        'passed': ok,
    }
    results.append(entry)
    if ok:
        passed.append(entry)

print("-" * 70)
print(f"\n合格パターン: {len(passed)}/{len(THRESHOLDS)}")

if passed:
    best = max(passed, key=lambda x: x['pnl'] - x['max_dd'] * 10)
    print(f"✅ 最良パターン: threshold={best['threshold']:.1f}  PnL={best['pnl']:+.2f} USD  MaxDD={best['max_dd']:.1f}%  Trades={best['trades']}")
    print(f"   ΔPnL={best['delta_pnl']:+.0f} USD  ΔMaxDD={best['delta_dd']:+.1f}%")
else:
    # 最もベースラインに近いパターンを表示
    valid = [r for r in results if not r.get('error')]
    if valid:
        closest = min(valid, key=lambda x: (0 if x['pnl'] > BASELINE_PNL else BASELINE_PNL - x['pnl'],
                                             0 if x['max_dd'] < BASELINE_DD else x['max_dd'] - BASELINE_DD))
        print(f"最ベースライン近似: threshold={closest['threshold']:.1f}  PnL={closest['pnl']:+.2f} USD  MaxDD={closest['max_dd']:.1f}%")
    print("❌ H-051: 採用基準を満たすパターンなし")

# 結果保存
ts = datetime.now().strftime('%Y%m%d_%H%M%S')
out_path = f'sweep_results/h051_sweep_{ts}.json'
import os; os.makedirs('sweep_results', exist_ok=True)
with open(out_path, 'w') as f:
    json.dump({
        'meta': {
            'hypothesis': 'H-051',
            'description': 'PSAR/ATR比フィルター（ストップ距離過大なエントリーを除外）',
            'baseline_pnl': BASELINE_PNL,
            'baseline_dd': BASELINE_DD,
            'run_at': ts,
        },
        'baseline': base_result,
        'results': results,
        'passed': passed,
    }, f, indent=2, ensure_ascii=False)
print(f"✅ 結果保存: {out_path}")
