"""
H-036 スキャン: ハーフケリー基準によるポジションサイズ最適化
enable_dynamic_position_sizing=1 のため、dynamic_tier_XX_risk を一括スケール
現状: tier_90=0.30, tier_70=0.20, tier_50=0.15, tier_below=0.10
仮説: 全tierを比例スケールしてMaxDDを改善

評価: 通年 2024/01/01〜2026/05/08 + 四半期テスト
"""
import configparser
import subprocess
import re
from datetime import datetime
from pathlib import Path

WORKSPACE = Path(__file__).parent
CONFIG_PATH = WORKSPACE / "src/config.ini"

# ベーstierを乗数で一括スケール
# 現状: [0.30, 0.20, 0.15, 0.10]
BASE_TIERS = [0.30, 0.20, 0.15, 0.10]
SCALE_FACTORS = [0.33, 0.50, 0.60, 0.70, 0.80, 1.00]  # 1.00=現状

YEAR_START = "2024/01/01 00:00"
YEAR_END   = "2026/05/08 23:59"
BASELINE_PNL = 1571.0
BASELINE_DD  = 75.7


def run_annual_backtest():
    result = subprocess.run(
        ["python3", "bot.py"],
        cwd=WORKSPACE / "src",
        capture_output=True, text=True, timeout=300
    )
    return result.stdout + result.stderr


def parse_results(output):
    pnl, maxdd, trades = None, None, None
    m = re.search(r'最終損益:\s*([+-]?\d+\.?\d*)', output)
    if m: pnl = float(m.group(1))
    m = re.search(r'最大ドローダウン率:\s*([0-9]+\.?[0-9]*)', output)
    if m: maxdd = float(m.group(1))
    m = re.search(r'Trades:\s*(\d+)', output)
    if m: trades = int(m.group(1))
    return pnl, maxdd, trades


def set_config(scale, tiers):
    c = configparser.ConfigParser()
    c.read(CONFIG_PATH)
    c['Period']['start_time'] = YEAR_START
    c['Period']['end_time']   = YEAR_END
    scaled = [round(t * scale, 3) for t in tiers]
    c['RiskManagement']['risk_percentage']        = str(scaled[0])
    c['RiskManagement']['dynamic_tier_90_risk']   = str(scaled[0])
    c['RiskManagement']['dynamic_tier_70_risk']   = str(scaled[1])
    c['RiskManagement']['dynamic_tier_50_risk']   = str(scaled[2])
    c['RiskManagement']['dynamic_tier_below_risk']= str(scaled[3])
    with open(CONFIG_PATH, 'w') as f:
        c.write(f)
    return scaled


def restore_config():
    c = configparser.ConfigParser()
    c.read(CONFIG_PATH)
    c['Period']['start_time'] = '2026/01/01 00:00'
    c['Period']['end_time']   = '2026/03/31 23:59'
    c['RiskManagement']['risk_percentage']        = str(BASE_TIERS[0])
    c['RiskManagement']['dynamic_tier_90_risk']   = str(BASE_TIERS[0])
    c['RiskManagement']['dynamic_tier_70_risk']   = str(BASE_TIERS[1])
    c['RiskManagement']['dynamic_tier_50_risk']   = str(BASE_TIERS[2])
    c['RiskManagement']['dynamic_tier_below_risk']= str(BASE_TIERS[3])
    with open(CONFIG_PATH, 'w') as f:
        c.write(f)


def main():
    print("=" * 65)
    print("H-036 スキャン: dynamic_tier リスク比例スケール")
    print(f"ベースtier: {BASE_TIERS} (現状 scale=1.00)")
    print(f"フルケリー≈18.8%≒scale=0.63 / ハーフケリー≈9.4%≒scale=0.31")
    print(f"ベースライン: PnL={BASELINE_PNL:+.0f} / MaxDD={BASELINE_DD:.1f}%")
    print("=" * 65)

    results = []
    total = len(SCALE_FACTORS)

    for idx, scale in enumerate(SCALE_FACTORS, 1):
        scaled = set_config(scale, BASE_TIERS)
        label = f"scale={scale:.2f} tier={scaled[0]:.3f}"
        if scale == 1.00:
            label += " (現状)"
        print(f"\n[{idx}/{total}] {label}  ", end="", flush=True)

        out = run_annual_backtest()
        pnl, maxdd, trades = parse_results(out)

        pnl_per_dd = pnl / maxdd if maxdd and maxdd > 0 else 0
        ok = (maxdd is not None and maxdd < 65.0 and
              pnl  is not None and pnl  > 1200.0)
        marker = "✅" if ok else ""
        print(f"PnL={pnl:+.0f} / MaxDD={maxdd:.1f}% / PnL/DD={pnl_per_dd:.1f} {marker}")

        results.append({
            'scale': scale, 'label': label, 'scaled_tiers': scaled,
            'pnl': pnl, 'maxdd': maxdd, 'trades': trades,
            'pnl_per_dd': pnl_per_dd, 'pass': ok
        })

    restore_config()

    # ---- 結果表示 ----
    print("\n\n" + "=" * 65)
    print("H-036 スキャン結果サマリー")
    print("=" * 65)
    print(f"{'条件':<30} {'PnL':>10} {'MaxDD':>8} {'PnL/DD':>8} {'Trades':>7}  判定")
    print("-" * 65)
    for r in results:
        pnl_s = f"{r['pnl']:+.0f}" if r['pnl'] is not None else "N/A"
        dd_s  = f"{r['maxdd']:.1f}%" if r['maxdd'] is not None else "N/A"
        pd_s  = f"{r['pnl_per_dd']:.1f}" if r['pnl_per_dd'] else "N/A"
        tr_s  = str(r['trades']) if r['trades'] else "N/A"
        flag  = "✅" if r['pass'] else ""
        print(f"{r['label']:<30} {pnl_s:>10} {dd_s:>8} {pd_s:>8} {tr_s:>7}  {flag}")

    candidates = [r for r in results if r['pass']]
    if candidates:
        best_eff = max(candidates, key=lambda r: r['pnl_per_dd'])
        print(f"\n採用候補: {len(candidates)}件")
        print(f"  最高効率: {best_eff['label']} → PnL={best_eff['pnl']:+.0f} / DD={best_eff['maxdd']:.1f}% / ratio={best_eff['pnl_per_dd']:.1f}")
    else:
        print("\n採用候補なし（MaxDD<65% かつ PnL>+1200 を満たすものがない）")

    print(f"\n完了: {datetime.now():%Y-%m-%d %H:%M:%S}")


if __name__ == "__main__":
    main()

