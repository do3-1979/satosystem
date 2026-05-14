#!/usr/bin/env python3
"""
PVOフィルター有効性検証スクリプト（BTC専用）

Phase 1: PVO閾値スイープ
  enable_pvo_filter と pvo_threshold を変化させて四半期バックテストを実行し、
  各評価指標の改善効果を比較する。

Phase 2: PVO EMA期間スイープ
  pvo_s_term / pvo_l_term を変化させて、PVO計算自体の適切な期間を検証する。

Phase 3: l_term=26 固定 + 閾値スイープ（Phase2の最優秀EMA期間で再検証）
  pvo_l_term=26, pvo_s_term=5 を固定して、Phase 1 と同じ閾値スイープを実行。
  Phase 2 で l_term=26 が最優秀だったため、最適な閾値を探索する。

使用方法:
  python3 run_pvo_sweep.py              # Phase 1 + Phase 2 両方実行
  python3 run_pvo_sweep.py --phase 1   # Phase 1 (閾値スイープ) のみ
  python3 run_pvo_sweep.py --phase 2   # Phase 2 (EMA期間スイープ) のみ
  python3 run_pvo_sweep.py --phase 3   # Phase 3 (l_term=26固定 + 閾値スイープ) のみ

結果:
  sweep_results/pvo_sweep_YYYYMMDD_HHMMSS.json に保存
  コンソールにQ別比較表と分析サマリーを出力

事前確認済みの実装ポイント:
  - [Strategy] セクション: pvo_s_term, pvo_l_term, pvo_threshold
  - [EntryFilters] セクション: enable_pvo_filter
  - サブプロセス実行のため各バックテストで config.ini を新規読み込み → 変更確実に反映
  - regex 置換時、^pvo_threshold は composite_exit_pvo_threshold にマッチしない
"""

import os
import sys
import json
import re
import subprocess
import argparse
from datetime import datetime

WORKSPACE_ROOT = os.path.dirname(os.path.abspath(__file__))
BTC_CONFIG_FILE  = os.path.join(WORKSPACE_ROOT, 'src', 'config.ini')
BTC_RESULTS_DIR  = os.path.join(WORKSPACE_ROOT, 'docs', 'quarterly_backtest_results', 'BTC')
SWEEP_RESULTS_DIR = os.path.join(WORKSPACE_ROOT, 'sweep_results')

os.makedirs(SWEEP_RESULTS_DIR, exist_ok=True)

# ============================================================
# スイープパターン定義
# ============================================================

# Phase 1: PVO閾値スイープ
# (enabled, threshold, label)
# enabled=None → enable_pvo_filter=0（フィルタ完全無効）
# enabled=1, threshold=N → enable_pvo_filter=1, pvo_threshold=N
BTC_THRESHOLD_SWEEP = [
    (None, None, "disabled"),           # PVOフィルタ完全無効（出来高条件なし）
    (1,   -10,  "pvo≤-10"),
    (1,     0,  "pvo≤0"),
    (1,     5,  "pvo≤5"),
    (1,    10,  "pvo≤10 ★BASELINE"),   # 現行ベースライン
    (1,    20,  "pvo≤20"),
    (1,    30,  "pvo≤30"),
]

BTC_THRESHOLD_BASELINE_LABEL = "pvo≤10 ★BASELINE"

# Phase 2: PVO EMA期間スイープ
# (s_term, l_term, label)
BTC_EMA_SWEEP = [
    ( 3,  26,  "s3_l26"),
    ( 5,  26,  "s5_l26"),
    ( 5,  70,  "s5_l70 ★BASELINE"),    # 現行ベースライン
    (12,  26,  "s12_l26"),
    ( 3,  70,  "s3_l70"),
]

BTC_EMA_BASELINE_LABEL = "s5_l70 ★BASELINE"

