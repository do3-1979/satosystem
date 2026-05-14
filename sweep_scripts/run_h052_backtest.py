"""
H-052 バックテスト（PSAR距離ベースのポジションサイジング）
根拠: position_size = balance × risk_pct / ATR (現在)
     しかし実際のストップはPSARで決まる → PSARがATRより遠いとき損失が膨らむ
修正: stop_range = max(ATR, PSAR距離) → PSARが遠いときは自動的にポジション縮小

H-051と異なる点: エントリーは維持（除外しない）、サイズのみ縮小するため
大利益トレードも保持しつつ、大損失トレードの損失額を圧縮できる

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

def make_config_enabled() -> str:
    content = read_config()
    content = re.sub(r'start_time\s*=.*', 'start_time = 2024/01/01 00:00', content)
    content = re.sub(r'end_time\s*=.*',   'end_time = 2026/05/08 23:59',   content)
    content = re.sub(r'psar_sizing_enabled\s*=.*', 'psar_sizing_enabled = 1', content)
    return content

# ===============================================================
print("=" * 70)
print("H-052 バックテスト（PSAR距離ベースのポジションサイジング）")
print(f"採用基準: PnL > {BASELINE_PNL} USD かつ MaxDD < {BASELINE_DD}%")
print("=" * 70)

# ベースライン確認
print("\n[BASE] H-052=OFF（ベースライン確認）...")
base_config = read_config()
base_mod = re.sub(r'start_time\s*=.*', 'start_time = 2024/01/01 00:00', base_config)
base_mod = re.sub(r'end_time\s*=.*',   'end_time = 2026/05/08 23:59',   base_mod)
base_result = run_backtest(base_mod)
print(f"  PnL={base_result['pnl']:+.2f} USD  MaxDD={base_result['max_dd']:.1f}%  Trades={base_result['trades']}")

# H-052有効
print("\n[H-052 ON] PSAR距離ベースのポジションサイジング...")
h052_config = make_config_enabled()
r = run_backtest(h052_config)

if r['pnl'] is None or r['max_dd'] is None:
    print(f"⚠️ 結果取得失敗")
    print(f"raw: {r['raw'][-500:]}")
else:
    pnl    = r['pnl']
    dd     = r['max_dd']
    trades = r['trades']

    delta_pnl = pnl - BASELINE_PNL
    delta_dd  = dd  - BASELINE_DD

    pnl_ok = pnl > BASELINE_PNL
    dd_ok  = dd  < BASELINE_DD
    ok     = pnl_ok and dd_ok

    print(f"\n{'':=<70}")
    print(f"  PnL    : {pnl:+.2f} USD  (Δ{delta_pnl:+.2f})  {'✅' if pnl_ok else '❌'}")
    print(f"  MaxDD  : {dd:.1f}%       (Δ{delta_dd:+.1f}%)    {'✅' if dd_ok else '❌'}")
    print(f"  Trades : {trades}")
    print(f"  総合   : {'✅ 採用基準クリア' if ok else '❌ 採用基準未達'}")
    print(f"{'':=<70}")

    # 結果保存
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_path = f'sweep_results/h052_result_{ts}.json'
    import os; os.makedirs('sweep_results', exist_ok=True)
    with open(out_path, 'w') as f:
        json.dump({
            'meta': {
                'hypothesis': 'H-052',
                'description': 'PSAR距離ベースのポジションサイジング（stop_range=max(ATR,PSAR距離)）',
                'baseline_pnl': BASELINE_PNL,
                'baseline_dd': BASELINE_DD,
                'run_at': ts,
            },
            'baseline': base_result,
            'h052': r,
            'delta_pnl': delta_pnl,
            'delta_dd': delta_dd,
            'passed': ok,
        }, f, indent=2, ensure_ascii=False)
    print(f"✅ 結果保存: {out_path}")
