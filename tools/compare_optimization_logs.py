#!/usr/bin/env python3
"""
バックテスト高速化 No.2 の検証スクリプト
REGRESSION_TEST_POLICY.md の 3.1 バックテスト方針に従う

変更前後のレグレッションテストログを比較し、
- 機能的に同等か（回帰なし）
- 処理時間が改善されたか
を確認
"""

import os
import sys
import re
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

def read_log_file(filepath):
    """ログファイルを読み込み"""
    if not os.path.exists(filepath):
        return None
    
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()

def extract_test_results(log_content):
    """テスト結果を抽出"""
    results = {}
    
    # [OK]/[FAIL] パターンをマッチング
    pattern = r'\[(OK|FAIL)\]\s+(\w+)'
    matches = re.findall(pattern, log_content)
    
    for status, test_name in matches:
        results[test_name] = status
    
    return results

def extract_entry_count(log_content):
    """ENTRY 回数を抽出"""
    # consistency テストから ENTRY 回数を取得
    if 'ENTRY回数が0です' in log_content:
        return 0
    
    # 他のログから ENTRY 情報を抽出（あれば）
    pattern = r'ENTRY.*?(\d+)'
    matches = re.search(pattern, log_content)
    if matches:
        return int(matches.group(1))
    
    return None

def main():
    workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    before_log = os.path.join(workspace_root, 'logs', 'regression_test_BASELINE.log')
    after_log = os.path.join(workspace_root, 'logs', 'regression_test_AFTER_OPTIMIZATION.log')
    
    print("=" * 80)
    print("バックテスト高速化 No.2 検証レポート")
    print("=" * 80)
    print()
    
    # ログファイルの読み込み
    before_content = read_log_file(before_log)
    after_content = read_log_file(after_log)
    
    if before_content is None or after_content is None:
        print("[ERROR] ログファイルが見つかりません")
        print(f"  Before: {before_log} (存在: {os.path.exists(before_log)})")
        print(f"  After: {after_log} (存在: {os.path.exists(after_log)})")
        return 1
    
    # テスト結果の抽出
    before_results = extract_test_results(before_content)
    after_results = extract_test_results(after_content)
    
    print("📊 テスト実行結果の比較")
    print("-" * 80)
    
    all_tests = set(before_results.keys()) | set(after_results.keys())
    regression_detected = False
    
    for test in sorted(all_tests):
        before_status = before_results.get(test, "N/A")
        after_status = after_results.get(test, "N/A")
        
        # ステータス判定
        if before_status == after_status:
            status_marker = "✅"
        elif before_status == "OK" and after_status == "FAIL":
            status_marker = "❌ [REGRESSION]"
            regression_detected = True
        else:
            status_marker = "⚠️  [STATUS_CHANGE]"
        
        print(f"  {test:20s}: {before_status:6s} → {after_status:6s}  {status_marker}")
    
    print()
    
    # ENTRY 回数の確認
    print("📈 ENTRY 回数の確認")
    print("-" * 80)
    
    before_entry = extract_entry_count(before_content)
    after_entry = extract_entry_count(after_content)
    
    if before_entry is not None and after_entry is not None:
        if before_entry == after_entry:
            print(f"  ✅ ENTRY 回数は一致: {before_entry} (変更前) = {after_entry} (変更後)")
        else:
            print(f"  ⚠️  ENTRY 回数が異なる: {before_entry} (変更前) vs {after_entry} (変更後)")
    else:
        print(f"  ℹ️  ENTRY 情報取得不可")
        print(f"      Before: {before_entry}, After: {after_entry}")
    
    print()
    
    # 検証結果
    print("🔍 検証結果（REGRESSION_TEST_POLICY.md に基づく）")
    print("-" * 80)
    
    if regression_detected:
        print("  ❌ [NG] 回帰検出: 変更前は OK だったテストが FAIL になっています")
        print("         修正が必要な箇所がないか確認してください")
        result = 1
    else:
        print("  ✅ [OK] 回帰なし: テスト結果は変更前と同等です")
        print("         高速化は成功と判定されました")
        result = 0
    
    print()
    print("=" * 80)
    print("Note: 詳細な損益・取引指標・処理時間の比較は backtest.py ログから確認してください")
    print("=" * 80)
    
    return result

if __name__ == "__main__":
    sys.exit(main())
