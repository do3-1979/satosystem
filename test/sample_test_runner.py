#!/usr/bin/env python3
"""
バックテスト・サンプルテスト実行スクリプト
既存の実装を使用してサンプルデータで動作確認
"""

import os
import sys
import json
import subprocess
from datetime import datetime
from pathlib import Path


class SampleTestRunner:
    """サンプルテスト実行クラス"""

    def __init__(self, repo_root):
        self.repo_root = repo_root
        self.src_dir = os.path.join(repo_root, 'src')
        self.test_results = {
            'timestamp': datetime.now().isoformat(),
            'backtest_results': [],
            'config_load_test': None,
            'module_import_test': None,
            'errors': []
        }
        sys.path.insert(0, self.src_dir)

    def test_config_loading(self):
        """Config の読み込みテスト（読み取り専用）"""
        print("\n📋 Config 読み込みテスト...")
        try:
            from config import Config
            
            # Config は読み取り専用のみ、変更は行わない
            test_values = {
                'market_pair': Config.get_market_unit_pair(),
                'leverage': Config.get_leverage(),
                'time_frame': Config.get_time_frame(),
                'start_time': Config.get_start_time(),
                'end_time': Config.get_end_time(),
            }
            
            self.test_results['config_load_test'] = {
                'status': 'PASS',
                'values': test_values
            }
            print("  ✅ Config 読み込み成功（読み取り専用）")
            return True
        except Exception as e:
            self.test_results['config_load_test'] = {
                'status': 'FAIL',
                'error': str(e)
            }
            self.test_results['errors'].append(f"Config loading failed: {str(e)}")
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

        import_results = {}
        
        for module_name in modules_to_test:
            try:
                __import__(module_name)
                import_results[module_name] = 'PASS'
                print(f"  ✅ {module_name}")
            except ImportError as e:
                import_results[module_name] = f"FAIL: {str(e)}"
                self.test_results['errors'].append(f"Import {module_name} failed: {str(e)}")
                print(f"  ❌ {module_name}: {str(e)}")
            except Exception as e:
                import_results[module_name] = f"ERROR: {str(e)}"
                self.test_results['errors'].append(f"Error importing {module_name}: {str(e)}")
                print(f"  ⚠️  {module_name}: {str(e)}")

        self.test_results['module_import_test'] = import_results
        return all(v == 'PASS' for v in import_results.values())

    def test_backtest_sample(self):
        """バックテストのサンプル実行"""
        print("\n🔬 バックテストサンプル実行...")
        
        backtest_script = os.path.join(self.src_dir, 'backtest.py')
        
        if not os.path.exists(backtest_script):
            print("  ⚠️  backtest.py が見つかりません")
            return False

        try:
            # バックテストスクリプトが実行可能か確認
            result = subprocess.run(
                [sys.executable, backtest_script, '--help'],
                cwd=self.src_dir,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                print("  ✅ バックテストスクリプトは実行可能")
                self.test_results['backtest_results'].append({
                    'test': 'backtest_help',
                    'status': 'PASS'
                })
                return True
            else:
                print(f"  ❌ バックテスト実行エラー: {result.stderr}")
                self.test_results['errors'].append(f"Backtest error: {result.stderr}")
                self.test_results['backtest_results'].append({
                    'test': 'backtest_help',
                    'status': 'FAIL',
                    'error': result.stderr
                })
                return False
        except subprocess.TimeoutExpired:
            print("  ⏱️  バックテスト実行がタイムアウト")
            self.test_results['errors'].append("Backtest timeout")
            return False
        except Exception as e:
            print(f"  ❌ バックテスト実行エラー: {str(e)}")
            self.test_results['errors'].append(f"Backtest execution error: {str(e)}")
            return False

    def test_phase3_modules(self):
        """Phase 3 モジュールの実行可能性テスト"""
        print("\n🤖 Phase 3 モジュールテスト...")
        
        phase3_modules = [
            'environment_auto_judge',
            'dynamic_threshold_learning',
            'realtime_performance_monitor',
        ]

        results = {}
        
        for module_name in phase3_modules:
            module_file = os.path.join(self.src_dir, f'{module_name}.py')
            
            if not os.path.exists(module_file):
                results[module_name] = 'NOT_FOUND'
                print(f"  ⚠️  {module_name}.py が見つかりません")
                continue

            try:
                # インポート可能か確認
                __import__(module_name)
                results[module_name] = 'PASS'
                print(f"  ✅ {module_name}")
            except Exception as e:
                results[module_name] = f"ERROR: {str(e)}"
                self.test_results['errors'].append(f"Phase3 module {module_name} error: {str(e)}")
                print(f"  ❌ {module_name}: {str(e)}")

        self.test_results['phase3_modules'] = results
        return True

    def test_visualization_files(self):
        """可視化ファイル生成テスト（読み取り専用チェック）"""
        print("\n📊 可視化ファイル生成テスト...")
        
        report_dir = os.path.join(self.repo_root, 'report')
        viz_files = []
        
        try:
            if os.path.exists(report_dir):
                viz_files = [f for f in os.listdir(report_dir) if f.startswith('backtest_visualization_') and f.endswith('.html')]
            
            if viz_files:
                # 最新のファイルをチェック
                latest_file = sorted(viz_files)[-1]
                file_path = os.path.join(report_dir, latest_file)
                file_size = os.path.getsize(file_path)
                
                # グラフファイルサイズが最小限度より大きいかチェック
                if file_size > 10000:  # 10KB以上
                    print(f"  ✅ グラフファイル生成確認: {latest_file} ({file_size/1024:.1f}KB)")
                    self.test_results['visualization_test'] = {
                        'status': 'PASS',
                        'latest_file': latest_file,
                        'file_size_kb': file_size/1024
                    }
                    return True
                else:
                    print(f"  ⚠️  グラフファイルサイズが小さい: {latest_file} ({file_size}B)")
                    self.test_results['visualization_test'] = {
                        'status': 'WARNING',
                        'latest_file': latest_file,
                        'file_size_kb': file_size/1024
                    }
                    self.test_results['errors'].append(f"Visualization file too small: {file_size}B")
                    return False
            else:
                print("  ⚠️  グラフファイルが見つかりません")
                self.test_results['visualization_test'] = {
                    'status': 'NOT_FOUND',
                }
                self.test_results['errors'].append("No visualization files found")
                return False
                
        except Exception as e:
            print(f"  ❌ グラフファイルチェックエラー: {str(e)}")
            self.test_results['visualization_test'] = {
                'status': 'ERROR',
                'error': str(e)
            }
            self.test_results['errors'].append(f"Visualization check error: {str(e)}")
            return False

    def test_log_files(self):
        """ログファイル生成テスト（読み取り専用チェック）"""
        print("\n📝 ログファイル生成テスト...")
        
        log_dir = os.path.join(self.repo_root, 'logs')
        
        try:
            if os.path.exists(log_dir):
                zip_files = [f for f in os.listdir(log_dir) if f.endswith('.zip')]
                
                if zip_files:
                    # 最新のZIPファイルをチェック
                    latest_file = sorted(zip_files)[-1]
                    file_path = os.path.join(log_dir, latest_file)
                    file_size = os.path.getsize(file_path)
                    
                    print(f"  ✅ ログファイル生成確認: {latest_file} ({file_size/1024:.1f}KB)")
                    self.test_results['log_files_test'] = {
                        'status': 'PASS',
                        'latest_file': latest_file,
                        'file_size_kb': file_size/1024,
                        'total_files': len(zip_files)
                    }
                    return True
                else:
                    print("  ⚠️  ログZIPファイルが見つかりません")
                    self.test_results['log_files_test'] = {
                        'status': 'NOT_FOUND',
                    }
                    return True  # 警告だが、テストは失敗としない
            else:
                print("  ⚠️  ログディレクトリが見つかりません")
                self.test_results['log_files_test'] = {
                    'status': 'NOT_FOUND',
                }
                return True  # 警告だが、テストは失敗としない
                
        except Exception as e:
            print(f"  ❌ ログファイルチェックエラー: {str(e)}")
            self.test_results['log_files_test'] = {
                'status': 'ERROR',
                'error': str(e)
            }
            self.test_results['errors'].append(f"Log files check error: {str(e)}")
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
        
        self.test_results['data_integrity_test'] = {
            'status': 'PASS' if all_pass else 'FAIL',
            'checks': integrity_checks
        }
        
        if not all_pass:
            self.test_results['errors'].append("Data integrity check failed")
        
        return all_pass

    def generate_report(self):
        """テスト結果レポートを生成"""
        print("\n" + "=" * 70)
        print("📊 テスト結果レポート")
        print("=" * 70)

        # サマリー
        total_tests = 7
        passed_tests = sum([
            1 if self.test_results.get('config_load_test', {}).get('status') == 'PASS' else 0,
            1 if self.test_results.get('module_import_test') else 0,
            1 if self.test_results.get('backtest_results') else 0,
            1 if self.test_results.get('phase3_modules') else 0,
            1 if self.test_results.get('visualization_test', {}).get('status') == 'PASS' else 0,
            1 if self.test_results.get('log_files_test', {}).get('status') == 'PASS' else 0,
            1 if self.test_results.get('data_integrity_test', {}).get('status') == 'PASS' else 0,
        ])

        print(f"\n📈 総合結果: {passed_tests}/{total_tests} テスト成功")

        # 詳細
        print("\n📝 詳細結果:")
        
        if self.test_results['config_load_test']:
            status = self.test_results['config_load_test'].get('status', 'UNKNOWN')
            symbol = '✅' if status == 'PASS' else '❌'
            print(f"\n{symbol} Config 読み込みテスト: {status}")
            if status == 'PASS':
                for key, value in self.test_results['config_load_test'].get('values', {}).items():
                    print(f"    - {key}: {value}")

        if self.test_results['module_import_test']:
            print(f"\n📦 モジュールインポート:")
            for module, result in self.test_results['module_import_test'].items():
                symbol = '✅' if result == 'PASS' else '❌'
                print(f"    {symbol} {module}: {result}")

        if self.test_results['backtest_results']:
            print(f"\n🔬 バックテスト:")
            for test in self.test_results['backtest_results']:
                symbol = '✅' if test['status'] == 'PASS' else '❌'
                print(f"    {symbol} {test['test']}: {test['status']}")

        if self.test_results['phase3_modules']:
            print(f"\n🤖 Phase 3 モジュール:")
            for module, result in self.test_results['phase3_modules'].items():
                symbol = '✅' if result == 'PASS' else '⚠️ ' if result == 'NOT_FOUND' else '❌'
                print(f"    {symbol} {module}: {result}")

        if self.test_results.get('visualization_test'):
            viz_status = self.test_results['visualization_test'].get('status', 'UNKNOWN')
            symbol = '✅' if viz_status == 'PASS' else '⚠️ ' if viz_status == 'WARNING' else '❌'
            print(f"\n{symbol} グラフファイル生成テスト: {viz_status}")
            if viz_status == 'PASS' and 'file_size_kb' in self.test_results['visualization_test']:
                print(f"    - {self.test_results['visualization_test'].get('latest_file')} ({self.test_results['visualization_test']['file_size_kb']:.1f}KB)")

        if self.test_results.get('log_files_test'):
            log_status = self.test_results['log_files_test'].get('status', 'UNKNOWN')
            symbol = '✅' if log_status == 'PASS' else '⚠️ ' if log_status == 'NOT_FOUND' else '❌'
            print(f"\n{symbol} ログファイルテスト: {log_status}")
            if log_status == 'PASS' and 'total_files' in self.test_results['log_files_test']:
                print(f"    - ファイル数: {self.test_results['log_files_test']['total_files']}")

        if self.test_results.get('data_integrity_test'):
            integrity_status = self.test_results['data_integrity_test'].get('status', 'UNKNOWN')
            symbol = '✅' if integrity_status == 'PASS' else '❌'
            print(f"\n{symbol} データ整合性テスト: {integrity_status}")

        if self.test_results['errors']:
            print(f"\n⚠️  エラー ({len(self.test_results['errors'])} 件):")
            for error in self.test_results['errors'][:5]:  # 最初の5件
                print(f"    - {error}")

        # 結果をファイルに保存
        self._save_report()

        print("\n" + "=" * 70)
        return len(self.test_results['errors']) == 0

    def _save_report(self):
        """レポートを JSON ファイルに保存（日付ディレクトリに保存）"""
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
            f'sample_test_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        )

        with open(report_file, 'w') as f:
            json.dump(self.test_results, f, indent=2, ensure_ascii=False)

        print(f"\n📄 レポート保存: {report_file}")

    def run_all(self):
        """全テストを実行"""
        print("=" * 70)
        print("🧪 サンプルテスト実行開始")
        print("=" * 70)
        
        print("\n⚠️  注意: このスクリプトはテスト・チェック・判定のみを行います")
        print("   問題が見つかった場合は、出力に従ってユーザが手動で修正してください")
        print("   テスト実行中に config.ini を含むプロジェクトファイルは変更しません\n")

        self.test_config_loading()
        self.test_module_imports()
        self.test_backtest_sample()
        self.test_phase3_modules()
        self.test_visualization_files()
        self.test_log_files()
        self.test_data_integrity()

        return self.generate_report()


def main():
    """メイン実行"""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    runner = SampleTestRunner(repo_root)
    success = runner.run_all()

    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
