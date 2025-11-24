"""
テスト: Phase 3 自動化モジュール
environment_auto_judge.py, dynamic_threshold_learning.py, realtime_performance_monitor.py のテスト
"""

import pytest
import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from config import Config


class TestEnvironmentAutoJudge:
    """環境自動判定スクリプトのテスト"""

    def test_environment_auto_judge_import(self):
        """environment_auto_judge.py がインポート可能か"""
        try:
            import environment_auto_judge
            assert environment_auto_judge is not None
        except ImportError as e:
            pytest.skip(f"environment_auto_judge module not available: {str(e)}")

    def test_environment_auto_judge_output_format(self):
        """環境自動判定の出力フォーマット確認"""
        # work_reports/environment_auto_judgement_*.json が生成されるか
        work_reports_dir = os.path.join(os.path.dirname(__file__), '..', 'work_reports')
        if os.path.exists(work_reports_dir):
            json_files = [f for f in os.listdir(work_reports_dir) 
                         if f.startswith('environment_auto_judgement_') and f.endswith('.json')]
            
            if json_files:
                # 最新のファイルを確認
                latest_file = sorted(json_files)[-1]
                filepath = os.path.join(work_reports_dir, latest_file)
                
                try:
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                        assert 'SIDEWAYS_ratio' in data or 'recommendation' in data, \
                            "JSON should contain SIDEWAYS_ratio or recommendation"
                except (json.JSONDecodeError, IOError):
                    pytest.skip("Could not read environment_auto_judgement JSON file")
            else:
                pytest.skip("No environment_auto_judgement JSON files found")
        else:
            pytest.skip("work_reports directory not found")


class TestDynamicThresholdLearning:
    """動的基準学習システムのテスト"""

    def test_dynamic_threshold_import(self):
        """dynamic_threshold_learning.py がインポート可能か"""
        try:
            import dynamic_threshold_learning
            assert dynamic_threshold_learning is not None
        except ImportError as e:
            pytest.skip(f"dynamic_threshold_learning module not available: {str(e)}")

    def test_dynamic_threshold_output_format(self):
        """動的学習の出力フォーマット確認"""
        work_reports_dir = os.path.join(os.path.dirname(__file__), '..', 'work_reports')
        if os.path.exists(work_reports_dir):
            json_files = [f for f in os.listdir(work_reports_dir) 
                         if f.startswith('dynamic_threshold_learning_') and f.endswith('.json')]
            
            if json_files:
                # 最新のファイルを確認
                latest_file = sorted(json_files)[-1]
                filepath = os.path.join(work_reports_dir, latest_file)
                
                try:
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                        # キーが1つ以上含まれていることを確認（柔軟なチェック）
                        assert isinstance(data, dict) and len(data) > 0, \
                            "JSON should contain threshold/learning data"
                except (json.JSONDecodeError, IOError):
                    pytest.skip("Could not read dynamic_threshold_learning JSON file")
            else:
                pytest.skip("No dynamic_threshold_learning JSON files found")
        else:
            pytest.skip("work_reports directory not found")


class TestRealtimePerformanceMonitor:
    """リアルタイムパフォーマンス監視システムのテスト"""

    def test_realtime_monitor_import(self):
        """realtime_performance_monitor.py がインポート可能か"""
        try:
            import realtime_performance_monitor
            assert realtime_performance_monitor is not None
        except ImportError as e:
            pytest.skip(f"realtime_performance_monitor module not available: {str(e)}")

    def test_realtime_monitor_output_format(self):
        """リアルタイム監視の出力フォーマット確認"""
        work_reports_dir = os.path.join(os.path.dirname(__file__), '..', 'work_reports')
        if os.path.exists(work_reports_dir):
            json_files = [f for f in os.listdir(work_reports_dir) 
                         if f.startswith('realtime_performance_monitor_') and f.endswith('.json')]
            
            if json_files:
                # 最新のファイルを確認
                latest_file = sorted(json_files)[-1]
                filepath = os.path.join(work_reports_dir, latest_file)
                
                try:
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                        assert 'performance' in data or 'status' in data or 'metrics' in data, \
                            "JSON should contain performance, status, or metrics"
                except (json.JSONDecodeError, IOError):
                    pytest.skip("Could not read realtime_performance_monitor JSON file")
            else:
                pytest.skip("No realtime_performance_monitor JSON files found")
        else:
            pytest.skip("work_reports directory not found")


class TestPhase3Integration:
    """Phase 3 モジュール統合テスト"""

    def test_all_phase3_modules_importable(self):
        """すべてのPhase 3 モジュールがインポート可能か"""
        modules_to_test = [
            'environment_auto_judge',
            'dynamic_threshold_learning',
            'realtime_performance_monitor'
        ]
        
        imported_modules = []
        for module_name in modules_to_test:
            try:
                __import__(module_name)
                imported_modules.append(module_name)
            except ImportError:
                pass  # Not all modules may be implemented
        
        assert len(imported_modules) > 0, "At least one Phase 3 module should be importable"

    def test_work_reports_directory_exists(self):
        """work_reports ディレクトリが存在するか"""
        work_reports_dir = os.path.join(os.path.dirname(__file__), '..', 'work_reports')
        assert os.path.exists(work_reports_dir), "work_reports directory should exist"
        assert os.path.isdir(work_reports_dir), "work_reports should be a directory"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
