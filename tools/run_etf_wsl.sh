#!/bin/bash
# WindowsタスクスケジューラからWSL経由で呼ばれるETF実行スクリプト。
#
# ■なぜWindowsタスクスケジューラなのか
#   ETF版はmoomoo証券のOpenD(ゲートウェイ)が必要だが、OpenDはARM64非対応で
#   RPi(aarch64)では動かない。一方ETFは米国市場のみ・月次リバランスなので
#   24時間稼働は不要で、1日1回動けば足りる。
#   Windowsタスクスケジューラの「ユーザーがログオンしているかに関わらず実行」
#   を使えば、ユーザー切り替えでも実行され、追加費用もかからない。
#
# ■多重起動の防止
#   moomooはClient Order IDに非対応で取引所側が重複を弾かない。
#   「注文照会 → 無ければ発注」の間に別プロセスが割り込むと二重発注に
#   なり得るため、ここでロックを取る。
#
# 使い方(Windows側から):
#   wsl.exe -d Ubuntu-22.04 -- bash -lc '~/work/satosystem-main/tools/run_etf_wsl.sh'

set -u
REPO="${ETF_REPO:-$HOME/work/satosystem-main}"
CONFIG="${ETF_CONFIG:-config/etf.ini}"
LOCK="/tmp/satosystem_etf.lock"
LOG_DIR="$REPO/state"

cd "$REPO" || { echo "リポジトリが見つかりません: $REPO" >&2; exit 1; }
mkdir -p "$LOG_DIR"

# venvがあれば使い、無ければシステムPythonにフォールバック
if [ -x "$REPO/.venv/bin/python3" ]; then
    PY="$REPO/.venv/bin/python3"
else
    PY="$(command -v python3)"
fi

# 多重起動を防ぐ（前の実行が終わっていなければ何もせず抜ける）
exec 9>"$LOCK"
if ! flock -n 9; then
    echo "$(date -Is) 前回の実行が継続中のためスキップ" >> "$LOG_DIR/etf_wsl_cron.log"
    exit 0
fi

{
    echo "----- $(date -Is) 開始 (python=$PY) -----"
    "$PY" run_paper.py --config "$CONFIG"
    rc=$?
    echo "----- $(date -Is) 終了 rc=$rc -----"
    exit $rc
} >> "$LOG_DIR/etf_wsl_cron.log" 2>&1
