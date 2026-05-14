#!/usr/bin/env python3
"""
H-058: スケールインADXフィルタ 検証スクリプト

仮説:
  スケールイン（追加エントリー）発動条件に ADX >= threshold を追加する
  → レンジ相場（低ADX）でのスケールインを禁止し、トレンド相場のみで追加

【狙ったトレードと期待効果】
  - ADXが低い（レンジ）状態でスケールインしたが、その後反転して損失になったトレード
  - 期待: それらのトレードでスケールインがキャンセルされ、損失幅が縮小
  - 代償: ADXが高いトレンド相場でも条件を満たさず見送られる可能性（ケアが必要）

【標準化分析】
  ATR標準化PnL = pnl_pct / (atr / entry_price * 100)
  スケールイン発動時のADX値を記録し、ADX帯域別にPnL分布を比較する

ベースライン(H-056 ScaleIn採用後): PnL=+3,417 USD / MaxDD=22.80%
採用基準: PnL >= +3,417 USD かつ MaxDD <= 22.80% (両指標維持 or 改善)
"""

import subprocess
import configparser
import re
import json
import os
import glob

CONFIG_PATH = "src/config.ini"
BASELINE_PNL   = 3417.0
BASELINE_MAXDD = 22.80

ADX_THRESHOLDS = [0, 25, 30, 35]   # 0 = OFF（ベースライン）


def read_config():
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_PATH)
    return cfg

def write_config(cfg):
    with open(CONFIG_PATH, 'w') as f:
        cfg.write(f)

def set_adx_threshold(threshold: float):
    cfg = read_config()
    cfg['ScaleIn']['scale_in_adx_threshold'] = str(threshold)
    write_config(cfg)

def run_backtest():
    result = subprocess.run(
        ["python3", "bot.py"],
        capture_output=True, text=True, cwd="src"
    )
    return result.stdout + result.stderr

def parse_results(output):
    pnl = max_dd = trades = None
    for pattern in [r"最終損益:\s*([+-]?[\d,]+\.?\d*)\s*\[", r"損益累計:([+-]?[\d,]+\.?\d*)\s*\["]:
        m = re.search(pattern, output)
        if m:
            try:
                pnl = float(m.group(1).replace(',', ''))
                break
            except ValueError:
                pass
    for pattern in [r"最大ドローダウン率:\s*([0-9]+\.?[0-9]*)\s*\[%\]", r"最大ドローダウン率[:\s]+([0-9]+\.?[0-9]*)"]:
        m = re.search(pattern, output)
        if m:
            max_dd = float(m.group(1))
            break
    m = re.search(r"Trades:\s*(\d+)", output)
    if m:
        trades = int(m.group(1))
    return pnl, max_dd, trades

def get_latest_trade_log(log_dir="src/logs"):
    pattern = os.path.join(log_dir, "trade_log_*.json")
    files = sorted(glob.glob(pattern))
    return files[-1] if files else None

def load_trade_log(filepath):
    if not filepath or not os.path.exists(filepath):
        return []
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('trades', [])

def compute_normalized_pnl(trade):
    """ATR標準化PnL = pnl_usd / ATR値
    ATRはvolatilityフィルター値で代替（1ATR分の利益を基準）"""
    entry = trade.get('entry', {})
    result = trade.get('result', {})
    if not result:
        return None
    atr = entry.get('filters', {}).get('volatility', {}).get('value', 0)
    pnl_usd = result.get('pnl_usd', None)
    if atr <= 0 or pnl_usd is None:
        return None
    return pnl_usd / atr

def get_scale_in_adx_at_event(trade):
    """トレードのスケールインイベント時のADX値を推定する"""
    scale_events = trade.get('scale_events', [])
    for e in scale_events:
        if e['type'] == 'SCALE_IN':
            return e.get('adx', None)
    return None

