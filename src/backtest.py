import os
import shutil
import time
import sys
from configparser import ConfigParser
from config import Config
from price_data_management import PriceDataManagement
from bybit_exchange import BybitExchange
from trading_strategy import TradingStrategy
from risk_management import RiskManagement
from portfolio import Portfolio
from order import Order
from bot import Bot  # Assuming the Bot class is in a separate file named bot.py

def generate_interactive_psar_graph():
    """
    バックテスト後にインタラクティブなPSAR分析グラフを生成
    """
    try:
        import json
        import re
        from datetime import datetime
        import numpy as np
        
        try:
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots
        except ImportError:
            print("plotlyをインストール中...")
            import subprocess
            subprocess.check_call(['pip', 'install', 'plotly', '-q'])
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots
        
        # 最新のバックテストログを取得
        log_dir = os.path.join(os.path.dirname(__file__), 'logs')
        log_files = [f for f in os.listdir(log_dir) if f.endswith('.json') and f[0].isdigit()]
        if not log_files:
            print("⚠️  ログファイルが見つかりません")
            return
        
        latest_log = sorted(log_files)[-1]
        log_file = os.path.join(log_dir, latest_log)
        
        # latest_backtest.logを使用（テキスト形式）
        text_log_file = os.path.join(log_dir, 'latest_backtest.log')
        if not os.path.exists(text_log_file):
            print("⚠️  latest_backtest.logが見つかりません")
            return
        
        print(f"📊 グラフ生成中: {text_log_file}")
        
        # ログファイルからデータ抽出
        data = {
            'datetime': [],
            'close': [],
            'high': [],
            'low': [],
            'stop': [],
            'volatility': []
        }
        
        with open(text_log_file, 'r', encoding='utf-8') as f:
            for line in f:
                # ログパターン: 時刻: 2025/10/10 09:00  高値: 121902  安値: 121483  終値: 121659  購入価格:     0  STOP:    0  ボラ: 1112.60
                match = re.search(r'時刻: (\d{4}/\d{2}/\d{2} \d{2}:\d{2}).*高値:\s+(\d+)\s+安値:\s+(\d+)\s+終値:\s+(\d+).*STOP:\s+(\d+).*ボラ:\s+([\d.]+)', line)
                if match:
                    dt_str = match.group(1)
                    high = float(match.group(2))
                    low = float(match.group(3))
                    close = float(match.group(4))
                    stop = float(match.group(5))
                    volatility = float(match.group(6))
                    
                    try:
                        dt = datetime.strptime(dt_str, "%Y/%m/%d %H:%M")
                        data['datetime'].append(dt)
                        data['high'].append(high)
                        data['low'].append(low)
                        data['close'].append(close)
                        data['stop'].append(stop)
                        data['volatility'].append(volatility)
                    except:
                        continue
        
        if len(data['datetime']) == 0:
            print("⚠️  データが抽出できませんでした")
            return
        
        print(f"✅ データ抽出: {len(data['datetime'])} candles")
        
        # 表示範囲の計算
        high_values = [h for h in data['high'] if h > 0]
        low_values = [l for l in data['low'] if l > 0]
        stop_values = [s for s in data['stop'] if s > 0]
        
        if high_values and low_values and stop_values:
            donchian_high_max = max(high_values)
            donchian_low_min = min(low_values)
            stop_max = max(stop_values)
            stop_min = min(stop_values)
            
            price_min = min(donchian_low_min, stop_min)
            price_max = max(donchian_high_max, stop_max)
            price_range = price_max - price_min
            margin = price_range * 0.1
            
            y_min = price_min - margin
            y_max = price_max + margin
        
        # Close > STOP / Close < STOP の判定
        close_above_stop = []
        for i in range(len(data['stop'])):
            if data['stop'][i] > 0:
                close_above_stop.append(data['close'][i] > data['stop'][i])
            else:
                close_above_stop.append(None)
        
        above_count = sum(1 for x in close_above_stop if x is True)
        below_count = sum(1 for x in close_above_stop if x is False)
        
        # Plotly図を作成
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.12,
            subplot_titles=('Close Price vs STOP (PSAR)', 'Volatility'),
            specs=[[{"secondary_y": False}], [{"secondary_y": False}]]
        )
        
        # メインチャート: Close と STOP
        fig.add_trace(
            go.Scatter(
                x=data['datetime'],
                y=data['close'],
                mode='lines+markers',
                name='Close Price',
                line=dict(color='blue', width=2),
                marker=dict(size=4, symbol='circle'),
                hovertemplate='<b>Close</b><br>%{x}<br>Price: %{y:.2f}<extra></extra>',
            ),
            row=1, col=1
        )
        
        fig.add_trace(
            go.Scatter(
                x=data['datetime'],
                y=data['stop'],
                mode='lines+markers',
                name='STOP (PSAR)',
                line=dict(color='red', width=2),
                marker=dict(size=4, symbol='square'),
                hovertemplate='<b>STOP</b><br>%{x}<br>Price: %{y:.2f}<extra></extra>',
            ),
            row=1, col=1
        )
        
        # Close > STOP の領域を背景で塗りつぶし
        for i in range(len(data['datetime']) - 1):
            if data['stop'][i] > 0 and data['stop'][i+1] > 0:
                if close_above_stop[i] is True:
                    fig.add_vrect(
                        x0=data['datetime'][i], x1=data['datetime'][i+1],
                        fillcolor="green", opacity=0.05,
                        layer="below", line_width=0,
                        row=1, col=1
                    )
                else:
                    fig.add_vrect(
                        x0=data['datetime'][i], x1=data['datetime'][i+1],
                        fillcolor="red", opacity=0.05,
                        layer="below", line_width=0,
                        row=1, col=1
                    )
        
        # High/Low をキャンドルチックで表示
        for i in range(len(data['datetime'])):
            fig.add_trace(
                go.Scatter(
                    x=[data['datetime'][i], data['datetime'][i]],
                    y=[data['low'][i], data['high'][i]],
                    mode='lines',
                    line=dict(color='gray', width=1),
                    showlegend=False,
                    hoverinfo='skip',
                    opacity=0.3
                ),
                row=1, col=1
            )
        
        # ボラティリティ（下側のサブプロット）
        fig.add_trace(
            go.Bar(
                x=data['datetime'],
                y=data['volatility'],
                name='Volatility',
                marker=dict(color='orange'),
                hovertemplate='<b>Volatility</b><br>%{x}<br>Value: %{y:.2f}<extra></extra>',
            ),
            row=2, col=1
        )
        
        # Y軸範囲を設定
        fig.update_yaxes(range=[y_min, y_max], title_text="Price (USD)", row=1, col=1)
        fig.update_yaxes(title_text="Volatility", row=2, col=1)
        fig.update_xaxes(title_text="DateTime", row=2, col=1)
        
        # 全体設定
        fig.update_layout(
            title=dict(
                text=f'<b>Backtest PSAR Analysis</b><br><sub>Close Price vs STOP | {data["datetime"][0].strftime("%Y-%m-%d")} to {data["datetime"][-1].strftime("%Y-%m-%d")}</sub>',
                x=0.5,
                xanchor='center',
                font=dict(size=18)
            ),
            hovermode='x unified',
            height=900,
            template='plotly_white',
            legend=dict(
                x=0.02,
                y=0.98,
                bgcolor='rgba(255, 255, 255, 0.8)',
                bordercolor='gray',
                borderwidth=1
            ),
            font=dict(size=12),
        )
        
        # HTML保存
        output_dir = os.path.join(os.path.dirname(__file__), '..', 'docs')
        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, 'backtest_psar_interactive.html')
        
        # 詳細統計情報をHTMLに追加
        chart_html = fig.to_html(include_plotlyjs='cdn', div_id='plotly-chart')
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Backtest PSAR Analysis</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        h1 {{
            text-align: center;
            color: #333;
            border-bottom: 3px solid #0066cc;
            padding-bottom: 15px;
        }}
        .stats {{
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 15px;
            margin: 20px 0;
        }}
        .stat-box {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }}
        .stat-box.good {{
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        }}
        .stat-box.warning {{
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        }}
        .stat-value {{
            font-size: 32px;
            font-weight: bold;
            margin: 10px 0;
        }}
        .stat-label {{
            font-size: 14px;
            opacity: 0.9;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #f2f2f2;
            font-weight: bold;
        }}
        tr:hover {{
            background-color: #f9f9f9;
        }}
        .section {{
            margin: 30px 0;
        }}
        .chart-container {{
            margin: 30px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Backtest PSAR Analysis Report</h1>
        
        <div class="section">
            <h2>Summary Statistics</h2>
            <div class="stats">
                <div class="stat-box good">
                    <div class="stat-label">Close > STOP (Uptrend)</div>
                    <div class="stat-value">{above_count}</div>
                    <div class="stat-label">{above_count*100/(above_count+below_count):.1f}%</div>
                </div>
                <div class="stat-box warning">
                    <div class="stat-label">Close < STOP (Downtrend)</div>
                    <div class="stat-value">{below_count}</div>
                    <div class="stat-label">{below_count*100/(above_count+below_count):.1f}%</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Total Observations</div>
                    <div class="stat-value">{above_count + below_count}</div>
                    <div class="stat-label">with STOP values</div>
                </div>
            </div>
        </div>
        
        <div class="section chart-container">
            <h2>📈 Interactive Chart</h2>
            <p><em>Hover over the chart to see detailed values. Use the toolbar to zoom, pan, and download.</em></p>
            {chart_html}
        </div>
        
        <div class="section">
            <h2>📋 Data Summary</h2>
            <table>
                <tr>
                    <th>Metric</th>
                    <th>Value</th>
                </tr>
                <tr>
                    <td>Period Start</td>
                    <td>{data['datetime'][0].strftime('%Y-%m-%d %H:%M')}</td>
                </tr>
                <tr>
                    <td>Period End</td>
                    <td>{data['datetime'][-1].strftime('%Y-%m-%d %H:%M')}</td>
                </tr>
                <tr>
                    <td>Total Candles</td>
                    <td>{len(data['datetime'])}</td>
                </tr>
                <tr>
                    <td>Donchian High (Max)</td>
                    <td>{donchian_high_max:.2f}</td>
                </tr>
                <tr>
                    <td>Donchian Low (Min)</td>
                    <td>{donchian_low_min:.2f}</td>
                </tr>
                <tr>
                    <td>STOP Max</td>
                    <td>{stop_max:.2f}</td>
                </tr>
                <tr>
                    <td>STOP Min</td>
                    <td>{stop_min:.2f}</td>
                </tr>
            </table>
        </div>
        
        <hr>
        <p style="text-align: center; color: #666; font-size: 12px;">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
</body>
</html>
"""
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"✅ グラフ生成完了: {output_file}")
        
    except Exception as e:
        print(f"⚠️  グラフ生成エラー: {e}")
        import traceback
        traceback.print_exc()

def find_config_files(directory):
    """
    指定したディレクトリ内のconfig_*.ini ファイルのリストを取得します。

    Args:
        directory (str): 検索対象のディレクトリパス

    Returns:
        list: config_*.ini ファイルのリスト
    """
    config_files = [f for f in os.listdir(directory) if f.startswith("config_") and f.endswith(".ini")]
    return [os.path.join(directory, config_file) for config_file in config_files]

def main():
    total_start_time = time.time()

    # 1. バックアップとしてconfig.iniをconfig_bak.iniにリネームする
    shutil.copy("config.ini", "config_bak.ini")

    # 2. output_configs以下のconfig_*.ini ファイルからファイルリストを作成
    config_files = find_config_files("output_configs")

    # 3. ファイルリストから一つずつconfig.iniにコピーしてbot.pyを実行する
    for idx, config_file in enumerate(config_files):
        # コピーしてconfig.iniに変更
        shutil.copy(config_file, "config.ini")
    
        # Replace API_KEY and API_SECRET in config.ini using replace_api_key.sh
        os.system("./replace_api_key.sh")
    
        # 取引所クラスを初期化
        exchange = BybitExchange(Config.get_api_key(), Config.get_api_secret())
        # 資産管理クラスを初期化（唯一であること TODO シングルトン化）
        portfolio = Portfolio()
        # 価格情報クラスを初期化
        price_data_management = PriceDataManagement()
        # リスク戦略クラスを初期化
        risk_management = RiskManagement(price_data_management, portfolio)
        # 取引戦略クラスを初期化
        strategy = TradingStrategy(price_data_management, risk_management, portfolio)
        # ボットのインスタンスを作成
        bot = Bot(exchange, strategy, risk_management, price_data_management, portfolio)

        # ボットを実行
        start_time = time.time()
        bot.run()
        elapsed_time = time.time() - start_time

        # 処理中のconfigファイルの名前と進捗率を表示
        progress = (idx + 1) / len(config_files) * 100
        print(f"Processing: {config_file}, Progress: {progress:.2f}%, Elapsed Time: {format_elapsed_time(elapsed_time)}")
        
    total_elapsed_time = time.time() - total_start_time
    print(f"Total Elapsed Time: {format_elapsed_time(total_elapsed_time)}")

    # 4. バックアップしたconfig_bak.iniをconfig.iniに戻す(config.iniに上書きして戻す)
    shutil.move("config_bak.ini", "config.ini")
    
    # 5. 設定に従ってインタラクティブグラフを生成
    try:
        config = ConfigParser()
        config.read("config.ini")
        generate_graph = config.getint('Backtest', 'generate_interactive_graph', fallback=1)
        if generate_graph == 1:
            print("\n🎨 バックテスト後のグラフ生成を実行中...")
            generate_interactive_psar_graph()
    except Exception as e:
        print(f"⚠️  グラフ生成スキップ: {e}")

def format_elapsed_time(seconds):
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return "{:02}:{:02}:{:02}".format(int(hours), int(minutes), int(seconds))

if __name__ == "__main__":
    main()
