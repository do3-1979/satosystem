#!/bin/bash
# Simple A/B experiment runner for Keltner and Pyramiding tests
# Usage: ./run_ab_simple.sh

set -e

SRCDIR="src"
OUTDIR="output_configs"
REPORTDIR="report/ab_experiments"

mkdir -p "$REPORTDIR"

echo "=========================================="
echo "A/B実験シンプル実行スクリプト"
echo "=========================================="

# Baseline (10月)を参照データとして使用
BASELINE_SUMMARY="report/backtest_summary_20251121092441.json"
BASELINE_TREND="report/trend_summary_20251121092441.json"

if [ ! -f "$BASELINE_SUMMARY" ]; then
    echo "ベースライン結果が見つかりません: $BASELINE_SUMMARY"
    echo "10月バックテストを先に実行してください"
    exit 1
fi

echo "ベースライン参照: $BASELINE_SUMMARY"

# Experiment 1: Keltner enabled
echo ""
echo "実験1: Keltner有効化テスト"
echo "------------------------------------------"
cp "$OUTDIR/ab_test_keltner_enabled.ini" "$SRCDIR/config.ini"
cd "$SRCDIR"
timeout 120 python bot.py > /dev/null 2>&1 || true
cd ..

# Find latest summary
KELTNER_SUMMARY=$(ls -t "$SRCDIR/report/backtest_summary_*.json" 2>/dev/null | head -1)
if [ -n "$KELTNER_SUMMARY" ]; then
    cp "$KELTNER_SUMMARY" "$REPORTDIR/keltner_enabled_summary.json"
    echo "Keltner有効結果: $REPORTDIR/keltner_enabled_summary.json"
else
    echo "Keltner有効テスト失敗"
fi

# Experiment 2: Pyramiding 3
echo ""
echo "実験2: ピラミッディング=3テスト"
echo "------------------------------------------"
cp "$OUTDIR/ab_test_pyramid_3.ini" "$SRCDIR/config.ini"
cd "$SRCDIR"
timeout 120 python bot.py > /dev/null 2>&1 || true
cd ..

PYRAMID_SUMMARY=$(ls -t "$SRCDIR/report/backtest_summary_*.json" 2>/dev/null | head -1)
if [ -n "$PYRAMID_SUMMARY" ]; then
    cp "$PYRAMID_SUMMARY" "$REPORTDIR/pyramid_3_summary.json"
    echo "Pyramid=3結果: $REPORTDIR/pyramid_3_summary.json"
else
    echo "Pyramid=3テスト失敗"
fi

echo ""
echo "=========================================="
echo "A/B実験完了"
echo "=========================================="
echo "比較レポート生成:"
echo "  python src/tools/compare_ab_results.py"
