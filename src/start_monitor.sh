#!/bin/bash
# start_monitor.sh — BOT監視プロセス起動スクリプト
#
# 使用方法:
#   ./start_monitor.sh
#   ./start_monitor.sh --config /path/to/.gmail

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

# --config 引数の解析
CONFIG_ARG=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --config)
            CONFIG_ARG="--config $2"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done

LOGS_DIR="$SCRIPT_DIR/logs"
PID_FILE="$LOGS_DIR/bot_monitor.pid"
LOG_FILE="$LOGS_DIR/bot_monitor.log"

# logsディレクトリ作成
mkdir -p "$LOGS_DIR"

# 多重起動チェック
if [ -f "$PID_FILE" ]; then
    existing_pid=$(cat "$PID_FILE")
    if kill -0 "$existing_pid" 2>/dev/null; then
        echo "⚠️  BOTモニターはすでに起動中です (PID: $existing_pid)"
        echo "ℹ️  停止する場合: ./stop_monitor.sh"
        exit 1
    else
        echo "⚠️  古いPIDファイルを削除: $PID_FILE"
        rm -f "$PID_FILE"
    fi
fi

# 起動
echo "🚀 BOTモニター起動中..."
nohup python3 "$SCRIPT_DIR/bot_monitor.py" $CONFIG_ARG >> "$LOG_FILE" 2>&1 &

MONITOR_PID=$!
sleep 1

if kill -0 "$MONITOR_PID" 2>/dev/null; then
    echo "✅ BOTモニター起動成功 (PID: $MONITOR_PID)"
    echo "ℹ️  ログ: $LOG_FILE"
    echo "ℹ️  停止: ./stop_monitor.sh"
else
    echo "❌ BOTモニター起動失敗。ログを確認してください: $LOG_FILE"
    exit 1
fi
