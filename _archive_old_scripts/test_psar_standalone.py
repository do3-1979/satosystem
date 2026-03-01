#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PSAR 初期化ロジックの詳細分析
- 初期化時に使用されるデータ範囲
- 初期トレンド判定の妥当性
- 10/1 時点の PSAR 値の検証
"""

import os
import sys
import json
from datetime import datetime

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(WORKSPACE_ROOT, "src")
sys.path.insert(0, SRC_DIR)
os.chdir(SRC_DIR)

from config import Config
from price_data_management import PriceDataManagement

def analyze_psar_initialization():
    """PSAR初期化ロジックを詳細分析"""
    
    print("="*80)
    print("PSAR初期化ロジック詳細分析")
    print("="*80)
    
    # 設定確認
    print(f"\n【設定値】")
    initial_term = Config.get_test_initial_max_term()
    time_frame = Config.get_time_frame()
    psar_time_frame = Config.get_psar_time_frame()
    start_time_str = Config.get_start_time()
    
    print(f"  初期化期間: {initial_term}")
    print(f"  メインタイムフレーム: {time_frame} 分")
    print(f"  PSAR時間フレーム: {psar_time_frame} 分")
    print(f"  開始時刻: {start_time_str}")
    print(f"  遡り時間: {initial_term * time_frame} 分")
    
    # Price Data Management初期化
    price_data = PriceDataManagement()
    price_data.initialise_back_test_ohlcv_data()
    
    # OHLCV データ取得
    ohlcv = price_data.get_back_test_ohlcv_data_by_time_frame(time_frame)
    
    print(f"\n【OHLCV データ（{time_frame}分足）】")
    print(f"  総件数: {len(ohlcv)}")
    
    # 最初のデータと最後のデータ
    if ohlcv:
        first = ohlcv[0]
        dt_first = datetime.fromtimestamp(first['close_time'])
        print(f"  最初: {dt_first.strftime('%Y-%m-%d %H:%M')}, close={first['close_price']:.2f}")
        
        # 10/1 のデータを探す
        target_time_str = "2025/10/01 00:00"
        target_dt = datetime.strptime(target_time_str, "%Y/%m/%d %H:%M")
        target_epoch = int(target_dt.timestamp())
        
        # 最も近いデータを探す
        oct1_idx = None
        for i, d in enumerate(ohlcv):
            if d['close_time'] >= target_epoch:
                oct1_idx = i
                break
        
        if oct1_idx is not None:
            print(f"\n【10/1 時点のデータ】")
            print(f"  インデックス: {oct1_idx}")
            
            # 10/1 前後のデータを表示
            start_idx = max(0, oct1_idx - 3)
            end_idx = min(len(ohlcv), oct1_idx + 3)
            
            for i in range(start_idx, end_idx):
                d = ohlcv[i]
                dt = datetime.fromtimestamp(d['close_time'])
                marker = " ← 10/1" if i == oct1_idx else ""
                print(f"    [{i:3d}] {dt.strftime('%Y-%m-%d %H:%M')}: close={d['close_price']:10.2f}, "
                      f"high={d['high_price']:10.2f}, low={d['low_price']:10.2f}{marker}")
            
            # 初期 2 バーの分析
            print(f"\n【初期トレンド判定用の 2 バー】")
            if oct1_idx >= 1:
                bar0 = ohlcv[oct1_idx - 1]
                bar1 = ohlcv[oct1_idx]
                dt0 = datetime.fromtimestamp(bar0['close_time'])
                dt1 = datetime.fromtimestamp(bar1['close_time'])
                
                print(f"  Bar 0: {dt0.strftime('%Y-%m-%d %H:%M')}, close={bar0['close_price']:.2f}")
                print(f"  Bar 1: {dt1.strftime('%Y-%m-%d %H:%M')}, close={bar1['close_price']:.2f}")
                
                # トレンド判定
                if bar1['close_price'] > bar0['close_price']:
                    trend = "UPtrend"
                    hp = max(bar0['high_price'], bar1['high_price'])
                    lp = min(bar0['low_price'], bar1['low_price'])
                    ep = hp
                    initial_sar = lp
                else:
                    trend = "DOWNtrend"
                    hp = max(bar0['high_price'], bar1['high_price'])
                    lp = min(bar0['low_price'], bar1['low_price'])
                    ep = lp
                    initial_sar = hp
                
                print(f"\n  トレンド判定: {trend}")
                print(f"  HP (Highest Point): {hp:.2f}")
                print(f"  LP (Lowest Point): {lp:.2f}")
                print(f"  EP (Extreme Point): {ep:.2f}")
                print(f"  初期 SAR 値: {initial_sar:.2f}")
        
        last = ohlcv[-1]
        dt_last = datetime.fromtimestamp(last['close_time'])
        print(f"\n  最後: {dt_last.strftime('%Y-%m-%d %H:%M')}, close={last['close_price']:.2f}")
    
    # PSAR 期待値データとの比較
    expected_file = os.path.join(WORKSPACE_ROOT, "docs/regression_test_results", "psar_expected.json")
    if os.path.exists(expected_file):
        with open(expected_file) as f:
            expected = json.load(f)
        
        print(f"\n【PSAR 期待値との比較】")
        print(f"  期待値の最初のデータ (Bar {expected[0]['bar_index']})")
        dt_exp_first = datetime.fromtimestamp(expected[0]['close_time'])
        print(f"    時刻: {dt_exp_first.strftime('%Y-%m-%d %H:%M')}")
        print(f"    close: {expected[0]['close_price']:.2f}")
        print(f"    psar: {expected[0]['psar']:.2f}")
        
        # 10/1 前後の期待値を探す
        for i, exp in enumerate(expected):
            dt_exp = datetime.fromtimestamp(exp['close_time'])
            if "2025-10-01" in dt_exp.strftime('%Y-%m-%d'):
                print(f"\n  期待値の 10/1 時点 (index {i})")
                start = max(0, i - 2)
                end = min(len(expected), i + 3)
                for j in range(start, end):
                    e = expected[j]
                    dt_e = datetime.fromtimestamp(e['close_time'])
                    marker = " ← 10/1" if j == i else ""
                    print(f"    [{j:3d}] {dt_e.strftime('%Y-%m-%d %H:%M')}: close={e['close_price']:10.2f}, psar={e['psar']:10.2f}{marker}")
                break
    
    print("="*80)


if __name__ == "__main__":
    analyze_psar_initialization()


def calculate_psar_standalone(ohlcv_data, iaf=0.02, maxaf=0.20, increment=0.02):
    """
    Parabolic SAR を単独で計算
    
    Args:
        ohlcv_data: OHLCV データリスト
        iaf: 初期 AF (Acceleration Factor)
        maxaf: 最大 AF
        increment: AF インクリメント
    
    Returns:
        psar_results: [{bar_index, close_time, close_price, psar, bull}, ...]
    """
    
    high = [d['high_price'] for d in ohlcv_data]
    low = [d['low_price'] for d in ohlcv_data]
    close = [d['close_price'] for d in ohlcv_data]
    close_time = [d['close_time'] for d in ohlcv_data]
    
    length = len(close)
    if length < 3:
        return []
    
    psar = [None] * length
    psarbull = [None] * length
    psarbear = [None] * length
    psar_results = []
    
    # 初期化 - 前回計算値がない場合
    psar[0] = close[0]
    psar[1] = close[0]
    
    psarbull = [None] * length
    psarbear = [None] * length
    bull = True
    af = iaf
    ep = low[0]
    hp = high[0]
    lp = low[0]
    
    print(f"[INIT] psar[0]={psar[0]:.2f}, psar[1]={psar[1]:.2f}, bull={bull}, af={af}")
    
    # PSAR 計算
    for i in range(2, length):
        if bull:
            psar[i] = psar[i - 1] + af * (hp - psar[i - 1])
        else:
            psar[i] = psar[i - 1] + af * (lp - psar[i - 1])
        
        reverse = False
        
        if bull:
            if low[i] < psar[i]:
                bull = False
                reverse = True
                psar[i] = hp
                lp = low[i]
                af = iaf
        else:
            if high[i] > psar[i]:
                bull = True
                reverse = True
                psar[i] = lp
                hp = high[i]
                af = iaf
        
        if not reverse:
            if bull:
                if high[i] > hp:
                    hp = high[i]
                    af = min(af + increment, maxaf)
                if low[i - 1] < psar[i]:
                    psar[i] = low[i - 1]
                if low[i - 2] < psar[i]:
                    psar[i] = low[i - 2]
            else:
                if low[i] < lp:
                    lp = low[i]
                    af = min(af + increment, maxaf)
                if high[i - 1] > psar[i]:
                    psar[i] = high[i - 1]
                if high[i - 2] > psar[i]:
                    psar[i] = high[i - 2]
        
        if bull:
            psarbull[i] = psar[i]
        else:
            psarbear[i] = psar[i]
        
        psar_results.append({
            "bar_index": i,
            "close_time": close_time[i],
            "close_price": close[i],
            "psar": psar[i],
            "bull": bull,
            "af": af
        })
    
    return psar_results


def main():
    print("="*80)
    print("PSAR単独計算スクリプト")
    print("="*80)
    
    # バックテスト設定を確認
    print(f"\n[INFO] バックテスト設定")
    print(f"  Start: {Config.get_start_time()}")
    print(f"  End: {Config.get_end_time()}")
    print(f"  Time Frame (Main): {Config.get_time_frame()} min")
    print(f"  Time Frame (PSAR): {Config.get_psar_time_frame()} min")
    
    # Price Data Management初期化
    price_data = PriceDataManagement()
    
    # バックテストOHLCVデータ初期化
    print(f"\n[INFO] バックテストOHLCVデータ初期化中...")
    price_data.initialise_back_test_ohlcv_data()
    
    # バックテスト用メソッドでデータを取得
    main_tf_data = price_data.get_back_test_ohlcv_data_by_time_frame(Config.get_time_frame())
    psar_tf_data = price_data.get_back_test_ohlcv_data_by_time_frame(Config.get_psar_time_frame())
    
    print(f"[INFO] メインタイムフレーム（120分）データ数: {len(main_tf_data)}")
    print(f"[INFO] PSARタイムフレーム（120分）データ数: {len(psar_tf_data)}")
    
    # PSAR期待値を計算
    print(f"\n[INFO] PSAR単独計算を実行中...")
    psar_expected = calculate_psar_standalone(
        psar_tf_data,
        iaf=Config.get_stop_AF_add(),
        maxaf=Config.get_stop_AF_max(),
        increment=Config.get_stop_AF_add()
    )
    
    print(f"[INFO] PSAR期待値計算完了: {len(psar_expected)} 件")
    
    # 期待値をJSONで保存
    output_file = os.path.join(WORKSPACE_ROOT, "docs/regression_test_results", "psar_expected.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(psar_expected, f, ensure_ascii=False, indent=2)
    
    print(f"\n[INFO] PSAR期待値を保存: {output_file}")
    
    # 最初の10件と最後の10件を表示
    print(f"\n【PSAR期待値 - 最初の10件】")
    for i, entry in enumerate(psar_expected[:10]):
        print(f"Bar {entry['bar_index']:3d}: close={entry['close_price']:10.2f}, "
              f"psar={entry['psar']:10.2f}, bull={entry['bull']}, af={entry['af']:.4f}")
    
    print(f"\n【PSAR期待値 - 最後の10件】")
    for entry in psar_expected[-10:]:
        print(f"Bar {entry['bar_index']:3d}: close={entry['close_price']:10.2f}, "
              f"psar={entry['psar']:10.2f}, bull={entry['bull']}, af={entry['af']:.4f}")
    
    print(f"\n[SUCCESS] PSAR期待値作成完了")
    print("="*80)


if __name__ == "__main__":
    main()
