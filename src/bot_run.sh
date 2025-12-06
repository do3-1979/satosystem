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
# レグレッションテスト用: backtest=1ならlogs/latest_backtest.log, backtest=0ならlogs/latest_hot_test.logに出力
# stderr のみをログに出力し、stdout（進捗メッセージなど）は破棄
BOT_SCRIPT="$SCRIPT_DIR/bot.py"
if grep -q '^backtest *= *0' config.ini 2>/dev/null; then
    # ホットテスト
    if [ "$#" -eq 1 ] && [ "$1" == "bg" ]; then
        python "$BOT_SCRIPT" 2> logs/latest_hot_test.log > /dev/null &
    else
        python "$BOT_SCRIPT" 2> logs/latest_hot_test.log > /dev/null
        end_time=$(date +%s)
        total_time=$((end_time - start_time))
        total_hours=$((total_time / 3600))
        total_minutes=$((total_time % 3600 / 60))
        total_seconds=$((total_time % 60))
        echo "実行時間: ${total_hours}h ${total_minutes}m ${total_seconds}s"
    fi
else
    # バックテスト
    if [ "$#" -eq 1 ] && [ "$1" == "bg" ]; then
        python "$BOT_SCRIPT" 2> logs/latest_backtest.log > /dev/null &
    else
        python "$BOT_SCRIPT" 2> logs/latest_backtest.log > /dev/null
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

