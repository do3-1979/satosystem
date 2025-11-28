#!/usr/bin/env python3
"""
統合テスト・チェック実行スクリプト

すべてのテストをシングルコマンドで実行：
- pytest によるユニットテスト
- セキュリティチェック
- サンプルテスト（モジュール/バックテスト/可視化/ログ）
- config.ini 整合性確認

実行方法:
  python3 test/verify_all.py
  または
  cd test && ./verify_all.py
"""

import os
import sys
import subprocess
import json
from datetime import datetime
from pathlib import Path


class UnifiedTestRunner:
    """統合テスト・チェック実行"""

    def __init__(self):
        self.repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.test_dir = os.path.join(self.repo_root, 'test')
        self.src_dir = os.path.join(self.repo_root, 'src')
        self.config_ini_path = os.path.join(self.src_dir, 'config.ini')
        self.config_ini_hash_before = self._get_file_hash(self.config_ini_path)
        
        # sys.pathに src を追加（モジュールインポート用）
        sys.path.insert(0, self.src_dir)
        
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

    # ==================== pytest テスト ====================
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

    # ==================== セキュリティチェック ====================
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

    # ==================== サンプルテスト ====================
    def test_config_loading(self):
        """Config の読み込みテスト（読み取り専用）"""
        print("\n📋 Config 読み込みテスト...")
        try:
            from config import Config
            
            test_values = {
                'market_pair': Config.get_market_unit_pair(),
                'leverage': Config.get_leverage(),
                'time_frame': Config.get_time_frame(),
                'start_time': Config.get_start_time(),
                'end_time': Config.get_end_time(),
            }
            
            print("  ✅ Config 読み込み成功（読み取り専用）")
            return True
        except Exception as e:
            print(f"  ❌ Config 読み込み失敗: {str(e)}")
            return False

    def test_module_imports(self):
        """主要モジュールのインポートテスト"""
        print("\n📦 モジュールインポートテスト...")
        
        modules_to_test = [
            'config',
            'risk_management',
            'trading_strategy',
            'price_data_management',
            'portfolio',
            'regime_detector',
            'indicator_service',
        ]

        all_pass = True
        
        for module_name in modules_to_test:
            try:
                __import__(module_name)
                print(f"  ✅ {module_name}")
            except ImportError as e:
                print(f"  ❌ {module_name}: {str(e)}")
                all_pass = False
            except Exception as e:
                print(f"  ⚠️  {module_name}: {str(e)}")
                all_pass = False

        return all_pass

    def test_backtest_sample(self):
        """バックテストのサンプル実行"""
        print("\n🔬 バックテストサンプル実行...")
        
        backtest_script = os.path.join(self.src_dir, 'backtest.py')
        
        if not os.path.exists(backtest_script):
            print("  ⚠️  backtest.py が見つかりません")
            return False

        try:
            result = subprocess.run(
                [sys.executable, backtest_script, '--help'],
                cwd=self.src_dir,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                print("  ✅ バックテストスクリプトは実行可能")
                return True
            else:
                print(f"  ❌ バックテスト実行エラー: {result.stderr}")
                return False
        except subprocess.TimeoutExpired:
            print("  ⏱️  バックテスト実行がタイムアウト")
            return False
        except Exception as e:
            print(f"  ❌ バックテスト実行エラー: {str(e)}")
            return False

    def test_phase3_modules(self):
        """Phase 3 モジュールの実行可能性テスト"""
        print("\n🤖 Phase 3 モジュールテスト...")
        
        phase3_modules = [
            'environment_auto_judge',
            'dynamic_threshold_learning',
            'realtime_performance_monitor',
        ]

        all_pass = True
        
        for module_name in phase3_modules:
            module_file = os.path.join(self.src_dir, f'{module_name}.py')
            
            if not os.path.exists(module_file):
                print(f"  ⚠️  {module_name}.py が見つかりません")
                all_pass = False
                continue

            try:
                __import__(module_name)
                print(f"  ✅ {module_name}")
            except Exception as e:
                print(f"  ❌ {module_name}: {str(e)}")
                all_pass = False

        return all_pass

    def test_visualization_files(self):
        """可視化ファイル生成テスト（読み取り専用チェック）"""
        print("\n📊 可視化ファイル生成テスト...")
        
        report_dir = os.path.join(self.repo_root, 'report')
        viz_files = []
        
        try:
            if os.path.exists(report_dir):
                viz_files = [f for f in os.listdir(report_dir) if f.startswith('backtest_visualization_') and f.endswith('.html')]
            
            if viz_files:
                latest_file = sorted(viz_files)[-1]
                file_path = os.path.join(report_dir, latest_file)
                file_size = os.path.getsize(file_path)
                
                if file_size > 10000:  # 10KB以上
                    print(f"  ✅ グラフファイル生成確認: {latest_file} ({file_size/1024:.1f}KB)")
                    return True
                else:
                    print(f"  ⚠️  グラフファイルサイズが小さい: {latest_file} ({file_size}B)")
                    return False
            else:
                print("  ⚠️  グラフファイルが見つかりません")
                return False
                
        except Exception as e:
            print(f"  ❌ グラフファイルチェックエラー: {str(e)}")
            return False

    def test_log_files(self):
        """ログファイル生成テスト（読み取り専用チェック）"""
        print("\n📝 ログファイル生成テスト...")
        
        log_dir = os.path.join(self.repo_root, 'logs')
        
        try:
            if os.path.exists(log_dir):
                zip_files = [f for f in os.listdir(log_dir) if f.endswith('.zip')]
                
                if zip_files:
                    latest_file = sorted(zip_files)[-1]
                    file_path = os.path.join(log_dir, latest_file)
                    file_size = os.path.getsize(file_path)
                    
                    print(f"  ✅ ログファイル生成確認: {latest_file} ({file_size/1024:.1f}KB)")
                    print(f"    - ファイル数: {len(zip_files)}")
                    return True
                else:
                    print("  ⚠️  ログZIPファイルが見つかりません")
                    return True  # 警告だが、テストは失敗としない
            else:
                print("  ⚠️  ログディレクトリが見つかりません")
                return True  # 警告だが、テストは失敗としない
                
        except Exception as e:
            print(f"  ❌ ログファイルチェックエラー: {str(e)}")
            return False

    def test_data_integrity(self):
        """データ整合性テスト（読み取り専用チェック）"""
        print("\n✔️  データ整合性テスト...")
        
        integrity_checks = {
            'src_directory_exists': os.path.exists(os.path.join(self.repo_root, 'src')),
            'config_ini_exists': os.path.exists(os.path.join(self.repo_root, 'src', 'config.ini')),
            'bot_py_exists': os.path.exists(os.path.join(self.repo_root, 'src', 'bot.py')),
            'run_backtest_py_exists': os.path.exists(os.path.join(self.repo_root, 'run_backtest.py')),
        }
        
        all_pass = all(integrity_checks.values())
        
        for check, result in integrity_checks.items():
            symbol = '✅' if result else '❌'
            print(f"  {symbol} {check}: {result}")
        
        return all_pass

    def run_sample_tests(self):
        """サンプルテスト実行"""
        print("\n" + "=" * 70)
        print("3️⃣  サンプルテスト実行 (config, modules, backtest)")
        print("=" * 70)
        print("\n⚠️  注意: このスクリプトはテスト・チェック・判定のみを行います")
        print("   問題が見つかった場合は、出力に従ってユーザが手動で修正してください\n")

        all_pass = True
        all_pass = self.test_config_loading() and all_pass
        all_pass = self.test_module_imports() and all_pass
        all_pass = self.test_backtest_sample() and all_pass
        all_pass = self.test_phase3_modules() and all_pass
        all_pass = self.test_visualization_files() and all_pass
        all_pass = self.test_log_files() and all_pass
        all_pass = self.test_data_integrity() and all_pass

        if all_pass:
            print("\n✅ サンプルテスト: PASS")
            self.results['checks']['sample_tests'] = 'PASS'
            self.results['summary']['passed'] += 1
        else:
            print("\n❌ サンプルテスト: FAIL")
            self.results['checks']['sample_tests'] = 'FAIL'
            self.results['summary']['failed'] += 1

        self.results['summary']['total'] += 1

    # ==================== config.ini 整合性確認 ====================
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
            self.results['checks']['config_integrity'] = 'FAIL'
            self.results['summary']['failed'] += 1

        self.results['summary']['total'] += 1
        return self.config_ini_hash_before == config_ini_hash_after

    # ==================== 最終レポート ====================
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

        # レポートをファイルに保存
        work_reports_dir = os.path.join(self.repo_root, 'work_reports')
        os.makedirs(work_reports_dir, exist_ok=True)

        date_dir = os.path.join(
            work_reports_dir,
            datetime.now().strftime("%Y-%m-%d")
        )
        os.makedirs(date_dir, exist_ok=True)

        report_file = os.path.join(
            date_dir,
            f'verify_all_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
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

    # ==================== メイン実行 ====================
    def run_all(self):
        """全チェックを実行"""
        print("\n" + "#" * 70)
        print("# 🧪 統合テスト・チェック実行")
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
    runner = UnifiedTestRunner()
    success = runner.run_all()
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
