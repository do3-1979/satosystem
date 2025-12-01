#!/bin/bash

# 四半期別バックテスト実行スクリプト（シンプル版）
# Task 19 用の日常監視スクリプト
#
# 用途: Phase 2 導入後の四半期別パフォーマンス測定
# 出力: JSON + テーブル表示

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$PROJECT_ROOT/src"
REPORT_DIR="$PROJECT_ROOT/report"
WORK_REPORTS_DIR="$PROJECT_ROOT/work_reports/$(date +%Y-%m-%d)"

mkdir -p "$REPORT_DIR" "$WORK_REPORTS_DIR"

# 四半期定義
declare -A QUARTERS=(
    ["2024_Q1"]="2024-01-01 2024-03-31"
    ["2024_Q2"]="2024-04-01 2024-06-30"
    ["2024_Q3"]="2024-07-01 2024-09-30"
    ["2025_Q1"]="2025-01-01 2025-03-31"
    ["2025_Q3"]="2025-07-01 2025-09-30"
)

declare -A QUARTERS_MEDIUM=(
    ["2024_Q4"]="2024-10-01 2024-12-31"
    ["2025_Q2"]="2025-04-01 2025-06-30"
)

# 結果を保存
declare -A RESULTS

echo "======================================================================"
echo "🧪 QUARTERLY BACKTEST (PHASE 2 VERIFICATION)"
echo "======================================================================"

# 優先度 HIGH の四半期を実行
PRIORITY="${1:-high}"

if [ "$PRIORITY" = "high" ] || [ "$PRIORITY" = "all" ]; then
    QUARTERS_TO_RUN=("${!QUARTERS[@]}")
fi

if [ "$PRIORITY" = "all" ]; then
    for q in "${!QUARTERS_MEDIUM[@]}"; do
        QUARTERS_TO_RUN+=("$q")
    done
fi