# Phase 3: l_term=26固定で閾値スイープ
# Phase 2 最優秀だった s5_l26 を基準に閾値を再探索
# (enabled, threshold, label)
BTC_PHASE3_SWEEP = [
    (None, None, "disabled"),           # PVOフィルタ完全無効
    (1,   -10,  "pvo≤-10"),
    (1,     0,  "pvo≤0"),
    (1,     5,  "pvo≤5"),
    (1,    10,  "pvo≤10 ★P1-BASE"),    # Phase1のベースライン閾値
    (1,    20,  "pvo≤20"),
    (1,    30,  "pvo≤30"),
]

BTC_PHASE3_FIXED_S_TERM = 5
BTC_PHASE3_FIXED_L_TERM = 26   # Phase 2 で最優秀だった値
BTC_PHASE3_BASELINE_LABEL = "disabled"  # 初期値不明なため、無効を比較基準とする


# ============================================================
# config 操作
# ============================================================

def read_config(config_file):
    with open(config_file, 'r', encoding='utf-8') as f:
        return f.read()


def write_config(config_file, content):
    with open(config_file, 'w', encoding='utf-8') as f:
        f.write(content)


def set_pvo_threshold_params(config_file, enabled, threshold):
    """
    PVO閾値フィルター設定を変更する。
    enabled=None  → enable_pvo_filter=0（完全無効）
    enabled=1     → enable_pvo_filter=1 + pvo_threshold=threshold
    """
    content = read_config(config_file)

    if enabled is None:
        # フィルタを完全に無効化
        content = re.sub(
            r'^(enable_pvo_filter\s*=\s*).*$',
            'enable_pvo_filter = 0',
            content, flags=re.MULTILINE
        )
    else:
        # フィルタを有効化して閾値を設定
        content = re.sub(
            r'^(enable_pvo_filter\s*=\s*).*$',
            'enable_pvo_filter = 1',
            content, flags=re.MULTILINE
        )
        # 注意: ^pvo_threshold は composite_exit_pvo_threshold にマッチしない（行頭マッチ）
        content = re.sub(
            r'^(pvo_threshold\s*=\s*).*$',
            f'pvo_threshold = {threshold}',
            content, flags=re.MULTILINE
        )

    write_config(config_file, content)


def set_pvo_ema_params(config_file, s_term, l_term):
    """PVO EMA期間設定を変更する"""
    content = read_config(config_file)

    content = re.sub(
        r'^(pvo_s_term\s*=\s*).*$',
        f'pvo_s_term = {s_term}',
        content, flags=re.MULTILINE
    )
    content = re.sub(
        r'^(pvo_l_term\s*=\s*).*$',
        f'pvo_l_term = {l_term}',
        content, flags=re.MULTILINE
    )

    write_config(config_file, content)


def restore_pvo_params(config_file, orig_enabled, orig_threshold, orig_s_term, orig_l_term):
    """全PVO設定を元の値に戻す"""
    content = read_config(config_file)

    content = re.sub(
        r'^(enable_pvo_filter\s*=\s*).*$',
        f'enable_pvo_filter = {orig_enabled}',
        content, flags=re.MULTILINE
    )
    content = re.sub(
        r'^(pvo_threshold\s*=\s*).*$',
        f'pvo_threshold = {orig_threshold}',
        content, flags=re.MULTILINE
    )
    content = re.sub(
        r'^(pvo_s_term\s*=\s*).*$',
        f'pvo_s_term = {orig_s_term}',
        content, flags=re.MULTILINE
    )
    content = re.sub(
        r'^(pvo_l_term\s*=\s*).*$',
        f'pvo_l_term = {orig_l_term}',
        content, flags=re.MULTILINE
    )

    write_config(config_file, content)


def get_original_pvo_params(config_file):
    """現在のPVO設定値を読み込んで返す"""
    content = read_config(config_file)

    m_en  = re.search(r'^enable_pvo_filter\s*=\s*(\d+)',  content, re.MULTILINE)
    m_th  = re.search(r'^pvo_threshold\s*=\s*(-?\d+)',    content, re.MULTILINE)
    m_st  = re.search(r'^pvo_s_term\s*=\s*(\d+)',         content, re.MULTILINE)
    m_lt  = re.search(r'^pvo_l_term\s*=\s*(\d+)',         content, re.MULTILINE)

    enabled   = int(m_en.group(1)) if m_en else 1
    threshold = int(m_th.group(1)) if m_th else 10
    s_term    = int(m_st.group(1)) if m_st else 5
    l_term    = int(m_lt.group(1)) if m_lt else 70

    return enabled, threshold, s_term, l_term


