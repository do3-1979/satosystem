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
import argparse
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import shutil

# ワークスペースルート設定
WORKSPACE_ROOT = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(WORKSPACE_ROOT, "src")

# デフォルト値（main()でargs により上書き）
CONFIG_FILE = os.path.join(SRC_DIR, "config.ini")
OUTPUT_DIR = os.path.join(WORKSPACE_ROOT, "docs/quarterly_backtest_results")


def get_market_from_config(config_file):
    """config.ini から market シンボルを取得して正規化名を返す"""
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('market =') or line.startswith('market='):
                    val = line.split('=', 1)[1].strip()
                    # XAUT/USDT → XAUT, BTC/USDT → BTC
                    return val.split('/')[0].strip()
    except Exception:
        pass
    return "BTC"


def get_quarters(symbol="BTC"):
    """シンボルに応じた四半期リストを返す"""
    quarters = []
    # BTC: 2024/Q1 から開始、XAUT: データ開始が 2025/04 なので 2025/Q2 から
    if symbol == "XAUT":
        start = datetime(2025, 4, 14)  # XAUT データ開始2025-04-03から初期ルックバック(40*4H=6.7日)を確保するため
    else:
        start = datetime(2024, 1, 1)   # 2024/Q1 から開始
    end = datetime(2026, 3, 31)    # 2026/Q1 まで（フルカバレッジ）

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


def verify_backtest_mode(config_file=None):
    """
    config.ini の back_test = 1 であることを確認する

    Returns:
        bool: back_test = 1 の場合 True、それ以外 False
    """
    if config_file is None:
        config_file = CONFIG_FILE
    if not os.path.exists(config_file):
        print(f"❌ エラー: config.ini が見つかりません")
        print(f"   場所: {CONFIG_FILE}")
        return False
    
    back_test_mode = None
    risk_percentage = None
    leverage = None

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
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
        print(f"❌ エラー: {os.path.basename(config_file)} に 'back_test' パラメータが見つかりません")
        print(f"   確認場所: {config_file}")
        print(f"   必須設定: back_test = 1")
        return False

    if back_test_mode == 1:
        print(f"✅ {os.path.basename(config_file)} 設定確認:")
        print(f"   - back_test = 1 (バックテストモード)")
        if risk_percentage is not None:
            print(f"   - risk_percentage = {risk_percentage} ({risk_percentage*100:.0f}%)")
        if leverage is not None:
            print(f"   - leverage = {leverage}倍")
        return True
    else:
        print(f"❌ エラー: {os.path.basename(config_file)} の back_test が 1 に設定されていません")
        print(f"   現在の値: back_test = {back_test_mode}")
        print(f"   必須設定: back_test = 1")
        return False


def get_quarter_dates(year, q, symbol="BTC"):
    """四半期の開始日と終了日を返す"""
    q_start = datetime(year, (q-1)*3 + 1, 1)
    # XAUT データ開始: 2025-04-03。初期ルックバック(40*4H=160H=6.7日)確保のため Q2 2025 は April 14 から
    if symbol == "XAUT" and year == 2025 and q == 2:
        q_start = datetime(2025, 4, 14)
    q_end = (q_start + relativedelta(months=3)) - timedelta(seconds=1)
    
    if q_end > datetime.now():
        q_end = datetime.now()
    
    return q_start, q_end


def update_config(year, q, config_file=None, symbol="BTC"):
    """指定した設定ファイルの期間を指定の四半期に更新"""
    if config_file is None:
        config_file = CONFIG_FILE
    q_start, q_end = get_quarter_dates(year, q, symbol=symbol)
    start_str = q_start.strftime("%Y/%m/%d %H:%M")
    end_str = q_end.strftime("%Y/%m/%d %H:%M")

    # config ファイルを読む
    with open(config_file, 'r', encoding='utf-8') as f:
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

    # config ファイルに書き込む
    with open(config_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_lines))

    return start_str, end_str


