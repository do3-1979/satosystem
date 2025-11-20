#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

LOG="/tmp/phaseA_monthly.log"
{
  echo "==== [$(date '+%F %T')] Phase A monthly batch start ===="
} >> "$LOG"

MONTHS=(
  "2025/04/01 0:00|2025/05/01 0:00|2025-04"
  "2025/05/01 0:00|2025/06/01 0:00|2025-05"
  "2025/06/01 0:00|2025/07/01 0:00|2025-06"
  "2025/07/01 0:00|2025/08/01 0:00|2025-07"
  "2025/08/01 0:00|2025/09/01 0:00|2025-08"
  "2025/09/01 0:00|2025/10/01 0:00|2025-09"
  "2025/10/01 0:00|2025/11/01 0:00|2025-10"
)

report_dir="report/monthly"
mkdir -p "$report_dir"

# Utility: update Period in config.ini
update_period() {
  local start="$1"; local end="$2"
  awk -v s="$start" -v e="$end" '
    BEGIN{inP=0}
    /^\[Period\]/ {print; inP=1; next}
    /^\[/ {print; inP=0; next}
    inP && /^start_time/ {print "start_time = " s; next}
    inP && /^end_time/ {print "end_time = " e; next}
    {print}
  ' config.ini > config.tmp && mv config.tmp config.ini
}

for m in "${MONTHS[@]}"; do
  IFS='|' read -r START END TAG <<< "$m"
  echo "[Phase A] Running $TAG ($START -> $END) ..." | tee -a "$LOG"
  update_period "$START" "$END"
  if [[ -x ./bot_run.sh ]]; then
    ./bot_run.sh > /dev/null 2>&1 || true
  else
    bash ./bot_run.sh > /dev/null 2>&1 || true
  fi
  latest_json=$(ls -t report/backtest_summary_*.json | head -1)
  if [[ -f "$latest_json" ]]; then
    cp "$latest_json" "$report_dir/phaseA_${TAG}.json"
    echo "Saved: $report_dir/phaseA_${TAG}.json" | tee -a "$LOG"
  else
    echo "Warning: summary JSON not found for $TAG" | tee -a "$LOG" >&2
  fi
  sleep 1
done

echo "Phase A monthly batch completed." | tee -a "$LOG"
{
  echo "==== [$(date '+%F %T')] Phase A monthly batch end ===="
} >> "$LOG"
