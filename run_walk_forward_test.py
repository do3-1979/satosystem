#!/usr/bin/env python3
"""
Walk-Forward Validation (過学習チェック)

目的:
  パラメータを全期間で最適化した場合、それが本当に汎化しているか（過学習でないか）を
  Walk-Forward方式で検証する。

方式:
  In-Sample (IS) 期間でパラメータを評価し、
  Out-of-Sample (OOS) 期間でそのパラメータの性能を確認する。
  これを複数ウィンドウで繰り返し、IS/OOSの乖離がないかを見る。

使用方法:
  # 現在のconfig.iniパラメータでIS/OOS分割検証（過学習チェック）
  python3 run_walk_forward_test.py

  # パラメータのIS最適化 → OOS検証
  python3 run_walk_forward_test.py --scan pvo_l_term --values 25 30 35 38 40 45

  # ウィンドウ設定をカスタマイズ
  python3 run_walk_forward_test.py --scan adx_filter_threshold --values 25 26 27 28 29 30
"""

import os
import sys
import json
import subprocess
import argparse
import shutil
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

# ワークスペースルート設定
WORKSPACE_ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(WORKSPACE_ROOT, "src")
CONFIG_FILE = os.path.join(SRC_DIR, "config.ini")

# Walk-Forward ウィンドウ定義
# IS = In-Sample（最適化対象）, OOS = Out-of-Sample（汎化性能検証）
WINDOWS = [
    {
        "name": "Window-1",
        "is_quarters": [
            (2024, 1), (2024, 2), (2024, 3), (2024, 4),
            (2025, 1), (2025, 2),
        ],
        "oos_quarters": [
            (2025, 3), (2025, 4),
        ],
    },
    {
        "name": "Window-2",
        "is_quarters": [
            (2024, 1), (2024, 2), (2024, 3), (2024, 4),
            (2025, 1), (2025, 2), (2025, 3), (2025, 4),
        ],
        "oos_quarters": [
            (2026, 1),
        ],
    },
    {
        "name": "Full-Period（参考）",
        "is_quarters": [
            (2024, 1), (2024, 2), (2024, 3), (2024, 4),
            (2025, 1), (2025, 2), (2025, 3), (2025, 4),
            (2026, 1),
        ],
        "oos_quarters": [],  # 全期間がIS（参考値）
    },
]


def get_quarter_dates(year, q):
    q_start = datetime(year, (q - 1) * 3 + 1, 1)
    q_end = (q_start + relativedelta(months=3)) - timedelta(seconds=1)
    if q_end > datetime.now():
        q_end = datetime.now()
    return q_start, q_end


