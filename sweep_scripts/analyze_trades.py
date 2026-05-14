#!/usr/bin/env python3
"""
H-048 前準備: 全トレード詳細分析スクリプト

分析観点（世界最高のトレーダー視点）:
1. 勝ちトレード / 負けトレードの分類と統計
2. エントリー条件（ADX, PVO, 相場局面）と結果の相関
3. MFE（Maximum Favorable Excursion）= 最大含み益 vs 実際の利益 → キャプチャー率
4. MAE（Maximum Adverse Excursion）= 最大逆行 → エントリーリスク評価
5. 残高水準別パフォーマンス（小中大残高での差異）
6. ドローダウン貢献トレードの特定
7. スケールアウト実施有無とその効果
8. 時系列・価格帯別の傾向
"""

import json
import sqlite3
import os
import sys
from datetime import datetime

TRADE_LOG = "/home/satoshi/work/satosystem/src/logs/trade_log_20260512234333.json"
OHLCV_DB  = "/home/satoshi/work/satosystem/ohlcv_data/ohlcv_cache.db"

# ============================================================
# データロード
# ============================================================
def load_trades(path):
    with open(path) as f:
        data = json.load(f)
    return data["trades"]

def load_ohlcv(db_path, symbol="BTC/USDT", timeframe=240):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    # テーブル名を確認
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    
    # symbolとtimeframeで検索
    target_table = None
    for t in tables:
        if "BTC" in t.upper() or "ohlcv" in t.lower():
            target_table = t
            break
    
    if target_table is None:
        print(f"Tables: {tables}")
        conn.close()
        return {}
    
    cur.execute(f"PRAGMA table_info({target_table})")
    cols = [r[1] for r in cur.fetchall()]
    
    # timestampとclose/high/lowを取得
    ts_col = next((c for c in cols if 'time' in c.lower() or 'ts' in c.lower()), cols[0])
    close_col = next((c for c in cols if 'close' in c.lower()), None)
    high_col = next((c for c in cols if 'high' in c.lower()), None)
    low_col = next((c for c in cols if 'low' in c.lower()), None)
    
    cur.execute(f"SELECT {ts_col},{high_col},{low_col},{close_col} FROM {target_table} ORDER BY {ts_col}")
    rows = cur.fetchall()
    conn.close()
    
    # タイムスタンプをキーにした辞書
    ohlcv = {}
    for ts, h, l, c in rows:
        ohlcv[int(ts)] = (h, l, c)
    
    return ohlcv

