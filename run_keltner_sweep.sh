#!/bin/bash
# Keltner parameter sweep runner (fixed version)
# Usage: ./run_keltner_sweep.sh

set -e

SRCDIR="src"
SWEEPDIR="output_configs/keltner_sweep"
REPORTDIR="report/keltner_sweep"

mkdir -p "$REPORTDIR"

echo "=========================================="
echo "Keltnerパラメータスイープ実行"
echo "=========================================="

# Generate sweep configs (idempotent)
python src/tools/generate_keltner_sweep.py

# Backup original config
if [ -f "$SRCDIR/config.ini" ]; then
    cp "$SRCDIR/config.ini" "$SRCDIR/config_sweep_backup.ini"
fi

total_configs=$(ls "$SWEEPDIR"/*.ini 2>/dev/null | wc -l)
current=0

for config in "$SWEEPDIR"/*.ini; do
    current=$((current + 1))
    config_name=$(basename "$config" .ini)

    echo "[$current/$total_configs] Running: $config_name"
    echo "------------------------------------------"

    cp "$config" "$SRCDIR/config.ini"

    pushd "$SRCDIR" >/dev/null
    timeout 90 ./bot_run.sh >/dev/null 2>&1 || true
    popd >/dev/null

    LATEST_SUMMARY=$(ls -t "$SRCDIR/report/backtest_summary_*.json" 2>/dev/null | head -1)
    if [ -n "$LATEST_SUMMARY" ]; then
        cp "$LATEST_SUMMARY" "$REPORTDIR/${config_name}_summary.json"
        echo "✓ Saved: ${config_name}_summary.json"
    else
        echo "✗ Summary missing for $config_name"
    fi

    LATEST_TREND=$(ls -t "$SRCDIR/report/trend_summary_*.json" 2>/dev/null | head -1)
    if [ -n "$LATEST_TREND" ]; then
        cp "$LATEST_TREND" "$REPORTDIR/${config_name}_trend.json"
    fi
done

if [ -f "$SRCDIR/config_sweep_backup.ini" ]; then
    mv "$SRCDIR/config_sweep_backup.ini" "$SRCDIR/config.ini"
fi

echo "=========================================="
echo "Keltnerスイープ完了"
echo "=========================================="
echo "分析レポート生成: python src/tools/analyze_keltner_sweep.py"
