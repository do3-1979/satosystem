#!/usr/bin/env python3
"""
config.ini 管理の改善版

問題点:
1. backtest.py実行時にコメントが削除される
2. 実行後にAPIキーが残ったままになる
3. config_bak.ini との同期が取れない
4. 手動でconfig.iniを復元する手間

解決策:
1. テンプレートファイル (config.template.ini) を作成・管理
2. backtest.py 実行時は temp_config.ini を使用
3. APIキーは環境変数 or .api_key から直接読み込む
4. 実行後は自動的にクリーンアップ
"""

import os
import shutil
from pathlib import Path


class ConfigManager:
    """config.ini を安全に管理するクラス"""
    
    # パス設定
    CONFIG_TEMPLATE = "config.template.ini"
    CONFIG_MAIN = "config.ini"
    CONFIG_BACKUP = "config_bak.ini"
    CONFIG_TEMP = "config_temp.ini"
    
    @staticmethod
    def create_template():
        """
        config.template.ini を作成
        - コメント保持
        - APIキーはプレースホルダ
        """
        template_content = """# Bitcoin 自動取引ボット設定ファイル
# 本ファイルは config.template.ini です
# backtest実行時は自動的に config_temp.ini がこれをベースに生成されます

[API]
# APIキーはバックテスト実行時に自動注入されます
# 本番環境では .api_key ファイルから読み込まれます
api_key = YOUR_API_KEY
api_secret = YOUR_API_SECRET

[RiskManagement]
# リスク管理パラメータ
risk_percentage = 0.03          # 1取引あたりのリスク率 (3%)
account_balance = 300           # 初期資本 (USD)
leverage = 1                    # レバレッジ倍率
entry_times = 3                 # 最大エントリー回数
entry_range = 2                 # エントリー追加レンジ (USD)
stop_range = 2                  # ストップロス幅 (USD)
stop_AF = 0.02                  # SAR初期加速度
stop_AF_add = 0.02              # SAR加速度増加分
stop_AF_max = 0.20              # SAR最大加速度
surge_follow_price_ratio = 0.011  # サージフォロー比率
psar_time_frame = 120           # PSAR時間足 (分)

[Market]
# 取引対象市場
market = BTC/USD                # 通貨ペア
time_frame = 120                # 取引時間足 (分)

[Period]
# バックテスト期間
start_time = 2024/01/01 0:00    # 開始時刻
end_time = 2024/12/31 23:59     # 終了時刻

[Strategy]
# 戦略パラメータ
volatility_term = 14            # ボラティリティ計算期間
donchian_buy_term = 20          # Donchian買いシグナル期間
donchian_sell_term = 20         # Donchian売りシグナル期間
keltner_ema_period = 20         # Keltner EMA期間
keltner_atr_multiplier = 2.0    # Keltner ATR乗数
keltner_enabled = False         # Keltnerフィルタ有効化
pvo_s_term = 12                 # PVO短期EMA
pvo_l_term = 26                 # PVO長期EMA
pvo_threshold = 0               # PVO閾値

[Potfolio]
# ポートフォリオ管理
lot_limit_lower = 0.0001        # 最小ロット数
balance_tether_limit = 0        # テザー残高上限

[Setting]
# 一般設定
server_retry_wait = 120         # サーバ再試行待機時間 (秒)
bot_operation_cycle = 60        # ボット動作サイクル (秒)
run_timeout_seconds = 300       # 実行タイムアウト (秒)
api_request_timeout_seconds = 20  # API要求タイムアウト
api_max_retry_seconds = 120     # API最大再試行時間

[Log]
# ログ設定
log_file = log.txt              # ログファイル名
log_directory = logs            # ログディレクトリ
report_directory = report       # レポートディレクトリ
logging_interval = 10000        # ロギング間隔

[Backtest]
# バックテスト設定
back_test = 1                   # バックテストモード (1=有効, 0=無効)

# 注記: 本ファイルはテンプレートです
# 個別の期間・パラメータ設定は output_configs/ に置いてください
"""
        return template_content
    
    @staticmethod
    def create_working_config(template_content, api_key, api_secret):
        """
        テンプレートをベースに実行用config_temp.iniを作成
        
        Args:
            template_content: テンプレート内容
            api_key: APIキー
            api_secret: APIシークレット
        """
        working_config = template_content.replace(
            "api_key = YOUR_API_KEY",
            f"api_key = {api_key}"
        ).replace(
            "api_secret = YOUR_API_SECRET",
            f"api_secret = {api_secret}"
        )
        return working_config
    
    @staticmethod
    def init_config_files(src_dir="."):
        """
        初期化: config.template.ini と config.ini を整備
        
        Args:
            src_dir: ファイルを配置するディレクトリ
        """
        template_path = os.path.join(src_dir, ConfigManager.CONFIG_TEMPLATE)
        config_path = os.path.join(src_dir, ConfigManager.CONFIG_MAIN)
        
        # テンプレートが存在しないなら作成
        if not os.path.exists(template_path):
            template_content = ConfigManager.create_template()
            with open(template_path, 'w', encoding='utf-8') as f:
                f.write(template_content)
            print(f"✅ Created {ConfigManager.CONFIG_TEMPLATE}")
        
        # config.ini が存在しないなら、テンプレートをコピー
        if not os.path.exists(config_path):
            shutil.copy(template_path, config_path)
            print(f"✅ Created {ConfigManager.CONFIG_MAIN} from template")
        else:
            print(f"ℹ️  {ConfigManager.CONFIG_MAIN} already exists")
    
    @staticmethod
    def prepare_for_backtest(output_config_file, api_key, api_secret, src_dir="."):
        """
        バックテスト実行前に config_temp.ini を準備
        
        Args:
            output_config_file: output_configs/ からのconfig ファイル
            api_key: APIキー
            api_secret: APIシークレット
            src_dir: 作業ディレクトリ
        """
        template_path = os.path.join(src_dir, ConfigManager.CONFIG_TEMPLATE)
        temp_path = os.path.join(src_dir, ConfigManager.CONFIG_TEMP)
        
        # テンプレートを読み込む
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()
        
        # 出力configの設定値を抽出・マージ
        with open(output_config_file, 'r', encoding='utf-8') as f:
            output_content = f.read()
        
        # テンプレートをベースに、出力configの値を上書き
        working_config = ConfigManager.merge_configs(template_content, output_content)
        
        # APIキーを注入
        working_config = ConfigManager.create_working_config(
            working_config, api_key, api_secret
        )
        
        # config_temp.ini に書き込む
        with open(temp_path, 'w', encoding='utf-8') as f:
            f.write(working_config)
        
        return temp_path
    
    @staticmethod
    def merge_configs(template, output_config):
        """
        テンプレートと出力configをマージ
        テンプレートのコメント構造を保持しながら、
        出力configの値で上書き
        
        Args:
            template: テンプレート内容
            output_config: 出力config内容
        """
        import configparser
        
        # パーサーで値を抽出
        output_parser = configparser.ConfigParser()
        output_parser.read_string(output_config)
        
        # テンプレート行を処理
        lines = template.split('\n')
        result_lines = []
        
        for line in lines:
            # セクション行はそのまま
            if line.strip().startswith('['):
                result_lines.append(line)
            # コメント行はそのまま
            elif line.strip().startswith('#') or line.strip() == '':
                result_lines.append(line)
            # キー=値 行を処理
            elif '=' in line and not line.strip().startswith('#'):
                key, _ = line.split('=', 1)
                key = key.strip()
                
                # 現在のセクションを特定
                current_section = None
                for i in range(len(result_lines)-1, -1, -1):
                    if result_lines[i].strip().startswith('['):
                        current_section = result_lines[i].strip()[1:-1]
                        break
                
                # 出力configに該当キーがあれば値を取得
                if current_section and output_parser.has_option(current_section, key):
                    new_value = output_parser.get(current_section, key)
                    result_lines.append(f"{key} = {new_value}")
                else:
                    result_lines.append(line)
            else:
                result_lines.append(line)
        
        return '\n'.join(result_lines)
    
    @staticmethod
    def cleanup_temp_configs(src_dir="."):
        """
        実行後のクリーンアップ
        - config_temp.ini を削除
        - config.ini が実際の値を持つなら、テンプレートに戻す
        
        Args:
            src_dir: 作業ディレクトリ
        """
        temp_path = os.path.join(src_dir, ConfigManager.CONFIG_TEMP)
        config_path = os.path.join(src_dir, ConfigManager.CONFIG_MAIN)
        template_path = os.path.join(src_dir, ConfigManager.CONFIG_TEMPLATE)
        
        # 一時ファイルを削除
        if os.path.exists(temp_path):
            os.remove(temp_path)
            print(f"✅ Cleaned up {ConfigManager.CONFIG_TEMP}")
        
        # config.ini をテンプレートに戻す
        if os.path.exists(config_path) and os.path.exists(template_path):
            shutil.copy(template_path, config_path)
            print(f"✅ Restored {ConfigManager.CONFIG_MAIN} from template")


if __name__ == "__main__":
    # 初期化テスト
    print("=== ConfigManager 初期化テスト ===\n")
    
    ConfigManager.init_config_files(".")
    
    print("\n=== テンプレート作成テスト ===\n")
    
    # テンプレートを表示（最初の30行）
    template = ConfigManager.create_template()
    lines = template.split('\n')[:30]
    for line in lines:
        print(line)
    
    print("\n... (以下省略)")
