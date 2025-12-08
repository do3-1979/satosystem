#!/bin/bash

# スクリプトディレクトリを取得（シンボリックリンク対応）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# スクリプトディレクトリに移動
cd "$SCRIPT_DIR" || exit 1

# 開始時間の取得
start_time=$(date +%s)

# 引数の確認
if [ "$#" -eq 1 ] && [ "$1" == "clear" ]; then
    # clearが指定された場合、1, 2, 3のファイル削除のみを実行
    echo "ファイルを削除して終了します。"
    # logs ディレクトリ以下の json ファイルと zip ファイルの削除
    find logs -name "*.json" -type f -delete
    find logs -name "*.zip" -type f -delete
    # log.txt の削除
    rm -f log.txt
    # err.log の削除
    rm -f err.log
    exit 0
fi

# 1: logs ディレクトリ以下の json ファイルと zip ファイルの削除
find logs -name "*.json" -type f -delete
find logs -name "*.zip" -type f -delete

# 2: log.txt の削除
rm -f log.txt

# 3: err.log の削除
rm -f err.log

# APIキーとシークレットを置換
./replace_api_key.sh


# 4: python bot.py の実行
# 実行モード判定: back_test と hot_test_dummy_mode の値で分岐
BOT_SCRIPT="$SCRIPT_DIR/bot.py"

# config.ini から設定値を読み込む
back_test=$(grep '^back_test *= *' config.ini | awk -F' *= *' '{print $2}' | tr -d '\n\r')
hot_test_dummy_mode=$(grep '^hot_test_dummy_mode *= *' config.ini | awk -F' *= *' '{print $2}' | tr -d '\n\r')

# デフォルト値設定
back_test=${back_test:-1}
hot_test_dummy_mode=${hot_test_dummy_mode:-1}

# 背景実行フラグ
bg_flag=""
if [ "$#" -eq 1 ] && [ "$1" == "bg" ]; then
    bg_flag=" (background)"
fi

# 実行モード判定
if [ "$back_test" = "1" ]; then
    # バックテストモード
    echo "📊 バックテストモード$bg_flag"
    log_file="logs/latest_backtest.log"
    if [ "$#" -eq 1 ] && [ "$1" == "bg" ]; then
        python "$BOT_SCRIPT" 2> "$log_file" > /dev/null &
    else
        python "$BOT_SCRIPT" 2> "$log_file" > /dev/null
        end_time=$(date +%s)
        total_time=$((end_time - start_time))
        total_hours=$((total_time / 3600))
        total_minutes=$((total_time % 3600 / 60))
        total_seconds=$((total_time % 60))
        echo "実行時間: ${total_hours}h ${total_minutes}m ${total_seconds}s"
    fi
elif [ "$hot_test_dummy_mode" = "1" ]; then
    # ホットテスト（ダミー取引）モード
    echo "🎭 ホットテスト（ペーパートレード）モード$bg_flag"
    log_file="logs/latest_hot_test_dummy.log"
    if [ "$#" -eq 1 ] && [ "$1" == "bg" ]; then
        python "$BOT_SCRIPT" 2> "$log_file" > /dev/null &
    else
        python "$BOT_SCRIPT" 2> "$log_file" > /dev/null
        end_time=$(date +%s)
        total_time=$((end_time - start_time))
        total_hours=$((total_time / 3600))
        total_minutes=$((total_time % 3600 / 60))
        total_seconds=$((total_time % 60))
        echo "実行時間: ${total_hours}h ${total_minutes}m ${total_seconds}s"
    fi
else
    # ホットテスト（本番取引）モード
    echo "🚀 ホットテスト（本番取引）モード$bg_flag"
    log_file="logs/latest_hot_test_live.log"
    echo "⚠️  WARNING: 本番取引モードで実行します。注意してください！"
    read -p "本当に実行しますか？ (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        echo "キャンセルしました。"
        exit 1
    fi
    if [ "$#" -eq 1 ] && [ "$1" == "bg" ]; then
        python "$BOT_SCRIPT" 2> "$log_file" > /dev/null &
    else
        python "$BOT_SCRIPT" 2> "$log_file" > /dev/null
        end_time=$(date +%s)
        total_time=$((end_time - start_time))
        total_hours=$((total_time / 3600))
        total_minutes=$((total_time % 3600 / 60))
        total_seconds=$((total_time % 60))
        echo "実行時間: ${total_hours}h ${total_minutes}m ${total_seconds}s"
    fi
fi

# 実行終了後、APIキーをプレースホルダに戻す
./replace_api_key.sh restore
