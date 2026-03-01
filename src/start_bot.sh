#!/bin/bash
# start_bot.sh - Bot 起動スクリプト
# 使用方法: ./start_bot.sh [--hot-test | --backtest | --live]

set -e

# スクリプトディレクトリ（src/）に移動
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

LOGS_DIR="logs"
PID_FILE="$LOGS_DIR/bot.pid"

# logsディレクトリ作成
mkdir -p "$LOGS_DIR"

# 多重起動チェック
if [ -f "$PID_FILE" ]; then
    existing_pid=$(cat "$PID_FILE")
    if kill -0 "$existing_pid" 2>/dev/null; then
        echo "⚠️  Botはすでに起動中です (PID: $existing_pid)"
        echo "ℹ️  停止する場合: ./stop_bot.sh"
        exit 1
    else
        echo "⚠️  古いPIDファイルを削除: $PID_FILE"
        rm -f "$PID_FILE"
    fi
fi

# モード確認
MODE=$(python3 -c "
import configparser
c = configparser.ConfigParser()
c.read('config.ini')
bt = c.get('Backtest', 'back_test', fallback='1').strip()
hot = c.get('Backtest', 'hot_test_dummy_mode', fallback='1').strip()
cached = c.get('Backtest', 'use_cached_data_for_hot_test', fallback='0').strip()
if bt == '1':
    print('BACKTEST')
elif hot == '1' and cached == '1':
    print('CACHED_HOT_TEST')
elif hot == '1':
    print('HOT_TEST')
else:
    print('LIVE')
")

echo "🤖 Bot 起動スクリプト"
echo "=========================================="
echo "📁 作業ディレクトリ: $SCRIPT_DIR"
echo "⚙️  実行モード: $MODE"
echo ""

# 本番モードは確認を求める
if [ "$MODE" = "LIVE" ]; then
    echo "⚠️  警告: 本番取引モードで起動します！"
    read -p "本当に続けますか？ (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        echo "❌ 起動をキャンセルしました"
        exit 1
    fi
fi

# ログファイル名（タイムスタンプ付き）
LOG_FILE="$LOGS_DIR/bot_$(date +%Y%m%d_%H%M%S).log"

echo "🚀 Bot を起動します..."
echo "📄 ログファイル: $SCRIPT_DIR/$LOG_FILE"
echo ""

# nohup でバックグラウンド起動
nohup python3 -u bot.py >> "$LOG_FILE" 2>&1 &
BOT_PID=$!

# PIDファイルに記録
echo "$BOT_PID" > "$PID_FILE"

# 起動確認（3秒待機）
sleep 3
if kill -0 "$BOT_PID" 2>/dev/null; then
    echo "✅ Bot 起動成功 (PID: $BOT_PID)"
    echo ""
    echo "📊 監視コマンド:"
    echo "  ログ確認:     tail -f $SCRIPT_DIR/$LOG_FILE"
    echo "  状態確認:     kill -0 \$(cat $SCRIPT_DIR/$PID_FILE) && echo '稼働中'"
    echo "  停止:         $SCRIPT_DIR/stop_bot.sh"
else
    echo "❌ Bot の起動に失敗しました"
    echo "ログを確認してください: cat $SCRIPT_DIR/$LOG_FILE"
    rm -f "$PID_FILE"
    exit 1
fi
