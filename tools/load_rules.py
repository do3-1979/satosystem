#!/usr/bin/env python3
"""開発ルール表示ツール - DEVELOPMENT_RULES.jsonを読み込んで表示"""

import json
from pathlib import Path


def load_rules():
    """DEVELOPMENT_RULES.jsonを読み込み"""
    rules_file = Path(__file__).parent.parent / 'DEVELOPMENT_RULES.json'
    
    if not rules_file.exists():
        print(f"❌ エラー: {rules_file} が見つかりません")
        return None
    
    with open(rules_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def display_rules(rules):
    """開発ルールを表示"""
    print("=" * 80)
    print("📋 DEVELOPMENT RULES - 開発ルール")
    print("=" * 80)
    print()
    
    # 重大ルール
    if 'critical_rules' in rules:
        print("🚨 重大ルール:")
        for rule in rules['critical_rules']:
            print(f"  • {rule['title']}")
            print(f"    {rule['description']}")
        print()
    
    # ドキュメント管理
    if 'document_management' in rules:
        print("📚 ドキュメント管理:")
        for item in rules['document_management']['required_files']:
            print(f"  • {item}")
        print()
    
    # 実行モード
    if 'execution_modes' in rules:
        print("⚙️  実行モード:")
        for mode in rules['execution_modes']['modes']:
            print(f"  {mode['name']}: back_test={mode['back_test']}, dummy={mode['hot_test_dummy_mode']}")
        print()
    
    # テスト品質
    if 'quality_metrics' in rules:
        metrics = rules['quality_metrics']['current']
        print(f"✅ 品質指標 ({metrics['date']}):")
        print(f"  • レグレッションテスト: {metrics['regression_tests']}")
        print(f"  • 四半期テスト: {metrics['quarterly_tests']}")
        print(f"  • 累積損益: {metrics['cumulative_pnl']}")
        print()
    
    print("=" * 80)


def main():
    rules = load_rules()
    if rules:
        display_rules(rules)
        return 0
    return 1


if __name__ == '__main__':
    exit(main())
