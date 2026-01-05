#!/usr/bin/env python3
"""
未来情報混入チェッカー
トレードログを分析して、エントリー時に未来の情報を使用していないかチェック
"""

import json
import glob
from pathlib import Path
from datetime import datetime

QUARTERLY_LOGS_DIR = 'logs/quarterly'

def load_latest_trade_logs():
    """最新のQ別ログファイルをすべて読み込む"""
    log_files = glob.glob(f"{QUARTERLY_LOGS_DIR}/Q*_trade_log_*.json")
    
    # 各Qの最新ファイルを取得
    latest_files = {}
    for f in log_files:
        basename = Path(f).name
        prefix = '_'.join(basename.split('_')[:2])
        
        if prefix not in latest_files:
            latest_files[prefix] = f
        else:
            current_timestamp = basename.split('_')[-1].replace('.json', '')
            existing_timestamp = Path(latest_files[prefix]).name.split('_')[-1].replace('.json', '')
            
            if current_timestamp > existing_timestamp:
                latest_files[prefix] = f
    
    # すべてのトレードを収集
    all_trades = []
    for q_prefix, filepath in sorted(latest_files.items()):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                trades = data.get('trades', [])
                
                # Q情報を追加
                for trade in trades:
                    trade['quarter'] = q_prefix
                    trade['log_file'] = filepath
                
                all_trades.extend(trades)
        except Exception as e:
            print(f"✗ {q_prefix}: エラー - {e}")
    
    return all_trades


def check_future_information_leakage(trades):
    """
    未来情報の混入をチェック
    
    Args:
        trades (list): トレードログのリスト
    
    Returns:
        dict: チェック結果
    """
    print("\n" + "=" * 100)
    print("🔍 未来情報混入チェック")
    print("=" * 100)
    
    issues = []
    warnings = []
    
    for idx, trade in enumerate(trades):
        trade_id = f"{trade.get('quarter', 'UNKNOWN')}_#{idx+1}"
        entry = trade.get('entry', {})
        exit_data = trade.get('exit', {})
        result = trade.get('result', {})
        
        # チェック1: エントリー時にエグジット情報を参照していないか
        if 'exit_price' in entry or 'exit_timestamp' in entry:
            issues.append({
                'severity': 'CRITICAL',
                'type': 'FUTURE_LEAK',
                'trade_id': trade_id,
                'description': 'エントリー時にエグジット情報が含まれています',
                'details': 'entry に exit_price または exit_timestamp が存在'
            })
        
        # チェック2: エントリー時にPnL情報を参照していないか
        if 'pnl' in entry or 'pnl_usd' in entry or 'pnl_pct' in entry:
            issues.append({
                'severity': 'CRITICAL',
                'type': 'PNL_LEAK',
                'trade_id': trade_id,
                'description': 'エントリー時にPnL情報が含まれています',
                'details': 'entry に pnl 関連フィールドが存在'
            })
        
        # チェック3: エントリー時にドローダウン情報を参照していないか
        if 'max_drawdown' in entry or 'drawdown' in entry:
            issues.append({
                'severity': 'CRITICAL',
                'type': 'DRAWDOWN_LEAK',
                'trade_id': trade_id,
                'description': 'エントリー時にドローダウン情報が含まれています',
                'details': 'entry に drawdown 関連フィールドが存在'
            })
        
        # チェック4: フィルター値のタイムスタンプチェック
        # （現在のログ構造では詳細なタイムスタンプがないため、簡易チェック）
        filters = entry.get('filters', {})
        entry_timestamp = entry.get('timestamp', '')
        
        # 注意: 現在の実装では各フィルター値が本当にエントリー時点より前の
        # データから計算されたかを完全に検証することはできない
        # これは将来的に各指標のタイムスタンプを記録することで改善可能
        
        # チェック5: エントリー判定に使用される指標が確定済みかどうか
        # 例: ドンチャンブレイクは現在の足が確定してからしか判定できない
        signals = entry.get('signals', {})
        donchian_signal = signals.get('donchian_signal', False)
        
        # 警告レベル: 現在の実装で確定判定が適切かチェック
        # （現在の bot.py では足確定前にエントリー判定している可能性がある）
        if donchian_signal:
            warnings.append({
                'severity': 'WARNING',
                'type': 'CONFIRMATION_CHECK',
                'trade_id': trade_id,
                'description': 'ドンチャンブレイク判定のタイミングを確認してください',
                'details': '現在の足が確定する前に判定していないか確認が必要'
            })
    
    # 結果サマリー
    print(f"\n📊 チェック結果:")
    print(f"  検査トレード数: {len(trades)}")
    print(f"  重大な問題: {len(issues)}")
    print(f"  警告: {len(warnings)}")
    
    if len(issues) == 0 and len(warnings) == 0:
        print(f"\n✅ 未来情報の混入は検出されませんでした")
    else:
        if issues:
            print(f"\n🔴 重大な問題が検出されました:")
            for issue in issues[:10]:  # 最初の10件を表示
                print(f"\n  [{issue['severity']}] {issue['type']}")
                print(f"    トレード: {issue['trade_id']}")
                print(f"    説明: {issue['description']}")
                print(f"    詳細: {issue['details']}")
            
            if len(issues) > 10:
                print(f"\n  ... 他 {len(issues) - 10} 件")
        
        if warnings:
            print(f"\n⚠️  警告が検出されました:")
            for warning in warnings[:5]:  # 最初の5件を表示
                print(f"\n  [{warning['severity']}] {warning['type']}")
                print(f"    トレード: {warning['trade_id']}")
                print(f"    説明: {warning['description']}")
                print(f"    詳細: {warning['details']}")
            
            if len(warnings) > 5:
                print(f"\n  ... 他 {len(warnings) - 5} 件")
    
    return {
        'clean': len(issues) == 0,
        'issues': issues,
        'warnings': warnings,
        'total_checks': len(trades)
    }


