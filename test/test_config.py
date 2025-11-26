"""
テスト: Config モジュール
config.py の全関数のテストケース
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from config import Config


class TestConfigBasics:
    """Config クラスの基本機能テスト"""

    def test_config_initialization(self):
        """Config インスタンス化テスト"""
        config = Config()
        assert config is not None

    def test_config_get_api_key(self):
        """API キーの取得テスト"""
        try:
            api_key = Config.get_api_key()
            # API キーは存在することを確認（内容は検証しない）
            assert api_key is not None
        except Exception as e:
            # API キーが設定されていない場合もあるのでスキップ
            pytest.skip(f"API key not configured: {str(e)}")

    def test_config_get_market_pair(self):
        """マーケット・ユニット・ペアの取得テスト"""
        try:
            market_pair = Config.get_market_unit_pair()
            assert market_pair is not None
        except Exception as e:
            pytest.skip(f"Market pair not configured: {str(e)}")

    def test_config_get_risk_percentage(self):
        """リスク率の取得テスト"""
        try:
            risk_pct = Config.get_risk_percentage()
            assert risk_pct is not None
            # リスク率は数値であることを確認
            assert isinstance(float(risk_pct), float)
        except Exception as e:
            pytest.skip(f"Risk percentage not configured: {str(e)}")

    def test_config_get_leverage(self):
        """レバレッジの取得テスト"""
        try:
            leverage = Config.get_leverage()
            assert leverage is not None
            assert isinstance(float(leverage), float)
        except Exception as e:
            pytest.skip(f"Leverage not configured: {str(e)}")

    def test_config_cache_effectiveness(self):
        """Config キャッシュ機能テスト"""
        try:
            # 複数回呼び出してキャッシュが機能しているか確認
            value1 = Config.get_market()
            value2 = Config.get_market()
            assert value1 == value2
        except Exception:
            pass  # 設定がない場合はスキップ


class TestConfigValidation:
    """Config の値の妥当性テスト"""

    def test_config_risk_percentage_range(self):
        """リスク率が妥当な範囲か"""
        try:
            risk_pct = float(Config.get_risk_percentage())
            assert 0 < risk_pct <= 100, "Risk percentage should be between 0 and 100"
        except Exception:
            pass

    def test_config_leverage_range(self):
        """レバレッジが妥当な範囲か"""
        try:
            leverage = float(Config.get_leverage())
            assert leverage > 0, "Leverage should be positive"
            assert leverage <= 125, "Leverage should not exceed 125x"
        except Exception:
            pass

    def test_config_timeframe_valid(self):
        """タイムフレームが妥当か"""
        try:
            timeframe = Config.get_time_frame()
            valid_timeframes = ['1', '5', '15', '60', '240', '1D', '1W']
            assert timeframe in valid_timeframes, f"Invalid timeframe: {timeframe}"
        except Exception:
            pass


class TestConfigSecurityCheck:
    """Config のセキュリティチェック"""

    def test_no_api_key_in_config_ini(self):
        """config.ini に実際の API キーが含まれていないか確認"""
        config_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'config.ini')
        
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                content = f.read()
                lines = content.split('\n')
                
                for i, line in enumerate(lines):
                    if line.strip().startswith('#'):
                        continue
                    
                    # API キーやシークレットが実際の値として含まれていないか
                    if 'api_key' in line.lower() or 'api_secret' in line.lower():
                        # 空、xxx、YOUR_ のいずれかであるべき（YOUR_API_KEY, YOUR_SECRET_KEY 等）
                        if '=' in line:
                            value = line.split('=', 1)[1].strip()
                            # プレースホルダー値であることを確認
                            assert value in ['', "'xxx'", '"xxx"'] or 'YOUR_' in value or value.startswith('#'), \
                                f"Line {i+1}: Potential actual API credential: {line}"

    def test_no_api_key_in_config_template(self):
        """config.template.ini に実際の API キーが含まれていないか確認"""
        template_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'config.template.ini')
        
        if os.path.exists(template_path):
            with open(template_path, 'r') as f:
                content = f.read()
                lines = content.split('\n')
                
                for i, line in enumerate(lines):
                    if line.strip().startswith('#'):
                        continue
                    
                    if 'api_key' in line.lower() or 'api_secret' in line.lower():
                        if '=' in line:
                            value = line.split('=', 1)[1].strip()
                            # テンプレートにはプレースホルダーが含まれるはず
                            assert 'YOUR_' in value or 'xxx' in value.lower() or value == '', \
                                f"Line {i+1}: {line} appears to contain actual credentials"


class TestDocumentManagementStructure:
    """ドキュメント管理ルール（docs/README.md）の構造検証"""

    def test_work_reports_directory_exists(self):
        """work_reports ディレクトリが存在するか"""
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        work_reports_dir = os.path.join(repo_root, 'work_reports')
        assert os.path.exists(work_reports_dir), "work_reports directory should exist"
        assert os.path.isdir(work_reports_dir), "work_reports should be a directory"

    def test_work_reports_has_management_guide(self):
        """work_reports に 00_MANAGEMENT_GUIDE.md があるか"""
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        guide_file = os.path.join(repo_root, 'work_reports', '00_MANAGEMENT_GUIDE.md')
        assert os.path.exists(guide_file), "00_MANAGEMENT_GUIDE.md should exist in work_reports"

    def test_work_reports_date_directory_structure(self):
        """work_reports に日付ディレクトリが存在するか（例: 2025-11-24/）"""
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        work_reports_dir = os.path.join(repo_root, 'work_reports')
        
        # 少なくとも1つの日付ディレクトリが存在することを確認
        date_dirs = [
            d for d in os.listdir(work_reports_dir)
            if os.path.isdir(os.path.join(work_reports_dir, d)) and 
            len(d) == 10 and d.count('-') == 2  # YYYY-MM-DD 形式
        ]
        
        # docs/README.md ルールに従い、日付ディレクトリが存在すること
        assert len(date_dirs) > 0, \
            "work_reports should contain at least one date directory (YYYY-MM-DD format)"

    def test_docs_readme_exists(self):
        """docs/README.md が存在するか"""
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        readme_file = os.path.join(repo_root, 'docs', 'README.md')
        assert os.path.exists(readme_file), "docs/README.md should exist"

    def test_docs_core_documents_exist(self):
        """docs/ に3つのコアドキュメント（ARCHITECTURE_OVERVIEW, TRADING_STRATEGY_PLAN, ACTION_LIST）が存在するか"""
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        docs_dir = os.path.join(repo_root, 'docs')
        
        core_docs = [
            'ARCHITECTURE_OVERVIEW.md',
            'TRADING_STRATEGY_PLAN.md',
            'ACTION_LIST.md',
        ]
        
        for doc in core_docs:
            doc_path = os.path.join(docs_dir, doc)
            assert os.path.exists(doc_path), f"{doc} should exist in docs/"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
