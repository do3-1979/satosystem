#!/bin/bash

# Bot プロセスを停止するヘルパースクリプト

# スクリプトディレクトリを取得
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# スクリプトディレクトリに移動
cd "$SCRIPT_DIR" || exit 1

PID_FILE="logs/bot.pid"

# PIDファイルの確認
if [ ! -f "$PID_FILE" ]; then
    echo "❌ PIDファイルが見つかりません: $PID_FILE"
    echo "ℹ️  プロセスが起動していない可能性があります"
    exit 1
fi

# PIDを読み込み
bot_pid=$(cat "$PID_FILE")

# プロセスが実行中か確認
if ! kill -0 "$bot_pid" 2>/dev/null; then
    echo "⚠️  PID $bot_pid のプロセスが実行中ではありません"
    rm -f "$PID_FILE"
    exit 1
fi

# プロセスを停止
echo "⏹️  Bot プロセスを停止しています... (PID: $bot_pid)"
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

echo "✅ Bot プロセスを停止しました"
echo "📝 ログファイルを確認: ls -la logs/latest_*.log"
