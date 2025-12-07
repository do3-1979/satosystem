#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
期待値と実際値のデータセット位置を合わせて、正確に比較する
"""

import os
import sys
import json
from pathlib import Path

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_json(filepath):
    """JSONファイルを読込"""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

def analyze_data_alignment():
    """期待値と実際値のデータ位置を分析"""
    
    print("="*80)
    print("データセット位置分析")
    print("="*80)
    
    # 期待値と実際値を読込
    expected_file = os.path.join(WORKSPACE_ROOT, "docs/regression_test_results", "psar_expected.json")
    actual_file = os.path.join(WORKSPACE_ROOT, "src/logs", "latest_backtest.log")
    
    expected = load_json(expected_file)
    print(f"\n期待値:")
    print(f"  件数: {len(expected)}")
    if expected:
        print(f"  最初: bar_index={expected[0]['bar_index']}, close_time={expected[0]['close_time']}, close={expected[0]['close_price']:.2f}")
        print(f"  最後: bar_index={expected[-1]['bar_index']}, close_time={expected[-1]['close_time']}, close={expected[-1]['close_price']:.2f}")
    
    # ログから実際値を抽出
    log_dir = os.path.join(WORKSPACE_ROOT, "src", "logs")
    log_files = sorted(Path(log_dir).glob("*.json"))
    log_files = [f for f in log_files if "backtest_summary" not in f.name]
    
    if not log_files:
        print("[ERROR] ログファイルが見つかりません")
        return
    
    actual_file_path = log_files[-1]
    print(f"\n[INFO] ログファイル: {actual_file_path.name}")
    
    with open(actual_file_path, "r", encoding="utf-8") as f:
        actual_data = json.load(f)
    
    print(f"\n実際値:")
    print(f"  件数: {len(actual_data)}")
    if actual_data:
        psar_first = actual_data[0].get('psar')
        psar_first_str = f"{psar_first:.2f}" if psar_first else 'None'
        psar_last = actual_data[-1].get('psar')
        psar_last_str = f"{psar_last:.2f}" if psar_last else 'None'
        print(f"  最初: close_time={actual_data[0].get('close_time')}, close={actual_data[0].get('close_price'):.2f}, psar={psar_first_str}")
        print(f"  最後: close_time={actual_data[-1].get('close_time')}, close={actual_data[-1].get('close_price'):.2f}, psar={psar_last_str}")
    
    # close_timeとclose_priceで一致する位置を探す
    print(f"\n【データ位置マッチング】")
    
    # 期待値の最初の数件と実際値を比較
    matches = []
    for i, exp in enumerate(expected):
        exp_close_time = exp.get("close_time")
        exp_close_price = exp.get("close_price")
        
        for j, act in enumerate(actual_data):
            act_close_time = act.get("close_time")
            act_close_price = act.get("close_price")
            
            # close_timeとclose_priceが一致
            if exp_close_time == act_close_time and abs(exp_close_price - act_close_price) < 0.01:
                matches.append((i, j, exp_close_time, exp_close_price))
                if len(matches) <= 5:
                    print(f"  マッチ: 期待値[{i}] ↔ 実際値[{j}] (time={exp_close_time}, close={exp_close_price:.2f})")
    
    if not matches:
        print(f"  [WARNING] close_time と close_price が一致するデータが見つかりません")
        print(f"\n  期待値データサンプル:")
        for exp in expected[:3]:
            print(f"    time={exp.get('close_time')}, close={exp.get('close_price'):.2f}")
        print(f"\n  実際値データサンプル:")
        for act in actual_data[:3]:
            print(f"    time={act.get('close_time')}, close={act.get('close_price'):.2f}")
        return
    
    # オフセットを計算
    offsets = [j - i for i, j, _, _ in matches]
    print(f"\n  オフセット: {set(offsets)}")
    
    if offsets:
        # 最も一般的なオフセットを使用
        from collections import Counter
        common_offset = Counter(offsets).most_common(1)[0][0]
        print(f"  推奨オフセット: {common_offset}")
        
        # オフセットを適用して再比較
        print(f"\n【オフセット適用後の比較】")
        differences_aligned = []
        
        for i in range(len(expected)):
            j = i + common_offset
            if j >= len(actual_data):
                break
            
            exp_psar = expected[i].get("psar")
            act_psar = actual_data[j].get("psar")
            
            if exp_psar is None or act_psar is None:
                continue
            
            diff = abs(exp_psar - act_psar)
            if diff > 0.01:
                differences_aligned.append({
                    "exp_idx": i,
                    "act_idx": j,
                    "exp_psar": exp_psar,
                    "act_psar": act_psar,
                    "diff": diff
                })
        
        match_rate = (len(expected) - len(differences_aligned)) / len(expected) * 100 if expected else 0
        print(f"  マッチ率: {match_rate:.1f}%")
        print(f"  差分件数: {len(differences_aligned)} / {len(expected)}")
        
        if differences_aligned:
            print(f"\n  最初の10件の差分:")
            for diff in differences_aligned[:10]:
                print(f"    Bar {diff['exp_idx']:3d}→{diff['act_idx']:3d}: "
                      f"exp={diff['exp_psar']:10.2f}, act={diff['act_psar']:10.2f}, "
                      f"diff={diff['diff']:10.2f}")
    
    print("="*80)


if __name__ == "__main__":
    analyze_data_alignment()
