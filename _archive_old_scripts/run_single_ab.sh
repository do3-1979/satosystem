#!/bin/bash
# A/B実験: 単一実験実行スクリプト
# Usage: ./run_single_ab.sh <config_name>
# Example: ./run_single_ab.sh ab_test_keltner_enabled

set -e

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <config_name>"
    echo "Example: $0 ab_test_keltner_enabled"
    exit 1
fi

CONFIG_NAME="$1"
SRCDIR="src"
OUTDIR="output_configs"
REPORTDIR="report/ab_experiments"

mkdir -p "$REPORTDIR"

CONFIG_PATH="$OUTDIR/${CONFIG_NAME}.ini"

if [ ! -f "$CONFIG_PATH" ]; then
    echo "Error: Config not found: $CONFIG_PATH"
    exit 1
fi

echo "=========================================="
echo "実験実行: $CONFIG_NAME"
echo "=========================================="

# Backup current config
if [ -f "$SRCDIR/config.ini" ]; then
    cp "$SRCDIR/config.ini" "$SRCDIR/config_backup_ab.ini"
fi

# Copy experiment config
cp "$CONFIG_PATH" "$SRCDIR/config.ini"

# Run backtest using bot_run.sh
cd "$SRCDIR"
./bot_run.sh

# Find latest summary
LATEST_SUMMARY=$(ls -t report/backtest_summary_*.json 2>/dev/null | head -1)
if [ -n "$LATEST_SUMMARY" ]; then
    cp "$LATEST_SUMMARY" "../$REPORTDIR/${CONFIG_NAME}_summary.json"
    echo "結果保存: $REPORTDIR/${CONFIG_NAME}_summary.json"
else
    echo "Error: No summary file found"
fi

# Also copy trend summary if exists
LATEST_TREND=$(ls -t report/trend_summary_*.json 2>/dev/null | head -1)
if [ -n "$LATEST_TREND" ]; then
    cp "$LATEST_TREND" "../$REPORTDIR/${CONFIG_NAME}_trend.json"
    echo "トレンドサマリ保存: $REPORTDIR/${CONFIG_NAME}_trend.json"
fi

cd ..

# Restore backup
if [ -f "$SRCDIR/config_backup_ab.ini" ]; then
    cp "$SRCDIR/config_backup_ab.ini" "$SRCDIR/config.ini"
    rm "$SRCDIR/config_backup_ab.ini"
fi

echo "=========================================="
echo "実験完了: $CONFIG_NAME"
echo "=========================================="
