#!/bin/bash

# OHLCVキャッシュ検査ツール ラッパースクリプト
# 
# 使用方法:
#   ./ohlcv_cache_info.sh                    # サマリーを表示
#   ./ohlcv_cache_info.sh summary            # サマリーを表示
#   ./ohlcv_cache_info.sh coverage           # データ範囲と断絶を表示
#   ./ohlcv_cache_info.sh all                # 詳細分析をすべて表示

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_CMD="/bin/python"
SRC_DIR="$SCRIPT_DIR/src"

# デフォルトは summary
COMMAND="${1:-summary}"

case "$COMMAND" in
    summary)
        echo "📊 キャッシュサマリーを表示します..."
        cd "$SRC_DIR" && $PYTHON_CMD ohlcv_cache_inspector.py --summary
        ;;
    coverage)
        echo "📈 データ範囲と断絶を表示します..."
        cd "$SRC_DIR" && $PYTHON_CMD ohlcv_cache_inspector.py --coverage
        ;;
    all)
        echo "🔬 詳細分析をすべて表示します..."
        cd "$SRC_DIR" && $PYTHON_CMD ohlcv_cache_inspector.py --all
        ;;
    help)
        echo "OHLCVキャッシュ検査ツール"
        echo ""
        echo "使用方法:"
        echo "  $0                  - キャッシュサマリーを表示（デフォルト）"
        echo "  $0 summary          - キャッシュサマリーを表示"
        echo "  $0 coverage         - データ範囲と断絶を表示"
        echo "  $0 all              - 詳細分析をすべて表示"
        echo "  $0 help             - このヘルプを表示"
        ;;
    *)
        echo "❌ 不正なコマンド: $COMMAND"
        echo ""
        $0 help
        exit 1
        ;;
esac
