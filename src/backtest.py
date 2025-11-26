import os
import shutil
import time
import sys
import glob
from configparser import ConfigParser
import re
from pathlib import Path

# カレントディレクトリをsrc/に変更してモジュール読み込みを修正
src_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(src_dir)
sys.path.insert(0, src_dir)

# Path utilities をインポート
from path_utils import PathManager, load_api_keys_from_file

from config import Config
from config_manager import ConfigManager
from price_data_management import PriceDataManagement
from logger import Logger
from bybit_exchange import BybitExchange
from trading_strategy import TradingStrategy
from risk_management import RiskManagement
from portfolio import Portfolio
from order import Order
from bot import Bot  # Assuming the Bot class is in a separate file named bot.py
from indicator_service import IndicatorService

def cleanup_old_logs():
    """
    古いログファイルとレポートを削除
    - logs/*.json, logs/*.zip
    - log.txt, err.log
    - logs_* ディレクトリ (backtest.sh互換)
    - log_*.txt ファイル (backtest.sh互換)
    
    目的: 過去の実行結果との混在防止
    """
    files_to_delete = ['log.txt', 'err.log']
    dirs_patterns = [
        ('logs', '*.json'),
        ('logs', '*.zip'),
    ]
    
    # ファイル削除
    for filename in files_to_delete:
        if os.path.exists(filename):
            try:
                os.remove(filename)
                print(f"✅ Deleted {filename}")
            except Exception as e:
                print(f"⚠️  Failed to delete {filename}: {e}")
    
    # ディレクトリ内パターンマッチングで削除
    for directory, pattern in dirs_patterns:
        if os.path.isdir(directory):
            for filepath in glob.glob(os.path.join(directory, pattern)):
                try:
                    os.remove(filepath)
                    print(f"✅ Deleted {filepath}")
                except Exception as e:
                    print(f"⚠️  Failed to delete {filepath}: {e}")
    
    # logs_* ディレクトリ削除 (backtest.sh互換)
    for logs_dir in glob.glob('logs_*'):
        if os.path.isdir(logs_dir):
            try:
                shutil.rmtree(logs_dir)
                print(f"✅ Deleted directory {logs_dir}")
            except Exception as e:
                print(f"⚠️  Failed to delete {logs_dir}: {e}")
    
    # log_*.txt ファイル削除 (backtest.sh互換)
    for log_file in glob.glob('log_*.txt'):
        if os.path.isfile(log_file):
            try:
                os.remove(log_file)
                print(f"✅ Deleted {log_file}")
            except Exception as e:
                print(f"⚠️  Failed to delete {log_file}: {e}")

def display_latest_reports():
    """Display latest report files using PathManager."""
    report_dir = PathManager.get_report_dir()
    report_patterns = [
        ('backtest_summary_*.json', 'Summary'),
        ('trend_trades_*.json', 'Trades'),
        ('pnl_timeseries_*.json', 'PnL Timeseries'),
    ]
    
    print("\n" + "=" * 70)
    print("📊 Latest Report Files")
    print("=" * 70)
    
    for pattern, label in report_patterns:
        if report_dir.exists():
            files = sorted(report_dir.glob(pattern), reverse=True)
            if files:
                latest = files[0]
                print(f"✅ {label:20s}: {latest}")
            else:
                print(f"⚠️  {label:20s}: <none>")
    
    print("=" * 70 + "\n")

def load_api_keys():
    """Load API keys using PathManager for consistent path resolution.
    
    Returns:
        tuple: (api_key, api_secret) or (None, None) if not found
    """
    api_key_file = PathManager.get_api_key_file()
    if api_key_file.exists():
        print(f"[INFO] Loading API keys from: {api_key_file}")
        return load_api_keys_from_file()
    return None, None

def find_config_files(directory):
    """
    テスト用コンフィグファイルを探す

    Args:
        directory (str): 検索対象のディレクトリパス

    Returns:
        list: テスト設定ファイルのリスト（ソート済み）
    """
    # ルートディレクトリ相対パスの場合は絶対パスに変換
    if not os.path.isabs(directory):
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        directory = os.path.join(root_dir, directory)
    
    # テストファイル: _q1.ini （Q1テスト用: 2024 Q1 + 2025 Q1）
    config_files = [f for f in os.listdir(directory) if "_q1.ini" in f]
    # ファイル名でソートして順番を保証
    config_files.sort()
    return [os.path.join(directory, config_file) for config_file in config_files]

