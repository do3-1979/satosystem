#!/bin/bash
# Keltner parameter sweep runner (debug version with verbose output)

set -e

SRCDIR="src"
SWEEPDIR="output_configs/keltner_sweep"
REPORTDIR="report/keltner_sweep"

mkdir -p "$REPORTDIR"

echo "=========================================="
echo "Keltnerパラメータスイープ実行 (修正版)"
echo "=========================================="

# Backup original config
if [ -f "$SRCDIR/config.ini" ]; then
    cp "$SRCDIR/config.ini" "$SRCDIR/config_sweep_backup.ini"
    echo "Config backed up"
fi

total_configs=$(ls "$SWEEPDIR"/*.ini 2>/dev/null | wc -l)
current=0
success_count=0

for config in "$SWEEPDIR"/*.ini; do
    current=$((current + 1))
    config_name=$(basename "$config" .ini)

    echo ""
    echo "[$current/$total_configs] Running: $config_name"
    echo "------------------------------------------"

    # Copy config
    cp "$config" "$SRCDIR/config.ini"
    
    # Run backtest (bot_run.sh clears logs but keeps reports)
    cd "$SRCDIR"
    if timeout 90 ./bot_run.sh >/dev/null 2>&1; then
        echo "  Backtest completed"
    else
        echo "  Backtest timed out or failed"
    fi
    cd ..

    # Find and copy latest summary (with verification)
    LATEST_SUMMARY=$(ls -t "$SRCDIR/report/backtest_summary_*.json" 2>/dev/null | head -1)
    if [ -n "$LATEST_SUMMARY" ] && [ -f "$LATEST_SUMMARY" ]; then
        cp "$LATEST_SUMMARY" "$REPORTDIR/${config_name}_summary.json"
        if [ -f "$REPORTDIR/${config_name}_summary.json" ]; then
            echo "  ✓ Summary saved: ${config_name}_summary.json"
            success_count=$((success_count + 1))
        else
            echo "  ✗ Failed to copy summary"
        fi
    else
        echo "  ✗ No summary generated"
    fi

    # Copy trend summary if exists
    LATEST_TREND=$(ls -t "$SRCDIR/report/trend_summary_*.json" 2>/dev/null | head -1)
    if [ -n "$LATEST_TREND" ] && [ -f "$LATEST_TREND" ]; then
        cp "$LATEST_TREND" "$REPORTDIR/${config_name}_trend.json"
    fi
done

# Restore backup
if [ -f "$SRCDIR/config_sweep_backup.ini" ]; then
    mv "$SRCDIR/config_sweep_backup.ini" "$SRCDIR/config.ini"
    echo "Config restored"
fi

echo ""
echo "=========================================="
echo "Keltnerスイープ完了"
echo "成功: $success_count / $total_configs"
echo "=========================================="

if [ $success_count -gt 0 ]; then
    echo "分析実行: python src/tools/analyze_keltner_sweep.py"
    python src/tools/analyze_keltner_sweep.py
else
    echo "結果ファイルが生成されませんでした"
fi
