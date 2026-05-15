"""
H-036 + H-033b 組み合わせ検証
4パターンを通年（2024/01/01〜2026/05/08）で比較

  A. ベースライン  : scale=1.00, H-033b無効
  B. H-033b のみ  : scale=1.00, H-033b有効（DD≤50%/100bars）
  C. H-036 のみ   : scale=0.80, H-033b無効
  D. H-036+H-033b : scale=0.80, H-033b有効（DD≤50%/100bars）

採用基準: MaxDD < 65% かつ PnL > +1200
"""
import configparser, subprocess, re
from datetime import datetime
from pathlib import Path

WORKSPACE   = Path(__file__).parent.parent
CONFIG_PATH = WORKSPACE / "src/config.ini"

YEAR_START = "2024/01/01 00:00"
YEAR_END   = "2026/05/08 23:59"

BASE_TIERS = [0.30, 0.20, 0.15, 0.10]  # [tier_90, tier_70, tier_50, below]

PATTERNS = [
    {"name": "A. ベースライン",      "scale": 1.00, "overlay": False},
    {"name": "B. H-033b のみ",       "scale": 1.00, "overlay": True},
    {"name": "C. H-036(0.80) のみ",  "scale": 0.80, "overlay": False},
    {"name": "D. H-036+H-033b",      "scale": 0.80, "overlay": True},
]


def apply_config(scale, overlay_enabled):
    c = configparser.ConfigParser()
    c.read(CONFIG_PATH)
    c['Period']['start_time'] = YEAR_START
    c['Period']['end_time']   = YEAR_END
    # tier スケーリング
    scaled = [round(t * scale, 3) for t in BASE_TIERS]
    c['RiskManagement']['risk_percentage']         = str(scaled[0])
    c['RiskManagement']['dynamic_tier_90_risk']    = str(scaled[0])
    c['RiskManagement']['dynamic_tier_70_risk']    = str(scaled[1])
    c['RiskManagement']['dynamic_tier_50_risk']    = str(scaled[2])
    c['RiskManagement']['dynamic_tier_below_risk'] = str(scaled[3])
    # H-033b (RiskOverlay)
    c['RiskOverlay']['enabled']          = '1' if overlay_enabled else '0'
    c['RiskOverlay']['max_drawdown_pct'] = '50'
    c['RiskOverlay']['dd_resume_bars']   = '100'
    with open(CONFIG_PATH, 'w') as f:
        c.write(f)
    return scaled


def restore_config():
    c = configparser.ConfigParser()
    c.read(CONFIG_PATH)
    c['Period']['start_time'] = '2026/01/01 00:00'
    c['Period']['end_time']   = '2026/03/31 23:59'
    c['RiskManagement']['risk_percentage']         = str(BASE_TIERS[0])
    c['RiskManagement']['dynamic_tier_90_risk']    = str(BASE_TIERS[0])
    c['RiskManagement']['dynamic_tier_70_risk']    = str(BASE_TIERS[1])
    c['RiskManagement']['dynamic_tier_50_risk']    = str(BASE_TIERS[2])
    c['RiskManagement']['dynamic_tier_below_risk'] = str(BASE_TIERS[3])
    c['RiskOverlay']['enabled'] = '0'
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
    print("H-036 + H-033b 組み合わせ検証（通年 2024/01/01〜2026/05/08）")
    print("採用基準: MaxDD < 65% かつ PnL > +1,200")
    print("=" * 68)

    results = []
    for i, p in enumerate(PATTERNS, 1):
        scaled = apply_config(p["scale"], p["overlay"])
        tier90 = scaled[0]
        ov_str = "有効(DD≤50/100bars)" if p["overlay"] else "無効"
        print(f"\n[{i}/4] {p['name']}  tier_90={tier90:.3f}  overlay={ov_str}")
        print("      実行中...", end="", flush=True)

        out = run_backtest()
        pnl, maxdd, trades = parse(out)
        eff = pnl / maxdd if maxdd and maxdd > 0 else 0
        ok  = (maxdd is not None and maxdd < 65.0 and
               pnl  is not None and pnl  > 1200.0)
        flag = "✅ 採用基準クリア" if ok else "❌"
        print(f"\r      PnL={pnl:+.0f}  MaxDD={maxdd:.1f}%  PnL/DD={eff:.1f}  {flag}")

        results.append({**p, 'pnl': pnl, 'maxdd': maxdd, 'trades': trades,
                        'eff': eff, 'pass': ok})

    restore_config()

    # ---- サマリー ----
    print("\n\n" + "=" * 68)
    print("結果サマリー")
    print("=" * 68)
    print(f"{'パターン':<28} {'PnL':>10} {'MaxDD':>8} {'PnL/DD':>8} {'Trades':>7}  判定")
    print("-" * 68)
    for r in results:
        pnl_s = f"{r['pnl']:+.0f}"   if r['pnl']    is not None else "N/A"
        dd_s  = f"{r['maxdd']:.1f}%" if r['maxdd']   is not None else "N/A"
        ef_s  = f"{r['eff']:.1f}"    if r['eff']              else "N/A"
        tr_s  = str(r['trades'])     if r['trades']  is not None else "N/A"
        flag  = "✅" if r['pass'] else "❌"
        print(f"{r['name']:<28} {pnl_s:>10} {dd_s:>8} {ef_s:>8} {tr_s:>7}  {flag}")

    ok_list = [r for r in results if r['pass']]
    if ok_list:
        best = max(ok_list, key=lambda r: r['eff'])
        print(f"\n採用推奨: {best['name']}")
        print(f"  → PnL={best['pnl']:+.0f}  MaxDD={best['maxdd']:.1f}%  PnL/DD={best['eff']:.1f}")
    else:
        print("\n採用基準を満たすパターンなし → H-036は見送り推奨")

    print(f"\n完了: {datetime.now():%Y-%m-%d %H:%M:%S}")


if __name__ == "__main__":
    main()
