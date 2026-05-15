"""
H-033b スイープスクリプト
RiskOverlay DDキルスイッチの閾値 × 再開バー数グリッドサーチ

評価: 通年バックテスト 2024/01/01〜2026/05/08
指標: 通年MaxDD < 65% かつ 通年PnL > +1,200 USD
"""
import configparser
import subprocess
import re
import itertools
from datetime import datetime
from pathlib import Path

WORKSPACE = Path(__file__).parent.parent
CONFIG_PATH = WORKSPACE / "src/config.ini"

# スキャン範囲
DD_THRESHOLDS = [35, 40, 45, 50]          # max_drawdown_pct (%)
RESUME_BARS  = [0, 100, 200, 300, 500]    # dd_resume_bars (4H足数)
# dd_resume_bars=0 は永続停止（ベースラインとして含む）

# ベースライン（enabled=0）
BASELINE_PNL = 3417.0   # USD（通年, H-056 ScaleIn採用後）
BASELINE_DD  = 22.80    # %（通年MaxDD）

# 通年テスト期間
YEAR_START = "2024/01/01 00:00"
YEAR_END   = "2026/05/08 23:59"


def read_config():
    c = configparser.ConfigParser()
    c.read(CONFIG_PATH)
    return c


def write_config(c):
    with open(CONFIG_PATH, "w") as f:
        c.write(f)


def run_annual_backtest():
    """通年バックテスト実行（src/bot.pyを直接呼び出し）"""
    result = subprocess.run(
        ["python3", "bot.py"],
        cwd=WORKSPACE / "src",
        capture_output=True, text=True, timeout=300
    )
    return result.stdout + result.stderr


def parse_results(output):
    """バックテスト出力からPnLとMaxDDを抽出"""
    pnl = None
    maxdd = None
    trades = None

    # 最終損益: 1571 [BTC/USD]
    m = re.search(r'最終損益:\s*([+-]?\d+\.?\d*)', output)
    if m:
        pnl = float(m.group(1))

    # 最大ドローダウン率: 75.70 [%]
    m = re.search(r'最大ドローダウン率:\s*([0-9]+\.?[0-9]*)', output)
    if m:
        maxdd = float(m.group(1))

    # Trades: 43
    m = re.search(r'Trades:\s*(\d+)', output)
    if m:
        trades = int(m.group(1))

    return pnl, maxdd, trades


def set_period_and_overlay(c, enabled, max_dd_pct, dd_resume_bars):
    """config.ini に通年期間 + RiskOverlay を設定"""
    c['Period']['start_time'] = YEAR_START
    c['Period']['end_time']   = YEAR_END

    if 'RiskOverlay' not in c:
        c['RiskOverlay'] = {}

    c['RiskOverlay']['enabled'] = str(enabled)
    c['RiskOverlay']['max_drawdown_pct'] = str(max_dd_pct)
    c['RiskOverlay']['dd_resume_bars']   = str(dd_resume_bars)
    # 日次・連続損失は無効化（DD閾値単独の効果を見る）
    c['RiskOverlay']['daily_loss_limit_pct'] = '999.0'
    c['RiskOverlay']['consecutive_losses_limit'] = '9999'
    c['RiskOverlay']['auto_resume_next_day'] = '1'


def main():
    print("=" * 65)
    print("H-033b スイープ: RiskOverlay DD閾値 × 再開バー数グリッドサーチ")
    print(f"ベースライン: PnL={BASELINE_PNL:+.2f} USD / MaxDD={BASELINE_DD:.1f}%")
    print("期間: 2024/01/01〜2026/05/08（通年）")
    print("=" * 65)

    original_c = read_config()
    original_period_start = original_c['Period']['start_time']
    original_period_end   = original_c['Period']['end_time']
    original_overlay_enabled = original_c['RiskOverlay'].get('enabled', '0') if 'RiskOverlay' in original_c else '0'

    results = []

    # ---- ベースライン（enabled=0）----
    print("\n[0/N] ベースライン (enabled=0) を確認中...")
    c = read_config()
    c['Period']['start_time'] = YEAR_START
    c['Period']['end_time']   = YEAR_END
    c['RiskOverlay']['enabled'] = '0'
    write_config(c)
    out = run_annual_backtest()
    pnl, maxdd, trades = parse_results(out)
    print(f"  → PnL={pnl:+.2f} USD / MaxDD={maxdd:.1f}% / Trades={trades}")
    results.append({
        'label': 'baseline (disabled)',
        'enabled': 0, 'max_dd_pct': '-', 'resume_bars': '-',
        'pnl': pnl, 'maxdd': maxdd, 'trades': trades,
        'pass': True
    })

    # ---- グリッドサーチ ----
    total = len(DD_THRESHOLDS) * len(RESUME_BARS)
    idx = 0
    for dd_thr, resume_bars in itertools.product(DD_THRESHOLDS, RESUME_BARS):
        idx += 1
        label = f"DD≤{dd_thr}% / resume={resume_bars}bars"
        resume_days = resume_bars * 4 / 24  # 4H × N ÷ 24h
        print(f"\n[{idx}/{total}] {label} ({resume_days:.0f}日後再開)  ", end="", flush=True)

        c = read_config()
        set_period_and_overlay(c, enabled=1, max_dd_pct=dd_thr, dd_resume_bars=resume_bars)
        write_config(c)

        out = run_annual_backtest()
        pnl, maxdd, trades = parse_results(out)

        ok = (maxdd is not None and maxdd < 65.0 and
              pnl  is not None and pnl  > 1200.0)
        marker = "✅" if ok else "  "
        print(f"PnL={pnl:+.2f} USD / MaxDD={maxdd:.1f}% / Trades={trades} {marker}")

        results.append({
            'label': label, 'enabled': 1,
            'max_dd_pct': dd_thr, 'resume_bars': resume_bars,
            'pnl': pnl, 'maxdd': maxdd, 'trades': trades,
            'pass': ok
        })

    # ---- config.ini を元に戻す ----
    c = read_config()
    c['Period']['start_time'] = original_period_start
    c['Period']['end_time']   = original_period_end
    c['RiskOverlay']['enabled'] = original_overlay_enabled
    write_config(c)

    # ---- 結果表示 ----
    print("\n\n" + "=" * 65)
    print("H-033b スイープ結果サマリー")
    print("=" * 65)
    print(f"{'条件':<35} {'PnL':>10} {'MaxDD':>8} {'Trades':>7}  判定")
    print("-" * 65)
    for r in results:
        flag = "✅" if r['pass'] else ""
        pnl_s  = f"{r['pnl']:+.2f}" if isinstance(r['pnl'],  float) else "N/A"
        dd_s   = f"{r['maxdd']:.1f}%" if isinstance(r['maxdd'], float) else "N/A"
        tr_s   = str(r['trades']) if r['trades'] else "N/A"
        print(f"{r['label']:<35} {pnl_s:>10} {dd_s:>8} {tr_s:>7}  {flag}")

    # ---- 採用候補 ----
    candidates = [r for r in results if r['pass'] and r['enabled'] == 1]
    print(f"\n採用候補（MaxDD<65% かつ PnL>+1200 USD）: {len(candidates)}件")
    if candidates:
        best = max(candidates, key=lambda r: r['pnl'])
        print(f"  最高PnL候補: DD閾値={best['max_dd_pct']}% / 再開={best['resume_bars']}bars"
              f" → PnL={best['pnl']:+.2f} USD / MaxDD={best['maxdd']:.1f}%")

    print(f"\n完了: {datetime.now():%Y-%m-%d %H:%M:%S}")


if __name__ == "__main__":
    main()
