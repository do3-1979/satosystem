#!/bin/bash

# backtest_and_visualize.sh
# bot_run.sh 実行後、自動的にグラフを生成・表示するスクリプト

set -e

cd "$(dirname "$0")/src" || exit 1

echo "=========================================="
echo "🚀 バックテスト実行 + グラフ生成スクリプト"
echo "=========================================="
echo ""

# Step 1: バックテスト実行
echo "📊 Step 1: バックテスト実行中..."
echo "実行中: ./bot_run.sh"
echo ""

if [ ! -f "./bot_run.sh" ]; then
    echo "❌ エラー: bot_run.sh が見つかりません"
    exit 1
fi

bash ./bot_run.sh

echo ""
echo "✅ バックテスト完了"
echo ""

# Step 2: グラフ生成
echo "📈 Step 2: グラフ生成中..."
echo "実行中: python3 visualizer.py True"
echo ""

if ! python3 visualizer.py True; then
    echo "❌ グラフ生成に失敗しました"
    exit 1
fi

echo ""
echo "✅ グラフ生成完了"
echo ""

# Step 3: HTMLファイルの情報表示
echo "🌐 Step 3: ファイル情報"
REPORT_FILE="../report/backtest_visualization.html"
if [ -f "$REPORT_FILE" ]; then
    echo "✅ ファイル生成: $REPORT_FILE"
    echo "📊 ファイルサイズ: $(ls -lh "$REPORT_FILE" | awk '{print $5}')"
    echo ""
    echo "=========================================="
    echo "✨ 完成!"
    echo "=========================================="
    echo ""
    echo "📂 ファイル: $REPORT_FILE"
    echo "🌐 ブラウザで開いてください"
    echo ""
    echo "🎯 確認ポイント:"
    echo "  - ポジション開始・終了のマーカー"
    echo "  - PSAR (パラボリックSAR) の動き"
    echo "  - ストップロス値の推移"
    echo "  - 累積損益 (PnL) の曲線"
    echo ""
else
    echo "❌ エラー: ファイル生成に失敗しました"
    exit 1
fi
