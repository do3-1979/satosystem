import os
import shutil
import time
import sys
from configparser import ConfigParser
import re
from config import Config
from price_data_management import PriceDataManagement
from logger import Logger
from bybit_exchange import BybitExchange
from trading_strategy import TradingStrategy
from risk_management import RiskManagement
from portfolio import Portfolio
from order import Order
from bot import Bot  # Assuming the Bot class is in a separate file named bot.py
from indicator_service import IndicatorService

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

def inject_api_keys(config_file, api_key, api_secret):
    """コメント保持したままAPIキー行のみ置換するテキスト注入方式。

    1. [API] セクション探索。
    2. api_key= / api_secret= 行を正規表現で置換。
    3. 未存在なら [API] セクション末尾に追記。
    """
    with open(config_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    api_section_start = None
    api_section_end = None
    for i, line in enumerate(lines):
        if re.match(r'\[API\]\s*', line):
            api_section_start = i
            # 探索範囲後続で別セクションが来るまで
            for j in range(i+1, len(lines)):
                if re.match(r'^\[.+\]', lines[j]):
                    api_section_end = j
                    break
            if api_section_end is None:
                api_section_end = len(lines)
            break

    if api_section_start is None:
        # セクションが無ければ末尾に生成
        lines.append('\n[API]\n')
        lines.append(f'api_key = {api_key}\n')
        lines.append(f'api_secret = {api_secret}\n')
    else:
        # 既存行を置換/追加
        found_key = False
        found_secret = False
        for k in range(api_section_start+1, api_section_end):
            if re.match(r'\s*api_key\s*=.*', lines[k]):
                lines[k] = f'api_key = {api_key}\n'
                found_key = True
            elif re.match(r'\s*api_secret\s*=.*', lines[k]):
                lines[k] = f'api_secret = {api_secret}\n'
                found_secret = True
        # ない場合末尾に追加
        insert_pos = api_section_end
        if not found_key:
            lines.insert(insert_pos, f'api_key = {api_key}\n')
            insert_pos += 1
        if not found_secret:
            lines.insert(insert_pos, f'api_secret = {api_secret}\n')

    with open(config_file, 'w', encoding='utf-8') as f:
        f.writelines(lines)

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
    total_start_time = time.time()
    
    # 0. APIキーを事前にロード
    api_key, api_secret = load_api_keys()
    if not api_key or not api_secret:
        print("Error: API keys not found in .api_key file")
        return
    
    print(f"Loaded API keys from .api_key")
    print(f"API Key: {api_key[:8]}... (masked)")
    print()

    # 1. バックアップとしてconfig.iniをconfig_bak.iniにリネームする
    if os.path.exists("config.ini"):
        shutil.copy("config.ini", "config_bak.ini")
        print("Backed up config.ini to config_bak.ini")

    # 2. output_configs以下のconfig_*.ini ファイルからファイルリストを作成
    config_files = find_config_files("output_configs")
    print(f"Found {len(config_files)} config files to process")
    print()

    # 3. ファイルリストから一つずつconfig.iniにコピーしてbot.pyを実行する
    for idx, config_file in enumerate(config_files):
        print(f"=" * 70)
        print(f"[{idx+1}/{len(config_files)}] Processing: {os.path.basename(config_file)}")
        print(f"=" * 70)
        
        # コピーしてconfig.iniに変更
        shutil.copy(config_file, "config.ini")
    
        # APIキーを直接注入（スクリプト実行は不要）
        inject_api_keys("config.ini", api_key, api_secret)
        
        # Configクラスのキャッシュをクリアして新しい設定を読み込む
        Config.reload_config()
        
        # シングルトンインスタンスをリセット（新しい期間データを取得するため）
        PriceDataManagement.reset_instance()
        Logger.reset_instance()
    
        # 取引所クラスを初期化
        exchange = BybitExchange(Config.get_api_key(), Config.get_api_secret())
        # 資産管理クラスを初期化（唯一であること TODO シングルトン化）
        portfolio = Portfolio()
        
        # IndicatorServiceを初期化（PriceDataManagementとRiskManagementで共有）
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
        
    total_elapsed_time = time.time() - total_start_time
    print("=" * 70)
    print(f"All backtests completed!")
    print(f"Total Elapsed Time: {format_elapsed_time(total_elapsed_time)}")
    print("=" * 70)

    # 4. バックアップしたconfig_bak.iniをconfig.iniに戻す(config.iniに上書きして戻す)
    if os.path.exists("config_bak.ini"):
        shutil.move("config_bak.ini", "config.ini")
        print("Restored config.ini from backup")

def format_elapsed_time(seconds):
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return "{:02}:{:02}:{:02}".format(int(hours), int(minutes), int(seconds))

if __name__ == "__main__":
    main()