def run_backtest(year, q, start_str, end_str, config_name=None, symbol="BTC"):
    """バックテストを実行し、結果を返す"""
    print(f"\n🚀 バックテスト実行: Q{q} {year} ({start_str} ～ {end_str})")

    os.chdir(SRC_DIR)

    # 実行前に古い backtest_summary_*.json を削除（前回結果の混入防止）
    import glob as _glob
    for old_f in _glob.glob('logs/**/backtest_summary_*.json', recursive=True):
        try:
            os.remove(old_f)
        except Exception:
            pass

    # 環境変数でログディレクトリを指定（Q別ロギング用）
    env = os.environ.copy()
    env['QUARTERLY_LOG_PREFIX'] = f"Q{q}_{year}"

    try:
        # bot.py を直接実行（bot_run.sh は削除済み）
        cmd = ['python', 'bot.py']
        if config_name and config_name != 'config.ini':
            cmd += ['--config', config_name]
        result = subprocess.run(
            cmd,
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

        # backtest_summary_*.json を優先的に探す（サブディレクトリも含む）
        summary_logs = glob.glob('logs/**/backtest_summary_*.json', recursive=True)
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
        
        # Trade Log ファイルを Q別・シンボル別ディレクトリにコピー
        trade_log_files = glob.glob('logs/**/trade_log_*.json', recursive=True)
        if trade_log_files:
            quarterly_logs_dir = os.path.join(WORKSPACE_ROOT, "logs/quarterly", symbol)
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
        print(f"      - 総損益: {metrics.get('total_pnl', 'N/A')} USD  |  利益因子: {metrics.get('profit_factor', 'N/A')}")
        print(f"      - 最大DD率: {metrics.get('max_drawdown_rate', 'N/A')}%  |  Sharpe: {metrics.get('sharpe', 'N/A')}  |  Sortino: {metrics.get('sortino', 'N/A')}")
        print(f"      - 勝率: {metrics.get('win_rate', 'N/A')}%  |  PayoffR: {metrics.get('payoff_ratio', 'N/A')}  |  Expectancy: {metrics.get('expectancy', 'N/A')} USD")
        
        return metrics
    
    except subprocess.TimeoutExpired:
        print(f"   ❌ バックテストタイムアウト（600秒超過）")
        return None
    except Exception as e:
        print(f"   ❌ エラー: {e}")
        return None
    finally:
        os.chdir(WORKSPACE_ROOT)


def save_results(results, output_dir=None):
    """結果をJSON形式で保存"""
    if output_dir is None:
        output_dir = OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f"quarterly_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    return output_file


def compute_annual_metrics(quarterly_results):
    """複数の四半期結果から年間集計メトリクスを計算"""
    valid = [r for r in quarterly_results if r.get('metrics')]
    if not valid:
        return None
    
    total_pnl = sum(r['metrics'].get('total_pnl', 0) for r in valid)
    total_trades = sum(r['metrics'].get('trades', 0) for r in valid)
    total_wins = sum(
        round(r['metrics'].get('win_rate', 0) / 100.0 * r['metrics'].get('trades', 0))
        for r in valid
    )
    win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0.0
    
    # 最悪ドローダウン
    max_dd_rate = max((r['metrics'].get('max_drawdown_rate', 0) for r in valid), default=0.0)
    max_dd_usd = max((r['metrics'].get('max_drawdown', 0) for r in valid), default=0.0)
    
    # Sharpe: 加重平均（trades比率）
    sharpe_vals = [(r['metrics'].get('sharpe', 0), r['metrics'].get('trades', 0)) for r in valid]
    total_w = sum(w for _, w in sharpe_vals)
    sharpe_avg = sum(s * w for s, w in sharpe_vals) / total_w if total_w > 0 else 0.0
    
    # Sortino: 加重平均
    sortino_vals = [(r['metrics'].get('sortino', 0), r['metrics'].get('trades', 0)) for r in valid]
    sortino_avg = sum(s * w for s, w in sortino_vals) / total_w if total_w > 0 else 0.0
    
    # Profit Factor: 年間合算
    pf_vals = [r['metrics'].get('profit_factor', 0) for r in valid]
    pf_avg = sum(pf_vals) / len(pf_vals) if pf_vals else 0.0
    
    # Payoff Ratio: 加重平均
    pr_vals = [(r['metrics'].get('payoff_ratio', 0), r['metrics'].get('trades', 0)) for r in valid]
    pr_avg = sum(p * w for p, w in pr_vals) / total_w if total_w > 0 else 0.0
    
    # Expectancy: 加重平均
    exp_vals = [(r['metrics'].get('expectancy', 0), r['metrics'].get('trades', 0)) for r in valid]
    exp_avg = sum(e * w for e, w in exp_vals) / total_w if total_w > 0 else 0.0
    
    # Recovery Factor: 年間(総損益/最大DD)
    recovery = round(total_pnl / max_dd_usd, 3) if max_dd_usd > 0 else 0.0
    
    # Max Consec Losses
    max_consec = max((r['metrics'].get('max_consec_losses', 0) for r in valid), default=0)
    
    # 勝ち/負け四半期数
    profit_quarters = sum(1 for r in valid if r['metrics'].get('total_pnl', 0) > 0)
    
    return {
        "total_pnl": round(total_pnl, 3),
        "profit_factor_avg": round(pf_avg, 3),
        "max_drawdown_rate": round(max_dd_rate, 3),
        "max_drawdown": round(max_dd_usd, 3),
        "sharpe_avg": round(sharpe_avg, 3),
        "sortino_avg": round(sortino_avg, 3),
        "win_rate": round(win_rate, 2),
        "payoff_ratio_avg": round(pr_avg, 3),
        "expectancy_avg": round(exp_avg, 3),
        "recovery_factor": round(recovery, 3),
        "max_consec_losses": max_consec,
        "total_trades": total_trades,
        "profit_quarters": profit_quarters,
        "total_quarters": len(valid),
    }


def print_summary(results):
    """結果の要約を表示"""
    print("\n" + "=" * 120)
    print("📊 四半期別バックテスト成績一覧（拡張指標）")
    print("=" * 120)
    
    # 基本指標テーブル
    print("\n{:<12} {:<12} {:<10} {:<10} {:<10} {:<10} {:<10} {:<12} {:<8}".format(
        "期間", "損益(USD)", "PF", "MaxDD%", "Sharpe", "Sortino", "Recov.", "Expectancy", "勝率"
    ))
    print("-" * 120)
    
    total_pnl = 0
    successful_quarters = 0
    
    for result in results:
        if result['metrics']:
            q_str = f"Q{result['quarter']} {result['year']}"
            m = result['metrics']
            total_pnl_val = m.get('total_pnl', 0)
            total_pnl += total_pnl_val
            successful_quarters += 1
            
            print("{:<12} {:<12.2f} {:<10.3f} {:<9.2f}% {:<10.3f} {:<10.3f} {:<10.3f} {:<12.2f} {:<8.1f}%".format(
                q_str,
                total_pnl_val,
                m.get('profit_factor', 0),
                m.get('max_drawdown_rate', 0),
                m.get('sharpe', 0),
                m.get('sortino', 0),
                m.get('recovery_factor', 0),
                m.get('expectancy', 0),
                m.get('win_rate', 0),
            ))
        else:
            q_str = f"Q{result['quarter']} {result['year']}"
            print("{:<12} {:<12}".format(q_str, "失敗"))
    
    print("-" * 120)
    print(f"\n📈 統計:")
    print(f"  - 成功した四半期: {successful_quarters}/{len(results)}")
    print(f"  - 累積損益: {total_pnl:.2f} USD")
    print(f"  - 平均四半期損益: {total_pnl / successful_quarters if successful_quarters > 0 else 0:.2f} USD")
    
    # 年間評価を計算・表示
    results_2024 = [r for r in results if r['year'] == 2024 and r['metrics']]
    results_2025 = [r for r in results if r['year'] == 2025 and r['metrics']]
    results_2026 = [r for r in results if r['year'] == 2026 and r['metrics']]
    
    annual_evals = {}
    for year, qresults in [(2024, results_2024), (2025, results_2025), (2026, results_2026)]:
        if qresults:
            ann = compute_annual_metrics(qresults)
            annual_evals[year] = ann
            print(f"\n  📅 {year}年 通年評価:")
            print(f"     総損益: {ann['total_pnl']:.2f} USD  |  勝率: {ann['win_rate']:.1f}%  |  総トレード: {ann['total_trades']}")
            print(f"     PF平均: {ann['profit_factor_avg']:.3f}  |  最大DD率: {ann['max_drawdown_rate']:.2f}%  |  RecovFactor: {ann['recovery_factor']:.3f}")
            print(f"     Sharpe: {ann['sharpe_avg']:.3f}  |  Sortino: {ann['sortino_avg']:.3f}  |  PayoffRatio: {ann['payoff_ratio_avg']:.3f}")
            print(f"     期待値/取引: {ann['expectancy_avg']:.2f} USD  |  最大連続損失: {ann['max_consec_losses']}回  |  利益Q: {ann['profit_quarters']}/{ann['total_quarters']}")
    
    print()
    return annual_evals


def parse_args():
    """コマンドライン引数を解析する"""
    parser = argparse.ArgumentParser(description='四半期別バックテスト実行')
    parser.add_argument('--config', default='config.ini',
                        help='使用する設定ファイル名 (src/ 相対, デフォルト: config.ini)')
    parser.add_argument('year', nargs='?', type=int, help='特定の年 (省略可)')
    parser.add_argument('quarter', nargs='?', type=int, help='特定の四半期 1-4 (省略可)')
    return parser.parse_args()


def main():
    args = parse_args()

    # 設定ファイルパスを確定
    config_name = args.config  # ファイル名のみ (例: config.ini, config_xaut.ini)
    config_file = os.path.join(SRC_DIR, config_name)

    # シンボル名を設定ファイルから取得
    symbol = get_market_from_config(config_file)

    # シンボル別の出力ディレクトリ
    output_dir = os.path.join(WORKSPACE_ROOT, "docs/quarterly_backtest_results", symbol)
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 100)
    print(f"🎯 四半期別バックテスト実行  [{symbol}]")
    print("=" * 100)

    # config の back_test = 1 を確認
    print("\n🔍 バックテスト設定確認")
    if not verify_backtest_mode(config_file):
        print("\n❌ バックテスト実行中止\n")
        sys.exit(1)

    # 特定四半期指定チェック
    target_quarters = None
    if args.year and args.quarter:
        if 2024 <= args.year <= datetime.now().year and 1 <= args.quarter <= 4:
            target_quarters = [(args.year, args.quarter)]

    quarters = target_quarters if target_quarters else get_quarters(symbol)
    results = []

    print(f"\n対象四半期: {len(quarters)}\n")

    # ログディレクトリを表示
    quarterly_logs_dir = os.path.join(WORKSPACE_ROOT, "logs/quarterly", symbol)
    print(f"📁 ログ出力先: {quarterly_logs_dir}\n")
    os.makedirs(quarterly_logs_dir, exist_ok=True)

    for year, q in quarters:
        q_start, q_end = get_quarter_dates(year, q, symbol=symbol)
        start_str = q_start.strftime("%Y/%m/%d %H:%M")
        end_str = q_end.strftime("%Y/%m/%d %H:%M")

        # config ファイルを更新
        print(f"\n📝 設定更新: Q{q} {year}")
        update_config(year, q, config_file, symbol=symbol)
        print(f"   ✅ {config_name} を更新しました")

        # バックテスト実行
        metrics = run_backtest(year, q, start_str, end_str, config_name, symbol=symbol)

        results.append({
            'year': year,
            'quarter': q,
            'start_date': start_str,
            'end_date': end_str,
            'metrics': metrics,
            'timestamp': datetime.now().isoformat()
        })

    # 結果を表示
    annual_evals = print_summary(results)

    # 結果をファイルに保存（年間評価も含む）
    save_data = {
        "symbol": symbol,
        "config": config_name,
        "quarterly": results,
        "annual": {str(k): v for k, v in annual_evals.items()},
        "generated_at": datetime.now().isoformat(),
    }
    output_file = save_results(save_data, output_dir)
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
