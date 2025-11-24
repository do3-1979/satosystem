#!/usr/bin/env python3
"""
セキュリティチェック: API キー流出確認
コミット前にこれを実行し、API キーが誤ってコミットされていないか確認
"""

import os
import sys
import re
from pathlib import Path


class SecurityChecker:
    """セキュリティチェック実行クラス"""

    def __init__(self, repo_root):
        self.repo_root = repo_root
        self.violations = []
        self.warnings = []

    def check_api_keys_in_files(self):
        """ソースコード内の API キー流出をチェック"""
        # チェック対象外ディレクトリ
        exclude_dirs = {'.git', '__pycache__', '.pytest_cache', 'node_modules', '.venv', 'venv'}
        # チェック対象ファイル拡張子
        include_extensions = {'.py', '.ini', '.json', '.yaml', '.yml', '.env', '.txt'}
        
        # チェック対象パターン
        patterns = {
            'api_key_with_value': r'api_key\s*=\s*["\'](?!YOUR_|xxx|placeholder)[^"\']+["\']',
            'api_secret_with_value': r'api_secret\s*=\s*["\'](?!YOUR_|xxx|placeholder)[^"\']+["\']',
            'bybit_key_pattern': r'BYBIT_API_KEY\s*=\s*["\'](?!YOUR_|xxx)[^"\']{20,}["\']',
            'bybit_secret_pattern': r'BYBIT_API_SECRET\s*=\s*["\'](?!YOUR_|xxx)[^"\']{20,}["\']',
        }

        for root, dirs, files in os.walk(self.repo_root):
            # 除外ディレクトリをフィルタ
            dirs[:] = [d for d in dirs if d not in exclude_dirs]

            for file in files:
                file_path = os.path.join(root, file)
                _, ext = os.path.splitext(file)

                # チェック対象ファイルのみ処理
                if ext.lower() in include_extensions:
                    self._check_file_content(file_path, patterns)

    def _check_file_content(self, file_path, patterns):
        """ファイルの内容をチェック"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

                for line_num, line in enumerate(content.split('\n'), 1):
                    # コメント行は除外
                    if line.strip().startswith('#'):
                        continue

                    for pattern_name, pattern in patterns.items():
                        if re.search(pattern, line, re.IGNORECASE):
                            rel_path = os.path.relpath(file_path, self.repo_root)
                            self.violations.append({
                                'file': rel_path,
                                'line': line_num,
                                'pattern': pattern_name,
                                'snippet': line.strip()[:80]  # 最初の80文字
                            })
        except Exception as e:
            # ファイル読み込みエラーは警告として扱う
            rel_path = os.path.relpath(file_path, self.repo_root)
            self.warnings.append(f"Could not read {rel_path}: {str(e)}")

    def check_git_staged_files(self):
        """git ステージングエリアのファイルをチェック"""
        import subprocess

        try:
            # ステージングエリアのファイル一覧を取得
            result = subprocess.run(
                ['git', 'diff', '--cached', '--name-only'],
                cwd=self.repo_root,
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                staged_files = result.stdout.strip().split('\n')
                
                for file_path in staged_files:
                    if not file_path:
                        continue
                    
                    full_path = os.path.join(self.repo_root, file_path)
                    if os.path.exists(full_path):
                        self._check_file_for_staged_api_keys(full_path)
        except Exception as e:
            self.warnings.append(f"Could not check git staged files: {str(e)}")

    def _check_file_for_staged_api_keys(self, file_path):
        """ステージングされたファイルの API キーをチェック"""
        sensitive_patterns = [
            r'(?i)(api_key|api_secret|bybit_key|bybit_secret)\s*[=:]\s*["\']([^"\']{20,})["\']',
        ]

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

                for line_num, line in enumerate(content.split('\n'), 1):
                    if line.strip().startswith('#'):
                        continue

                    for pattern in sensitive_patterns:
                        if re.search(pattern, line):
                            rel_path = os.path.relpath(file_path, self.repo_root)
                            self.violations.append({
                                'file': rel_path,
                                'line': line_num,
                                'type': 'staged_file',
                                'severity': 'CRITICAL'
                            })
        except Exception:
            pass

    def check_dotenv_files(self):
        """環境変数ファイル（.env など）のチェック"""
        env_files = ['.env', '.env.local', '.env.development', '.env.production']
        
        for env_file in env_files:
            file_path = os.path.join(self.repo_root, env_file)
            
            if os.path.exists(file_path):
                # .env ファイルが git にコミットされていないか確認
                try:
                    import subprocess
                    result = subprocess.run(
                        ['git', 'ls-files', env_file],
                        cwd=self.repo_root,
                        capture_output=True,
                        text=True
                    )
                    
                    if result.stdout.strip():  # ファイルが git に登録されている
                        self.violations.append({
                            'file': env_file,
                            'severity': 'CRITICAL',
                            'issue': f'{env_file} should not be committed to git'
                        })
                except Exception:
                    pass

    def check_gitignore(self):
        """.gitignore に機密ファイルが含まれているか確認"""
        gitignore_path = os.path.join(self.repo_root, '.gitignore')
        required_ignores = ['.api_key', '.env', '*.pem', '*.key']

        if os.path.exists(gitignore_path):
            with open(gitignore_path, 'r') as f:
                gitignore_content = f.read()

            for ignore_pattern in required_ignores:
                if ignore_pattern not in gitignore_content:
                    self.warnings.append(f"Recommended to add '{ignore_pattern}' to .gitignore")

    def report(self):
        """チェック結果をレポート"""
        print("\n" + "=" * 70)
        print("🔐 セキュリティチェックレポート")
        print("=" * 70)

        if not self.violations and not self.warnings:
            print("✅ 問題は検出されませんでした")
            return True

        if self.violations:
            print(f"\n❌ 違反 ({len(self.violations)} 件):")
            for v in self.violations:
                print(f"  - {v.get('file', 'unknown')}:{v.get('line', '?')} - {v.get('pattern', v.get('type', 'unknown'))}")
                if 'snippet' in v:
                    print(f"    {v['snippet']}")

        if self.warnings:
            print(f"\n⚠️  警告 ({len(self.warnings)} 件):")
            for w in self.warnings:
                print(f"  - {w}")

        print("\n" + "=" * 70)
        return len(self.violations) == 0


def main():
    """メイン実行"""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    checker = SecurityChecker(repo_root)
    
    print("🔍 セキュリティチェック実行中...")
    print("  - ファイルの内容をスキャン中...")
    checker.check_api_keys_in_files()
    
    print("  - Git ステージングエリアをチェック中...")
    checker.check_git_staged_files()
    
    print("  - 環境変数ファイルをチェック中...")
    checker.check_dotenv_files()
    
    print("  - .gitignore を確認中...")
    checker.check_gitignore()

    # レポート出力
    is_safe = checker.report()

    return 0 if is_safe else 1


if __name__ == '__main__':
    sys.exit(main())