def read_config_param(config_file, param_name):
    """config.ini から指定パラメータの値を読む"""
    with open(config_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line.startswith(f'{param_name} =') or line.startswith(f'{param_name}='):
                return line.split('=', 1)[1].strip()
    return None


def write_config_param(config_file, param_name, value):
    """config.ini の指定パラメータを書き換える"""
    with open(config_file, 'r', encoding='utf-8') as f:
        content = f.read()
    import re
    new_content = re.sub(
        rf'^({re.escape(param_name)}\s*=\s*).*$',
        rf'\g<1>{value}',
        content,
        flags=re.MULTILINE
    )
    with open(config_file, 'w', encoding='utf-8') as f:
        f.write(new_content)


def update_config_period(config_file, start_str, end_str):
    """config.ini の期間設定を更新"""
    with open(config_file, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')
    new_lines = []
    in_period = False
    for line in lines:
        if line.strip().startswith('[Period]'):
            in_period = True
            new_lines.append(line)
        elif line.strip().startswith('['):
            in_period = False
            new_lines.append(line)
        elif in_period and line.strip().startswith('start_time'):
            new_lines.append(f"start_time = {start_str}")
        elif in_period and line.strip().startswith('end_time'):
            new_lines.append(f"end_time = {end_str}")
        else:
            new_lines.append(line)

    with open(config_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_lines))


def run_backtest_for_quarters(quarters, config_file, label=""):
    """指定四半期リストのバックテストを実行して合計PnLを返す"""
    if not quarters:
        return None, []

    total_pnl = 0.0
    quarter_results = []

    os.chdir(SRC_DIR)
    import glob

    for year, q in quarters:
        q_start, q_end = get_quarter_dates(year, q)
        start_str = q_start.strftime("%Y/%m/%d %H:%M")
        end_str = q_end.strftime("%Y/%m/%d %H:%M")

        update_config_period(config_file, start_str, end_str)

        # 古いbacktest_summaryを削除
        for old_f in glob.glob('logs/**/backtest_summary_*.json', recursive=True):
            try:
                os.remove(old_f)
            except Exception:
                pass

        env = os.environ.copy()
        env['QUARTERLY_LOG_PREFIX'] = f"Q{q}_{year}"

        try:
            result = subprocess.run(
                ['python', 'bot.py'],
                capture_output=True,
                text=True,
                timeout=600,
                env=env
            )

            if result.returncode != 0:
                print(f"      ❌ Q{q}_{year} 失敗")
                quarter_results.append({'quarter': f"Q{q}_{year}", 'pnl': None})
                continue

            summary_logs = glob.glob('logs/**/backtest_summary_*.json', recursive=True)
            if not summary_logs:
                print(f"      ❌ Q{q}_{year} ログなし")
                quarter_results.append({'quarter': f"Q{q}_{year}", 'pnl': None})
                continue

            latest_log = max(summary_logs, key=os.path.getmtime)
            with open(latest_log, 'r', encoding='utf-8') as f:
                data = json.load(f)

            pnl = float(data.get('total_pnl', 0))
            total_pnl += pnl
            quarter_results.append({'quarter': f"Q{q}_{year}", 'pnl': pnl})
            print(f"      Q{q}_{year}: {pnl:+.2f} USD")

        except subprocess.TimeoutExpired:
            print(f"      ❌ Q{q}_{year} タイムアウト")
            quarter_results.append({'quarter': f"Q{q}_{year}", 'pnl': None})
        except Exception as e:
            print(f"      ❌ Q{q}_{year} エラー: {e}")
            quarter_results.append({'quarter': f"Q{q}_{year}", 'pnl': None})

    os.chdir(WORKSPACE_ROOT)
    return total_pnl, quarter_results


def run_current_param_check():
    """
    現在のconfig.iniパラメータでIS/OOS分割検証（過学習チェック）
    パラメータは変更せず、期間を分けて性能を確認する。
    """
    print("=" * 60)
    print("  Walk-Forward Validation（現在パラメータのIS/OOS検証）")
    print("=" * 60)

    # 現在のパラメータ表示
    key_params = ['donchian_buy_term', 'pvo_s_term', 'pvo_l_term',
                  'pvo_threshold', 'adx_filter_threshold', 'tsmom_filter_lookback']
    print("\n現在のパラメータ:")
    for p in key_params:
        val = read_config_param(CONFIG_FILE, p)
        if val:
            print(f"  {p} = {val}")

    print()

    window_summary = []

    for win in WINDOWS:
        print(f"\n{'─'*50}")
        print(f"  {win['name']}")
        print(f"{'─'*50}")

        # IS
        if win['is_quarters']:
            print(f"  [IS] In-Sample ({len(win['is_quarters'])} 四半期):")
            is_pnl, is_details = run_backtest_for_quarters(win['is_quarters'], CONFIG_FILE, "IS")
            is_sum = sum(r['pnl'] for r in is_details if r['pnl'] is not None)
            print(f"  → IS 合計: {is_sum:+.2f} USD")
        else:
            is_sum = None
            is_details = []

        # OOS
        if win['oos_quarters']:
            print(f"\n  [OOS] Out-of-Sample ({len(win['oos_quarters'])} 四半期):")
            oos_pnl, oos_details = run_backtest_for_quarters(win['oos_quarters'], CONFIG_FILE, "OOS")
            oos_sum = sum(r['pnl'] for r in oos_details if r['pnl'] is not None)
            print(f"  → OOS 合計: {oos_sum:+.2f} USD")

            # IS平均とOOS平均の比較
            is_avg = is_sum / len(win['is_quarters']) if win['is_quarters'] else 0
            oos_avg = oos_sum / len(win['oos_quarters']) if win['oos_quarters'] else 0
            ratio = oos_avg / is_avg if is_avg > 0 else float('nan')

            print(f"\n  IS 四半期平均:  {is_avg:+.2f} USD")
            print(f"  OOS 四半期平均: {oos_avg:+.2f} USD")
            if is_avg > 0:
                if ratio >= 0.5:
                    verdict = "✅ 良好（OOS≥IS×0.5）"
                elif ratio >= 0.0:
                    verdict = "⚠️  要注意（OOS>0だがIS比50%未満）"
                else:
                    verdict = "❌ 過学習疑い（OOSがマイナス）"
                print(f"  OOS/IS 比率:    {ratio:.2f}  {verdict}")
        else:
            oos_sum = None
            oos_details = []

        window_summary.append({
            'name': win['name'],
            'is_total': is_sum,
            'oos_total': oos_sum,
            'is_details': is_details,
            'oos_details': oos_details,
        })

    # 総合判定
    print(f"\n{'='*60}")
    print("  総合評価")
    print(f"{'='*60}")
    oos_positives = sum(
        1 for w in window_summary
        if w['oos_total'] is not None and w['oos_total'] > 0
    )
    oos_total = sum(
        1 for w in window_summary if w['oos_total'] is not None
    )
    print(f"  OOS プラス: {oos_positives}/{oos_total} ウィンドウ")

    if oos_positives == oos_total and oos_total > 0:
        print("  → ✅ 汎化性能あり（全OOSウィンドウでプラス）")
        print("  → 現在のパラメータは過学習ではない可能性が高い")
    elif oos_positives > 0:
        print("  → ⚠️  部分的に汎化（一部OOSがマイナス）")
        print("  → パラメータの安定性を再確認すること")
    else:
        print("  → ❌ 過学習の疑いあり（OOSが全てマイナス）")
        print("  → パラメータを見直すこと")

    return window_summary


def run_scan_walk_forward(param_name, param_values):
    """
    指定パラメータをIS期間で最適化し、OOS期間で検証する。
    全期間最適値とIS最適値のOOS性能を比較する。
    """
    print("=" * 60)
    print(f"  Walk-Forward Scan: {param_name}")
    print(f"  スキャン範囲: {param_values}")
    print("=" * 60)

    # 元の値を保存
    original_value = read_config_param(CONFIG_FILE, param_name)
    if original_value is None:
        print(f"❌ パラメータ '{param_name}' がconfig.iniに見つかりません")
        return

    print(f"  元の値: {param_name} = {original_value}\n")

    # Walk-Forward ウィンドウ（Window-1のみ使用）
    win = WINDOWS[0]  # IS: 2024Q1-2025Q2 / OOS: 2025Q3-2025Q4
    win2 = WINDOWS[1]  # IS: 2024Q1-2025Q4 / OOS: 2026Q1

    results = []

    try:
        for val in param_values:
            print(f"\n{'─'*50}")
            print(f"  {param_name} = {val}")
            print(f"{'─'*50}")
            write_config_param(CONFIG_FILE, param_name, str(val))

            # Window-1 IS
            print(f"  [W1-IS] 2024Q1-2025Q2:")
            w1_is_pnl, _ = run_backtest_for_quarters(win['is_quarters'], CONFIG_FILE)
            # Window-1 OOS
            print(f"  [W1-OOS] 2025Q3-2025Q4:")
            w1_oos_pnl, _ = run_backtest_for_quarters(win['oos_quarters'], CONFIG_FILE)

            # Window-2 OOS (2026Q1)
            print(f"  [W2-OOS] 2026Q1:")
            w2_oos_pnl, _ = run_backtest_for_quarters(win2['oos_quarters'], CONFIG_FILE)

            # 全期間
            all_q = win['is_quarters'] + win2['oos_quarters']
            all_pnl = (w1_is_pnl or 0) + (w2_oos_pnl or 0)
            # 2025Q3-2025Q4はWindow-1 OOSに含まれる
            total_pnl = (w1_is_pnl or 0) + (w1_oos_pnl or 0) + (w2_oos_pnl or 0)

            results.append({
                'value': val,
                'w1_is': w1_is_pnl,
                'w1_oos': w1_oos_pnl,
                'w2_oos': w2_oos_pnl,
                'total': total_pnl,
            })
            print(f"  W1-IS: {w1_is_pnl:+.2f} | W1-OOS: {w1_oos_pnl:+.2f} | W2-OOS: {w2_oos_pnl:+.2f} | 合計: {total_pnl:+.2f}")

    finally:
        # 元の値に戻す
        write_config_param(CONFIG_FILE, param_name, original_value)
        print(f"\n✅ {param_name} を元の値 {original_value} に戻しました")

    # 結果サマリー
    print(f"\n{'='*60}")
    print(f"  スキャン結果サマリー: {param_name}")
    print(f"{'='*60}")
    print(f"  {'値':>6}  {'IS合計':>10}  {'OOS合計':>10}  {'全期間':>10}  OOS判定")
    print(f"  {'─'*6}  {'─'*10}  {'─'*10}  {'─'*10}  {'─'*10}")

    best_total = max(results, key=lambda r: r['total'] or -9999)
    best_oos = max(results, key=lambda r: (r['w1_oos'] or 0) + (r['w2_oos'] or 0))

    for r in results:
        oos_sum = (r['w1_oos'] or 0) + (r['w2_oos'] or 0)
        oos_ok = "✅" if oos_sum > 0 else "❌"
        is_best = " ← 全期間最大" if r == best_total else ""
        is_best_oos = " ← OOS最大" if r == best_oos and r != best_total else ""
        print(f"  {r['value']:>6}  {r['w1_is']:>+10.2f}  {oos_sum:>+10.2f}  {r['total']:>+10.2f}  {oos_ok}{is_best}{is_best_oos}")

    # 過学習評価
    print(f"\n  全期間最大値: {param_name}={best_total['value']} → {best_total['total']:+.2f} USD")
    best_total_oos = (best_total['w1_oos'] or 0) + (best_total['w2_oos'] or 0)
    print(f"  そのOOS合計: {best_total_oos:+.2f} USD")

    if best_total_oos > 0:
        print(f"  ✅ 全期間最大パラメータのOOSもプラス → 過学習の疑いは低い")
    else:
        print(f"  ❌ 全期間最大パラメータのOOSがマイナス → 過学習の可能性あり")
        print(f"     OOS最大は {param_name}={best_oos['value']} を検討")

    return results


def main():
    parser = argparse.ArgumentParser(
        description='Walk-Forward Validation（過学習チェック）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument('--scan', type=str, default=None,
                        help='スキャンするパラメータ名 (例: pvo_l_term)')
    parser.add_argument('--values', type=float, nargs='+', default=None,
                        help='スキャンする値リスト (例: 25 30 35 38 40)')
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print("  Walk-Forward Validation")
    print(f"  実行日時: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}\n")

    if args.scan:
        if args.values is None:
            print(f"❌ --scan を指定する場合は --values も必要です")
            sys.exit(1)
        # 整数か浮動小数かを自動判定
        int_params = ['donchian_buy_term', 'donchian_sell_term', 'pvo_s_term', 'pvo_l_term',
                      'adx_filter_threshold', 'adx_continue_num', 'tsmom_filter_lookback']
        if args.scan in int_params:
            values = [int(v) for v in args.values]
        else:
            values = args.values
        run_scan_walk_forward(args.scan, values)
    else:
        run_current_param_check()


if __name__ == '__main__':
    main()
