#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PSAR と close_price の詳細分析レポート（HTML形式）
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_actual_data():
    """バックテスト結果からPSAR値を抽出"""
    
    log_dir = os.path.join(WORKSPACE_ROOT, "src", "logs")
    log_files = sorted(Path(log_dir).glob("*.json"))
    log_files = [f for f in log_files if "backtest_summary" not in f.name]
    
    if not log_files:
        return None
    
    latest_log = log_files[-1]
    
    with open(latest_log, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    return data


def generate_html_report():
    """HTML形式の詳細レポートを生成"""
    
    print("="*80)
    print("PSAR と Close Price の詳細分析レポート生成中...")
    print("="*80)
    
    # データ取得
    data = load_actual_data()
    if not data:
        print("[ERROR] データが見つかりません")
        return
    
    # 分析データ収集
    rows = []
    close_higher = 0
    close_lower = 0
    
    for i, entry in enumerate(data):
        close_time = entry.get('close_time')
        close_price = entry.get('close_price')
        psar = entry.get('psar')
        psarbull = entry.get('psarbull')
        psarbear = entry.get('psarbear')
        
        if close_time is None or close_price is None:
            continue
        
        # 時刻をフォーマット
        dt = datetime.fromtimestamp(close_time)
        time_str = dt.strftime('%Y-%m-%d %H:%M')
        
        # 関係を判定
        if psar:
            diff = close_price - psar
            relationship = "High" if diff > 0 else "Low"
            if diff > 0:
                close_higher += 1
            else:
                close_lower += 1
        else:
            diff = 0
            relationship = "N/A"
        
        row = {
            'index': i,
            'time': time_str,
            'close_price': close_price,
            'psar': psar if psar else 'N/A',
            'psarbull': psarbull if psarbull else '-',
            'psarbear': psarbear if psarbear else '-',
            'relationship': relationship,
            'diff': diff
        }
        rows.append(row)
    
    # HTML生成
    html_content = f"""
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PSAR vs Close Price 分析レポート</title>
    <style>
        body {{
            font-family: 'Arial', sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        h1, h2 {{
            color: #333;
        }}
        .summary {{
            background-color: #fff;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .stat {{
            display: inline-block;
            margin-right: 30px;
            font-size: 16px;
        }}
        .stat-value {{
            font-weight: bold;
            font-size: 20px;
            color: #0066cc;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background-color: #fff;
            margin-top: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        th {{
            background-color: #0066cc;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: bold;
        }}
        td {{
            padding: 10px 12px;
            border-bottom: 1px solid #ddd;
        }}
        tr:hover {{
            background-color: #f9f9f9;
        }}
        .high {{
            background-color: #e8f4f8;
            color: #006699;
        }}
        .low {{
            background-color: #ffe8e8;
            color: #cc0000;
        }}
        .chart-info {{
            background-color: #fff;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .chart-info img {{
            max-width: 100%;
            height: auto;
        }}
    </style>
</head>
<body>
    <h1>PSAR vs Close Price 分析レポート</h1>
    <p>生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    
    <div class="summary">
        <h2>【サマリー】</h2>
        <div class="stat">
            データ件数: <span class="stat-value">{len(rows)}</span> 件
        </div>
        <div class="stat">
            Close > PSAR: <span class="stat-value" style="color: #0066cc;">{close_higher}</span> 件 ({close_higher/len(rows)*100:.1f}%)
        </div>
        <div class="stat">
            Close < PSAR: <span class="stat-value" style="color: #cc0000;">{close_lower}</span> 件 ({close_lower/len(rows)*100:.1f}%)
        </div>
    </div>
    
    <div class="chart-info">
        <h2>【グラフ】</h2>
        <img src="psar_vs_close_price.png" alt="PSAR vs Close Price Chart">
    </div>
    
    <div>
        <h2>【詳細データ】</h2>
        <table>
            <thead>
                <tr>
                    <th>No.</th>
                    <th>時刻</th>
                    <th>Close Price</th>
                    <th>PSAR</th>
                    <th>PSAR Bull</th>
                    <th>PSAR Bear</th>
                    <th>関係</th>
                    <th>差分 (Close - PSAR)</th>
                </tr>
            </thead>
            <tbody>
"""
    
    # テーブル行を追加
    for row in rows:
        row_class = "high" if row['relationship'] == "High" else "low"
        psar_str = f"{row['psar']:.2f}" if isinstance(row['psar'], (int, float)) else row['psar']
        diff_str = f"{row['diff']:.2f}" if isinstance(row['diff'], (int, float)) else row['diff']
        
        html_content += f"""
                <tr class="{row_class}">
                    <td>{row['index']}</td>
                    <td>{row['time']}</td>
                    <td>{row['close_price']:.2f}</td>
                    <td>{psar_str}</td>
                    <td>{row['psarbull']}</td>
                    <td>{row['psarbear']}</td>
                    <td><strong>{row['relationship']}</strong></td>
                    <td>{diff_str}</td>
                </tr>
"""
    
    html_content += """
            </tbody>
        </table>
    </div>
</body>
</html>
"""
    
    # ファイル保存
    output_file = os.path.join(WORKSPACE_ROOT, "docs", "psar_analysis_report.html")
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print(f"\n[SUCCESS] HTMLレポート生成: {output_file}")
    print("="*80)


if __name__ == "__main__":
    generate_html_report()