def check_indicator_calculation_timing():
    """
    指標計算のタイミングをチェック
    
    各指標が本当に「直前の確定した足」のデータを使って計算されているか確認
    """
    print("\n" + "=" * 100)
    print("🕐 指標計算タイミングチェック")
    print("=" * 100)
    
    checks = []
    
    # チェック項目
    check_items = [
        {
            'indicator': 'PVO (Price Volume Oscillator)',
            'requirement': '直前の確定した足までの出来高データを使用',
            'implementation': 'price_data_management.py の get_pvo() を確認',
            'status': '要確認'
        },
        {
            'indicator': 'ADX (Average Directional Index)',
            'requirement': '直前の確定した足までのOHLCデータを使用',
            'implementation': 'price_data_management.py の get_adx() を確認',
            'status': '要確認'
        },
        {
            'indicator': 'Donchian Channel',
            'requirement': '直前の確定した足までの高値・安値を使用',
            'implementation': 'price_data_management.py の get_donchian_channel() を確認',
            'status': '要確認'
        },
        {
            'indicator': 'Volatility (ATR)',
            'requirement': '直前の確定した足までのOHLCデータを使用',
            'implementation': 'price_data_management.py の get_latest_volatility() を確認',
            'status': '要確認'
        },
        {
            'indicator': 'Volume Filter',
            'requirement': '直前の確定した足の出来高を使用',
            'implementation': 'price_data_management.py の get_volume() を確認',
            'status': '要確認'
        },
    ]
    
    print("\n指標計算タイミングの要件:")
    print("-" * 100)
    
    for item in check_items:
        print(f"\n📌 {item['indicator']}")
        print(f"   要件: {item['requirement']}")
        print(f"   実装: {item['implementation']}")
        print(f"   状態: {item['status']}")
    
    print("\n" + "-" * 100)
    print("\n⚠️  重要:")
    print("  1. バックテストでは過去の確定足を使うため問題ありませんが、")
    print("  2. リアルトレードでは「現在進行中の足」のデータを使わないよう注意が必要です")
    print("  3. エントリー判定は必ず「足確定後」に行う必要があります")
    
    print("\n💡 推奨事項:")
    print("  - price_data_management.py の各指標計算メソッドで")
    print("    ohlcv_df.iloc[-2] または ohlcv_df[:-1] を使用しているか確認")
    print("  - bot.py のメインループで足確定タイミングを判定")
    print("  - テストモードで実際の挙動を確認")
    
    return check_items


def main():
    print("\n" + "=" * 100)
    print("🛡️  未来情報混入チェックシステム")
    print("=" * 100)
    
    # トレードログをロード
    print(f"\n📂 Q別ログファイルを読み込み中...")
    trades = load_latest_trade_logs()
    
    if not trades:
        print("❌ エラー: トレードログが見つかりません")
        return
    
    print(f"✅ 合計 {len(trades)} トレードを読み込みました")
    
    # 未来情報混入チェック
    leak_check = check_future_information_leakage(trades)
    
    # 指標計算タイミングチェック
    timing_check = check_indicator_calculation_timing()
    
    # 最終判定
    print("\n" + "=" * 100)
    print("📋 最終判定")
    print("=" * 100)
    
    if leak_check['clean']:
        print("\n✅ トレードログレベル: クリーン")
        print("   エントリー時に未来情報の混入は検出されませんでした")
    else:
        print("\n❌ トレードログレベル: 問題あり")
        print(f"   {len(leak_check['issues'])} 件の重大な問題が検出されました")
        print("   ログ構造を修正してください")
    
    if leak_check['warnings']:
        print(f"\n⚠️  {len(leak_check['warnings'])} 件の警告があります")
        print("   実装レベルでの確認が必要です")
    
    print("\n💡 次のステップ:")
    print("  1. price_data_management.py の各指標計算メソッドを確認")
    print("  2. bot.py のエントリー判定タイミングを確認")
    print("  3. DUMMYモードでリアルタイム動作をテスト")
    
    print("\n" + "=" * 100)


if __name__ == '__main__':
    main()
