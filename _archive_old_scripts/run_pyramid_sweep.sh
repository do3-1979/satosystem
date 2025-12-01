#!/bin/bash
# Pyramiding optimization sweep

SRCDIR="src"
SWEEPDIR="output_configs/pyramid_sweep"
REPORTDIR="report/pyramid_sweep"

mkdir -p "$REPORTDIR"

echo "=========================================="
echo "Pyramiding最適化スイープ"
echo "=========================================="

# Generate configs
python src/tools/generate_pyramid_configs.py

# Backup
if [ -f "$SRCDIR/config.ini" ]; then
    cp "$SRCDIR/config.ini" "$SRCDIR/config_pyramid_backup.ini"
fi

count=0
for config in "$SWEEPDIR"/*.ini; do
    count=$((count + 1))
    config_name=$(basename "$config" .ini)
    
    echo "[$count/6] $config_name"
    
    cp "$config" "$SRCDIR/config.ini"
    cd "$SRCDIR"
    ./bot_run.sh >/dev/null 2>&1
    cd ..
    
    latest=$(ls -t "$SRCDIR/report/backtest_summary_"*.json 2>/dev/null | head -1)
    if [ -f "$latest" ]; then
        cp "$latest" "$REPORTDIR/${config_name}_summary.json"
        echo "  → Saved"
    else
        echo "  → Failed"
    fi
    
    # Also copy trend summary
    latest_trend=$(ls -t "$SRCDIR/report/trend_summary_"*.json 2>/dev/null | head -1)
    if [ -f "$latest_trend" ]; then
        cp "$latest_trend" "$REPORTDIR/${config_name}_trend.json"
    fi
done

# Restore
if [ -f "$SRCDIR/config_pyramid_backup.ini" ]; then
    mv "$SRCDIR/config_pyramid_backup.ini" "$SRCDIR/config.ini"
fi

echo "=========================================="
echo "完了"
echo "=========================================="
python src/tools/analyze_pyramid_sweep.py
