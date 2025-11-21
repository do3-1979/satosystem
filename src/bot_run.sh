#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

START_TS=$(date +%s)
DATE_TAG=$(date +%Y%m%d_%H%M%S)
REPORT_DIR="report"

usage() {
    cat <<'USAGE'
Usage: ./bot_run.sh [command]

Commands:
    run           通常実行 (前処理→bot.py→後処理)
    bg            バックグラウンド実行 (& err.logへリダイレクト)
    clear         古い一時ログ(json/zip/log.txt/err.log)削除のみ
    help          このヘルプを表示

特徴:
    - APIキー自動注入/復元 (replace_api_key.sh)
    - 前処理で古いjson/zipを掃除し結果混在防止
    - 実行後 summary を最新ファイル名とともに表示
    - trend_trades 未生成検出時は警告

推奨フロー:
    1) config.ini 編集 (期間/パラメータ)
    2) ./bot_run.sh run
    3) report/*summary*.json / trend_trades_*.json / pnl_timeseries_*.json 確認
    4) 分類再グリッド: python tools/reclassify_trades_grid.py --input report/<trend_trades_file> --output report/classification_grid_results.json

再発防止策:
    - 直接 python bot.py を使うと API キー復元/ログ掃除/後処理が抜けるため禁止 (wrapper経由で統一)
USAGE
}

if [[ ${1-} == "help" ]]; then
    usage; exit 0
fi

if [[ ${1-} == "clear" ]]; then
    echo "[CLEAN] 清掃のみ実行" >&2
    find logs -name "*.json" -type f -delete || true
    find logs -name "*.zip"  -type f -delete || true
    rm -f log.txt err.log || true
    exit 0
fi

# 直接 bot.py 実行へのガード (対話シェル環境で検出困難だが alias 提案用メッセージ)
if [[ ${1-} == "python" || ${1-} == "bot.py" ]]; then
    echo "[ERROR] Use ./bot_run.sh run で実行してください" >&2
    exit 1
fi

CMD=${1-run}

echo "[START] bot_run.sh mode=$CMD at $DATE_TAG"

echo "[PRE] 古いログ/成果物の軽量掃除";
find logs -name "*.json" -type f -delete || true
find logs -name "*.zip"  -type f -delete || true
rm -f log.txt err.log || true

echo "[PRE] APIキー注入";
./replace_api_key.sh

run_bot() {
    python bot.py
}

if [[ $CMD == "bg" ]]; then
    echo "[RUN] 背景実行開始";
    run_bot &> err.log &
    PID=$!
    echo "[RUN] Background PID=$PID (err.log 監視)";
    exit 0
elif [[ $CMD == "run" ]]; then
    echo "[RUN] 通常実行"
    run_bot
else
    echo "[ERROR] Unknown command: $CMD" >&2
    usage; exit 1
fi

END_TS=$(date +%s)
ELAPSED=$((END_TS-START_TS))
H=$((ELAPSED/3600)); M=$(((ELAPSED%3600)/60)); S=$((ELAPSED%60))

echo "[POST] APIキー復元"; ./replace_api_key.sh restore || true

latest_summary=$(ls -t report/backtest_summary_*.json 2>/dev/null | head -1 || true)
latest_trades=$(ls -t report/trend_trades_*.json 2>/dev/null | head -1 || true)
latest_pnl=$(ls -t report/pnl_timeseries_*.json 2>/dev/null | head -1 || true)

echo "[DONE] 実行時間: ${H}h ${M}m ${S}s"
echo "[DONE] Summary: ${latest_summary:-<none>}"
echo "[DONE] Trades : ${latest_trades:-<none>}"
echo "[DONE] PnL Ts : ${latest_pnl:-<none>}"

if [[ -z "$latest_trades" ]]; then
    echo "[WARN] trend_trades_* が生成されていません。EOB記録 or EXIT ロジック要確認。" >&2
fi

echo "[NEXT] 分類再グリッド例:" >&2
echo "python tools/reclassify_trades_grid.py --input ${latest_trades:-report/trend_trades_<timestamp>.json} --output report/classification_grid_results.json" >&2

exit 0