# ============================================================
# バックテスト実行
# ============================================================

def get_latest_result_file(results_dir):
    """最新のバックテスト結果 JSON を返す"""
    if not os.path.isdir(results_dir):
        return None
    files = [f for f in os.listdir(results_dir)
             if f.startswith('quarterly_results_') and f.endswith('.json')]
    if not files:
        return None
    return os.path.join(results_dir, max(files))


def run_backtest(results_dir):
    """
    run_quarterly_backtest.py をサブプロセスで実行し、結果 JSON のパスを返す。
    失敗時は None を返す。
    """
    cmd = [sys.executable, 'run_quarterly_backtest.py', '--config', 'config.ini']
    result = subprocess.run(
        cmd,
        capture_output=True, text=True,
        timeout=600,
        cwd=WORKSPACE_ROOT
    )
    if result.returncode != 0:
        print(f"   ❌ バックテスト失敗:\n{result.stderr[-800:]}")
        return None
    return get_latest_result_file(results_dir)


# ============================================================
# 結果解析
# ============================================================

def extract_quarterly(result_file):
    """結果 JSON から Q 別データを抽出"""
    with open(result_file, encoding='utf-8') as f:
        data = json.load(f)

    quarterly = {}
    for q in data.get('quarterly', []):
        key = f"{q['year']}Q{q['quarter']}"
        quarterly[key] = {
            'pnl':    round(q['metrics']['total_pnl'], 2),
            'trades': q['metrics']['trades'],
        }

    annual = {}
    for yr, metrics in data.get('annual', {}).items():
        annual[yr] = {
            'pnl':    round(metrics.get('total_pnl', 0), 2),
            'trades': metrics.get('total_trades', 0),
        }

    total_pnl    = round(sum(q['pnl'] for q in quarterly.values()), 2)
    total_trades = sum(q['trades'] for q in quarterly.values())

    return quarterly, annual, total_pnl, total_trades


# ============================================================
# 表示
# ============================================================

DIVIDER = "=" * 120


def print_sweep_table(phase_name, all_results, quarters, baseline_label):
    """Q別・累積損益の比較表を出力"""
    print()
    print(DIVIDER)
    print(f"  {phase_name} 結果")
    print(DIVIDER)

    q_width = 9
    header = f"{'設定':<28}"
    for q in quarters:
        header += f" {q:>{q_width}}"
    header += f" {'合計PnL':>10}  {'取引数':>6}"
    print(header)
    print("-" * 120)

    baseline_row = next((r for r in all_results if r['label'] == baseline_label), None)

    for r in all_results:
        is_base = (r['label'] == baseline_label)
        marker = "★" if is_base else " "
        row = f"{marker} {r['label']:<26}"
        for q in quarters:
            pnl = r['quarterly'].get(q, {}).get('pnl', None)
            if pnl is None:
                row += f" {'N/A':>{q_width}}"
            else:
                row += f" {pnl:>{q_width}.2f}"
        row += f" {r['total_pnl']:>10.2f}  {r['total_trades']:>6}"
        if is_base:
            row += "  ← BASELINE"
        elif baseline_row and not r.get('error'):
            diff = r['total_pnl'] - baseline_row['total_pnl']
            row += f"  ({diff:+.2f})"
        print(row)

    print("-" * 120)

    # 取引数テーブル
    print()
    print(f"  【取引数詳細】")
    th_row = f"{'設定':<28}"
    for q in quarters:
        th_row += f" {q:>{q_width}}"
    th_row += f" {'合計':>10}"
    print(th_row)
    print("-" * 90)
    for r in all_results:
        is_base = (r['label'] == baseline_label)
        marker = "★" if is_base else " "
        row = f"{marker} {r['label']:<26}"
        for q in quarters:
            trades = r['quarterly'].get(q, {}).get('trades', None)
            if trades is None:
                row += f" {'N/A':>{q_width}}"
            else:
                row += f" {trades:>{q_width}}"
        row += f" {r['total_trades']:>10}"
        if is_base:
            row += "  ← BASELINE"
        print(row)
    print()


