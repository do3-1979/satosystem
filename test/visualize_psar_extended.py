#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
拡張PSAR初期化後の結果を可視化
ログファイルから PSAR と close_price を抽出してグラフ化
"""

import json
import re
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.dates import DateFormatter
import numpy as np

# ログファイルからデータ抽出
log_file = "/home/satoshi/work/satosystem/src/logs/latest_backtest.log"

data = {
    'datetime': [],
    'close': [],
    'stop': [],
    'high': [],
    'low': []
}

with open(log_file, 'r', encoding='utf-8') as f:
    for line in f:
        # ログパターン: 時刻: 2025/10/10 09:00  高値: 121902  安値: 121483  終値: 121659  購入価格:     0  STOP:    0
        match = re.search(r'時刻: (\d{4}/\d{2}/\d{2} \d{2}:\d{2}).*高値:\s+(\d+)\s+安値:\s+(\d+)\s+終値:\s+(\d+).*STOP:\s+(\d+)', line)
        if match:
            dt_str = match.group(1)
            high = float(match.group(2))
            low = float(match.group(3))
            close = float(match.group(4))
            stop = float(match.group(5))
            
            try:
                dt = datetime.strptime(dt_str, "%Y/%m/%d %H:%M")
                data['datetime'].append(dt)
                data['high'].append(high)
                data['low'].append(low)
                data['close'].append(close)
                data['stop'].append(stop)
            except:
                continue

print(f"抽出データ数: {len(data['datetime'])}")
if len(data['datetime']) > 0:
    print(f"期間: {data['datetime'][0]} ~ {data['datetime'][-1]}")
    print(f"Close: min={min(data['close']):.2f}, max={max(data['close']):.2f}")
    print(f"STOP: min={min(data['stop']):.2f}, max={max(data['stop']):.2f}")

# グラフ作成
fig, ax = plt.subplots(figsize=(16, 8))

# Close Price をプロット
ax.plot(data['datetime'], data['close'], label='Close Price', color='blue', linewidth=2, marker='o', markersize=3, alpha=0.7)

# STOP (PSAR相当) をプロット
ax.plot(data['datetime'], data['stop'], label='STOP (PSAR)', color='red', linewidth=2, marker='s', markersize=3, alpha=0.7)

# Close > STOPの領域を背景で表示
for i in range(len(data['datetime'])):
    if data['stop'][i] > 0:
        if data['close'][i] > data['stop'][i]:
            ax.axvspan(data['datetime'][i], data['datetime'][i+1] if i+1 < len(data['datetime']) else data['datetime'][i], 
                       alpha=0.1, color='green', label='Close > STOP' if i == 0 else '')
        else:
            ax.axvspan(data['datetime'][i], data['datetime'][i+1] if i+1 < len(data['datetime']) else data['datetime'][i], 
                       alpha=0.1, color='red', label='Close < STOP' if i == 0 else '')

ax.set_xlabel('DateTime', fontsize=12, fontweight='bold')
ax.set_ylabel('Price (USD)', fontsize=12, fontweight='bold')
ax.set_title('PSAR (STOP) vs Close Price - Extended Lookback (100 bars)', fontsize=14, fontweight='bold')
ax.legend(loc='best', fontsize=11)
ax.grid(True, alpha=0.3)

# x軸のフォーマット
ax.xaxis.set_major_formatter(DateFormatter("%m/%d"))
ax.xaxis.set_major_locator(mdates.HourLocator(interval=72))
plt.xticks(rotation=45, ha='right')

plt.tight_layout()
plt.savefig('/home/satoshi/work/satosystem/test/psar_extended_visualization.png', dpi=150, bbox_inches='tight')
print("\n✅ グラフ保存: test/psar_extended_visualization.png")

# 統計情報
close_array = np.array(data['close'])
stop_array = np.array([s for s in data['stop'] if s > 0])

if len(stop_array) > 0:
    above_count = sum(1 for i in range(len(data['stop'])) if data['stop'][i] > 0 and data['close'][i] > data['stop'][i])
    below_count = sum(1 for i in range(len(data['stop'])) if data['stop'][i] > 0 and data['close'][i] < data['stop'][i])
    total_with_stop = above_count + below_count
    
    if total_with_stop > 0:
        above_pct = (above_count / total_with_stop) * 100
        below_pct = (below_count / total_with_stop) * 100
        
        print(f"\n📊 統計情報:")
        print(f"  Close > STOP: {above_count} ({above_pct:.1f}%)")
        print(f"  Close < STOP: {below_count} ({below_pct:.1f}%)")
        print(f"  Total: {total_with_stop}")

plt.show()
