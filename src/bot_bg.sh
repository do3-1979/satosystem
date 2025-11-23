#!/usr/bin/env bash
# bot_bg.sh - バックグラウンド実行用スクリプト（bot_run.sh の bg モード代替）
#
# 使い方:
#   ./bot_bg.sh          : バックグラウンド実行、PID表示
#   ./bot_bg.sh wait     : フォアグラウンド実行（完了待機）
#   ./bot_bg.sh stop PID : 指定PIDを停止
#
# 本番運用時のみ使用。バックテストは backtest.py で実行。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

usage() {
    cat <<'USAGE'
Usage: ./bot_bg.sh [command]

Commands:
    (no args)      バックグラウンド実行 (err.log へリダイレクト)
    wait           フォアグラウンド実行 (完了まで待機)
    stop <PID>     指定PIDを停止
    help           このヘルプを表示

注記:
    - 本番環境でのみ使用
    - バックテストは python backtest.py で実行
    - ログは err.log に記録される
USAGE
}

if [[ ${1-} == "help" ]]; then
    usage; exit 0
fi

CMD=${1-bg}

case $CMD in
    bg)
        echo "[INFO] bot.py をバックグラウンド実行開始"
        python bot.py &> err.log &
        PID=$!
        echo "[INFO] Background PID=$PID"
        echo "[INFO] ログは err.log に記録されます"
        echo $PID > .bot_bg.pid
        exit 0
        ;;
    wait)
        echo "[INFO] bot.py をフォアグラウンド実行開始"
        python bot.py
        exit 0
        ;;
    stop)
        PID=${2-}
        if [[ -z "$PID" ]]; then
            if [[ -f .bot_bg.pid ]]; then
                PID=$(cat .bot_bg.pid)
            else
                echo "[ERROR] PIDを指定するか .bot_bg.pid ファイルを確認してください"
                exit 1
            fi
        fi
        echo "[INFO] PID=$PID を停止します"
        kill $PID 2>/dev/null && echo "[INFO] 停止しました" || echo "[ERROR] PID=$PID は見つかりません"
        rm -f .bot_bg.pid
        exit 0
        ;;
    *)
        echo "[ERROR] Unknown command: $CMD"
        usage; exit 1
        ;;
esac
