"""
トレーディングボットのバックテスト結果を可視化するモジュール

機能:
- 設定タイムフレームのローソク足チャート + 1分足ティック価格の重ね表示
- インタラクティブな拡大縮小・範囲変更
- 指標(Donchian/PSAR/PVO等)の表示切替
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
import sys


class Visualizer:
    def __init__(self):
        self.config = Config()
        # タイムフレームをconfig.iniから取得
        self.time_frame = self.config.get_time_frame()  # 240分 = 4時間
        self.time_frame_hours = self.time_frame / 60
        self.time_frame_label = self._get_timeframe_label(self.time_frame)
    
    def _get_timeframe_label(self, minutes):
        """タイムフレーム（分）をラベル文字列に変換"""
        if minutes < 60:
            return f"{minutes}分足"
        else:
            hours = minutes / 60
            if hours == int(hours):
                return f"{int(hours)}時間足"
            else:
                return f"{hours}時間足"
        
    def detect_period_log_files(self, log_directory, start_time, end_time):
        """
        指定期間に含まれるZIPファイルを自動検出
        
        ファイル名のパターン: *.zip または *-YYYYMMDD_HHMMSS-YYYYMMDD_HHMMSS.zip
        ファイル名から期間を抽出し、指定期間と一致するファイルを検出
        
        Args:
            log_directory: ログディレクトリ
            start_time: 期間開始時刻 (datetime)
            end_time: 期間終了時刻 (datetime)
        
        Returns:
            list: 期間に含まれるZIPファイルパスのリスト（時系列順）
        """
        import re
        
        if isinstance(start_time, str):
            start_time = datetime.strptime(start_time, "%Y/%m/%d %H:%M")
        if isinstance(end_time, str):
            end_time = datetime.strptime(end_time, "%Y/%m/%d %H:%M")
        
        # ファイル名フォーマット例: 20251126184913-20250101_0000-20250131_2359.zip
        pattern = r'(\d{8})_(\d{4})-(\d{8})_(\d{4})\.zip$'
        
        zip_files = []
        for root, _, files in os.walk(log_directory):
            for file in files:
                if file.endswith(".zip"):
                    zip_files.append(os.path.join(root, file))
        
        if not zip_files:
            print(f"[INFO] ZIPファイルが見つかりません: {log_directory}")
            return []
        
        zip_files.sort()
        relevant_files = []
        
        print(f"[INFO] 期間 {start_time:%Y/%m/%d %H:%M} ～ {end_time:%Y/%m/%d %H:%M} に含まれるログファイルを検出中...")
        
        for zf in zip_files:
            basename = os.path.basename(zf)
            match = re.search(pattern, basename)
            
            if match:
                # ファイル名から期間を抽出
                # Group 1: start_date (YYYYMMDD), Group 2: start_time (HHMM)
                # Group 3: end_date (YYYYMMDD), Group 4: end_time (HHMM)
                start_date_str = match.group(1)  # YYYYMMDD
                start_time_str = match.group(2)  # HHMM
                end_date_str = match.group(3)    # YYYYMMDD
                end_time_str = match.group(4)    # HHMM
                
                file_start_str = f"{start_date_str[:4]}/{start_date_str[4:6]}/{start_date_str[6:8]} {start_time_str[:2]}:{start_time_str[2:4]}"
                file_end_str = f"{end_date_str[:4]}/{end_date_str[4:6]}/{end_date_str[6:8]} {end_time_str[:2]}:{end_time_str[2:4]}"
                
                file_start = datetime.strptime(file_start_str, "%Y/%m/%d %H:%M")
                file_end = datetime.strptime(file_end_str, "%Y/%m/%d %H:%M")
                
                # 指定期間と重複するかチェック
                if file_end >= start_time and file_start <= end_time:
                    relevant_files.append((file_start, zf))
                    print(f"  ✓ {basename}: {file_start_str} ～ {file_end_str}")
        
        if relevant_files:
            relevant_files.sort(key=lambda x: x[0])
            result_files = [f[1] for f in relevant_files]
            print(f"[INFO] 検出: {len(result_files)} ファイル")
            return result_files
        else:
            print(f"[INFO] 期間内のファイルが見つかりません")
            return []
    
    def load_logs_data(self, log_directory, start_time=None, end_time=None, log_file=None, lookback_days=20):
        """
        ログディレクトリから全データを読み込む (JSON/ZIP対応)
        
        計算用の拡張期間を遡って読み込み、計算完了後に指定期間のみを返す
        
        指定期間に含まれるすべてのZIPファイルを自動検出して統合する
        
        Args:
            log_directory: ログディレクトリパス
            start_time: 表示開始時刻 (datetime or str)
            end_time: 表示終了時刻 (datetime or str)
            log_file: 特定のログファイルを指定（Noneの場合は自動検出）
            lookback_days: 計算用に遡る日数（デフォルト: 20日）
        
        Returns:
            tuple: (全データDF, 表示用期間のみのDF, 表示用のstart_time, 表示用のend_time)
        """
        if isinstance(start_time, str):
            start_time = datetime.strptime(start_time, "%Y/%m/%d %H:%M")
        if isinstance(end_time, str):
            end_time = datetime.strptime(end_time, "%Y/%m/%d %H:%M")
        
        # 計算用に拡張期間を設定
        calc_start_time = start_time - timedelta(days=lookback_days) if start_time else None
        display_start_time = start_time
        display_end_time = end_time
        
        log_files = []
        # log_directory 直下のみスキャン（サブディレクトリは除外）
        # os.walk を使うと logs/xaut/ など別シンボルのファイルまで拾ってしまうため
        for file in os.listdir(log_directory):
            full_path = os.path.join(log_directory, file)
            if os.path.isfile(full_path):
                # zipファイル + JSONファイルを対象とする
                if file.endswith(".zip") or (file.endswith(".json") and file[0].isdigit()):
                    log_files.append(full_path)
        
        if not log_files:
            print(f"No log files in {log_directory}")
            return None, None, display_start_time, display_end_time
        
        # ログファイルを選択
        if log_file is not None:
            # 特定ファイルが指定されている場合
            target_file = log_file if os.path.isabs(log_file) else os.path.join(log_directory, log_file)
            if not os.path.exists(target_file):
                print(f"Log file not found: {target_file}")
                return None, None, display_start_time, display_end_time
            files_to_process = [target_file]
            print(f"[INFO] Using specified log file: {os.path.basename(target_file)}")
        else:
            # デフォルト: 最新のJSONファイルを使用（または最新のZIP）
            json_files = [f for f in log_files if f.endswith('.json')]
            zip_files = [f for f in log_files if f.endswith('.zip')]
            
            if json_files:
                json_files.sort()
                # 最新から順に有効なJSONファイルを探す（空/壊れたファイルをスキップ）
                files_to_process = []
                for f in reversed(json_files):
                    if os.path.getsize(f) > 100:
                        files_to_process = [f]
                        print(f"[INFO] Using latest JSON log: {os.path.basename(f)}")
                        break
                if not files_to_process:
                    print(f"[INFO] 有効なJSONファイルが見つかりません ({log_directory})")
                    return None, None, display_start_time, display_end_time
            elif zip_files:
                # ZIPファイルから期間検出
                files_to_process = self.detect_period_log_files(log_directory, calc_start_time, display_end_time)
                if not files_to_process:
                    zip_files.sort()
                    files_to_process = [zip_files[-1]]
                    print(f"[INFO] Using latest ZIP: {os.path.basename(files_to_process[0])}")
            else:
                print(f"No usable log files in {log_directory}")
                return None, None, display_start_time, display_end_time
        
        print(f"[INFO] Processing {len(files_to_process)} log file(s)")
        print(f"[INFO] Calculation period: {calc_start_time} to {display_end_time}")
        print(f"[INFO] Display period: {display_start_time} to {display_end_time}")
        
        dataframes = []
        processed_count = 0
        
        for file_idx, path in enumerate(files_to_process, 1):
            try:
                if path.endswith('.zip'):
                    with zipfile.ZipFile(path, 'r') as zf:
                        name = zf.namelist()[0]
                        with zf.open(name) as f:
                            df = pd.read_json(f)
                else:
                    df = pd.read_json(path)
                
                # __CONFIG__ レコードを除外（最後の設定オブジェクト）
                if df is not None and not df.empty:
                    # real_time が存在し、かつ有効な値を持つレコードのみを保持
                    df = df[df['real_time'].notna() & (df['real_time'] != '')]
                    # close_price が 0.0 でないレコードのみを保持（__CONFIG__除外）
                    df = df[df['close_price'] != 0.0]
                    # NaN レコードを除外
                    df = df.dropna(subset=['close_price', 'real_time'])
                
                # real_time をdatetimeに変換（最初に実施）
                if 'real_time' in df.columns:
                    df['real_time_dt'] = pd.to_datetime(df['real_time'], errors='coerce')
                    # 1970年の無効な日付を除外（エポック時刻の異常レコード）
                    if 'real_time_dt' in df.columns:
                        df = df[df['real_time_dt'] >= pd.Timestamp('2000-01-01')]
                
                # 計算用期間でフィルタリング（拡張期間を含む）
                if calc_start_time is not None and display_end_time is not None:
                    if 'real_time_dt' in df.columns:
                        mask = (df['real_time_dt'] >= calc_start_time) & (df['real_time_dt'] <= display_end_time)
                        df = df.loc[mask]
                
                if not df.empty:
                    dataframes.append(df)
                    processed_count += 1
                    print(f"  [File {file_idx}/{len(files_to_process)}] Loaded {len(df)} records from {os.path.basename(path)}")
            except Exception as e:
                print(f"  [Warning] Skip {path}: {str(e)[:50]}")
        
        if not dataframes:
            print("No valid data found")
            return None, None, display_start_time, display_end_time
        
        # 複数ファイルのデータを統合
        combined = pd.concat(dataframes, ignore_index=True)
        
        # real_time_dt が存在することを確認してソート
        if 'real_time_dt' in combined.columns:
            combined.sort_values('real_time_dt', inplace=True)
        elif 'real_time' in combined.columns:
            combined['real_time_dt'] = pd.to_datetime(combined['real_time'])
            combined.sort_values('real_time_dt', inplace=True)
        
        # 重複排除（real_time_dt が同じレコードは最後のものを保持）
        if 'real_time_dt' in combined.columns:
            combined = combined.drop_duplicates(subset=['real_time_dt'], keep='last')
        
        print(f"[INFO] Loaded {len(combined)} records (including {lookback_days}-day lookback) from {processed_count} file(s)")
        
        # 表示用期間のデータを抽出
        if 'real_time_dt' in combined.columns:
            mask_display = (combined['real_time_dt'] >= display_start_time) & (combined['real_time_dt'] <= display_end_time)
            df_display = combined.loc[mask_display].copy()
        else:
            df_display = combined.copy()
        
        print(f"[INFO] Display records: {len(df_display)} (after filtering to display period)")
        
        return combined, df_display, display_start_time, display_end_time
    
    def resample_to_candles(self, df):
        """与えられた時系列を設定タイムフレームへ変換。ただし既に同等以上のステップであれば再サンプリングせずそのまま返す。"""
        if df is None or df.empty or 'real_time_dt' not in df.columns:
            return None

        # 間隔推定
        times = df['real_time_dt'].sort_values().unique()
        if len(times) >= 3:
            deltas = pd.Series(times[1:]) - pd.Series(times[:-1])
            median_delta = deltas.median()
        else:
            median_delta = timedelta(hours=self.time_frame_hours)

        # 既に設定タイムフレーム以上の粒度ならそのままOHLC扱い
        if median_delta >= timedelta(hours=self.time_frame_hours) and {'open_price','high_price','low_price','close_price'}.issubset(df.columns):
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
        # タイムフレームに応じたリサンプリング
        resample_rule = f'{int(self.time_frame_hours)}h' if self.time_frame_hours == int(self.time_frame_hours) else f'{int(self.time_frame)}T'
        candles = df_candle.resample(resample_rule).agg(ohlc_dict).dropna()
        candles.reset_index(inplace=True)
        return candles
    
    def _normalize_series(self, series):
        """
        時系列データを標準化（Z-score正規化）
        
        Args:
            series: pd.Series
        
        Returns:
            pd.Series: 標準化されたシリーズ (平均0、標準偏差1)
        """
        mean = series.mean()
        std = series.std()
        if std == 0:
            return series - mean  # 標準偏差0の場合は平均のみ引く
        return (series - mean) / std
    
    def create_interactive_chart(self, df, candles_2h, output_html="backtest_visualization.html", normalize_indicators=True):
        """
        インタラクティブなチャートを生成（3つのサブプロット）
        
        Args:
            df: 1分足データ (全指標含む)
            candles_2h: 設定タイムフレームのローソク足データ
            output_html: 出力HTMLファイルパス
            normalize_indicators: True=標準化, False=元の値 (デフォルト: True)
        """
        # サブプロット: 4行
        # Row 1: 価格系 (ローソク足 + Donchian + PSAR)
        # Row 2: ボリューム (Volume Bar)
        # Row 3: テクニカル指標系 (Volatility / PVO / ADX)
        # Row 4: 累積損益 (PnL)
        fig = make_subplots(
            rows=4, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.06,
            row_heights=[0.4, 0.15, 0.25, 0.2],
            subplot_titles=("価格チャート (2h足ローソク + Donchian + PSAR)", 
                           "ボリューム (Volume)", 
                           "テクニカル指標 (Volatility / PVO / ADX)", 
                           "累積損益 (PnL)")
        )
        
        # === Row 1: 価格チャート (ローソク足 + Donchian + PSAR) ===
        
        # ローソク足を最初に追加（後のトレースに隠されないように）
        if candles_2h is not None and not candles_2h.empty:
            candlestick = go.Candlestick(
                x=candles_2h['real_time_dt'],
                open=candles_2h['open_price'],
                high=candles_2h['high_price'],
                low=candles_2h['low_price'],
                close=candles_2h['close_price'],
                name=self.time_frame_label,
                visible=True,
                xaxis="x",
                yaxis="y"
            )
            fig.add_trace(candlestick, row=1, col=1)
        
        # ポジション保有区間を背景色でハイライト（BUY=淡緑 / SELL=淡赤）
        # action_name から ENTRY/EXIT を検出してハイライト
        if 'action_name' in df.columns:
            entry_records = df[df['action_name'] == 'ENTRY']
            exit_records = df[df['action_name'] == 'EXIT']
            
            # ENTRYとEXITをペアリング
            for entry_idx, entry_row in entry_records.iterrows():
                # この ENTRY より後ろの EXIT を探す
                exit_candidates = exit_records[exit_records.index > entry_idx]
                if len(exit_candidates) > 0:
                    exit_idx = exit_candidates.index[0]
                    exit_row = df.loc[exit_idx]
                else:
                    # EXIT がない場合は最後まで
                    exit_idx = df.index[-1]
                    exit_row = df.loc[exit_idx]
                
                entry_time = entry_row['real_time_dt']
                exit_time = exit_row['real_time_dt']
                
                position_side = entry_row['side'] if 'side' in entry_row else 'BUY'
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
        elif 'position_quantity' in df.columns:
            # フォールバック: position_quantity ベース
            df['has_position'] = df['position_quantity'] > 0
            df['position_change'] = df['has_position'].astype(int).diff().fillna(0)
            
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
        # ENTRY/EXIT/ADD アクションのあるレコード、または position_quantity > 0 のレコードを含める
        mask = (df['position_quantity'] > 0)
        if 'action_name' in df.columns:
            mask = mask | df['action_name'].isin(['ENTRY', 'EXIT', 'ADD'])
        df_with_position = df[mask].copy()
        
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
        if 'action_name' in df.columns:
            mask = (df['action_name'].notna()) & (df['action_name'].isin(['ENTRY', 'EXIT', 'ADD']))
            df_trades = df[mask].copy()
        elif 'decision' in df.columns:
            mask = (df['decision'].notna()) & (df['decision'] != 'NONE')
            df_trades = df[mask].copy()
        
        if not df_trades.empty:
            # ENTRY
            action_col = 'action_name' if 'action_name' in df_trades.columns else 'decision'
            
            df_entry = df_trades[df_trades[action_col] == 'ENTRY']
            if not df_entry.empty:
                # テキスト情報の準備
                entry_texts = df_entry.apply(
                    lambda row: f"ENTRY<br>Price: {row['close_price']:.2f}", 
                    axis=1
                )
                # ホバー情報の準備
                entry_hover = df_entry.apply(
                    lambda row: f"<b>ENTRY</b><br>時刻: {row.get('real_time_dt', '')}<br>価格: {row['close_price']:.2f}<br>エントリー価格: {row.get('entry_price', 'N/A')}", 
                    axis=1
                )
                fig.add_trace(
                    go.Scatter(
                        x=df_entry['real_time_dt'],
                        y=df_entry['close_price'],
                        mode='markers+text',
                        name="ENTRY",
                        text=entry_texts,
                        hovertext=entry_hover,
                        hoverinfo='text',
                        textposition='top center',
                        marker=dict(color='lime', size=14, symbol='triangle-up', line=dict(color='darkgreen', width=2)),
                        textfont=dict(size=10, color='darkgreen'),
                        visible=True
                    ),
                    row=1, col=1
                )
            
            # ADD
            df_add = df_trades[df_trades[action_col] == 'ADD']
            if not df_add.empty:
                add_texts = df_add.apply(
                    lambda row: f"ADD<br>Price: {row['close_price']:.2f}", 
                    axis=1
                )
                # ホバー情報の準備
                add_hover = df_add.apply(
                    lambda row: f"<b>ADD</b><br>時刻: {row.get('real_time_dt', '')}<br>追加価格: {row['close_price']:.2f}<br>平均購入価格: {row.get('avg_entry_price', 'N/A')}", 
                    axis=1
                )
                fig.add_trace(
                    go.Scatter(
                        x=df_add['real_time_dt'],
                        y=df_add['close_price'],
                        mode='markers+text',
                        name="ADD",
                        text=add_texts,
                        hovertext=add_hover,
                        hoverinfo='text',
                        textposition='top center',
                        marker=dict(color='yellow', size=12, symbol='circle', line=dict(color='orange', width=2)),
                        textfont=dict(size=9, color='orange'),
                        visible=True
                    ),
                    row=1, col=1
                )
            
            # EXIT
            df_exit = df_trades[df_trades[action_col] == 'EXIT']
            if not df_exit.empty:
                exit_texts = df_exit.apply(
                    lambda row: f"EXIT<br>Price: {row['close_price']:.2f}", 
                    axis=1
                )
                # ホバー情報の準備
                exit_hover = df_exit.apply(
                    lambda row: f"<b>EXIT</b><br>時刻: {row.get('real_time_dt', '')}<br>清算価格: {row['close_price']:.2f}<br>平均購入価格: {row.get('avg_entry_price', 'N/A')}", 
                    axis=1
                )
                fig.add_trace(
                    go.Scatter(
                        x=df_exit['real_time_dt'],
                        y=df_exit['close_price'],
                        mode='markers+text',
                        name="EXIT",
                        text=exit_texts,
                        hovertext=exit_hover,
                        hoverinfo='text',
                        textposition='bottom center',
                        marker=dict(color='red', size=14, symbol='triangle-down', line=dict(color='darkred', width=2)),
                        textfont=dict(size=10, color='darkred'),
                        visible=True
                    ),
                    row=1, col=1
                )
        
        # === Row 2: ボリューム (Volume Bar) ===
        
        if 'Volume' in df.columns and df['Volume'].notna().any():
            fig.add_trace(
                go.Bar(
                    x=df['real_time_dt'],
                    y=df['Volume'],
                    name="Volume",
                    marker=dict(color='steelblue'),
                    visible=True,
                    showlegend=True
                ),
                row=2, col=1
            )
        
        # === Row 3: テクニカル指標 (Volatility / PVO / ADX) ===
        
        # Volatility (ボラティリティ)
        if 'volatility' in df.columns:
            vol_data = df['volatility'].copy()
            if normalize_indicators:
                vol_data = self._normalize_series(vol_data)
            fig.add_trace(
                go.Scatter(
                    x=df['real_time_dt'],
                    y=vol_data,
                    mode='lines',
                    name="Volatility (標準化)" if normalize_indicators else "Volatility",
                    line=dict(color='purple', width=1),
                    visible=True
                ),
                row=3, col=1
            )
        
        # PVO (Percentage Volume Oscillator)
        if 'pvo_val' in df.columns:
            pvo_data = df['pvo_val'].copy()
            if normalize_indicators:
                pvo_data = self._normalize_series(pvo_data)
            fig.add_trace(
                go.Scatter(
                    x=df['real_time_dt'],
                    y=pvo_data,
                    mode='lines',
                    name="PVO (標準化)" if normalize_indicators else "PVO",
                    line=dict(color='cyan', width=1),
                    visible=True
                ),
                row=3, col=1
            )
        elif 'pvo' in df.columns:
            pvo_data = df['pvo'].copy()
            if normalize_indicators:
                pvo_data = self._normalize_series(pvo_data)
            fig.add_trace(
                go.Scatter(
                    x=df['real_time_dt'],
                    y=pvo_data,
                    mode='lines',
                    name="PVO (標準化)" if normalize_indicators else "PVO",
                    line=dict(color='cyan', width=1),
                    visible=True
                ),
                row=3, col=1
            )
        
        # Row 3: ADX (テクニカル指標系)
        if 'adx' in df.columns:
            adx_data = df['adx'].copy()
            if normalize_indicators:
                adx_data = self._normalize_series(adx_data)
            fig.add_trace(
                go.Scatter(
                    x=df['real_time_dt'],
                    y=adx_data,
                    mode='lines',
                    name="ADX (標準化)" if normalize_indicators else "ADX",
                    line=dict(color='orange', width=1.5),
                    visible=True
                ),
                row=3, col=1
            )
        
        # === Row 4: 累積損益 (PnL) ===
        # 実績PnL (確定損益)
        if 'total_profit_and_loss' in df.columns:
            fig.add_trace(
                go.Scatter(
                    x=df['real_time_dt'],
                    y=df['total_profit_and_loss'],
                    mode='lines',
                    name="実績PnL (確定損益)",
                    line=dict(color='darkblue', width=2.5),
                    fill='tozeroy',
                    fillcolor='rgba(0,100,255,0.1)',
                    visible=True
                ),
                row=4, col=1
            )
        
        # 未決済益 (みなし損益) を合算したPnL
        if 'total_profit_and_loss' in df.columns and 'profit_and_loss' in df.columns:
            # 実績PnL + みなし損益 = トータルPnL
            df['total_pnl_with_unrealized'] = df['total_profit_and_loss'] + df['profit_and_loss']
            fig.add_trace(
                go.Scatter(
                    x=df['real_time_dt'],
                    y=df['total_pnl_with_unrealized'],
                    mode='lines',
                    name="トータルPnL (含む未決済)",
                    line=dict(color='orange', width=2, dash='dash'),
                    visible=True
                ),
                row=4, col=1
            )
        
        # PnLゼロライン
        fig.add_hline(y=0, line_dash="dash", line_color="gray", row=4, col=1)
        
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
        fig.update_yaxes(title_text="ボリューム", row=2, col=1)
        y_label_row3 = "テクニカル指標値 (標準化)" if normalize_indicators else "テクニカル指標値"
        fig.update_yaxes(title_text=y_label_row3, row=3, col=1)
        fig.update_yaxes(title_text="累積損益 (USD)", row=4, col=1)
        
        # HTML出力
        fig.write_html(output_html, include_plotlyjs='cdn')
        print(f"Interactive chart saved: {output_html}")
        
        return fig
    
    def visualize_backtest(self, log_directory="logs", output_html="report/backtest_visualization.html", 
                          start_time=None, end_time=None, normalize_indicators=True):
        """
        バックテスト結果を可視化 (メインエントリポイント)
        
        計算用の拡張期間でデータを読み込み、表示用期間のみでグラフを出力
        
        Args:
            log_directory: ログディレクトリ
            output_html: 出力HTMLファイル名（デフォルト: report/backtest_visualization.html）
            start_time: 表示開始時刻 (datetime or str "%Y/%m/%d %H:%M")
            end_time: 表示終了時刻 (datetime or str "%Y/%m/%d %H:%M")
            normalize_indicators: True=標準化, False=元の値 (デフォルト: True)
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
        
        print(f"Loading logs from {log_directory} (display period: {start_time} to {end_time})...")
        
        # 計算用の拡張期間でデータを読み込む
        df_calc, df_display, display_start, display_end = self.load_logs_data(
            log_directory, start_time, end_time, lookback_days=20
        )
        
        if df_calc is None or df_calc.empty:
            print("No data to visualize")
            return
        
        print(f"Loaded {len(df_calc)} records for calculation (including lookback period)")
        print(f"Display period: {len(df_display)} records")
        
        # タイムフレームのローソク足作成 (計算用データから作成)
        print(f"Preparing {self.time_frame_label} candles (no thinning)...")
        candles_2h_calc = self.resample_to_candles(df_calc)
        
        if candles_2h_calc is not None:
            print(f"Created {len(candles_2h_calc)} {self.time_frame_label} candles (including lookback)")
            # 表示用期間のみに絞る
            if 'real_time_dt' in candles_2h_calc.columns:
                mask = (candles_2h_calc['real_time_dt'] >= display_start) & (candles_2h_calc['real_time_dt'] <= display_end)
                candles_2h_display = candles_2h_calc.loc[mask].copy()
                print(f"Display candles: {len(candles_2h_display)}")
            else:
                candles_2h_display = candles_2h_calc
        else:
            candles_2h_display = None
        
        # チャート生成（表示用データ + 計算用データ for 指標）
        print("Generating interactive chart...")
        self.create_interactive_chart(df_display, candles_2h_display, output_html, normalize_indicators=normalize_indicators)
        
        print("Done!")