def print_final_summary(phase_name, all_results, baseline_label):
    """最終サマリーを出力"""
    print(DIVIDER)
    print(f"  {phase_name} 分析サマリー")
    print(DIVIDER)

    baseline = next((r for r in all_results if r['label'] == baseline_label), None)
    if not baseline:
        print("  ベースラインデータが見つかりません")
        return

    valid_results = [r for r in all_results if not r.get('error')]
    sorted_results = sorted(valid_results, key=lambda x: x['total_pnl'], reverse=True)

    print(f"  ベースライン ({baseline_label}): {baseline['total_pnl']:+.2f} USD / {baseline['total_trades']} trades")
    print()
    print(f"  ランキング (累積損益順):")
    for i, r in enumerate(sorted_results):
        diff = r['total_pnl'] - baseline['total_pnl']
        is_base = (r['label'] == baseline_label)
        marker = "★" if is_base else f"  {i+1}"
        print(f"    {marker}. {r['label']:<28}  {r['total_pnl']:>9.2f} USD  ({diff:+.2f})  {r['total_trades']} trades")

    if sorted_results:
        best = sorted_results[0]
        if best['label'] != baseline_label:
            diff = best['total_pnl'] - baseline['total_pnl']
            pct = diff / abs(baseline['total_pnl']) * 100 if baseline['total_pnl'] != 0 else 0
            print()
            print(f"  → 最優秀: {best['label']}  ベースライン比 {diff:+.2f} USD ({pct:+.1f}%)")
        else:
            print()
            print(f"  → 現ベースライン（{baseline_label}）が最優秀")
    print()


def print_progress(phase_name, current, total, elapsed_sec, label):
    """進捗バーと推定残り時間を表示"""
    pct = (current / total) * 100
    filled = int(pct / 5)
    bar = "█" * filled + "░" * (20 - filled)
    avg_sec = elapsed_sec / current if current > 0 else 0
    remain_sec = avg_sec * (total - current)
    remain_min = remain_sec / 60
    print(f"  [{bar}] {current}/{total} ({pct:.0f}%)  経過: {elapsed_sec/60:.1f}分  "
          f"残り推定: {remain_min:.1f}分  → {label}")


# ============================================================
# Phase 1: PVO閾値スイープ
# ============================================================

