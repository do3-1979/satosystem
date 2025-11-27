#!/usr/bin/env python3
"""
全テスト・チェック一括実行スクリプト
コミット前にこれを実行し、すべての問題がないことを確認する

実行方法:
  python3 test/run_all_checks.py
  または
  cd test && ./run_all_checks.py
"""

import os
import sys
import subprocess
import json
from datetime import datetime
from pathlib import Path


class AllChecksRunner:
    """全テスト・チェック一括実行"""

    def __init__(self):
        self.repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.test_dir = os.path.join(self.repo_root, 'test')
        self.config_ini_path = os.path.join(self.repo_root, 'src', 'config.ini')
        self.config_ini_hash_before = self._get_file_hash(self.config_ini_path)
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'checks': {},
            'summary': {
                'total': 0,
                'passed': 0,
                'failed': 0,
            }
        }

    def _get_file_hash(self, file_path):
        """ファイルのハッシュ値を取得（変更検知用）"""
        if not os.path.exists(file_path):
            return None
        
        try:
            import hashlib
            with open(file_path, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception:
            return None

    def run_pytest(self):
        """pytest によるユニットテスト実行"""
        print("\n" + "=" * 70)
        print("1️⃣  ユニットテスト実行 (pytest)")
        print("=" * 70)

        test_files = [
            'test_config.py',
            'test_risk_management.py',
            'test_phase3.py',
        ]

        for test_file in test_files:
            test_path = os.path.join(self.test_dir, test_file)
            
            if not os.path.exists(test_path):
                print(f"⚠️  {test_file} が見つかりません")
                continue

            try:
                result = subprocess.run(
                    [sys.executable, '-m', 'pytest', test_path, '-v', '--tb=short'],
                    cwd=self.test_dir,
                    capture_output=True,
                    text=True,
                    timeout=120
                )

                if result.returncode == 0:
                    print(f"✅ {test_file}: PASS")
                    self.results['checks'][test_file] = 'PASS'
                    self.results['summary']['passed'] += 1
                else:
                    print(f"❌ {test_file}: FAIL")
                    if result.stdout:
                        print(f"  Output: {result.stdout[:200]}")
                    if result.stderr:
                        print(f"  Error: {result.stderr[:200]}")
                    self.results['checks'][test_file] = 'FAIL'
                    self.results['summary']['failed'] += 1

                self.results['summary']['total'] += 1
            except subprocess.TimeoutExpired:
                print(f"⏱️  {test_file}: TIMEOUT")
                self.results['checks'][test_file] = 'TIMEOUT'
                self.results['summary']['failed'] += 1
                self.results['summary']['total'] += 1
            except Exception as e:
                print(f"⚠️  {test_file}: ERROR - {str(e)}")
                self.results['checks'][test_file] = 'ERROR'
                self.results['summary']['failed'] += 1
                self.results['summary']['total'] += 1

    def run_security_check(self):
        """セキュリティチェック実行"""
        print("\n" + "=" * 70)
        print("2️⃣  セキュリティチェック (API キー流出確認)")
        print("=" * 70)

        security_script = os.path.join(self.test_dir, 'security_check.py')

        try:
            result = subprocess.run(
                [sys.executable, security_script],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                print("✅ セキュリティチェック: PASS")
                self.results['checks']['security_check'] = 'PASS'
                self.results['summary']['passed'] += 1
                print(result.stdout)
            else:
                print("❌ セキュリティチェック: FAIL")
                print(result.stdout)
                if result.stderr:
                    print(f"Error: {result.stderr}")
                self.results['checks']['security_check'] = 'FAIL'
                self.results['summary']['failed'] += 1

            self.results['summary']['total'] += 1
        except subprocess.TimeoutExpired:
            print("⏱️  セキュリティチェック: TIMEOUT")
            self.results['checks']['security_check'] = 'TIMEOUT'
            self.results['summary']['failed'] += 1
            self.results['summary']['total'] += 1
        except Exception as e:
            print(f"⚠️  セキュリティチェック: ERROR - {str(e)}")
            self.results['checks']['security_check'] = 'ERROR'
            self.results['summary']['failed'] += 1
            self.results['summary']['total'] += 1

    def run_sample_tests(self):
        """サンプルテスト実行"""
        print("\n" + "=" * 70)
        print("3️⃣  サンプルテスト実行 (config, modules, backtest)")
        print("=" * 70)

        sample_script = os.path.join(self.test_dir, 'sample_test_runner.py')

        try:
            result = subprocess.run(
                [sys.executable, sample_script],
                cwd=self.test_dir,
                capture_output=True,
                text=True,
                timeout=60
            )

            print(result.stdout)

            if result.returncode == 0:
                print("\n✅ サンプルテスト: PASS")
                self.results['checks']['sample_tests'] = 'PASS'
                self.results['summary']['passed'] += 1
            else:
                print("\n❌ サンプルテスト: FAIL")
                if result.stderr:
                    print(f"Error: {result.stderr}")
                self.results['checks']['sample_tests'] = 'FAIL'
                self.results['summary']['failed'] += 1

            self.results['summary']['total'] += 1
        except subprocess.TimeoutExpired:
            print("⏱️  サンプルテスト: TIMEOUT")
            self.results['checks']['sample_tests'] = 'TIMEOUT'
            self.results['summary']['failed'] += 1
            self.results['summary']['total'] += 1
        except Exception as e:
            print(f"⚠️  サンプルテスト: ERROR - {str(e)}")
            self.results['checks']['sample_tests'] = 'ERROR'
            self.results['summary']['failed'] += 1
            self.results['summary']['total'] += 1

    def check_config_integrity(self):
        """config.ini が変更されていないか確認"""
        print("\n" + "=" * 70)
        print("4️⃣  ファイル整合性チェック (config.ini)")
        print("=" * 70)

        config_ini_hash_after = self._get_file_hash(self.config_ini_path)

        if self.config_ini_hash_before is None:
            print("⚠️  config.ini が見つかりません（スキップ）")
            self.results['checks']['config_integrity'] = 'SKIP'
            return True

        if self.config_ini_hash_before == config_ini_hash_after:
            print("✅ config.ini: 変更なし")
            self.results['checks']['config_integrity'] = 'PASS'
            self.results['summary']['passed'] += 1
        else:
            print("❌ config.ini: テスト実行中に変更されました")
            print(f"   ⚠️  警告: テストスクリプトが config.ini を修正しようとしました")
            print(f"   🔧 修正対象のテストスクリプトを確認してください")
            print(f"      - test/run_all_checks.py")
            print(f"      - test/sample_test_runner.py")
            print(f"      - test/security_check.py")
            self.results['checks']['config_integrity'] = 'FAIL'
            self.results['summary']['failed'] += 1

        self.results['summary']['total'] += 1
        return self.config_ini_hash_before == config_ini_hash_after

    def generate_final_report(self):
        """最終レポート生成"""
        print("\n" + "=" * 70)
        print("📊 最終テスト結果レポート")
        print("=" * 70)

        summary = self.results['summary']
        
        print(f"\n📈 総合結果:")
        print(f"  - 総テスト数: {summary['total']}")
        print(f"  - 成功: {summary['passed']} ✅")
        print(f"  - 失敗: {summary['failed']} ❌")

        success_rate = 100 * summary['passed'] / summary['total'] if summary['total'] > 0 else 0
        print(f"  - 成功率: {success_rate:.1f}%")

        print(f"\n📝 詳細:")
        for check, result in self.results['checks'].items():
            symbol = '✅' if result == 'PASS' else '❌' if result == 'FAIL' else ('⏱️ ' if result == 'TIMEOUT' else '⊘ ')
            print(f"  {symbol} {check}: {result}")

        # レポートをファイルに保存（日付ディレクトリに保存）
        work_reports_dir = os.path.join(self.repo_root, 'work_reports')
        os.makedirs(work_reports_dir, exist_ok=True)

        # 日付ごとのディレクトリを作成（docs/README.md ルール）
        date_dir = os.path.join(
            work_reports_dir,
            datetime.now().strftime("%Y-%m-%d")
        )
        os.makedirs(date_dir, exist_ok=True)

        report_file = os.path.join(
            date_dir,
            f'all_checks_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        )

        with open(report_file, 'w') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)

        print(f"\n📄 詳細レポート保存: {report_file}")

        print("\n" + "=" * 70)

        # 最終判定
        if summary['failed'] == 0:
            print("\n✅ すべてのテスト・チェックに合格しました！")
            print("✅ プロジェクトファイル（config.ini）の整合性も確認されました。")
            print("🚀 コミット・プッシュの準備ができています。")
            return True
        else:
            print(f"\n❌ {summary['failed']} 個のテスト・チェックが失敗しました。")
            print("🔧 問題を修正してから再度実行してください。")
            return False

    def run_all(self):
        """全チェックを実行"""
        print("\n" + "#" * 70)
        print("# 🧪 全テスト・チェック一括実行")
        print("#" * 70)
        print("\n⚠️  注意: このスクリプトはチェック・判定のみを行い、修正は行いません")
        print("   問題が見つかった場合は、出力に従ってユーザが手動で修正してください")
        print("   テスト実行中に config.ini を含むプロジェクトファイルは変更しません\n")

        self.run_pytest()
        self.run_security_check()
        self.run_sample_tests()
        self.check_config_integrity()

        return self.generate_final_report()


def main():
    """メイン実行"""
    runner = AllChecksRunner()
    success = runner.run_all()
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
