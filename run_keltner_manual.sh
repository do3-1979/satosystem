#!/bin/bash
# Keltner sweep simplified - run one config at a time manually

SRCDIR="src"
SWEEPDIR="output_configs/keltner_sweep"
REPORTDIR="report/keltner_sweep"

mkdir -p "$REPORTDIR"

echo "=========================================="
echo "Keltnerスイープ: 手動実行版"
echo "=========================================="

# Backup
if [ -f "$SRCDIR/config.ini" ]; then
    cp "$SRCDIR/config.ini" "$SRCDIR/config_original.ini"
fi

count=0
for config in "$SWEEPDIR"/*.ini; do
    count=$((count + 1))
    config_name=$(basename "$config" .ini)
    
    echo "[$count/12] $config_name"
    
    # Copy and run
    cp "$config" "$SRCDIR/config.ini"
    cd "$SRCDIR"
    ./bot_run.sh >/dev/null 2>&1
    cd ..
    
    # Copy most recent summary
    latest=$(ls -t "$SRCDIR/report/backtest_summary_"*.json 2>/dev/null | head -1)
    if [ -f "$latest" ]; then
        cp "$latest" "$REPORTDIR/${config_name}_summary.json"
        echo "  → Saved"
    else
        echo "  → Failed"
    fi
done

# Restore
if [ -f "$SRCDIR/config_original.ini" ]; then
    mv "$SRCDIR/config_original.ini" "$SRCDIR/config.ini"
fi

echo "完了"
python src/tools/analyze_keltner_sweep.py