def run_phase1(config_file, results_dir, sweep_params, baseline_label):
    """Phase 1 実行: PVO閾値スイープ"""
    phase_name = "Phase 1 [PVO閾値スイープ]"
    orig_enabled, orig_threshold, orig_s_term, orig_l_term = get_original_pvo_params(config_file)
    total = len(sweep_params)

    print()
    print(DIVIDER)
    print(f"  {phase_name} 開始  ({total} パターン)")
    print(f"  元の設定: enable_pvo_filter={orig_enabled}, pvo_threshold={orig_threshold}")
    print(DIVIDER)

    all_results = []
    phase_start = datetime.now()

    try:
        for i, (enabled, threshold, label) in enumerate(sweep_params, 1):
            en_str = "無効" if enabled is None else f"有効(threshold={threshold})"
            print(f"\n[{i}/{total}] {label}  (PVOフィルタ: {en_str})")

            # 進捗表示
            elapsed = (datetime.now() - phase_start).total_seconds()
            print_progress(phase_name, i - 1, total, elapsed, label)

            # config 変更（enable_pvo_filter + pvo_threshold を設定）
            set_pvo_threshold_params(config_file, enabled, threshold)

            # 変更確認（最初の1回だけ表示）
            if i == 1:
                _verify_config_change(config_file, enabled, threshold, None, None)

            # バックテスト実行
            start = datetime.now()
            result_file = run_backtest(results_dir)
            elapsed_run = (datetime.now() - start).total_seconds()

            if not result_file:
                print(f"   ❌ スキップ")
                all_results.append({
                    'label': label, 'enabled': enabled, 'threshold': threshold,
                    'quarterly': {}, 'annual': {},
                    'total_pnl': 0, 'total_trades': 0, 'error': True,
                })
                continue

            quarterly, annual, total_pnl, total_trades = extract_quarterly(result_file)
            print(f"   ✅ {elapsed_run:.0f}秒  合計={total_pnl:+.2f} USD  {total_trades}trades")

            all_results.append({
                'label': label,
                'enabled': enabled,
                'threshold': threshold,
                'quarterly': quarterly,
                'annual': annual,
                'total_pnl': total_pnl,
                'total_trades': total_trades,
                'elapsed_sec': round(elapsed_run, 1),
                'result_file': result_file,
            })

    finally:
        # 元の設定に必ず戻す
        restore_pvo_params(config_file, orig_enabled, orig_threshold, orig_s_term, orig_l_term)
        total_elapsed = (datetime.now() - phase_start).total_seconds()
        print(f"\n🔄 config を元の設定に復元")
        print(f"   enable_pvo_filter={orig_enabled}, pvo_threshold={orig_threshold}")
        print(f"   Phase 1 合計所要時間: {total_elapsed/60:.1f}分")

    return all_results


# ============================================================
# Phase 3: l_term=26固定 + 閾値スイープ
# ============================================================

def run_phase3(config_file, results_dir, sweep_params, fixed_s_term, fixed_l_term, baseline_label):
    """Phase 3 実行: EMA期間を固定した上でPVO閾値スイープ"""
    phase_name = f"Phase 3 [l_term={fixed_l_term}固定 + 閾値スイープ]"
    orig_enabled, orig_threshold, orig_s_term, orig_l_term = get_original_pvo_params(config_file)
    total = len(sweep_params)

    print()
    print(DIVIDER)
    print(f"  {phase_name} 開始  ({total} パターン)")
    print(f"  固定設定: pvo_s_term={fixed_s_term}, pvo_l_term={fixed_l_term}")
    print(f"  元の設定: enable_pvo_filter={orig_enabled}, pvo_threshold={orig_threshold}, "
          f"pvo_s_term={orig_s_term}, pvo_l_term={orig_l_term}")
    print(DIVIDER)

    all_results = []
    phase_start = datetime.now()

    try:
        for i, (enabled, threshold, label) in enumerate(sweep_params, 1):
            en_str = "無効" if enabled is None else f"有効(threshold={threshold})"
            print(f"\n[{i}/{total}] {label}  (PVOフィルタ: {en_str}, l_term={fixed_l_term})")

            elapsed = (datetime.now() - phase_start).total_seconds()
            print_progress(phase_name, i - 1, total, elapsed, label)

            # EMA期間を固定値に設定してから閾値を設定
            set_pvo_ema_params(config_file, fixed_s_term, fixed_l_term)
            set_pvo_threshold_params(config_file, enabled, threshold)

            # 変更確認（最初の1回だけ表示）
            if i == 1:
                _verify_config_change(config_file, enabled, threshold, fixed_s_term, fixed_l_term)

            start = datetime.now()
            result_file = run_backtest(results_dir)
            elapsed_run = (datetime.now() - start).total_seconds()

            if not result_file:
                print(f"   ❌ スキップ")
                all_results.append({
                    'label': label, 'enabled': enabled, 'threshold': threshold,
                    'quarterly': {}, 'annual': {},
                    'total_pnl': 0, 'total_trades': 0, 'error': True,
                })
                continue

            quarterly, annual, total_pnl, total_trades = extract_quarterly(result_file)
            print(f"   ✅ {elapsed_run:.0f}秒  合計={total_pnl:+.2f} USD  {total_trades}trades")

            all_results.append({
                'label': label,
                'enabled': enabled,
                'threshold': threshold,
                'fixed_s_term': fixed_s_term,
                'fixed_l_term': fixed_l_term,
                'quarterly': quarterly,
                'annual': annual,
                'total_pnl': total_pnl,
                'total_trades': total_trades,
                'elapsed_sec': round(elapsed_run, 1),
                'result_file': result_file,
            })

    finally:
        restore_pvo_params(config_file, orig_enabled, orig_threshold, orig_s_term, orig_l_term)
        total_elapsed = (datetime.now() - phase_start).total_seconds()
        print(f"\n🔄 config を元の設定に復元")
        print(f"   enable_pvo_filter={orig_enabled}, pvo_threshold={orig_threshold}, "
              f"pvo_s_term={orig_s_term}, pvo_l_term={orig_l_term}")
        print(f"   Phase 3 合計所要時間: {total_elapsed/60:.1f}分")

    return all_results


