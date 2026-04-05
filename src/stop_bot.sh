#!/bin/bash

# Bot プロセスを停止するヘルパースクリプト
# 使用方法: ./stop_bot.sh [--config <config_file>]
# 例: ./stop_bot.sh                          # BTC (config.ini)
#     ./stop_bot.sh --config config_xaut.ini  # XAUT

# スクリプトディレクトリを取得
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# スクリプトディレクトリに移動
cd "$SCRIPT_DIR" || exit 1

# --config 引数の解析
CONFIG_FILE="config.ini"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --config)
            CONFIG_FILE="$2"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done

# configからシンボル名を取得
SYMBOL=$(python3 -c "
import configparser
c = configparser.ConfigParser()
c.read('$CONFIG_FILE')
market = c.get('Market', 'market', fallback='BTC/USDT')
print(market.split('/')[0])
")

# configからログディレクトリを取得
LOGS_DIR=$(python3 -c "
import configparser
c = configparser.ConfigParser()
c.read('$CONFIG_FILE')
print(c.get('Log', 'log_directory', fallback='logs'))
")

PID_FILE="$LOGS_DIR/bot_${SYMBOL}.pid"

# PIDファイルの確認
if [ ! -f "$PID_FILE" ]; then
    echo "❌ ${SYMBOL} PIDファイルが見つかりません: $PID_FILE"
    echo "ℹ️  ${SYMBOL} プロセスが起動していない可能性があります"
    exit 1
fi

# PIDを読み込み
bot_pid=$(cat "$PID_FILE")

# プロセスが実行中か確認
if ! kill -0 "$bot_pid" 2>/dev/null; then
    echo "⚠️  ${SYMBOL} PID $bot_pid のプロセスが実行中ではありません"
    rm -f "$PID_FILE"
    exit 1
fi

# プロセスを停止
echo "⏹️  ${SYMBOL} Bot プロセスを停止しています... (PID: $bot_pid)"
kill "$bot_pid"

# プロセス終了を待機（最大5秒）
count=0
while kill -0 "$bot_pid" 2>/dev/null && [ $count -lt 50 ]; do
    sleep 0.1
    count=$((count + 1))
done

# プロセスが終了したか確認
if kill -0 "$bot_pid" 2>/dev/null; then
    echo "⚠️  正常終了できなかったため、強制終了します..."
    kill -9 "$bot_pid"
fi

# PIDファイルを削除
rm -f "$PID_FILE"

echo "✅ ${SYMBOL} Bot プロセスを停止しました"
echo "📝 ログファイルを確認: ls -la $LOGS_DIR/latest_*.log"
