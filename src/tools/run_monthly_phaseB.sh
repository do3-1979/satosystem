#!/usr/bin/env bash
set -e
cd "$(dirname "$0")/.."

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
  echo "[Phase B] Running $TAG ($START -> $END) ..."
  update_period "$START" "$END"
  ./bot_run.sh > /dev/null 2>&1 || true
  latest_json=$(ls -t report/backtest_summary_*.json | head -1)
  if [[ -f "$latest_json" ]]; then
    cp "$latest_json" "$report_dir/phaseB_${TAG}.json"
    echo "Saved: $report_dir/phaseB_${TAG}.json"
  else
    echo "Warning: summary JSON not found for $TAG" >&2
  fi
  sleep 1
done

echo "Phase B monthly batch completed."
