#!/bin/bash
# stop_monitor.sh — BOT監視プロセス停止スクリプト
#
# 使用方法:
#   ./stop_monitor.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

LOGS_DIR="$SCRIPT_DIR/logs"
PID_FILE="$LOGS_DIR/bot_monitor.pid"

if [ ! -f "$PID_FILE" ]; then
    echo "❌ PIDファイルが見つかりません: $PID_FILE"
    echo "ℹ️  BOTモニターが起動していない可能性があります"
    exit 1
fi

MONITOR_PID=$(cat "$PID_FILE")

if ! kill -0 "$MONITOR_PID" 2>/dev/null; then
    echo "⚠️  PID $MONITOR_PID のプロセスが実行中ではありません"
    rm -f "$PID_FILE"
    exit 0
fi

echo "⏹️  BOTモニター停止中 (PID: $MONITOR_PID)..."
kill -TERM "$MONITOR_PID"

# 最大10秒待機
for i in $(seq 1 10); do
    if ! kill -0 "$MONITOR_PID" 2>/dev/null; then
        echo "✅ BOTモニター停止完了"
        rm -f "$PID_FILE"
        exit 0
    fi
    sleep 1
done

echo "⚠️  TERM で停止できないため KILL を送ります..."
kill -KILL "$MONITOR_PID" 2>/dev/null || true
rm -f "$PID_FILE"
echo "✅ BOTモニター強制停止完了"
