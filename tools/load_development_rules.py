#!/usr/bin/env python3
"""
開発ルール読み込みモジュール

DEVELOPMENT_RULES.jsonを読み込み、プロジェクト起動時にルールを適用する。
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional


class DevelopmentRules:
    """開発ルール管理クラス"""
    
    def __init__(self, rules_file: Optional[Path] = None):
        """
        初期化
        
        Args:
            rules_file: ルールファイルのパス（デフォルト: DEVELOPMENT_RULES.json）
        """
        if rules_file is None:
            # プロジェクトルートのDEVELOPMENT_RULES.jsonを読み込み
            project_root = Path(__file__).parent.parent
            rules_file = project_root / 'DEVELOPMENT_RULES.json'
        
        self.rules_file = Path(rules_file)
        self.rules = self._load_rules()
    
    def _load_rules(self) -> Dict[str, Any]:
        """ルールファイルを読み込み"""
        if not self.rules_file.exists():
            raise FileNotFoundError(f"ルールファイルが見つかりません: {self.rules_file}")
        
        with open(self.rules_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def get_version(self) -> str:
        """ルールバージョンを取得"""
        return self.rules.get('version', 'unknown')
    
    def get_critical_rules(self) -> Dict[str, Any]:
        """重大ルールを取得"""
        return self.rules.get('critical_rules', {})
    
    def get_commit_workflow(self) -> List[Dict[str, Any]]:
        """コミット・プッシュワークフローを取得"""
        commit_rule = self.rules.get('critical_rules', {}).get(
            'commit_and_push_authorization', {}
        )
        return commit_rule.get('workflow', [])
    
    def get_prohibited_actions(self) -> List[str]:
        """禁止事項リストを取得"""
        commit_rule = self.rules.get('critical_rules', {}).get(
            'commit_and_push_authorization', {}
        )
        return commit_rule.get('prohibited_actions', [])
    
    def get_core_documents(self) -> List[Dict[str, Any]]:
        """コアドキュメント一覧を取得"""
        doc_mgmt = self.rules.get('documentation_management', {})
        return doc_mgmt.get('core_documents', [])
    
    def get_execution_modes(self) -> List[Dict[str, Any]]:
        """実行モード一覧を取得"""
        exec_modes = self.rules.get('execution_modes', {})
        return exec_modes.get('modes', [])
    
    def get_current_test_metrics(self) -> Dict[str, Any]:
        """現在のテストメトリクスを取得"""
        qa = self.rules.get('quality_assurance', {})
        testing = qa.get('testing', {})
        return testing.get('current_metrics', {})
    
    def get_progress_json_updates(self) -> Dict[str, Any]:
        """PROGRESS.json更新ルールを取得"""
        comm = self.rules.get('communication', {})
        doc_updates = comm.get('document_updates', {})
        return doc_updates.get('progress_json_updates', {})
    
    def validate_commit_prerequisites(self) -> List[str]:
        """
        コミット前の前提条件をチェック
        
        Returns:
            警告メッセージのリスト（問題がなければ空リスト）
        """
        warnings = []
        
        # コアドキュメントの存在チェック
        project_root = self.rules_file.parent
        for doc in self.get_core_documents():
            if doc.get('required', False):
                doc_path = project_root / doc['file']
                if not doc_path.exists():
                    warnings.append(f"⚠️  必須ドキュメントが見つかりません: {doc['file']}")
        
        return warnings
    
    def print_commit_workflow(self):
        """コミットワークフローを表示"""
        print("=" * 70)
        print("📋 コミット・プッシュワークフロー")
        print("=" * 70)
        
        for step in self.get_commit_workflow():
            print(f"\n【ステップ {step['step']}】{step['action']}")
            print(f"  └─ {step['detail']}")
        
        print("\n" + "=" * 70)
        print("🚫 禁止事項")
        print("=" * 70)
        
        for i, action in enumerate(self.get_prohibited_actions(), 1):
            print(f"  {i}. ❌ {action}")
        
        print("\n")
    
    def print_execution_modes(self):
        """実行モード一覧を表示"""
        print("=" * 70)
        print("🚀 実行モード")
        print("=" * 70)
        
        for mode in self.get_execution_modes():
            print(f"\n【{mode['name']}】")
            print(f"  back_test: {mode['back_test']}")
            print(f"  hot_test_dummy_mode: {mode['hot_test_dummy_mode']}")
            print(f"  用途: {mode['purpose']}")
            print(f"  取引: {mode['trading']}")
            print(f"  データ: {mode['data_source']}")
            print(f"  ログ: {mode['log_file']}")
            if mode.get('confirmation_required'):
                print(f"  ⚠️  {mode['warning_message']}")
        
        print("\n")
    
    def print_progress_json_workflow(self):
        """PROGRESS.json更新ワークフローを表示"""
        progress_updates = self.get_progress_json_updates()
        if not progress_updates:
            return
        
        print("=" * 70)
        print("📝 PROGRESS.json更新ルール")
        print("=" * 70)
        
        print(f"\n要件: {progress_updates.get('requirement', '')}")
        print(f"ツール: {progress_updates.get('tool', '')}")
        
        print("\n更新タイミング:")
        for trigger in progress_updates.get('update_triggers', []):
            print(f"  • {trigger}")
        
        if 'manual_update' in progress_updates:
            print(f"\n手動更新: {progress_updates['manual_update']}")
        
        print("\n")
    
    def print_summary(self):
        """ルールサマリーを表示"""
        print("\n" + "=" * 70)
        print(f"📖 DEVELOPMENT RULES v{self.get_version()}")
        print(f"📅 最終更新: {self.rules.get('last_updated', 'unknown')}")
        print("=" * 70)
        
        print(f"\n✅ コアドキュメント: {len(self.get_core_documents())}ファイル")
        for doc in self.get_core_documents():
            required = "✅ 必須" if doc.get('required') else "  任意"
            print(f"  {required} - {doc['file']}")
        
        print(f"\n🚀 実行モード: {len(self.get_execution_modes())}種類")
        for mode in self.get_execution_modes():
            print(f"  - {mode['name']}: {mode['purpose']}")
        
        metrics = self.get_current_test_metrics()
        if metrics:
            print(f"\n📊 テストメトリクス（{metrics.get('date', 'N/A')}）:")
            reg_tests = metrics.get('regression_tests', {})
            if reg_tests:
                print(f"  - レグレッションテスト: {reg_tests.get('passed', 0)}/{reg_tests.get('total', 0)} "
                      f"({reg_tests.get('success_rate', 'N/A')}) {reg_tests.get('status', '')}")
        
        print("\n")


def load_development_rules(rules_file: Optional[Path] = None) -> DevelopmentRules:
    """
    開発ルールを読み込み
    
    Args:
        rules_file: ルールファイルのパス（デフォルト: DEVELOPMENT_RULES.json）
    
    Returns:
        DevelopmentRulesインスタンス
    """
    return DevelopmentRules(rules_file)


def main():
    """メイン実行（テスト用）"""
    try:
        rules = load_development_rules()
        
        # サマリー表示
        rules.print_summary()
        
        # コミットワークフロー表示
        rules.print_commit_workflow()
        
        # PROGRESS.json更新ワークフロー表示
        rules.print_progress_json_workflow()
        
        # 実行モード表示
        rules.print_execution_modes()
        
        # 前提条件チェック
        warnings = rules.validate_commit_prerequisites()
        if warnings:
            print("⚠️  警告:")
            for warning in warnings:
                print(f"  {warning}")
        else:
            print("✅ すべての前提条件を満たしています")
        
    except FileNotFoundError as e:
        print(f"❌ エラー: {e}")
        return 1
    except json.JSONDecodeError as e:
        print(f"❌ JSON解析エラー: {e}")
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())
