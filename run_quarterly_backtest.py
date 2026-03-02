#!/usr/bin/env python3
"""
四半期別バックテスト実行スクリプト

2024/1Q ～ 現在までのすべての四半期について、
バックテストを実行し、成績を一覧で表示します。

使用方法:
  python run_quarterly_backtest.py
  python run_quarterly_backtest.py 2024 1  # 特定の四半期のみ実行
"""

import os
import sys
import json
import subprocess
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import shutil

# ワークスペースルート設定
WORKSPACE_ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(WORKSPACE_ROOT, "src")
CONFIG_FILE = os.path.join(SRC_DIR, "config.ini")
OUTPUT_DIR = os.path.join(WORKSPACE_ROOT, "docs/quarterly_backtest_results")

# 結果ディレクトリ作成
os.makedirs(OUTPUT_DIR, exist_ok=True)


def get_quarters():
    """2024/1Q ～ 2025/4Q までの四半期リストを返す"""
    quarters = []
    start = datetime(2024, 1, 1)   # 2024/Q1 から開始
    end = datetime(2025, 12, 31)   # 2025/Q4 まで（フルカバレッジ）
    
    # 現在日時が終了日より前の場合は、現在日時を終了日とする
    now = datetime.now()
    if now < end:
        end = now
    
    current = start
    while current <= end:
        q = (current.month - 1) // 3 + 1
        year = current.year
        quarters.append((year, q))
        current += relativedelta(months=3)
    
    return quarters


def verify_backtest_mode():
    """
    config.ini の back_test = 1 であることを確認する
    
    Returns:
        bool: back_test = 1 の場合 True、それ以外 False
    """
    if not os.path.exists(CONFIG_FILE):
        print(f"❌ エラー: config.ini が見つかりません")
        print(f"   場所: {CONFIG_FILE}")
        return False
    
    back_test_mode = None
    risk_percentage = None
    leverage = None
    
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('back_test ='):
                    parts = line.split('=')
                    if len(parts) == 2:
                        try:
                            back_test_mode = int(parts[1].strip())
                        except ValueError:
                            pass
                elif line.startswith('risk_percentage ='):
                    parts = line.split('=')
                    if len(parts) == 2:
                        try:
                            risk_percentage = float(parts[1].strip())
                        except ValueError:
                            pass
                elif line.startswith('leverage ='):
                    parts = line.split('=')
                    if len(parts) == 2:
                        try:
                            leverage = int(parts[1].strip())
                        except ValueError:
                            pass
    except Exception as e:
        print(f"❌ エラー: config.ini の読み込みに失敗しました: {e}")
        return False
    
    if back_test_mode is None:
        print(f"❌ エラー: config.ini に 'back_test' パラメータが見つかりません")
        print(f"   確認場所: {CONFIG_FILE}")
        print(f"   必須設定: back_test = 1")
        return False
    
    if back_test_mode == 1:
        print(f"✅ config.ini 設定確認:")
        print(f"   - back_test = 1 (バックテストモード)")
        if risk_percentage is not None:
            print(f"   - risk_percentage = {risk_percentage} ({risk_percentage*100:.0f}%)")
        if leverage is not None:
            print(f"   - leverage = {leverage}倍")
        return True
    else:
        print(f"❌ エラー: config.ini の back_test が 1 に設定されていません")
        print(f"   現在の値: back_test = {back_test_mode}")
        print(f"   必須設定: back_test = 1")
        print(f"")
        print(f"修正方法:")
        print(f"  1. {CONFIG_FILE} を開く")
        print(f"  2. '[Backtest]' セクション内の 'back_test' を 1 に変更")
        print(f"  3. ファイルを保存")
        print(f"  4. 再度このスクリプトを実行")
        return False


def get_quarter_dates(year, q):
    """四半期の開始日と終了日を返す"""
    q_start = datetime(year, (q-1)*3 + 1, 1)
    q_end = (q_start + relativedelta(months=3)) - timedelta(seconds=1)
    
    if q_end > datetime.now():
        q_end = datetime.now()
    
    return q_start, q_end


def update_config(year, q):
    """config.ini の期間を指定の四半期に更新"""
    q_start, q_end = get_quarter_dates(year, q)
    start_str = q_start.strftime("%Y/%m/%d %H:%M")
    end_str = q_end.strftime("%Y/%m/%d %H:%M")
    
    # config.ini を読む
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Period セクションを更新
    lines = content.split('\n')
    new_lines = []
    in_period = False
    
    for line in lines:
        if line.strip().startswith('[Period]'):
            in_period = True
            new_lines.append(line)
        elif line.strip().startswith('['):
            in_period = False
            new_lines.append(line)
        elif in_period and line.strip().startswith('start_time'):
            new_lines.append(f"start_time = {start_str}")
        elif in_period and line.strip().startswith('end_time'):
            new_lines.append(f"end_time = {end_str}")
        else:
            new_lines.append(line)
    
    # config.ini に書き込む
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_lines))
    
    return start_str, end_str