def analyze_trades(trades, label):
    """全トレードと特にスケールイン発動トレードを分析"""
    completed = [t for t in trades if t.get('result') is not None]
    if not completed:
        print(f"  [{label}] 完了トレードなし")
        return {}

    trades_with_si = [t for t in completed if any(
        e['type'] == 'SCALE_IN' for e in t.get('scale_events', [])
    )]
    trades_no_si = [t for t in completed if not any(
        e['type'] == 'SCALE_IN' for e in t.get('scale_events', [])
    )]

    si_wins  = [t for t in trades_with_si if t.get('result', {}).get('win', False)]
    si_loses = [t for t in trades_with_si if not t.get('result', {}).get('win', False)]

    # ATR標準化
    norm_all  = [x for x in (compute_normalized_pnl(t) for t in completed) if x is not None]
    norm_si   = [x for x in (compute_normalized_pnl(t) for t in trades_with_si) if x is not None]
    norm_nosi = [x for x in (compute_normalized_pnl(t) for t in trades_no_si) if x is not None]

    avg_all  = sum(norm_all)  / len(norm_all)  if norm_all  else 0
    avg_si   = sum(norm_si)   / len(norm_si)   if norm_si   else 0
    avg_nosi = sum(norm_nosi) / len(norm_nosi) if norm_nosi else 0

    win_rate_si = len(si_wins) / len(trades_with_si) * 100 if trades_with_si else 0

    print(f"\n  [{label}]")
    print(f"    全{len(completed)}トレード  スケールイン発動: {len(trades_with_si)}件")
    print(f"    SI発動トレード: 勝率={win_rate_si:.0f}%  ({len(si_wins)}勝/{len(si_loses)}敗)")
    print(f"    ATR標準化PnL: 全体={avg_all:+.3f}  SI発動={avg_si:+.3f}  SI未発動={avg_nosi:+.3f}")

    # SI発動トレードの個別表示
    if trades_with_si:
        print(f"    ─── スケールイン発動トレード ───")
        for t in trades_with_si:
            entry  = t.get('entry', {})
            result = t.get('result', {})
            norm   = compute_normalized_pnl(t)
            adx    = get_scale_in_adx_at_event(t)
            date   = entry.get('close_time_dt', '')
            side   = entry.get('side', '')
            pnl    = result.get('pnl_usd', 0)
            win    = "✓" if result.get('win', False) else "✗"
            adx_str = f"ADX={adx:.1f}" if adx is not None else "ADX=N/A"
            norm_str = f"{norm:+.2f}ATR" if norm is not None else "N/A"
            print(f"    {win} {date} {side:4s}  {adx_str:10s}  PnL={pnl:+.1f} USD  標準化={norm_str}")

    return {
        'total': len(completed),
        'si_count': len(trades_with_si),
        'si_win_rate': win_rate_si,
        'avg_norm_all': avg_all,
        'avg_norm_si': avg_si,
        'avg_norm_nosi': avg_nosi,
        'trades_with_si': trades_with_si,
    }

def compare_si_trades_across_thresholds(base_trades, th_trades, threshold):
    """スケールインが発動しなくなったトレードのPnL変化を比較"""
    def trade_key(t):
        return t.get('entry', {}).get('close_time_dt', '')

    base_by_key = {trade_key(t): t for t in base_trades if t.get('result')}
    th_by_key   = {trade_key(t): t for t in th_trades   if t.get('result')}

    base_si_keys = {trade_key(t) for t in base_trades
                    if any(e['type'] == 'SCALE_IN' for e in t.get('scale_events', []))}

    changed = []
    for k in sorted(base_si_keys):
        if k not in base_by_key or k not in th_by_key:
            continue
        bt = base_by_key[k]
        ht = th_by_key[k]

        # H-058でSIが消えたか確認
        h_has_si = any(e['type'] == 'SCALE_IN' for e in ht.get('scale_events', []))
        base_pnl = bt.get('result', {}).get('pnl_usd', 0)
        h_pnl    = ht.get('result', {}).get('pnl_usd', 0)
        diff     = h_pnl - base_pnl

        changed.append({
            'date':     k,
            'side':     bt.get('entry', {}).get('side', ''),
            'price':    bt.get('entry', {}).get('price', 0),
            'si_cancelled': not h_has_si,
            'base_pnl': base_pnl,
            'h_pnl':    h_pnl,
            'diff':     diff,
            'norm_base': compute_normalized_pnl(bt),
            'norm_h':    compute_normalized_pnl(ht),
        })

    return changed

