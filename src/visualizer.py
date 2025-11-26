"""
トレーディングボットのバックテスト結果を可視化するモジュール

機能:
- 2時間足ローソク足チャート + 1分足ティック価格の重ね表示
- インタラクティブな拡大縮小・範囲変更
- 指標(Donchian/PSAR/ADX/PVO等)の表示切替
- ポジション開始・終了・損切値の可視化
"""

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import zipfile
import os
from datetime import datetime, timedelta
from config import Config


class Visualizer:
    def __init__(self):
        self.config = Config()
        
    def load_logs_data(self, log_directory, start_time=None, end_time=None):
        """
        ログディレクトリから全データを読み込む (JSON/ZIP対応)
        
        Args:
            log_directory: ログディレクトリパス
            start_time: 開始時刻 (datetime or str)
            end_time: 終了時刻 (datetime or str)
        
        Returns:
            DataFrame: 統合されたログデータ
        """
        if isinstance(start_time, str):
            start_time = datetime.strptime(start_time, "%Y/%m/%d %H:%M")
        if isinstance(end_time, str):
            end_time = datetime.strptime(end_time, "%Y/%m/%d %H:%M")
        
        log_files = []
        for root, _, files in os.walk(log_directory):
            for file in files:
                if file.endswith(".json") or file.endswith(".zip"):
                    log_files.append(os.path.join(root, file))
        
        if not log_files:
            print(f"No log files in {log_directory}")
            return None
        
        # 最新のログファイルのみを使用（複数ファイルの重複データを防ぐ）
        log_files.sort()
        latest_file = log_files[-1]
        print(f"[INFO] Using latest log file: {latest_file}")
        
        dataframes = []
        
        try:
            path = latest_file
            if path.endswith('.zip'):
                with zipfile.ZipFile(path, 'r') as zf:
                    name = zf.namelist()[0]
                    with zf.open(name) as f:
                        df = pd.read_json(f)
            else:
                df = pd.read_json(path)
            
            if start_time is not None and end_time is not None:
                if 'real_time' in df.columns:
                    df['real_time_dt'] = pd.to_datetime(df['real_time'])
                    mask = (df['real_time_dt'] >= start_time) & (df['real_time_dt'] <= end_time)
                    df = df.loc[mask]
                elif 'close_time_dt' in df.columns:
                    df['close_time_dt_parsed'] = pd.to_datetime(df['close_time_dt'])
                    mask = (df['close_time_dt_parsed'] >= start_time) & (df['close_time_dt_parsed'] <= end_time)
                    df = df.loc[mask]
            
            if not df.empty:
                dataframes.append(df)
        except Exception as e:
            print(f"Skip {latest_file}: {e}")
        
        if not dataframes:
            print("No valid data found")
            return None
        
        combined = dataframes[0]
        # real_time をdatetimeに変換
        if 'real_time' in combined.columns:
            combined['real_time_dt'] = pd.to_datetime(combined['real_time'])
            combined.sort_values('real_time_dt', inplace=True)
        
        print(f"[INFO] Loaded {len(combined)} records from {latest_file}")
        return combined
    
    def resample_to_2h_candles(self, df):
        """与えられた時系列を2時間足へ変換。ただし既に2時間以上のステップであれば再サンプリングせずそのまま返す。"""
        if df is None or df.empty or 'real_time_dt' not in df.columns:
            return None

        # 間隔推定
        times = df['real_time_dt'].sort_values().unique()
        if len(times) >= 3:
            deltas = pd.Series(times[1:]) - pd.Series(times[:-1])
            median_delta = deltas.median()
        else:
            median_delta = timedelta(hours=2)

        # 既に2時間以上の粒度ならそのままOHLC扱い
        if median_delta >= timedelta(hours=2) and {'open_price','high_price','low_price','close_price'}.issubset(df.columns):
            # 重複を削除してから返す
            result = df[['real_time_dt','open_price','high_price','low_price','close_price']].copy()
            result = result.drop_duplicates(subset=['real_time_dt'], keep='first')
            result = result.sort_values('real_time_dt').reset_index(drop=True)
            return result

        # 重複を削除してからリサンプリング
        df_unique = df.drop_duplicates(subset=['real_time_dt'], keep='first').copy()
        df_candle = df_unique.set_index('real_time_dt')
        ohlc_dict = {
            'open_price': 'first',
            'high_price': 'max',
            'low_price': 'min',
            'close_price': 'last',
            'Volume': 'sum' if 'Volume' in df_candle.columns else 'count'
        }
        candles_2h = df_candle.resample('2h').agg(ohlc_dict).dropna()
        candles_2h.reset_index(inplace=True)
        return candles_2h
    
    def create_interactive_chart(self, df, candles_2h, output_html="backtest_visualization.html"):
        """
        インタラクティブなチャートを生成（3つのサブプロット）
        
        Args:
            df: 1分足データ (全指標含む)
            candles_2h: 2時間足ローソク足データ
            output_html: 出力HTMLファイルパス
        """
        # サブプロット: 3行
        # Row 1: 価格系 (ローソク足 + Donchian + PSAR)
        # Row 2: テクニカル指標系 (Volatility + PVO + ADX)
        # Row 3: 累積損益 (PnL)
        fig = make_subplots(
            rows=3, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.08,
            row_heights=[0.4, 0.3, 0.3],
            subplot_titles=("価格チャート (2h足ローソク + Donchian + PSAR)", 
                           "テクニカル指標 (Volatility / PVO / ADX)", 
                           "累積損益 (PnL)")
        )
        
        # === Row 1: 価格チャート (ローソク足 + Donchian + PSAR) ===
        
        # 2時間足ローソク足を最初に追加（後のトレースに隠されないように）
        if candles_2h is not None and not candles_2h.empty:
            print(f"[DEBUG] Adding Candlestick: {len(candles_2h)} candles")
            candlestick = go.Candlestick(
                x=candles_2h['real_time_dt'],
                open=candles_2h['open_price'],
                high=candles_2h['high_price'],
                low=candles_2h['low_price'],
                close=candles_2h['close_price'],
                name="2時間足",
                visible=True,
                xaxis="x",
                yaxis="y"
            )
            fig.add_trace(candlestick, row=1, col=1)
            print(f"[DEBUG] Traces after Candlestick: {len(fig.data)}")
        else:
            print("[WARNING] candles_2h is None or empty")
        
        # ポジション保有区間を背景色でハイライト（BUY=淡緑 / SELL=淡赤）
        if 'position_quantity' in df.columns:
            df['has_position'] = df['position_quantity'] > 0
            df['position_change'] = df['has_position'].astype(int).diff().fillna(0)
        else:
            df['has_position'] = False
            df['position_change'] = 0
        
        entry_indices = df[df['position_change'] == 1].index
        exit_indices = df[df['position_change'] == -1].index
        
        # ENTRYとEXITをペアリング
        for entry_idx in entry_indices:
            exit_idx_candidates = exit_indices[exit_indices > entry_idx]
            if len(exit_idx_candidates) > 0:
                exit_idx = exit_idx_candidates[0]
            else:
                exit_idx = df.index[-1]
            
            entry_time = df.loc[entry_idx, 'real_time_dt']
            exit_time = df.loc[exit_idx, 'real_time_dt']
            
            position_side = df.loc[entry_idx, 'side'] if 'side' in df.columns else 'BUY'
            if position_side == 'BUY':
                fill_color = "lightgreen"
            else:
                fill_color = "lightcoral"
            
            fig.add_vrect(
                x0=entry_time, x1=exit_time,
                fillcolor=fill_color, opacity=0.1,
                layer="below", line_width=0,
                row=1, col=1
            )
        
        # Donchian High/Low
        if 'dc_h' in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df['real_time_dt'],
                    y=df['dc_h'],
                    mode='lines',
                    name="Donchian High",
                    line=dict(color='green', width=1, dash='dash'),
                    visible=True
                ),
                row=1, col=1
            )
        
        if 'dc_l' in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df['real_time_dt'],
                    y=df['dc_l'],
                    mode='lines',
                    name="Donchian Low",
                    line=dict(color='red', width=1, dash='dash'),
                    visible=True
                ),
                row=1, col=1
            )
        
        # PSAR
        if 'psar' in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df['real_time_dt'],
                    y=df['psar'],
                    mode='markers',
                    name="PSAR",
                    marker=dict(color='orange', size=4),
                    visible=True
                ),
                row=1, col=1
            )
        
        # ストップ価格 (ポジション保有時のみ表示)
        # stop_price が 0 の場合は PSAR から推定、またはエントリー価格から計算
        df_with_position = df[df['position_quantity'] > 0].copy()
        
        if not df_with_position.empty:
            # stop_price が 0 の場合、PSAR または推定値を使用
            df_with_position['display_stop'] = df_with_position['stop_price'].copy()
            
            # stop_price が 0 で PSAR がある場合は PSAR を使用
            zero_stop_mask = df_with_position['display_stop'] == 0
            if 'psar' in df_with_position.columns:
                df_with_position.loc[zero_stop_mask, 'display_stop'] = df_with_position.loc[zero_stop_mask, 'psar']
            
            # それでも 0 の場合は、エントリー価格から stop_offset で計算
            still_zero = (df_with_position['display_stop'] == 0) & ('position_price' in df_with_position.columns)
            if still_zero.any() and 'stop_offset' in df_with_position.columns:
                df_with_position.loc[still_zero, 'display_stop'] = (
                    df_with_position.loc[still_zero, 'position_price'] - 
                    df_with_position.loc[still_zero, 'stop_offset']
                )
            
            # display_stop が 0 より大きいレコードのみを表示
            df_stop_display = df_with_position[df_with_position['display_stop'] > 0]
            
            if not df_stop_display.empty:
                fig.add_trace(
                    go.Scatter(
                        x=df_stop_display['real_time_dt'],
                        y=df_stop_display['display_stop'],
                        mode='lines',
                        name="損切値 (Stop)",
                        line=dict(color='orangered', width=2, dash='dot'),
                        visible=True
                    ),
                    row=1, col=1
                )
        
        # ポジション開始・終了マーカー
        df_trades = pd.DataFrame()
        if 'decision' in df.columns:
            mask = (df['decision'].notna()) & (df['decision'] != 'NONE')
            df_trades = df[mask].copy()
        if not df_trades.empty:
            # ENTRY
            df_entry = df_trades[df_trades['decision'] == 'ENTRY']
            if not df_entry.empty:
                fig.add_trace(
                    go.Scatter(
                        x=df_entry['real_time_dt'],
                        y=df_entry['close_price'],
                        mode='markers',
                        name="ENTRY",
                        marker=dict(color='lime', size=10, symbol='triangle-up'),
                        visible=True
                    ),
                    row=1, col=1
                )
            
            # ADD
            df_add = df_trades[df_trades['decision'] == 'ADD']
            if not df_add.empty:
                fig.add_trace(
                    go.Scatter(
                        x=df_add['real_time_dt'],
                        y=df_add['close_price'],
                        mode='markers',
                        name="ADD",
                        marker=dict(color='yellow', size=8, symbol='circle'),
                        visible=True
                    ),
                    row=1, col=1
                )
            
            # EXIT
            df_exit = df_trades[df_trades['decision'] == 'EXIT']
            if not df_exit.empty:
                fig.add_trace(
                    go.Scatter(
                        x=df_exit['real_time_dt'],
                        y=df_exit['close_price'],
                        mode='markers',
                        name="EXIT",
                        marker=dict(color='red', size=10, symbol='triangle-down'),
                        visible=True
                    ),
                    row=1, col=1
                )
        
        # === Row 2: テクニカル指標 (Volatility / PVO / ADX) ===
        
        # Volatility (ボラティリティ)
        if 'volatility' in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df['real_time_dt'],
                    y=df['volatility'],
                    mode='lines',
                    name="Volatility",
                    line=dict(color='purple', width=1),
                    visible=True
                ),
                row=2, col=1
            )
        
        # PVO (Percentage Volume Oscillator)
        if 'pvo_val' in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df['real_time_dt'],
                    y=df['pvo_val'],
                    mode='lines',
                    name="PVO",
                    line=dict(color='cyan', width=1),
                    visible=True
                ),
                row=2, col=1
            )
        elif 'pvo' in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df['real_time_dt'],
                    y=df['pvo'],
                    mode='lines',
                    name="PVO",
                    line=dict(color='cyan', width=1),
                    visible=True
                ),
                row=2, col=1
            )
        
        # ADX (Average Directional Index)
        if 'adx' in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df['real_time_dt'],
                    y=df['adx'],
                    mode='lines',
                    name="ADX",
                    line=dict(color='navy', width=1),
                    visible=True
                ),
                row=2, col=1
            )
        
        # ATR (Average True Range) - オプション表示
        if 'atr' in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df['real_time_dt'],
                    y=df['atr'],
                    mode='lines',
                    name="ATR",
                    line=dict(color='brown', width=1),
                    visible='legendonly'
                ),
                row=2, col=1
            )
        
        # === Row 3: 累積損益 (PnL) ===
        if 'total_profit_and_loss' in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df['real_time_dt'],
                    y=df['total_profit_and_loss'],
                    mode='lines',
                    name="累積損益 (PnL)",
                    line=dict(color='darkblue', width=2),
                    fill='tozeroy',
                    fillcolor='rgba(0,100,255,0.1)',
                    visible=True
                ),
                row=3, col=1
            )
            # PnLゼロライン
            fig.add_hline(y=0, line_dash="dash", line_color="gray", row=3, col=1)
        
        # レイアウト設定
        fig.update_layout(
            title="バックテスト可視化 (インタラクティブ - 3グラフ表示)",
            xaxis_title="時刻",
            height=1400,
            hovermode='x unified',
            xaxis_rangeslider_visible=False,
            legend=dict(
                orientation="v",
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=1.01
            )
        )
        
        # Y軸ラベル
        fig.update_yaxes(title_text="価格 (USD)", row=1, col=1)
        fig.update_yaxes(title_text="テクニカル指標値", row=2, col=1)
        fig.update_yaxes(title_text="累積損益 (USD)", row=3, col=1)
        
        # HTML出力
        fig.write_html(output_html, include_plotlyjs='cdn')
        print(f"Interactive chart saved: {output_html}")
        
        return fig
    
    def visualize_backtest(self, log_directory="logs", output_html="report/backtest_visualization.html", 
                          start_time=None, end_time=None):
        """
        バックテスト結果を可視化 (メインエントリポイント)
        
        Args:
            log_directory: ログディレクトリ
            output_html: 出力HTMLファイル名（デフォルト: report/backtest_visualization.html）
            start_time: 開始時刻 (datetime or str "%Y/%m/%d %H:%M")
            end_time: 終了時刻 (datetime or str "%Y/%m/%d %H:%M")
        """
        # デフォルト期間はConfigから取得
        if start_time is None:
            start_time = self.config.get_start_time()
        if end_time is None:
            end_time = self.config.get_end_time()
        
        # 出力ディレクトリを確保
        output_dir = os.path.dirname(output_html)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"Created directory: {output_dir}")
        
        print(f"Loading logs from {log_directory} (period: {start_time} to {end_time})...")
        df = self.load_logs_data(log_directory, start_time, end_time)
        
        if df is None or df.empty:
            print("No data to visualize")
            return
        
        print(f"Loaded {len(df)} records")
        
        # 2時間足ローソク足作成 (既に2h足なら間引きなし)
        print("Preparing 2-hour candles (no thinning)...")
        candles_2h = self.resample_to_2h_candles(df)
        
        if candles_2h is not None:
            print(f"Created {len(candles_2h)} 2-hour candles")
        
        # チャート生成
        print("Generating interactive chart...")
        self.create_interactive_chart(df, candles_2h, output_html)
        
        print("Done!")


if __name__ == "__main__":
    visualizer = Visualizer()
    
    # config.iniの期間で可視化
    log_directory = "logs"
    output_html = "report/backtest_visualization.html"
    
    visualizer.visualize_backtest(
        log_directory=log_directory,
        output_html=output_html
    )
    
    print(f"\n可視化完了: {output_html}")
    print("ブラウザで開いて確認してください。")
