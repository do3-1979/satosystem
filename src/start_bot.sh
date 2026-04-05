#!/bin/bash
# start_bot.sh - Bot 起動スクリプト
# 使用方法: ./start_bot.sh [--config <config_file>]
# 例: ./start_bot.sh                          # BTC (config.ini)
#     ./start_bot.sh --config config_xaut.ini  # XAUT

set -e

# スクリプトディレクトリ（src/）に移動
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

# --config 引数の解析
CONFIG_FILE="config.ini"
CONFIG_ARG=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --config)
            CONFIG_FILE="$2"
            CONFIG_ARG="--config $2"
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

# logsディレクトリ作成
mkdir -p "$LOGS_DIR"

# 多重起動チェック
if [ -f "$PID_FILE" ]; then
    existing_pid=$(cat "$PID_FILE")
    if kill -0 "$existing_pid" 2>/dev/null; then
        echo "⚠️  ${SYMBOL} Botはすでに起動中です (PID: $existing_pid)"
        echo "ℹ️  停止する場合: ./stop_bot.sh --config $CONFIG_FILE"
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

echo "🤖 ${SYMBOL} Bot 起動スクリプト"
echo "=========================================="
echo "📁 作業ディレクトリ: $SCRIPT_DIR"
echo "📋 設定ファイル: $CONFIG_FILE"
echo "💱 シンボル: $SYMBOL"
echo "⚙️  実行モード: $MODE"
echo ""

# 本番モードは確認を求める（非インタラクティブ時はスキップ）
if [ "$MODE" = "LIVE" ]; then
    echo "⚠️  警告: ${SYMBOL} 本番取引モードで起動します！"
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
LOG_FILE="$LOGS_DIR/bot_${SYMBOL}_$(date +%Y%m%d_%H%M%S).log"

echo "🚀 ${SYMBOL} Bot を起動します..."
echo "📄 ログファイル: $SCRIPT_DIR/$LOG_FILE"
echo ""

# nohup でバックグラウンド起動
nohup python3 -u bot.py $CONFIG_ARG >> "$LOG_FILE" 2>&1 &
BOT_PID=$!

# PIDファイルに記録
echo "$BOT_PID" > "$PID_FILE"

# 起動確認（3秒待機）
sleep 3
if kill -0 "$BOT_PID" 2>/dev/null; then
    echo "✅ ${SYMBOL} Bot 起動成功 (PID: $BOT_PID)"
    echo ""
    echo "📊 監視コマンド:"
    echo "  ログ確認:     tail -f $SCRIPT_DIR/$LOG_FILE"
    echo "  状態確認:     kill -0 \$(cat $SCRIPT_DIR/$PID_FILE) && echo '稼働中'"
    echo "  停止:         $SCRIPT_DIR/stop_bot.sh --config $CONFIG_FILE"
else
    echo "❌ ${SYMBOL} Bot の起動に失敗しました"
    echo "ログを確認してください: cat $SCRIPT_DIR/$LOG_FILE"
    rm -f "$PID_FILE"
    exit 1
fi
