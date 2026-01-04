#!/bin/bash

# loss_trade_analysis_pipeline.sh
# トレード分析の完全なパイプラインを実行

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=================================================="
echo "🔍 損失トレード分析パイプライン"
echo "=================================================="

# Step 1: ディレクトリ確認
echo ""
echo "📁 ディレクトリ構造確認..."
mkdir -p "$PROJECT_DIR/analysis"

# Step 2: トレード抽出
echo ""
echo "📖 Step 1: ログからトレードを抽出中..."
python3 "$SCRIPT_DIR/trade_extractor.py"

if [ ! -f "$PROJECT_DIR/analysis/trades_with_metadata.csv" ]; then
    echo "✗ トレード抽出に失敗しました"
    exit 1
fi

# Step 3: トレード分析
echo ""
echo "🔍 Step 2: トレード分析中..."
python3 "$SCRIPT_DIR/trade_analyzer.py"

# Step 4: 結果サマリー
echo ""
echo "📊 Step 3: 分析結果をサマリー中..."

CSV_FILE="$PROJECT_DIR/analysis/trades_with_metadata.csv"

if [ -f "$CSV_FILE" ]; then
    echo ""
    echo "📋 抽出結果:"
    wc -l < "$CSV_FILE" | xargs echo "  トレード数:"
    
    # CSV の簡単な統計
    python3 << 'EOF'
import pandas as pd
import sys

csv_file = sys.argv[1]
df = pd.read_csv(csv_file)

print(f"\n📈 統計情報:")
print(f"  総トレード数: {len(df)}")
print(f"  勝ちトレード: {len(df[df['pnl_usd'] > 0])}")
print(f"  負けトレード: {len(df[df['pnl_usd'] < 0])}")
print(f"  勝率: {len(df[df['pnl_usd'] > 0]) / len(df) * 100:.1f}%")
print(f"  総利益: {df['pnl_usd'].sum():.2f} USD")

if len(df[df['pnl_usd'] < 0]) > 0:
    print(f"\n⚠️  損失トレード分析:")
    lose_df = df[df['pnl_usd'] < 0]
    print(f"  負けトレード総数: {len(lose_df)}")
    print(f"  平均損失: {lose_df['pnl_usd'].mean():.2f} USD")
    print(f"  最大損失: {lose_df['pnl_usd'].min():.2f} USD")
    print(f"  平均ドローダウン: {lose_df['max_drawdown_pct'].mean():.2f}%")
EOF
    
python3 -c "
import pandas as pd
csv_file = '$CSV_FILE'
df = pd.read_csv(csv_file)

print(f'\n📈 統計情報:')
print(f'  総トレード数: {len(df)}')
print(f'  勝ちトレード: {len(df[df[\"pnl_usd\"] > 0])}')
print(f'  負けトレード: {len(df[df[\"pnl_usd\"] < 0])}')
print(f'  勝率: {len(df[df[\"pnl_usd\"] > 0]) / len(df) * 100:.1f}%')
print(f'  総利益: {df[\"pnl_usd\"].sum():.2f} USD')

if len(df[df['pnl_usd'] < 0]) > 0:
    print(f'\n⚠️  損失トレード分析:')
    lose_df = df[df['pnl_usd'] < 0]
    print(f'  負けトレード総数: {len(lose_df)}')
    print(f'  平均損失: {lose_df[\"pnl_usd\"].mean():.2f} USD')
    print(f'  最大損失: {lose_df[\"pnl_usd\"].min():.2f} USD')
    print(f'  平均ドローダウン: {lose_df[\"max_drawdown_pct\"].mean():.2f}%')
"
fi

echo ""
echo "=================================================="
echo "✅ 分析完了！"
echo "=================================================="
echo ""
echo "📁 出力ファイル:"
echo "  • analysis/trades_with_metadata.csv - トレード詳細データ"
echo "  • analysis/trades_with_metadata.json - トレード詳細データ (JSON)"
echo "  • analysis/causality_matrix.csv - 因果関係マトリックス"
echo "  • analysis/loss_trade_analysis_report.html - 分析レポート"
echo ""
echo "🔍 次のステップ:"
echo "  1. HTML レポートを確認"
echo "  2. 因果関係マトリックスから相関を分析"
echo "  3. 改善案をテストして、バックテストで検証"
echo ""