# ============================================================
# Phase 2: PVO EMA期間スイープ
# ============================================================

def run_phase2(config_file, results_dir, sweep_params, baseline_label):
    """Phase 2 実行: PVO EMA期間スイープ"""
    phase_name = "Phase 2 [PVO EMA期間スイープ]"
    orig_enabled, orig_threshold, orig_s_term, orig_l_term = get_original_pvo_params(config_file)
    total = len(sweep_params)

    print()
    print(DIVIDER)
    print(f"  {phase_name} 開始  ({total} パターン)")
    print(f"  元の設定: pvo_s_term={orig_s_term}, pvo_l_term={orig_l_term}")
    print(f"  ※ enable_pvo_filter={orig_enabled}, pvo_threshold={orig_threshold} は固定")
    print(DIVIDER)

    all_results = []
    phase_start = datetime.now()

    try:
        for i, (s_term, l_term, label) in enumerate(sweep_params, 1):
            print(f"\n[{i}/{total}] {label}  (pvo_s={s_term}, pvo_l={l_term})")

            # 進捗表示
            elapsed = (datetime.now() - phase_start).total_seconds()
            print_progress(phase_name, i - 1, total, elapsed, label)

            # config 変更（EMA期間のみ変更、フィルタ有効設定は維持）
            set_pvo_ema_params(config_file, s_term, l_term)

            # 変更確認（最初の1回だけ表示）
            if i == 1:
                _verify_config_change(config_file, None, None, s_term, l_term)

            # バックテスト実行
            start = datetime.now()
            result_file = run_backtest(results_dir)
            elapsed_run = (datetime.now() - start).total_seconds()

            if not result_file:
                print(f"   ❌ スキップ")
                all_results.append({
                    'label': label, 's_term': s_term, 'l_term': l_term,
                    'quarterly': {}, 'annual': {},
                    'total_pnl': 0, 'total_trades': 0, 'error': True,
                })
                continue

            quarterly, annual, total_pnl, total_trades = extract_quarterly(result_file)
            print(f"   ✅ {elapsed_run:.0f}秒  合計={total_pnl:+.2f} USD  {total_trades}trades")

            all_results.append({
                'label': label,
                's_term': s_term,
                'l_term': l_term,
                'quarterly': quarterly,
                'annual': annual,
                'total_pnl': total_pnl,
                'total_trades': total_trades,
                'elapsed_sec': round(elapsed_run, 1),
                'result_file': result_file,
            })

    finally:
        # 元の設定に必ず戻す
        restore_pvo_params(config_file, orig_enabled, orig_threshold, orig_s_term, orig_l_term)
        total_elapsed = (datetime.now() - phase_start).total_seconds()
        print(f"\n🔄 config を元の設定に復元")
        print(f"   pvo_s_term={orig_s_term}, pvo_l_term={orig_l_term}")
        print(f"   Phase 2 合計所要時間: {total_elapsed/60:.1f}分")

    return all_results