if __name__ == "__main__":
    visualizer = Visualizer()
    
    # config.iniの期間で可視化
    log_directory = "logs"
    output_html = "../report/backtest_visualization.html"
    
    # コマンドライン引数で標準化の ON/OFF を制御
    # デフォルト: True (標準化ON)
    # 使用方法: python3 visualizer.py False
    normalize_indicators = True
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg in ['false', '0', 'no', 'off']:
            normalize_indicators = False
    
    # 出力ディレクトリを確保
    output_dir = os.path.dirname(output_html)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    print("\n🎬 バックテスト可視化を開始します")
    print(f"📂 ログディレクトリ: {log_directory}")
    print(f"📊 指標標準化: {'ON (Volatility/PVO/ADXを正規化)' if normalize_indicators else 'OFF (元の値)'}")
    if not normalize_indicators:
        print(f"   - 標準化ON: python3 visualizer.py True")
    
    try:
        visualizer.visualize_backtest(
            log_directory=log_directory,
            output_html=output_html,
            normalize_indicators=normalize_indicators
        )
        
        abs_path = os.path.abspath(output_html)
        print(f"\n✅ 可視化完了!")
        print(f"📊 ファイル: {output_html}")
        print(f"🌐 ブラウザで開く: {abs_path}")
        
    except Exception as e:
        print(f"\n❌ エラー: {e}")
        import traceback
        traceback.print_exc()