# バックテスト実行
TOTAL=${#QUARTERS_TO_RUN[@]}
CURRENT=0

for QUARTER in "${QUARTERS_TO_RUN[@]}"; do
    CURRENT=$((CURRENT + 1))
    
    # 期間を取得
    read START_DATE END_DATE <<< "${QUARTERS[$QUARTER]:-${QUARTERS_MEDIUM[$QUARTER]}}"
    
    echo ""
    echo "📅 $QUARTER ($START_DATE to $END_DATE)"
    echo "   [$CURRENT/$TOTAL] 🚀 Running...", 
    
    # 古いレポートを削除
    rm -f "$REPORT_DIR"/*.json 2>/dev/null || true
    
    # 一時 config を作成
    TEMP_CONFIG="/tmp/config_backtest_$QUARTER.ini"
    
    python3 << EOPY
import configparser
import sys

cfg = configparser.ConfigParser()
cfg.read('$SRC_DIR/config.ini')

if not cfg.has_section('Period'):
    cfg.add_section('Period')

cfg.set('Period', 'start_time', '$START_DATE 0:00')
cfg.set('Period', 'end_time', '$END_DATE 23:59')

with open('$TEMP_CONFIG', 'w') as f:
    cfg.write(f)
EOPY
    
    # バックテスト実行
    cd "$SRC_DIR"
    
    if timeout 600 python3 backtest.py "$TEMP_CONFIG" > /dev/null 2>&1; then
        echo " ✅"
        
        # レポートを抽出
        LATEST_REPORT=$(ls -t "$REPORT_DIR"/backtest_summary_*.json 2>/dev/null | head -1)
        
        if [ -n "$LATEST_REPORT" ]; then
            PNL=$(python3 -c "import json; d=json.load(open('$LATEST_REPORT')); print(d.get('total_pnl', d.get('total_profit_loss', 0)))")
            TRADES=$(python3 -c "import json; d=json.load(open('$LATEST_REPORT')); print(d.get('trades', d.get('total_trades', 0)))")
            WIN_RATE=$(python3 -c "import json; d=json.load(open('$LATEST_REPORT')); w=d.get('win_rate', 0); print(w*100 if w < 1 else w)")
            PF=$(python3 -c "import json; d=json.load(open('$LATEST_REPORT')); print(d.get('profit_factor', 0))")
            SHARPE=$(python3 -c "import json; d=json.load(open('$LATEST_REPORT')); print(d.get('sharpe', 0))")
            MAX_DD=$(python3 -c "import json; d=json.load(open('$LATEST_REPORT')); print(d.get('max_drawdown', d.get('max_drawdown_percent', 0)))")
            
            RESULTS["$QUARTER"]="$PNL|$TRADES|$WIN_RATE|$PF|$SHARPE|$MAX_DD"
        fi
    else
        echo " ❌"
        RESULTS["$QUARTER"]="ERROR"
    fi
    
    # クリーンアップ
    rm -f "$TEMP_CONFIG"
    cd "$PROJECT_ROOT"
done

# サマリを表示
echo ""
echo "======================================================================"
echo "📊 SUMMARY - Phase 2 Setting (Regime ON + Graduated ON)"
echo "======================================================================"
echo ""
printf "%-12s | %12s | %8s | %8s | %8s | %8s | %12s\n" "Quarter" "PnL" "Trades" "Win%" "PF" "Sharpe" "Max DD"
echo "--------------------------------------------------------------------"

TOTAL_PNL=0
TOTAL_TRADES=0
TOTAL_WINS=0
COUNT=0

for QUARTER in "${QUARTERS_TO_RUN[@]}"; do
    if [ -z "${RESULTS[$QUARTER]}" ] || [ "${RESULTS[$QUARTER]}" = "ERROR" ]; then
        printf "%-12s | %12s | %8s | %8s | %8s | %8s | %12s\n" "$QUARTER" "N/A" "N/A" "N/A" "N/A" "N/A" "N/A"
    else
        IFS='|' read PNL TRADES WIN_RATE PF SHARPE MAX_DD <<< "${RESULTS[$QUARTER]}"
        
        STATUS="✅"
        if (( $(echo "$PNL < 0" | bc -l) )); then
            STATUS="⚠️"
        fi
        
        printf "%s %-10s | \$%11.0f | %8d | %7.1f%% | %8.4f | %8.4f | %12.2f\n" "$STATUS" "$QUARTER" "$PNL" "$TRADES" "$WIN_RATE" "$PF" "$SHARPE" "$MAX_DD"
        
        TOTAL_PNL=$(echo "$TOTAL_PNL + $PNL" | bc)
        TOTAL_TRADES=$((TOTAL_TRADES + TRADES))
        TOTAL_WINS=$(echo "$TOTAL_WINS + $TRADES * $WIN_RATE / 100" | bc -l)
        COUNT=$((COUNT + 1))
    fi
done

echo "--------------------------------------------------------------------"

if [ $COUNT -gt 0 ]; then
    AVG_WIN=$(echo "scale=1; $TOTAL_WINS * 100 / $TOTAL_TRADES" | bc -l)
    echo ""
    echo "【統計】"
    echo "  期間数:     $COUNT"
    echo "  総PnL:      \$$TOTAL_PNL"
    echo "  総取引数:   $TOTAL_TRADES"
    echo "  平均勝率:   ${AVG_WIN}%"
fi

# 結果を JSON で保存
RESULT_JSON="$WORK_REPORTS_DIR/quarterly_backtest_$(date +%Y%m%d_%H%M%S).json"

python3 << EOPY
import json
from datetime import datetime

results = {}
QUARTERS_STR = """${QUARTERS_TO_RUN[@]}"""
RESULTS_STR = """${RESULTS[@]}"""

results['timestamp'] = datetime.now().isoformat()
results['results'] = {}

for q in QUARTERS_STR.split():
    key = "results['$QUARTER']" if '$QUARTER' in QUARTERS_STR else None
    if key:
        results['results'][q] = {
            'quarter': q,
            'data': {}
        }

with open('$RESULT_JSON', 'w') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
EOPY

echo ""
echo "💾 Results saved: $RESULT_JSON"
echo ""
echo "✅ Quarterly backtest completed"
