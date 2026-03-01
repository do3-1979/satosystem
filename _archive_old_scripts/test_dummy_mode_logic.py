#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ダミーモード判定ロジックのテストスクリプト

Config.is_dummy_mode() メソッドが正しく動作することを確認します。
"""

import sys
import os

# プロジェクトのsrcディレクトリをPythonパスに追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from config import Config

def test_dummy_mode_logic():
    """ダミーモード判定ロジックをテスト"""
    print("\n" + "=" * 70)
    print("  ダミーモード判定ロジックテスト")
    print("=" * 70)
    
    # 現在の設定を取得
    back_test = Config.get_back_test_mode()
    hot_test_dummy = Config.get_hot_test_dummy_mode()
    is_dummy = Config.is_dummy_mode()
    
    print(f"\n現在の設定値:")
    print(f"  back_test = {back_test}")
    print(f"  hot_test_dummy_mode = {hot_test_dummy}")
    print(f"  is_dummy_mode() = {is_dummy}")
    
    # 判定ロジック
    print(f"\n判定ロジック:")
    print(f"  - back_test == 1 → ダミーモード（バックテスト）")
    print(f"  - back_test == 0 かつ hot_test_dummy_mode == 1 → ダミーモード（ペーパートレード）")
    print(f"  - back_test == 0 かつ hot_test_dummy_mode == 0 → 本番取引")
    
    # 期待値との比較
    expected_dummy = (back_test == 1) or (back_test == 0 and hot_test_dummy == 1)
    
    print(f"\n期待値との比較:")
    print(f"  期待値: {expected_dummy}")
    print(f"  実績値: {is_dummy}")
    
    if is_dummy == expected_dummy:
        print(f"  ✅ 判定ロジックが正確です")
        return True
    else:
        print(f"  ❌ 判定ロジックが異なります")
        return False


def test_mode_scenarios():
    """異なるモード設定シナリオをテスト"""
    print("\n" + "=" * 70)
    print("  各モードシナリオのテスト")
    print("=" * 70)
    
    scenarios = [
        {"name": "バックテスト", "expected": True, "description": "back_test=1 → 常にダミーモード"},
        {"name": "ペーパートレード", "expected": True, "description": "back_test=0, hot_test_dummy_mode=1 → ダミーモード"},
        {"name": "本番取引", "expected": False, "description": "back_test=0, hot_test_dummy_mode=0 → 本番取引"},
    ]
    
    back_test = Config.get_back_test_mode()
    hot_test_dummy = Config.get_hot_test_dummy_mode()
    is_dummy = Config.is_dummy_mode()
    
    print(f"\n現在の設定: back_test={back_test}, hot_test_dummy_mode={hot_test_dummy}")
    print(f"現在のモード: {is_dummy}\n")
    
    # 現在の設定に対応するシナリオを特定
    if back_test == 1:
        current_scenario = 0  # バックテスト
    elif back_test == 0 and hot_test_dummy == 1:
        current_scenario = 1  # ペーパートレード
    else:
        current_scenario = 2  # 本番取引
    
    scenario = scenarios[current_scenario]
    
    print(f"現在実行中のシナリオ: {scenario['name']}")
    print(f"説明: {scenario['description']}")
    print(f"期待値: {scenario['expected']}")
    print(f"実績値: {is_dummy}")
    
    if is_dummy == scenario['expected']:
        print(f"✅ シナリオテスト成功")
        return True
    else:
        print(f"❌ シナリオテスト失敗")
        return False


def test_config_methods():
    """Config のその他のメソッドをテスト"""
    print("\n" + "=" * 70)
    print("  Config メソッドの動作確認")
    print("=" * 70)
    
    try:
        # 注文実行パラメータを取得
        entry_slippage = Config.get_entry_slippage()
        slippage_multiplier = Config.get_slippage_multiplier()
        max_entry_retries = Config.get_max_entry_retries()
        max_exit_retries = Config.get_max_exit_retries()
        order_timeout = Config.get_order_timeout()
        
        print(f"\n注文実行パラメータ:")
        print(f"  - entry_slippage: {entry_slippage}%")
        print(f"  - slippage_multiplier: {slippage_multiplier}")
        print(f"  - max_entry_retries: {max_entry_retries}")
        print(f"  - max_exit_retries: {max_exit_retries}")
        print(f"  - order_timeout: {order_timeout}s")
        
        # バックテストモードを取得
        back_test_mode = Config.get_back_test_mode()
        hot_test_dummy_mode = Config.get_hot_test_dummy_mode()
        
        print(f"\nバックテストモード:")
        print(f"  - back_test_mode: {back_test_mode}")
        print(f"  - hot_test_dummy_mode: {hot_test_dummy_mode}")
        
        # ダミーモード判定
        is_dummy = Config.is_dummy_mode()
        print(f"  - is_dummy_mode(): {is_dummy}")
        
        print(f"\n✅ すべての Config メソッドが正常に動作しました")
        return True
        
    except Exception as e:
        print(f"\n❌ Config メソッドエラー: {str(e)}")
        return False


def main():
    """メインテスト"""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 68 + "║")
    print("║" + "  ダミーモード判定ロジック テストスイート".center(68) + "║")
    print("║" + " " * 68 + "║")
    print("╚" + "=" * 68 + "╝")
    
    all_pass = True
    
    # テスト1: ダミーモード判定ロジック
    result1 = test_dummy_mode_logic()
    all_pass = all_pass and result1
    
    # テスト2: モードシナリオ
    result2 = test_mode_scenarios()
    all_pass = all_pass and result2
    
    # テスト3: Config メソッド動作確認
    result3 = test_config_methods()
    all_pass = all_pass and result3
    
    # 結果表示
    print("\n" + "=" * 70)
    print("  テスト結果")
    print("=" * 70)
    
    if all_pass:
        print("✅ すべてのテストが成功しました")
        print("\nダミーモード判定ロジックが正常に動作しています。")
        return 0
    else:
        print("❌ テストが失敗しました")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