# ============================================================
# 設定変更の確認（デバッグ用）
# ============================================================

def _verify_config_change(config_file, enabled, threshold, s_term, l_term):
    """設定変更が正しく適用されたかを読み返して確認"""
    cur_enabled, cur_threshold, cur_s_term, cur_l_term = get_original_pvo_params(config_file)

    print(f"   [設定確認] enable_pvo={cur_enabled}, threshold={cur_threshold}, "
          f"s_term={cur_s_term}, l_term={cur_l_term}")

    ok = True
    if enabled is not None and cur_enabled != enabled:
        print(f"   ⚠️  enable_pvo_filter: 期待={enabled}, 実際={cur_enabled}")
        ok = False
    if enabled is None and cur_enabled != 0:
        print(f"   ⚠️  enable_pvo_filter: 期待=0(無効), 実際={cur_enabled}")
        ok = False
    if threshold is not None and cur_threshold != threshold:
        print(f"   ⚠️  pvo_threshold: 期待={threshold}, 実際={cur_threshold}")
        ok = False
    if s_term is not None and cur_s_term != s_term:
        print(f"   ⚠️  pvo_s_term: 期待={s_term}, 実際={cur_s_term}")
        ok = False
    if l_term is not None and cur_l_term != l_term:
        print(f"   ⚠️  pvo_l_term: 期待={l_term}, 実際={cur_l_term}")
        ok = False
    if ok:
        print(f"   ✅ 設定変更確認OK")


# ============================================================
# 結果保存
# ============================================================

