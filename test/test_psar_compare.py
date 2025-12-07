#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
バックテスト結果からPSAR値を抽出して期待値と比較
"""

import os
import sys
import json
from pathlib import Path

# ワークスペースルート設定
WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(WORKSPACE_ROOT, "src")
sys.path.insert(0, SRC_DIR)

def extract_psar_from_latest_log():
    """最新のバックテストログからPSAR値を抽出"""
    
    log_dir = os.path.join(SRC_DIR, "logs")
    log_files = sorted(Path(log_dir).glob("*.json"))
    
    if not log_files:
        print("[ERROR] ログファイルが見つかりません")
        return None
    
    # 最新のログファイルを取得（backtest_summary を除外）
    log_files = [f for f in log_files if "backtest_summary" not in f.name]
    if not log_files:
        print("[ERROR] 有効なログファイルが見つかりません")
        return None
    
    latest_log = log_files[-1]
    print(f"[INFO] ログファイルを読込: {latest_log.name}")
    
    with open(latest_log, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # psar値を抽出
    psar_actual = []
    for entry in data:
        if "psar" in entry:
            psar_actual.append({
                "close_time": entry.get("close_time"),
                "close_price": entry.get("close_price"),
                "psar": entry.get("psar"),
                "psarbull": entry.get("psarbull"),
                "psarbear": entry.get("psarbear"),
                "bull": entry.get("psarbull") is not None
            })
    
    return psar_actual


def compare_psar():
    """期待値と実際値を比較"""
    
    print("="*80)
    print("PSAR値の比較")
    print("="*80)
    
    # 期待値を読込
    expected_file = os.path.join(WORKSPACE_ROOT, "docs/regression_test_results", "psar_expected.json")
    if not os.path.exists(expected_file):
        print(f"[ERROR] 期待値ファイルが見つかりません: {expected_file}")
        return
    
    with open(expected_file, "r", encoding="utf-8") as f:
        psar_expected = json.load(f)
    
    print(f"[INFO] 期待値: {len(psar_expected)} 件")
    
    # 実際値を抽出
    psar_actual = extract_psar_from_latest_log()
    if not psar_actual:
        print("[ERROR] 実際値の抽出に失敗")
        return
    
    print(f"[INFO] 実際値: {len(psar_actual)} 件")
    
    # 比較
    print(f"\n【差分分析】")
    differences = []
    
    for i, (exp, act) in enumerate(zip(psar_expected, psar_actual)):
        exp_psar = exp["psar"]
        act_psar = act["psar"]
        
        if exp_psar is None or act_psar is None:
            continue
        
        diff = abs(exp_psar - act_psar)
        if diff > 0.01:  # 0.01以上の差分を記録
            differences.append({
                "index": i,
                "close_price": act.get("close_price"),
                "expected_psar": exp_psar,
                "actual_psar": act_psar,
                "diff": diff,
                "pct_diff": (diff / exp_psar * 100) if exp_psar != 0 else 0,
                "exp_bull": exp.get("bull"),
                "act_bull": act.get("bull")
            })
    
    if not differences:
        print("[SUCCESS] 完全に一致しました！")
    else:
        print(f"[WARNING] {len(differences)} 件の差分が検出されました")
        print(f"\n【差分詳細 - 最初の20件】")
        for diff_entry in differences[:20]:
            print(f"Bar {diff_entry['index']:3d}: "
                  f"exp_psar={diff_entry['expected_psar']:10.2f}, "
                  f"act_psar={diff_entry['actual_psar']:10.2f}, "
                  f"diff={diff_entry['diff']:10.2f} ({diff_entry['pct_diff']:6.2f}%), "
                  f"close={diff_entry['close_price']:10.2f}")
        
        if len(differences) > 20:
            print(f"\n【差分詳細 - 最後の20件】")
            for diff_entry in differences[-20:]:
                print(f"Bar {diff_entry['index']:3d}: "
                      f"exp_psar={diff_entry['expected_psar']:10.2f}, "
                      f"act_psar={diff_entry['actual_psar']:10.2f}, "
                      f"diff={diff_entry['diff']:10.2f} ({diff_entry['pct_diff']:6.2f}%), "
                      f"close={diff_entry['close_price']:10.2f}")
    
    # 統計情報
    if differences:
        max_diff = max(d["diff"] for d in differences)
        avg_diff = sum(d["diff"] for d in differences) / len(differences)
        print(f"\n【統計】")
        print(f"  最大差分: {max_diff:.2f}")
        print(f"  平均差分: {avg_diff:.2f}")
        print(f"  差分件数: {len(differences)} / {len(psar_expected)}")
        print(f"  マッチ率: {(1 - len(differences) / len(psar_expected)) * 100:.1f}%")
    
    # 差分ファイルを保存
    output_file = os.path.join(WORKSPACE_ROOT, "docs/regression_test_results", "psar_differences.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "expected_count": len(psar_expected),
            "actual_count": len(psar_actual),
            "difference_count": len(differences),
            "match_rate": (1 - len(differences) / len(psar_expected)) * 100 if psar_expected else 0,
            "differences": differences[:50]  # 最初の50件のみ保存
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n[INFO] 差分ファイルを保存: {output_file}")
    print("="*80)


if __name__ == "__main__":
    compare_psar()