def main():
    print("=" * 70)
    print("H-058: スケールインADXフィルタ 検証")
    print(f"ベースライン: PnL={BASELINE_PNL:+.0f} USD / MaxDD={BASELINE_MAXDD:.2f}%")
    print(f"ADXしきい値テスト: {ADX_THRESHOLDS}")
    print("=" * 70)

    results = {}
    trade_logs = {}

    for thr in ADX_THRESHOLDS:
        label = f"ADX={thr}" if thr > 0 else "OFF(ベースライン)"
        print(f"\n[{label}] 実行中...")
        set_adx_threshold(thr)
        out = run_backtest()
        pnl, dd, tr = parse_results(out)
        results[thr] = {'pnl': pnl, 'dd': dd, 'tr': tr}
        log_path = get_latest_trade_log()
        trade_logs[thr] = load_trade_log(log_path)
        print(f"  結果: PnL={pnl:+.0f} USD  MaxDD={dd:.2f}%  Trades={tr}")

    # 設定をOFF（デフォルト=0）に戻す
    set_adx_threshold(0)

    # ---- トレード詳細分析 ----
    print("\n" + "=" * 70)
    print("【トレード詳細分析】")
    print("=" * 70)

    base_analysis = analyze_trades(trade_logs[0], "OFF(ベースライン)")

    for thr in ADX_THRESHOLDS[1:]:  # 0以外
        label = f"ADX>={thr}"
        analyze_trades(trade_logs[thr], label)

    # ---- スケールインが阻害されたトレードの比較 ----
    print("\n" + "=" * 70)
    print("【スケールインが阻害されたトレードの個別比較】")
    print("(ベースラインでSIあり → H-058でSIなし になったトレード)")
    print("=" * 70)

    for thr in ADX_THRESHOLDS[1:]:
        label = f"ADX>={thr}"
        changed = compare_si_trades_across_thresholds(trade_logs[0], trade_logs[thr], thr)
        cancelled = [c for c in changed if c['si_cancelled']]
        improved  = [c for c in cancelled if c['diff'] > 0.5]
        worsened  = [c for c in cancelled if c['diff'] < -0.5]
        unchanged = [c for c in cancelled if abs(c['diff']) <= 0.5]

        print(f"\n  [{label}]  SIキャンセル={len(cancelled)}件  "
              f"改善={len(improved)}件  悪化={len(worsened)}件  変化なし={len(unchanged)}件")

        if cancelled:
            print(f"  {'日時':24s} {'側':4s}  {'SI?':5s}  {'BASE':>8s}  {'H058':>8s}  {'差':>7s}  {'BASE標準化':>10s}  {'H058標準化':>10s}")
            for c in sorted(cancelled, key=lambda x: abs(x['diff']), reverse=True)[:10]:
                si_str = "→なし" if c['si_cancelled'] else "あり"
                nb = f"{c['norm_base']:+.2f}ATR" if c['norm_base'] is not None else "N/A"
                nh = f"{c['norm_h']:+.2f}ATR"    if c['norm_h']    is not None else "N/A"
                mark = "✅" if c['diff'] > 0.5 else ("⚠️" if c['diff'] < -0.5 else "  ")
                print(f"  {c['date']:24s} {c['side']:4s}  {si_str:5s}  "
                      f"{c['base_pnl']:+8.1f}  {c['h_pnl']:+8.1f}  {c['diff']:+7.1f}  "
                      f"{nb:>10s}  {nh:>10s}  {mark}")

    # ---- サマリ比較 ----
    print("\n" + "=" * 70)
    print("【スイープ結果サマリ】")
    print("=" * 70)
    print(f"  {'設定':<20s}  {'PnL':>10s}  {'Δ':>8s}  {'MaxDD':>8s}  {'Δ':>8s}  {'Trades':>6s}  {'採用?'}")
    print("  " + "-" * 75)
    for thr in ADX_THRESHOLDS:
        r = results[thr]
        pnl = r['pnl'] or 0
        dd  = r['dd']  or 0
        tr  = r['tr']  or 0
        dpnl = pnl - BASELINE_PNL
        ddd  = dd  - BASELINE_MAXDD
        label = f"ADX={thr}" if thr > 0 else "OFF"
        pnl_ok = pnl >= BASELINE_PNL
        dd_ok  = dd  <= BASELINE_MAXDD
        if pnl_ok and dd_ok:
            adopt = "✅ 採用候補"
        elif dd_ok:
            adopt = "⚠️ DD改善のみ"
        elif pnl_ok:
            adopt = "⚠️ PnL改善のみ"
        else:
            adopt = "❌ 非採用"
        print(f"  {label:<20s}  {pnl:>+10.0f}  {dpnl:>+8.0f}  {dd:>8.2f}%  {ddd:>+8.2f}%  {tr:>6d}  {adopt}")

    # ---- ATR標準化比較 ----
    print("\n" + "=" * 70)
    print("【ATR標準化PnL比較（スケールインの質の変化）】")
    print("=" * 70)

    for thr in ADX_THRESHOLDS:
        trades = trade_logs[thr]
        completed = [t for t in trades if t.get('result')]
        norm_all = [x for x in (compute_normalized_pnl(t) for t in completed) if x is not None]
        avg_all = sum(norm_all) / len(norm_all) if norm_all else 0

        si_trades = [t for t in completed if any(e['type'] == 'SCALE_IN' for e in t.get('scale_events', []))]
        norm_si = [x for x in (compute_normalized_pnl(t) for t in si_trades) if x is not None]
        avg_si = sum(norm_si) / len(norm_si) if norm_si else None

        label = f"ADX={thr}" if thr > 0 else "OFF"
        si_str = f"SI発動時={avg_si:+.3f}" if avg_si is not None else "SI発動=N/A"
        print(f"  [{label:8s}]  全体平均={avg_all:+.3f}ATR  {si_str}ATR  SI件数={len(si_trades)}")

    # ---- 最適閾値の判定 ----
    print("\n" + "=" * 70)
    print("【最終判定と考察】")
    print("=" * 70)

    best = None
    for thr in ADX_THRESHOLDS[1:]:
        r = results[thr]
        pnl = r['pnl'] or 0
        dd  = r['dd']  or 0
        if pnl >= BASELINE_PNL and dd <= BASELINE_MAXDD:
            if best is None or pnl > results[best]['pnl']:
                best = thr

    if best:
        br = results[best]
        print(f"  最適閾値: ADX >= {best}")
        print(f"  結果: PnL={br['pnl']:+.0f} USD ({br['pnl']-BASELINE_PNL:+.0f})  "
              f"MaxDD={br['dd']:.2f}% ({br['dd']-BASELINE_MAXDD:+.2f}%)")
        print(f"  判定: ✅ 採用")
    else:
        print(f"  採用基準を満たす閾値なし → ❌ H-058 非採用")
        # 最もDD改善効果の高い設定を参考表示
        best_dd = min(ADX_THRESHOLDS[1:], key=lambda t: results[t]['dd'] or 999)
        br = results[best_dd]
        print(f"  参考（最DD改善): ADX >= {best_dd}  PnL={br['pnl']:+.0f}  MaxDD={br['dd']:.2f}%")

    # 考察テンプレート
    print(f"\n【考察】")
    base_si = base_analysis.get('si_count', 0)
    base_total = base_analysis.get('total', 0)
    si_win_rate = base_analysis.get('si_win_rate', 0)

    print(f"  ベースラインのスケールイン発動数: {base_si}件 / {base_total}トレード")
    print(f"  スケールイン時の勝率: {si_win_rate:.0f}%")

    if si_win_rate >= 50:
        print(f"  → スケールイン自体は概ね有効 (勝率{si_win_rate:.0f}%)")
        print(f"     ADXフィルタで見送りが増えると一部機会損失が生じる可能性")
    else:
        print(f"  → スケールイン時の勝率が低い ({si_win_rate:.0f}%) → ADXフィルタの効果が期待される")

    if best:
        changed = compare_si_trades_across_thresholds(trade_logs[0], trade_logs[best], best)
        cancelled = [c for c in changed if c['si_cancelled']]
        improved_pct = len([c for c in cancelled if c['diff'] > 0.5]) / max(len(cancelled), 1) * 100
        print(f"  ADX>={best}でのSIキャンセル: {len(cancelled)}件 (うち改善={improved_pct:.0f}%)")

    print("\n設定をOFF（デフォルト=0）に戻しました")
    print("=" * 70)


if __name__ == "__main__":
    main()