def parse_dt(dt_str):
    """'2024/01/30 12:00:00' や ISO形式を datetime に変換"""
    if not dt_str:
        return None
    for fmt in ("%Y/%m/%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(dt_str[:19], fmt)
        except:
            pass
    return None

def dt_to_ts_ms(dt):
    """datetime → milliseconds timestamp"""
    import calendar
    return int(calendar.timegm(dt.timetuple())) * 1000

# ============================================================
# MFE / MAE 計算
# ============================================================
def compute_mfe_mae(side, entry_ts_ms, exit_ts_ms, entry_price, ohlcv, tf_ms=240*60*1000):
    """
    OHLCV データから MFE（最大含み益）と MAE（最大逆行）を計算する。
    
    Returns: (mfe_usd_per_unit, mae_usd_per_unit, num_bars)
    """
    highs, lows = [], []
    ts = ((entry_ts_ms) // tf_ms + 1) * tf_ms  # エントリーの次のバーから
    end = exit_ts_ms + tf_ms

    # エントリーバーも含む（エントリー時点のバーのhigh/lowも重要）
    start_search = (entry_ts_ms // tf_ms) * tf_ms

    while ts <= end:
        if ts in ohlcv:
            h, l, c = ohlcv[ts]
            highs.append(h)
            lows.append(l)
        ts += tf_ms

    if not highs:
        return 0, 0, 0

    num_bars = len(highs)
    if side == 'BUY':
        max_high = max(highs)
        min_low  = min(lows)
        mfe = max_high - entry_price  # 最大有利方向
        mae = entry_price - min_low   # 最大逆行
    else:  # SELL
        max_high = max(highs)
        min_low  = min(lows)
        mfe = entry_price - min_low
        mae = max_high - entry_price

    return max(0, mfe), max(0, mae), num_bars

# ============================================================
# メイン分析
# ============================================================
def main():
    trades = load_trades(TRADE_LOG)
    print(f"トレード数: {len(trades)}")
    print()
    
    # OHLCV ロード
    ohlcv = load_ohlcv(OHLCV_DB)
    tf_ms = 240 * 60 * 1000  # 4時間足

    # ============================================================
    # 1. 基本トレード分類テーブル
    # ============================================================
    print("=" * 100)
    print("1. 全トレード詳細テーブル（ポートフォリオ寄与ベース）")
    print("=" * 100)
    print(f"{'No':>3} {'Date':>10} {'Side':>4} {'Entry':>8} {'Exit':>8} "
          f"{'ΔPort':>9} {'pnl_usd':>9} {'ScaleOut':>9} "
          f"{'MFE':>8} {'MAE':>8} {'Capture%':>9} {'DD%':>7} {'Bars':>5} {'ADX':>6} {'PVO':>6}")
    print("-" * 100)
    
    records = []
    prev_cum = 0
    
    for i, t in enumerate(trades):
        e  = t['entry']
        ex = t.get('exit', {}) or {}
        r  = t.get('result', {}) or {}
        
        side       = e.get('side', 'BUY')
        entry_dt   = parse_dt(e.get('close_time_dt', ''))
        exit_dt    = parse_dt(ex.get('close_time_dt', ''))
        entry_p    = e.get('price', 0)
        exit_p     = ex.get('price', 0)
        pnl_usd    = r.get('pnl_usd', 0) or 0
        cum        = r.get('cumulative_pnl', 0) or 0
        dd_pct     = r.get('max_drawdown_pct', 0) or 0
        adx        = (e.get('filters', {}).get('adx', {}) or {}).get('value', 0) or 0
        pvo        = (e.get('filters', {}).get('pvo', {}) or {}).get('value', 0) or 0
        exit_reason = ex.get('reason', '')
        
        delta_cum = cum - prev_cum  # ポートフォリオへの実際の寄与
        scale_out_pnl = delta_cum - pnl_usd  # スケールアウト分
        
        # MFE / MAE 計算
        mfe_pts = mae_pts = 0.0
        num_bars = 0
        if entry_dt and exit_dt and ohlcv:
            ts_entry = dt_to_ts_ms(entry_dt)
            ts_exit  = dt_to_ts_ms(exit_dt)
            mfe_pts, mae_pts, num_bars = compute_mfe_mae(side, ts_entry, ts_exit, entry_p, ohlcv, tf_ms)
        
        # キャプチャー率: 実際の利益 / MFE
        mfe_usd = mfe_pts  # 1単位あたりの含み益（BTCの場合はpriceベース、量は含まない）
        capture_pct = (delta_cum / (mfe_pts + 0.001)) * 100 if mfe_pts > 0 else 0
        
        win = delta_cum > 0
        
        records.append({
            'no': i+1,
            'date': e.get('close_time_dt', '')[:10],
            'side': side,
            'entry_p': entry_p,
            'exit_p': exit_p,
            'delta_cum': delta_cum,
            'pnl_usd': pnl_usd,
            'scale_out_pnl': scale_out_pnl,
            'mfe_pts': mfe_pts,
            'mae_pts': mae_pts,
            'capture_pct': capture_pct,
            'dd_pct': dd_pct,
            'num_bars': num_bars,
            'adx': adx,
            'pvo': pvo,
            'exit_reason': exit_reason,
            'win': win,
            'cum': cum,
        })
        
        prev_cum = cum
        sign = "✅" if win else "❌"
        print(f"{i+1:>3} {e.get('close_time_dt','')[:10]:>10} {side:>4} {entry_p:>8.0f} {exit_p:>8.0f} "
              f"{delta_cum:>+9.2f} {pnl_usd:>+9.2f} {scale_out_pnl:>+9.2f} "
              f"{mfe_pts:>8.0f} {mae_pts:>8.0f} {capture_pct:>8.1f}% {dd_pct:>6.1f}% {num_bars:>5d} "
              f"{adx:>6.1f} {pvo:>6.1f} {sign}")
    
    print()
    wins   = [r for r in records if r['win']]
    losses = [r for r in records if not r['win']]
    total_delta = sum(r['delta_cum'] for r in records)
    
    # ============================================================
    # 2. 勝ち/負け統計
    # ============================================================
    print("=" * 70)
    print("2. 勝ち/負けトレード統計")
    print("=" * 70)
    print(f"{'':20s} {'勝ち':>10} {'負け':>10} {'合計':>10}")
    print(f"件数               {len(wins):>10d} {len(losses):>10d} {len(records):>10d}")
    print(f"勝率               {len(wins)/len(records)*100:>9.1f}%")
    print(f"平均 delta_cum     {(sum(r['delta_cum'] for r in wins)/len(wins) if wins else 0):>+10.2f} "
          f"{(sum(r['delta_cum'] for r in losses)/len(losses) if losses else 0):>+10.2f} "
          f"{total_delta/len(records):>+10.2f}")
    print(f"最大 delta_cum     {max(r['delta_cum'] for r in wins) if wins else 0:>+10.2f} "
          f"{min(r['delta_cum'] for r in losses) if losses else 0:>+10.2f}")
    print(f"合計 delta_cum     {sum(r['delta_cum'] for r in wins):>+10.2f} "
          f"{sum(r['delta_cum'] for r in losses):>+10.2f} {total_delta:>+10.2f}")
    
    # ============================================================
    # 3. スケールアウト効果
    # ============================================================
    print()
    print("=" * 70)
    print("3. スケールアウト分析（scale_out_pnl = delta_cum - pnl_usd）")
    print("=" * 70)
    with_so = [r for r in records if abs(r['scale_out_pnl']) > 5]
    without_so = [r for r in records if abs(r['scale_out_pnl']) <= 5]
    print(f"スケールアウト あり: {len(with_so)}件 / なし: {len(without_so)}件")
    if with_so:
        print(f"スケールアウト利益合計: {sum(r['scale_out_pnl'] for r in with_so):+.2f} USD")
        print(f"スケールアウト後の最終exit合計: {sum(r['pnl_usd'] for r in with_so):+.2f} USD")
        print(f"スケールアウト後の最終exit（負）: {[r['no'] for r in with_so if r['pnl_usd'] < 0]}")
        
    print()
    print("スケールアウトありトレード詳細:")
    print(f"{'No':>3} {'Date':>10} {'ΔPort':>9} {'ScaleOut':>9} {'FinalExit':>10} {'DD%':>7} {'MFE':>8}")
    for r in sorted(with_so, key=lambda x: x['delta_cum'], reverse=True):
        print(f"{r['no']:>3} {r['date']:>10} {r['delta_cum']:>+9.2f} {r['scale_out_pnl']:>+9.2f} {r['pnl_usd']:>+10.2f} {r['dd_pct']:>6.1f}% {r['mfe_pts']:>8.0f}")
    
    # ============================================================
    # 4. MFE / キャプチャー率分析（最重要）
    # ============================================================
    print()
    print("=" * 70)
    print("4. MFE（最大含み益）vs 実際の利益：キャプチャー率分析")
    print("   ＝「利益を逃しているかどうか」を定量化")
    print("=" * 70)
    
    r_with_mfe = [r for r in records if r['mfe_pts'] > 100]
    if r_with_mfe:
        print(f"{'No':>3} {'Date':>10} {'ΔPort':>9} {'MFE(pts)':>10} {'Capture%':>10} {'DD%':>7} {'ADX':>6}")
        for r in sorted(r_with_mfe, key=lambda x: x['capture_pct']):
            flag = "⚠️ " if r['capture_pct'] < 50 else ("✅" if r['capture_pct'] > 200 else "  ")
            print(f"{r['no']:>3} {r['date']:>10} {r['delta_cum']:>+9.2f} "
                  f"{r['mfe_pts']:>10.0f} {r['capture_pct']:>9.1f}% {r['dd_pct']:>6.1f}% {r['adx']:>6.1f}  {flag}")
        
        avg_capture = sum(r['capture_pct'] for r in r_with_mfe) / len(r_with_mfe)
        low_capture = [r for r in r_with_mfe if r['capture_pct'] < 100]
        print(f"\n平均キャプチャー率: {avg_capture:.1f}%")
        print(f"キャプチャー率<100%のトレード（含み益以下の実現益）: {len(low_capture)}件")
        print(f"  逃した利益の合計: "
              f"{sum(r['mfe_pts'] - r['delta_cum'] for r in low_capture):+.0f} pts相当")
    
    # ============================================================
    # 5. ドローダウン寄与度（上位損失トレード）
    # ============================================================
    print()
    print("=" * 70)
    print("5. ポートフォリオ下落を引き起こしたトレードTOP10")
    print("   ＝ドローダウンの主要因を特定")
    print("=" * 70)
    sorted_by_loss = sorted(records, key=lambda x: x['delta_cum'])
    print(f"{'No':>3} {'Date':>10} {'ΔPort':>9} {'Entry':>8} {'Exit':>8} "
          f"{'ScaleOut':>9} {'FinalExit':>10} {'DD@exit':>9} {'ADX':>6} {'PVO':>6}")
    for r in sorted_by_loss[:10]:
        print(f"{r['no']:>3} {r['date']:>10} {r['delta_cum']:>+9.2f} {r['entry_p']:>8.0f} {r['exit_p']:>8.0f} "
              f"{r['scale_out_pnl']:>+9.2f} {r['pnl_usd']:>+10.2f} {r['dd_pct']:>8.1f}% "
              f"{r['adx']:>6.1f} {r['pvo']:>6.1f}")
    
    # ============================================================
    # 6. 残高水準別パフォーマンス
    # ============================================================
    print()
    print("=" * 70)
    print("6. 残高水準別パフォーマンス")
    print("   （残高=初期300+前累積PnL 概算）")
    print("=" * 70)
    tiers = {
        '極小  (< 300)': [],
        '小    (300-600)': [],
        '中    (600-1500)': [],
        '大    (1500-3000)': [],
        '超大  (>3000)': [],
    }
    
    running_balance = 300.0
    for r in records:
        b = running_balance
        if b < 300:
            tiers['極小  (< 300)'].append(r)
        elif b < 600:
            tiers['小    (300-600)'].append(r)
        elif b < 1500:
            tiers['中    (600-1500)'].append(r)
        elif b < 3000:
            tiers['大    (1500-3000)'].append(r)
        else:
            tiers['超大  (>3000)'].append(r)
        running_balance += r['delta_cum']
    
    for tier, recs in tiers.items():
        if recs:
            total = sum(r['delta_cum'] for r in recs)
            avg   = total / len(recs)
            wins  = sum(1 for r in recs if r['win'])
            print(f"{tier}: {len(recs):>3}件  合計{total:>+8.2f} USD  平均{avg:>+8.2f}  勝率{wins/len(recs)*100:>5.1f}%")
    
    # ============================================================
    # 7. 相場局面（ADX水準）別パフォーマンス
    # ============================================================
    print()
    print("=" * 70)
    print("7. ADX水準別パフォーマンス（エントリー時ADX）")
    print("=" * 70)
    adx_tiers = {
        '強いトレンド (ADX≥40)': [r for r in records if r['adx'] >= 40],
        'トレンド    (30≤ADX<40)': [r for r in records if 30 <= r['adx'] < 40],
        '弱いトレンド(20≤ADX<30)': [r for r in records if 20 <= r['adx'] < 30],
    }
    for tier, recs in adx_tiers.items():
        if recs:
            total = sum(r['delta_cum'] for r in recs)
            avg   = total / len(recs)
            wins  = sum(1 for r in recs if r['win'])
            avg_mfe = sum(r['mfe_pts'] for r in recs) / len(recs)
            print(f"{tier}: {len(recs):>3}件  合計{total:>+8.2f}  平均{avg:>+7.2f}  勝率{wins/len(recs)*100:>5.1f}%  平均MFE{avg_mfe:>7.0f}pts")
    
    # ============================================================
    # 8. 時期別パフォーマンス（フェーズ分析）
    # ============================================================
    print()
    print("=" * 70)
    print("8. 時期別フェーズ分析")
    print("=" * 70)
    phases = {
        '2024 Q1-Q2 (初期上昇)': [],
        '2024 Q3-Q4 (中間調整)': [],
        '2025 Q1    (強調整)': [],
        '2025 Q2-Q3 (急騰局面)': [],
        '2025 Q4    (高値圏)': [],
        '2026 Q1+   (下落局面)': [],
    }
    for r in records:
        d = r['date']
        if '2024/01' <= d <= '2024/06/30':
            phases['2024 Q1-Q2 (初期上昇)'].append(r)
        elif '2024/07' <= d <= '2024/12/31':
            phases['2024 Q3-Q4 (中間調整)'].append(r)
        elif '2025/01' <= d <= '2025/03/31':
            phases['2025 Q1    (強調整)'].append(r)
        elif '2025/04' <= d <= '2025/09/30':
            phases['2025 Q2-Q3 (急騰局面)'].append(r)
        elif '2025/10' <= d <= '2025/12/31':
            phases['2025 Q4    (高値圏)'].append(r)
        elif d >= '2026/01':
            phases['2026 Q1+   (下落局面)'].append(r)
    
    for phase, recs in phases.items():
        if recs:
            total = sum(r['delta_cum'] for r in recs)
            wins  = sum(1 for r in recs if r['win'])
            avg_dd = sum(r['dd_pct'] for r in recs) / len(recs)
            print(f"{phase}: {len(recs):>3}件  合計{total:>+8.2f} USD  勝率{wins/len(recs)*100:>5.1f}%  avg_DD{avg_dd:>5.1f}%")
    
    # ============================================================
    # 9. 「利益が大きかった期間」vs「実現益が少なかった期間」の特定
    # ============================================================
    print()
    print("=" * 70)
    print("9. 「大きな含み益があったのに実現益が少ないトレード」TOP10")
    print("   ＝MFEは大きいが、最終的なΔPortが小さいトレード")
    print("=" * 70)
    # MFE対比でdelta_cumが低いトレード（= 利益の多くを逃した）
    eligible = [r for r in records if r['mfe_pts'] > 500]
    if eligible:
        # mfe_pts / delta_cum の比率でソート（大きいほど利益を逃している）
        for r in eligible:
            r['opportunity_loss'] = r['mfe_pts'] - max(0, r['delta_cum'])
        sorted_opp = sorted(eligible, key=lambda x: x['opportunity_loss'], reverse=True)
        print(f"{'No':>3} {'Date':>10} {'ΔPort':>9} {'MFE(pts)':>10} {'逃した利益':>10} {'Capture%':>10} {'DD%':>7}")
        for r in sorted_opp[:10]:
            print(f"{r['no']:>3} {r['date']:>10} {r['delta_cum']:>+9.2f} "
                  f"{r['mfe_pts']:>10.0f} {r['opportunity_loss']:>10.0f} "
                  f"{r['capture_pct']:>9.1f}% {r['dd_pct']:>6.1f}%")
    
    # ============================================================
    # 10. 問題の根本原因特定: ドローダウン構造
    # ============================================================
    print()
    print("=" * 70)
    print("10. ドローダウン構造の解析")
    print("    ＝「累積PnLのピーク → 底」を特定し、何が起きていたかを説明")
    print("=" * 70)
    
    # ピーク→底のシーケンスを特定
    cum_vals = [r['cum'] for r in records]
    peak_idx = 0
    peak_val = cum_vals[0]
    dd_episodes = []
    
    for i, v in enumerate(cum_vals):
        if v > peak_val:
            if peak_idx < i - 1 and peak_val > cum_vals[peak_idx + 1]:
                # ドローダウンエピソード記録
                pass
            peak_val = v
            peak_idx = i
        else:
            dd = (peak_val - v) / (300 + peak_val) * 100 if (300 + peak_val) > 0 else 0
            if dd > 5:  # 5%超のドローダウン
                dd_episodes.append((peak_idx, i, peak_val, v, dd))
    
    # 最大DDエピソードを特定
    if dd_episodes:
        # 重複を除いて最大のものを表示
        shown = set()
        for start_i, end_i, p_val, v_val, dd_pct_ep in sorted(dd_episodes, key=lambda x: -x[4]):
            key = (start_i, end_i)
            if key in shown:
                continue
            shown.add(key)
            start_r = records[start_i]
            end_r = records[end_i]
            print(f"DDエピソード: T{start_i+1}({start_r['date']}) → T{end_i+1}({end_r['date']})")
            print(f"  ピーク cum={p_val:.2f} → 谷 cum={v_val:.2f}  落差={p_val-v_val:.2f} USD  {dd_pct_ep:.1f}%")
            print(f"  このDD中のトレード:")
            for j in range(start_i, end_i + 1):
                r2 = records[j]
                print(f"    T{j+1} {r2['date']} ΔPort={r2['delta_cum']:+.2f}  MFE={r2['mfe_pts']:.0f}pts  scale_out={r2['scale_out_pnl']:+.2f}  final_exit={r2['pnl_usd']:+.2f}  ADX={r2['adx']:.1f}")
            print()
            if len(shown) >= 4:
                break
    
    # ============================================================
    # 11. 結論と改善案の優先順位
    # ============================================================
    print("=" * 70)
    print("11. 分析結論サマリー")
    print("=" * 70)
    
    total_scale_out = sum(r['scale_out_pnl'] for r in records)
    total_final_exit = sum(r['pnl_usd'] for r in records)
    scale_out_share = total_scale_out / total_delta * 100 if total_delta != 0 else 0
    
    print(f"通年損益 (ΔPort合計): +{total_delta:.2f} USD")
    print(f"  うちスケールアウト利益: {total_scale_out:+.2f} USD ({scale_out_share:.1f}%)")
    print(f"  うち最終EXIT利益:       {total_final_exit:+.2f} USD ({100-scale_out_share:.1f}%)")
    print()
    
    # スケールアウト後に最終EXITがマイナスになったトレード
    so_then_loss = [r for r in records if r['scale_out_pnl'] > 10 and r['pnl_usd'] < -10]
    print(f"スケールアウトで利益確保したが最終EXITでマイナスになったトレード: {len(so_then_loss)}件")
    for r in so_then_loss:
        net_back = abs(r['pnl_usd']) / r['scale_out_pnl'] * 100
        print(f"  T{r['no']:02d} {r['date']}  SO利益={r['scale_out_pnl']:+.2f}  最終={r['pnl_usd']:+.2f}  返却率={net_back:.0f}%  DD={r['dd_pct']:.1f}%")
    
    print()
    print(f"最大含み益（MFE）の平均: {sum(r['mfe_pts'] for r in records)/len(records):.0f} pts")
    print(f"最大逆行（MAE）の平均:   {sum(r['mae_pts'] for r in records)/len(records):.0f} pts")
    
    # 純粋な負けトレード（scale_outなし + delta_cum < 0）
    pure_loss = [r for r in records if r['delta_cum'] < 0]
    print(f"\n純粋な負けトレード (ΔPort<0): {len(pure_loss)}件")
    for r in pure_loss:
        print(f"  T{r['no']:02d} {r['date']}  ΔPort={r['delta_cum']:+.2f}  MFE={r['mfe_pts']:.0f}pts  MAE={r['mae_pts']:.0f}pts")

if __name__ == "__main__":
    main()
