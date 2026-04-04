#!/bin/bash
# start_gold_bot.sh - Gold (XAUT/USDT) Bot 起動スクリプト
# 使用方法: ./start_gold_bot.sh [--hot-test | --backtest | --live]

set -e

# スクリプトディレクトリ（src/）に移動
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

CONFIG_FILE="config_xaut.ini"
LOGS_DIR="logs/xaut"
PID_FILE="$LOGS_DIR/bot.pid"

# logsディレクトリ作成
mkdir -p "$LOGS_DIR"

# 設定ファイル存在確認
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ 設定ファイルが見つかりません: $SCRIPT_DIR/$CONFIG_FILE"
    exit 1
fi

# 多重起動チェック
if [ -f "$PID_FILE" ]; then
    existing_pid=$(cat "$PID_FILE")
    if kill -0 "$existing_pid" 2>/dev/null; then
        echo "⚠️  Gold Botはすでに起動中です (PID: $existing_pid)"
        echo "ℹ️  停止する場合: kill \$(cat $PID_FILE)"
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
c.read('$CONFIG_FILE')
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

echo "🥇 Gold Bot (XAUT/USDT) 起動スクリプト"
echo "=========================================="
echo "📁 作業ディレクトリ: $SCRIPT_DIR"
echo "📋 設定ファイル: $CONFIG_FILE"
echo "⚙️  実行モード: $MODE"
echo ""

# 本番モードは確認を求める
if [ "$MODE" = "LIVE" ]; then
    echo "⚠️  警告: 本番取引モードで起動します！(XAUT/USDT)"
    if [ -t 0 ]; then
        read -p "本当に続けますか？ (yes/no): " confirm
        if [ "$confirm" != "yes" ]; then
            echo "❌ 起動をキャンセルしました"
            exit 1
        fi
    else
        echo "ℹ️  非インタラクティブモード: 確認プロンプトをスキップして起動します"
    fi
fi

# ログファイル名（タイムスタンプ付き）
LOG_FILE="$LOGS_DIR/bot_$(date +%Y%m%d_%H%M%S).log"

echo "🚀 Gold Bot を起動します..."
echo "📄 ログファイル: $SCRIPT_DIR/$LOG_FILE"
echo ""

# nohup でバックグラウンド起動（--config で金設定を指定）
nohup python3 -u bot.py --config "$CONFIG_FILE" >> "$LOG_FILE" 2>&1 &
BOT_PID=$!

# PIDファイルに記録
echo "$BOT_PID" > "$PID_FILE"

# 起動確認（3秒待機）
sleep 3
if kill -0 "$BOT_PID" 2>/dev/null; then
    echo "✅ Gold Bot 起動成功 (PID: $BOT_PID)"
    echo ""
    echo "📊 監視コマンド:"
    echo "  ログ確認:     tail -f $SCRIPT_DIR/$LOG_FILE"
    echo "  状態確認:     kill -0 \$(cat $SCRIPT_DIR/$PID_FILE) && echo '稼働中'"
    echo "  停止:         kill \$(cat $SCRIPT_DIR/$PID_FILE) && rm -f $SCRIPT_DIR/$PID_FILE"
else
    echo "❌ Gold Bot の起動に失敗しました"
    echo "ログを確認してください: cat $SCRIPT_DIR/$LOG_FILE"
    rm -f "$PID_FILE"
    exit 1
fi
