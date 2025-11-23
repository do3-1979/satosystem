import os
import shutil
import time
import sys
import glob
from configparser import ConfigParser
import re
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
    """
    実行後の最新レポートファイルを表示
    """
    report_patterns = [
        ('report', 'backtest_summary_*.json', 'Summary'),
        ('report', 'trend_trades_*.json', 'Trades'),
        ('report', 'pnl_timeseries_*.json', 'PnL Timeseries'),
    ]
    
    print("\n" + "=" * 70)
    print("📊 Latest Report Files")
    print("=" * 70)
    
    for directory, pattern, label in report_patterns:
        if os.path.isdir(directory):
            files = sorted(glob.glob(os.path.join(directory, pattern)), reverse=True)
            if files:
                latest = files[0]
                print(f"✅ {label:20s}: {latest}")
            else:
                print(f"⚠️  {label:20s}: <none>")
    
    print("=" * 70 + "\n")

def load_api_keys():
    """
    .api_keyファイルからAPIキーとシークレットを読み込む
    
    Returns:
        tuple: (api_key, api_secret)
    """
    api_key = None
    api_secret = None
    
    api_key_file = ".api_key"
    if os.path.exists(api_key_file):
        with open(api_key_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('api_key'):
                    api_key = line.split('=', 1)[1].strip()
                elif line.startswith('api_secret'):
                    api_secret = line.split('=', 1)[1].strip()
    
    return api_key, api_secret

def find_config_files(directory):
    """
    指定したディレクトリ内のconfig_*.ini ファイルのリストを取得します。

    Args:
        directory (str): 検索対象のディレクトリパス

    Returns:
        list: config_*.ini ファイルのリスト（ソート済み）
    """
    config_files = [f for f in os.listdir(directory) if f.startswith("config_") and f.endswith(".ini")]
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
    
    total_start_time = time.time()
    
    # 0. 古いログファイルをクリーンアップ（混在防止）
    print("=" * 70)
    print("🧹 Cleaning up old log files")
    print("=" * 70)
    cleanup_old_logs()
    print()
    
    # 1. ConfigManager初期化（テンプレート作成）
    ConfigManager.init_config_files(".")
    
    # 1. APIキーを事前にロード
    api_key, api_secret = load_api_keys()
    if not api_key or not api_secret:
        print("Error: API keys not found in .api_key file")
        return
    
    print(f"Loaded API keys from .api_key")
    print(f"API Key: {api_key[:8]}... (masked)")
    print()

    # 2. output_configs以下のconfig_*.ini ファイルからファイルリストを作成
    config_files = find_config_files("output_configs")
    print(f"Found {len(config_files)} config files to process")
    print()

    # 3. ファイルリストから一つずつバックテストを実行
    for idx, config_file in enumerate(config_files):
        print(f"=" * 70)
        print(f"[{idx+1}/{len(config_files)}] Processing: {os.path.basename(config_file)}")
        print(f"=" * 70)
        
        try:
            # 一時的なconfig_temp.iniを準備
            temp_config_path = ConfigManager.prepare_for_backtest(
                config_file, api_key, api_secret, "."
            )
            
            # Config を temp_config で読み込む
            # （元の config.ini は保護される）
            Config.set_config_file(temp_config_path)
            Config.reload_config()
            
            # シングルトンインスタンスをリセット
            PriceDataManagement.reset_instance()
            Logger.reset_instance()
        
            # 取引所クラスを初期化
            exchange = BybitExchange(Config.get_api_key(), Config.get_api_secret())
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
            progress = (idx + 1) / len(config_files) * 100
            print()
            print(f"Completed: {os.path.basename(config_file)}")
            print(f"Progress: {progress:.2f}% ({idx+1}/{len(config_files)})")
            print(f"Elapsed Time: {format_elapsed_time(elapsed_time)}")
            print()
        
        except Exception as e:
            print(f"❌ Error processing {os.path.basename(config_file)}: {e}")
            print()
        
        finally:
            # 一時ファイルをクリーンアップ
            ConfigManager.cleanup_temp_configs(".")
        
    total_elapsed_time = time.time() - total_start_time
    print("=" * 70)
    print(f"All backtests completed!")
    print(f"Total Elapsed Time: {format_elapsed_time(total_elapsed_time)}")
    print("=" * 70)
    
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