def save_results(phase1_results, phase2_results, phase3_results,
                 quarters_p1, quarters_p2, quarters_p3):
    """全結果をJSONに保存"""
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = os.path.join(SWEEP_RESULTS_DIR, f'pvo_sweep_{ts}.json')

    data = {
        'generated_at': datetime.now().isoformat(),
        'symbol': 'BTC',
        'config': BTC_CONFIG_FILE,
        'phase1_threshold_sweep': {
            'description': 'PVO閾値スイープ: enable_pvo_filter + pvo_threshold（l_term=70固定）',
            'baseline': BTC_THRESHOLD_BASELINE_LABEL,
            'quarters': quarters_p1,
            'results': phase1_results,
        },
        'phase2_ema_sweep': {
            'description': 'PVO EMA期間スイープ: pvo_s_term + pvo_l_term',
            'baseline': BTC_EMA_BASELINE_LABEL,
            'quarters': quarters_p2,
            'results': phase2_results,
        },
        'phase3_threshold_l26_sweep': {
            'description': f'PVO閾値スイープ: l_term={BTC_PHASE3_FIXED_L_TERM}固定 + 閾値変化（Phase2最優秀EMA期間）',
            'fixed_s_term': BTC_PHASE3_FIXED_S_TERM,
            'fixed_l_term': BTC_PHASE3_FIXED_L_TERM,
            'baseline': BTC_PHASE3_BASELINE_LABEL,
            'quarters': quarters_p3,
            'results': phase3_results,
        },
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n💾 結果保存: {output_path}")
    return output_path


# ============================================================
# メイン
# ============================================================

def main():
    parser = argparse.ArgumentParser(description='PVOフィルター有効性検証スクリプト（BTC専用）')
    parser.add_argument('--phase', type=int, choices=[1, 2, 3], default=None,
                        help='実行フェーズ: 1=閾値スイープのみ, 2=EMA期間スイープのみ, '
                             '3=l_term=26固定+閾値スイープのみ, 省略=全フェーズ')
    args = parser.parse_args()

    run_phase1_flag = (args.phase is None or args.phase == 1)
    run_phase2_flag = (args.phase is None or args.phase == 2)
    run_phase3_flag = (args.phase is None or args.phase == 3)

    print()
    print(DIVIDER)
    print("  PVO フィルター有効性検証（BTC専用）")
    print(f"  実行: {'Phase1+Phase2' if not args.phase else f'Phase{args.phase}のみ'}")
    print(f"  config: {BTC_CONFIG_FILE}")
    print(f"  総パターン数: "
          f"{len(BTC_THRESHOLD_SWEEP) if run_phase1_flag else 0} (P1) + "
          f"{len(BTC_EMA_SWEEP) if run_phase2_flag else 0} (P2) + "
          f"{len(BTC_PHASE3_SWEEP) if run_phase3_flag else 0} (P3)")
    print(DIVIDER)

    # 現在のconfig確認
    orig_enabled, orig_threshold, orig_s_term, orig_l_term = get_original_pvo_params(BTC_CONFIG_FILE)
    print(f"\n[現在のPVO設定]")
    print(f"  enable_pvo_filter = {orig_enabled}")
    print(f"  pvo_threshold     = {orig_threshold}")
    print(f"  pvo_s_term        = {orig_s_term}")
    print(f"  pvo_l_term        = {orig_l_term}")

    # ============ Phase 1 実行 ============
    phase1_results = []
    quarters_p1 = []

    if run_phase1_flag:
        phase1_results = run_phase1(
            BTC_CONFIG_FILE, BTC_RESULTS_DIR,
            BTC_THRESHOLD_SWEEP, BTC_THRESHOLD_BASELINE_LABEL
        )
        # Q 一覧の収集
        q_set = set()
        for r in phase1_results:
            q_set.update(r['quarterly'].keys())
        quarters_p1 = sorted(q_set)

        # 結果テーブル表示
        print_sweep_table("Phase 1 [PVO閾値スイープ] BTC",
                          phase1_results, quarters_p1, BTC_THRESHOLD_BASELINE_LABEL)
        print_final_summary("Phase 1 [PVO閾値スイープ] BTC",
                            phase1_results, BTC_THRESHOLD_BASELINE_LABEL)

    # ============ Phase 2 実行 ============
    phase2_results = []
    quarters_p2 = []

    if run_phase2_flag:
        phase2_results = run_phase2(
            BTC_CONFIG_FILE, BTC_RESULTS_DIR,
            BTC_EMA_SWEEP, BTC_EMA_BASELINE_LABEL
        )
        q_set = set()
        for r in phase2_results:
            q_set.update(r['quarterly'].keys())
        quarters_p2 = sorted(q_set)

        print_sweep_table("Phase 2 [PVO EMA期間スイープ] BTC",
                          phase2_results, quarters_p2, BTC_EMA_BASELINE_LABEL)
        print_final_summary("Phase 2 [PVO EMA期間スイープ] BTC",
                            phase2_results, BTC_EMA_BASELINE_LABEL)

    # ============ Phase 3 実行 ============
    phase3_results = []
    quarters_p3 = []

    if run_phase3_flag:
        phase3_results = run_phase3(
            BTC_CONFIG_FILE, BTC_RESULTS_DIR,
            BTC_PHASE3_SWEEP,
            BTC_PHASE3_FIXED_S_TERM, BTC_PHASE3_FIXED_L_TERM,
            BTC_PHASE3_BASELINE_LABEL
        )
        q_set = set()
        for r in phase3_results:
            q_set.update(r['quarterly'].keys())
        quarters_p3 = sorted(q_set)

        print_sweep_table(
            f"Phase 3 [l_term={BTC_PHASE3_FIXED_L_TERM}固定+閾値スイープ] BTC",
            phase3_results, quarters_p3, BTC_PHASE3_BASELINE_LABEL
        )
        print_final_summary(
            f"Phase 3 [l_term={BTC_PHASE3_FIXED_L_TERM}固定+閾値スイープ] BTC",
            phase3_results, BTC_PHASE3_BASELINE_LABEL
        )

    # ============ 結果保存 ============
    if phase1_results or phase2_results or phase3_results:
        save_results(phase1_results, phase2_results, phase3_results,
                     quarters_p1, quarters_p2, quarters_p3)

    print()
    print(DIVIDER)
    print("  全フェーズ完了")
    print(DIVIDER)


if __name__ == '__main__':
    main()
