#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PSAR と close_price を同じグラフに表示
バックテスト実行時の値を可視化
"""

import os
import sys
import json
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime

WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_actual_data():
    """バックテスト結果からPSAR値を抽出"""
    
    log_dir = os.path.join(WORKSPACE_ROOT, "src", "logs")
    log_files = sorted(Path(log_dir).glob("*.json"))
    log_files = [f for f in log_files if "backtest_summary" not in f.name]
    
    if not log_files:
        print("[ERROR] ログファイルが見つかりません")
        return None
    
    latest_log = log_files[-1]
    print(f"[INFO] ログファイルを読込: {latest_log.name}")
    
    with open(latest_log, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    return data


def plot_psar_vs_close():
    """PSAR と close_price をグラフに表示"""
    
    print("="*80)
    print("PSAR と Close Price の可視化")
    print("="*80)
    
    # データ取得
    data = load_actual_data()
    if not data:
        return
    
    print(f"\n[INFO] データ件数: {len(data)}")
    
    # データ抽出
    times = []
    close_prices = []
    psars = []
    psarbulls = []
    psarbears = []
    
    for entry in data:
        close_time = entry.get('close_time')
        close_price = entry.get('close_price')
        psar = entry.get('psar')
        psarbull = entry.get('psarbull')
        psarbear = entry.get('psarbear')
        
        if close_time is None or close_price is None:
            continue
        
        # UnixタイムスタンプをDatetimeに変換
        try:
            dt = datetime.fromtimestamp(close_time)
            times.append(dt)
            close_prices.append(close_price)
            psars.append(psar if psar else None)
            psarbulls.append(psarbull if psarbull else None)
            psarbears.append(psarbear if psarbear else None)
        except:
            continue
    
    if not times:
        print("[ERROR] 有効なデータが見つかりません")
        return
    
    print(f"[INFO] グラフ作成中... ({len(times)} 件のデータ)")
    
    # グラフ作成
    fig, ax = plt.subplots(figsize=(16, 8))
    
    # Close Price をプロット
    ax.plot(times, close_prices, label='Close Price', color='blue', linewidth=2, marker='o', markersize=3)
    
    # PSAR をプロット
    ax.plot(times, psars, label='PSAR', color='red', linewidth=1.5, marker='^', markersize=3, alpha=0.7)
    
    # PSARBULLとPSARBEARを分けて表示（オプション）
    # 青いドットはPSARBULL、赤いドットはPSARBEARを表す
    bull_times = [t for t, b in zip(times, psarbulls) if b is not None]
    bull_values = [b for b in psarbulls if b is not None]
    bear_times = [t for t, b in zip(times, psarbears) if b is not None]
    bear_values = [b for b in psarbears if b is not None]
    
    if bull_times:
        ax.scatter(bull_times, bull_values, label='PSAR Bull', color='green', marker='o', s=50, alpha=0.5)
    if bear_times:
        ax.scatter(bear_times, bear_values, label='PSAR Bear', color='orange', marker='o', s=50, alpha=0.5)
    
    # グラフ設定
    ax.set_xlabel('Time', fontsize=12)
    ax.set_ylabel('Price (BTC/USD)', fontsize=12)
    ax.set_title('Close Price vs PSAR (Parabolic SAR)', fontsize=14, fontweight='bold')
    ax.legend(loc='best', fontsize=10)
    ax.grid(True, alpha=0.3)
    
    # X軸の日付フォーマット
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    fig.autofmt_xdate(rotation=45, ha='right')
    
    # 保存
    output_file = os.path.join(WORKSPACE_ROOT, "docs", "psar_vs_close_price.png")
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    plt.tight_layout()
    plt.savefig(output_file, dpi=100, bbox_inches='tight')
    print(f"\n[SUCCESS] グラフを保存: {output_file}")
    
    # 表示
    plt.show()
    
    # 統計情報
    print(f"\n【統計情報】")
    print(f"  Close Price 範囲: {min(close_prices):.2f} - {max(close_prices):.2f}")
    print(f"  PSAR 範囲: {min([p for p in psars if p]):.2f} - {max([p for p in psars if p]):.2f}")
    
    # Close Price > PSAR か Close Price < PSAR かの比較
    above_count = sum(1 for cp, psar in zip(close_prices, psars) if psar and cp > psar)
    below_count = sum(1 for cp, psar in zip(close_prices, psars) if psar and cp < psar)
    equal_count = sum(1 for cp, psar in zip(close_prices, psars) if psar and cp == psar)
    
    print(f"\n【Close Price と PSAR の関係】")
    print(f"  Close > PSAR: {above_count} 件 ({above_count/(above_count+below_count)*100:.1f}%)")
    print(f"  Close < PSAR: {below_count} 件 ({below_count/(above_count+below_count)*100:.1f}%)")
    print(f"  Close = PSAR: {equal_count} 件")
    
    print("="*80)


if __name__ == "__main__":
    plot_psar_vs_close()
