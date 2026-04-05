#!/bin/bash

# backtest_and_visualize_xaut.sh
# XAUT/USDT バックテスト + グラフ生成スクリプト

# ワークスペースルートを取得
WORKSPACE_ROOT="$(cd "$(dirname "$0")" && pwd)"
SRC_DIR="${WORKSPACE_ROOT}/src"
REPORT_DIR="${WORKSPACE_ROOT}/report_xaut"

# ヘルプ表示
show_help() {
    cat << 'EOF'
使用方法: bash backtest_and_visualize_xaut.sh [オプション]

オプション:
  --help, -h       このヘルプを表示
  --backtest-only  バックテストのみ実行（グラフ生成なし）
  --viz-only       グラフ生成のみ実行（バックテストスキップ）
  --quiet          進捗表示を最小限にする

例:
  bash backtest_and_visualize_xaut.sh              # 通常実行（XAUT）
  bash backtest_and_visualize_xaut.sh --backtest-only  # バックテストのみ
  bash backtest_and_visualize_xaut.sh --viz-only       # グラフ生成のみ

注: このスクリプトは config_xaut.ini を使用します（BTC版は backtest_and_visualize.sh）

EOF
}

# オプション解析
BACKTEST_ONLY=0
VIZ_ONLY=0
QUIET=0

while [[ $# -gt 0 ]]; do
    case $1 in
        --help|-h)
            show_help
            exit 0
            ;;
        --backtest-only)
            BACKTEST_ONLY=1
            shift
            ;;
        --viz-only)
            VIZ_ONLY=1
            shift
            ;;
        --quiet)
            QUIET=1
            shift
            ;;
        *)
            echo "❌ 不明なオプション: $1"
            show_help
            exit 1
            ;;
    esac
done

# ディレクトリ確認
if [ ! -d "$SRC_DIR" ]; then
    echo "❌ エラー: src ディレクトリが見つかりません"
    echo "   期待位置: $SRC_DIR"
    exit 1
fi

if [ $QUIET -eq 0 ]; then
    echo "=========================================="
    echo "🚀 XAUT バックテスト実行 + グラフ生成"
    echo "=========================================="
    echo ""
    echo "📂 ワークスペース: $WORKSPACE_ROOT"
    echo "📂 ソースディレクトリ: $SRC_DIR"
    echo "📂 レポート出力先: $REPORT_DIR"
    echo ""
fi

# レポートディレクトリ作成
mkdir -p "$REPORT_DIR"

# Step 1: バックテスト実行
if [ $VIZ_ONLY -eq 0 ]; then
    if [ $QUIET -eq 0 ]; then
        echo "📊 Step 1: XAUT バックテスト実行中..."
        echo "実行中: python3 bot.py --config config_xaut.ini"
        echo ""
    fi

    if [ ! -f "$SRC_DIR/bot.py" ]; then
        echo "❌ エラー: bot.py が見つかりません"
        echo "   期待位置: $SRC_DIR/bot.py"
        exit 1
    fi

    if [ ! -f "$SRC_DIR/config_xaut.ini" ]; then
        echo "❌ エラー: config_xaut.ini が見つかりません"
        echo "   期待位置: $SRC_DIR/config_xaut.ini"
        exit 1
    fi

    # back_test=1 であることを確認（バックテストモード強制）
    if ! grep -q "^back_test.*=.*1" "$SRC_DIR/config_xaut.ini" 2>/dev/null; then
        echo "⚠️  config_xaut.ini の back_test が 1 ではありません。バックテストモードで実行する場合は設定を確認してください。"
    fi

    # bot.py を config_xaut.ini で実行（SRC_DIR から実行）
    cd "$SRC_DIR"
    python3 bot.py --config config_xaut.ini
    EXIT_CODE=$?
    cd "$WORKSPACE_ROOT"

    if [ $EXIT_CODE -ne 0 ]; then
        echo "❌ XAUTバックテストに失敗しました (exit code: $EXIT_CODE)"
        exit $EXIT_CODE
    fi

    if [ $QUIET -eq 0 ]; then
        echo ""
        echo "✅ XAUT バックテスト完了"
        echo ""
    fi
fi

# Step 2: グラフ生成（XAUT）
#   注: visualizer.py は現在 config.ini 固定のため、XAUT用には
#   ログディレクトリを一時切り替えてグラフを生成する
if [ $BACKTEST_ONLY -eq 0 ]; then
    if [ $QUIET -eq 0 ]; then
        echo "📈 Step 2: XAUT グラフ生成中..."
        echo ""
    fi

    cd "$SRC_DIR"
    # XAUT ログから最新のバックテスト結果を確認
    XAUT_LOG_COUNT=$(find logs/xaut -name "*.json" -not -name "latest_status.json" -not -name "trade_log_*.json" 2>/dev/null | wc -l)
    if [ "$XAUT_LOG_COUNT" -gt 0 ]; then
        if [ $QUIET -eq 0 ]; then
            echo "📂 XAUT ログファイル: ${XAUT_LOG_COUNT}件"
            echo "⚠️  visualizer.py は現在 BTC 専用のため、XAUT のグラフ生成はスキップします"
            echo "    バックテスト結果は logs/xaut/ に保存されています"
        fi
    else
        if [ $QUIET -eq 0 ]; then
            echo "⚠️  XAUT ログファイルが見つかりません (logs/xaut/)"
        fi
    fi
    cd "$WORKSPACE_ROOT"

    if [ $QUIET -eq 0 ]; then
        echo ""
        echo "✅ グラフ確認完了"
        echo ""
    fi
fi

# Step 3: HTMLファイルの情報表示
if [ $BACKTEST_ONLY -eq 0 ]; then
    if [ $QUIET -eq 0 ]; then
        echo "🌐 Step 3: ファイル情報"
    fi
    REPORT_FILE="$REPORT_DIR/backtest_visualization.html"
    if [ -f "$REPORT_FILE" ]; then
        if [ $QUIET -eq 0 ]; then
            echo "✅ ファイル生成: $REPORT_FILE"
            echo "📊 ファイルサイズ: $(ls -lh "$REPORT_FILE" | awk '{print $5}')"
            echo ""
            echo "=========================================="
            echo "✨ 完成! (XAUT グラフ)"
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
        fi
    else
        if [ $QUIET -eq 0 ]; then
            echo "⚠️  警告: HTMLファイルが生成されていません"
            echo "   期待位置: $REPORT_FILE"
            echo ""
            echo "📋 ログ出力は正常に完了しました"
            echo "   ログファイル位置: $SRC_DIR/logs/xaut/"
            echo ""
        fi
    fi
fi

if [ $QUIET -eq 0 ]; then
    echo "✅ スクリプト処理完了"
fi

exit 0