def run_backtest(year, q, start_str, end_str):
    """バックテストを実行し、結果を返す"""
    print(f"\n🚀 バックテスト実行: Q{q} {year} ({start_str} ～ {end_str})")
    
    os.chdir(SRC_DIR)
    
    # 環境変数でログディレクトリを指定（Q別ロギング用）
    env = os.environ.copy()
    env['QUARTERLY_LOG_PREFIX'] = f"Q{q}_{year}"
    
    try:
        # bot.py を直接実行（bot_run.sh は削除済み）
        result = subprocess.run(
            ['python', 'bot.py'],
            capture_output=True,
            text=True,
            timeout=600,
            env=env
        )
        
        # # デバッグ用：stdout出力を表示（Time-Based Exit検証用）
        # debug_keywords = ["Time-Based Exit", "🕐", "⏰", "📍"]
        # if any(kw in result.stdout for kw in debug_keywords):
        #     print(f"   [DEBUG] Time-Based Exit関連出力:")
        #     lines = result.stdout.split('\n')
        #     for i, line in enumerate(lines):
        #         if any(kw in line for kw in debug_keywords):
        #             # マッチした行の前後2行を含めて表示
        #             start = max(0, i-1)
        #             end = min(len(lines), i+4)
        #             for j in range(start, end):
        #                 print(f"      {lines[j]}")
        #             print(f"      ---")
        
        if result.returncode != 0:
            print(f"   ❌ バックテスト失敗")
            return None
        
        # ログファイルから結果を抽出
        import glob
        
        # backtest_summary_*.json を優先的に探す
        summary_logs = glob.glob('logs/backtest_summary_*.json')
        if summary_logs:
            latest_log = max(summary_logs, key=os.path.getmtime)
        else:
            # 見つからない場合は全JSONファイルから探す
            log_files = glob.glob('logs/*.json')
            if not log_files:
                print(f"   ⚠️  ログファイルが見つかりません")
                return None
            # backtest_summary 以外のファイルを除外
            log_files = [f for f in log_files if 'backtest_summary' not in f]
            if not log_files:
                print(f"   ⚠️  有効なログファイルが見つかりません")
                return None
            latest_log = max(log_files, key=os.path.getctime)
        
        with open(latest_log, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # ログファイル形式の確認と正規化
        if isinstance(data, list):
            # list 形式の場合は無視（古い形式）
            print(f"   ⚠️  ログファイル形式が古い形式です（list）")
            return None
        elif isinstance(data, dict):
            metrics = data
        else:
            print(f"   ⚠️  ログファイル形式が不正です")
            return None
        
        # Trade Log ファイルを Q別ディレクトリにコピー
        trade_log_files = glob.glob('logs/trade_log_*.json')
        if trade_log_files:
            quarterly_logs_dir = os.path.join(WORKSPACE_ROOT, "logs/quarterly")
            os.makedirs(quarterly_logs_dir, exist_ok=True)
            
            copied_count = 0
            for trade_log in trade_log_files:
                try:
                    basename = os.path.basename(trade_log)
                    # ファイル名に Q情報を挿入: trade_log_YYYYMMDD_HHMMSS.json → Q1_2024_trade_log_YYYYMMDD_HHMMSS.json
                    new_basename = f"Q{q}_{year}_{basename}"
                    dest = os.path.join(quarterly_logs_dir, new_basename)
                    shutil.copy2(trade_log, dest)
                    copied_count += 1
                except Exception as e:
                    print(f"   ⚠️  Trade Log コピーエラー: {e}")
            
            # コピー完了を1行で表示
            if copied_count > 0:
                print(f"   📁 Trade Log を {copied_count} 件バックアップ")
            
            # 古い四半期ログを削除（同一四半期の古い実行結果のみ保持最小限に）
            try:
                quarterly_prefix = f"Q{q}_{year}_"
                quarterly_files = [
                    f for f in os.listdir(quarterly_logs_dir) 
                    if f.startswith(quarterly_prefix)
                ]
                
                # タイムスタンプでソート（新しい順）
                quarterly_files.sort(reverse=True)
                
                # 最新8ファイル以外を削除（通常1四半期あたり1-2ファイル）
                files_to_keep = 8
                if len(quarterly_files) > files_to_keep:
                    deleted_count = 0
                    for old_file in quarterly_files[files_to_keep:]:
                        old_path = os.path.join(quarterly_logs_dir, old_file)
                        os.remove(old_path)
                        deleted_count += 1
                    
                    if deleted_count > 0:
                        print(f"   🗑️  古いログ {deleted_count} 件を削除")
            except Exception as e:
                print(f"   ⚠️  古いログ削除エラー: {e}")
        
        print(f"   ✅ バックテスト完了")
        print(f"      - 総損益: {metrics.get('total_pnl', 'N/A')} USD")
        print(f"      - 利益因子: {metrics.get('profit_factor', 'N/A')}")
        print(f"      - 最大DD率: {metrics.get('max_drawdown_rate', 'N/A')}%")
        print(f"      - Sharpe: {metrics.get('sharpe', 'N/A')}")
        print(f"      - 勝率: {metrics.get('win_rate', 'N/A')}%")
        
        return metrics
    
    except subprocess.TimeoutExpired:
        print(f"   ❌ バックテストタイムアウト（600秒超過）")
        return None
    except Exception as e:
        print(f"   ❌ エラー: {e}")
        return None
    finally:
        os.chdir(WORKSPACE_ROOT)


def save_results(results):
    """結果をJSON形式で保存"""
    output_file = os.path.join(OUTPUT_DIR, f"quarterly_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    return output_file


def print_summary(results):
    """結果の要約を表示"""
    print("\n" + "=" * 100)
    print("📊 四半期別バックテスト成績一覧")
    print("=" * 100)
    
    print("\n{:<12} {:<15} {:<15} {:<15} {:<12} {:<12}".format(
        "期間", "総損益 (USD)", "利益因子", "最大DD率", "Sharpe", "勝率"
    ))
    print("-" * 100)
    
    total_pnl = 0
    successful_quarters = 0
    
    for result in results:
        if result['metrics']:
            q_str = f"Q{result['quarter']} {result['year']}"
            total_pnl_val = result['metrics'].get('total_pnl', 0)
            total_pnl += total_pnl_val
            successful_quarters += 1
            
            # max_drawdown_rate（%）を使用（修正済み：初期資産込み計算で100%以下）
            max_dd_rate = result['metrics'].get('max_drawdown_rate', 0)
            
            print("{:<12} {:<15.2f} {:<15.3f} {:<14.2f}% {:<12.3f} {:<12.2f}%".format(
                q_str,
                total_pnl_val,
                result['metrics'].get('profit_factor', 0),
                max_dd_rate,
                result['metrics'].get('sharpe', 0),
                result['metrics'].get('win_rate', 0)
            ))
        else:
            q_str = f"Q{result['quarter']} {result['year']}"
            print("{:<12} {:<15} {:<15} {:<15} {:<12} {:<12}".format(
                q_str, "失敗", "-", "-", "-", "-"
            ))
    
    print("-" * 100)
    print(f"\n📈 統計:")
    print(f"  - 成功した四半期: {successful_quarters}/{len(results)}")
    print(f"  - 累積損益: {total_pnl:.2f} USD")
    print(f"  - 平均四半期損益: {total_pnl / successful_quarters if successful_quarters > 0 else 0:.2f} USD")
    print()


def main():
    print("=" * 100)
    print("🎯 四半期別バックテスト実行")
    print("=" * 100)
    
    # config.ini の back_test = 1 を確認
    print("\n🔍 バックテスト設定確認")
    if not verify_backtest_mode():
        print("\n❌ バックテスト実行中止\n")
        sys.exit(1)
    
    # 引数チェック
    target_quarters = None
    if len(sys.argv) > 2:
        try:
            year = int(sys.argv[1])
            q = int(sys.argv[2])
            if 2024 <= year <= datetime.now().year and 1 <= q <= 4:
                target_quarters = [(year, q)]
        except ValueError:
            pass
    
    quarters = target_quarters if target_quarters else get_quarters()
    results = []
    
    print(f"\n対象四半期: {len(quarters)}\n")
    
    # ログディレクトリを表示
    quarterly_logs_dir = os.path.join(WORKSPACE_ROOT, "logs/quarterly")
    print(f"📁 ログ出力先: {quarterly_logs_dir}\n")
    
    for year, q in quarters:
        q_start, q_end = get_quarter_dates(year, q)
        start_str = q_start.strftime("%Y/%m/%d %H:%M")
        end_str = q_end.strftime("%Y/%m/%d %H:%M")
        
        # config.ini を更新
        print(f"\n📝 設定更新: Q{q} {year}")
        update_config(year, q)
        print(f"   ✅ config.ini を更新しました")
        
        # バックテスト実行
        metrics = run_backtest(year, q, start_str, end_str)
        
        results.append({
            'year': year,
            'quarter': q,
            'start_date': start_str,
            'end_date': end_str,
            'metrics': metrics,
            'timestamp': datetime.now().isoformat()
        })
    
    # 結果を表示
    print_summary(results)
    
    # 結果をファイルに保存
    output_file = save_results(results)
    print(f"✅ 結果を保存しました: {output_file}")
    
    # ログファイルの確認（要約情報のみ）
    print(f"\n📊 Q別ログファイル要約:")
    if os.path.exists(quarterly_logs_dir):
        log_files = os.listdir(quarterly_logs_dir)
        if log_files:
            total_size_mb = sum(
                os.path.getsize(os.path.join(quarterly_logs_dir, f)) 
                for f in log_files
            ) / (1024 * 1024)
            print(f"  ✓ ファイル数: {len(log_files)} 件")
            print(f"  ✓ 合計サイズ: {total_size_mb:.1f} MB")
            print(f"  ✓ 保存先: {quarterly_logs_dir}")
        else:
            print(f"  (ログファイルなし)")
    
    return results


if __name__ == '__main__':
    main()