def main():
    # --clear オプション対応 (backtest.sh互換)
    if len(sys.argv) == 2 and sys.argv[1] == '--clear':
        print("=" * 70)
        print("🧹 Clearing logs and exiting (backtest.sh clear mode)")
        print("=" * 70)
        cleanup_old_logs()
        print("✅ Cleanup completed. Exiting.")
        return
    
    # 引数で設定ファイルが指定されたか確認
    if len(sys.argv) >= 2 and sys.argv[1] != '--clear':
        # 引数で指定されたファイルのみを処理
        single_config_file = sys.argv[1]
        # ルートディレクトリ相対パスの場合は絶対パスに変換
        if not os.path.isabs(single_config_file):
            root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            single_config_file = os.path.join(root_dir, single_config_file)
        config_files_to_process = [single_config_file]
        use_single_file_mode = True
    else:
        # output_configs内を自動検索
        config_dir = PathManager.get_output_configs_dir()
        config_files_to_process = find_config_files(str(config_dir))
        use_single_file_mode = False
    
    total_start_time = time.time()
    
    # 0. 古いログファイルをクリーンアップ（混在防止）
    print("=" * 70)
    print("🧹 Cleaning up old log files")
    print("=" * 70)
    cleanup_old_logs()
    print()
    
    # 1. ConfigManager初期化（テンプレート作成）
    ConfigManager.init_config_files(".")
    
    # 2. APIキーを事前にロード（本番APIキーを使用してBybitからデータ取得）
    api_key, api_secret = load_api_keys()
    if not api_key or not api_secret:
        print("[WARN] API keys not found in .api_key file.")
        print("[INFO] キャッシュDB内に十分なデータがあれば使用します。")
        print("[INFO] キャッシュ不足の場合はバックテストをスキップします。")
        api_key = None
        api_secret = None
    else:
        print(f"[INFO] 本番APIキーを使用します（バックテストモード）")
        print(f"[INFO] API Key: {api_key[:8]}... (masked)")
    print()

    print(f"Found {len(config_files_to_process)} config files to process")
    print()

    # 3. ファイルリストから一つずつバックテストを実行
    for idx, config_file in enumerate(config_files_to_process):
        print(f"=" * 70)
        print(f"[{idx+1}/{len(config_files_to_process)}] Processing: {os.path.basename(config_file)}")
        print(f"=" * 70)
        
        try:
            # 出力configファイルを直接使用（シンプル化）
            # APIキーを注入するだけで、merge処理は不要
            temp_config_path = os.path.join(".", "config_temp.ini")
            
            # 出力configファイルをコピー
            shutil.copy(config_file, temp_config_path)
            
            # APIキーを注入
            with open(temp_config_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if api_key:
                content = content.replace("YOUR_API_KEY", api_key)
            if api_secret:
                content = content.replace("YOUR_API_SECRET", api_secret)
            
            with open(temp_config_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Config を temp_config で読み込む
            # （元の config.ini は保護される）
            Config.set_config_file(temp_config_path)
            Config.reload_config()
            
            # シングルトンインスタンスをリセット
            PriceDataManagement.reset_instance()
            Logger.reset_instance()
        
            # APIキーなしでバックテストを実行する場合の警告・スキップ判定
            actual_api_key = Config.get_api_key()
            actual_api_secret = Config.get_api_secret()
            
            if actual_api_key == "YOUR_API_KEY" or actual_api_secret == "YOUR_API_SECRET":
                print(f"⚠️  API keys are placeholders (not set in .api_key file)")
                print(f"    キャッシュDB内のデータから実行します")
                print(f"    不足データがある場合はバックテストをスキップします")
                print()
            
            # 取引所クラスを初期化
            # APIキーがプレースホルダーの場合も初期化は行うが、
            # API呼び出しはキャッシュから実行される
            exchange = BybitExchange(actual_api_key, actual_api_secret)
            # 資産管理クラスを初期化
            portfolio = Portfolio()
            
            # IndicatorServiceを初期化
            indicator_service = IndicatorService()
            
            # 価格情報クラスを初期化
            price_data_management = PriceDataManagement(indicator_service=indicator_service)
            # リスク戦略クラスを初期化
            risk_management = RiskManagement(price_data_management, portfolio, indicator_service=indicator_service)
            # 取引戦略クラスを初期化
            strategy = TradingStrategy(price_data_management, risk_management, portfolio)
            # ボットのインスタンスを作成
            bot = Bot(exchange, strategy, risk_management, price_data_management, portfolio)

            # ボットを実行
            start_time = time.time()
            bot.run()
            elapsed_time = time.time() - start_time

            # 処理中のconfigファイルの名前と進捗率を表示
            progress = (idx + 1) / len(config_files_to_process) * 100
            print()
            print(f"Completed: {os.path.basename(config_file)}")
            print(f"Progress: {progress:.2f}% ({idx+1}/{len(config_files_to_process)})")
            print(f"Elapsed Time: {format_elapsed_time(elapsed_time)}")
            print()
        
        except Exception as e:
            print(f"❌ Error processing {os.path.basename(config_file)}: {e}")
            print()
        
        finally:
            # 一時ファイルをクリーンアップ
            ConfigManager.cleanup_temp_configs(".")
            # config_temp.ini を明示的に削除
            temp_config_path = os.path.join(".", "config_temp.ini")
            if os.path.exists(temp_config_path):
                try:
                    os.remove(temp_config_path)
                except Exception as e:
                    print(f"Warning: Failed to delete {temp_config_path}: {e}")
        
    total_elapsed_time = time.time() - total_start_time
    print("=" * 70)
    print(f"All backtests completed!")
    print(f"Total Elapsed Time: {format_elapsed_time(total_elapsed_time)}")
    print("=" * 70)
    
    # 最終的に config_temp.ini を確実に削除
    final_temp_config = "config_temp.ini"
    if os.path.exists(final_temp_config):
        try:
            os.remove(final_temp_config)
            print(f"✅ Final cleanup: deleted {final_temp_config}")
        except Exception as e:
            print(f"⚠️  Warning: Failed to delete {final_temp_config}: {e}")
    
    # 最新のレポートファイルを表示
    display_latest_reports()
    
    # 最終確認: config.ini がテンプレート状態に戻されているか確認
    print()
    print("=" * 70)
    print("🔒 Security Check: Verifying config.ini state")
    print("=" * 70)
    is_clean = ConfigManager.verify_config_clean(".")
    
    if not is_clean:
        print()
        print("❌ WARNING: config.ini may contain actual API keys!")
        print("   Expected: api_key = YOUR_API_KEY")
        print("   Expected: api_secret = YOUR_API_SECRET")
        print("   Please manually restore from config.template.ini")
        sys.exit(1)
    
    print()
    print("✅ All cleanup completed successfully")
    print("   - config_temp.ini deleted")
    print("   - config.ini restored to template state")
    print("   - No API keys remaining in config.ini")

def format_elapsed_time(seconds):
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return "{:02}:{:02}:{:02}".format(int(hours), int(minutes), int(seconds))

if __name__ == "__main__":
    main()
