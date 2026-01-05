#!/usr/bin/env python3
"""
フェーズ4: Core Logic Validation

Trade Log JSON データを使用して、以下を検証:
1. Volatility フィルター実装の正確性
2. Market Regime Detection ロジックの機能性
3. Strategy Signal 検出ロジックの有効性

実行方法:
  python3 tools/phase4_core_logic_validation.py
"""

import json
import os
import glob
from collections import defaultdict
from datetime import datetime
import statistics
import configparser

# logs/quarterly/ 内のすべてのファイルを取得
QUARTERLY_LOGS_DIR = os.path.join(os.path.dirname(__file__), '..', 'logs', 'quarterly')
CONFIG_FILE = os.path.join(os.path.dirname(__file__), '..', 'src', 'config.ini')


def load_config():
    """config.ini から機能の有効/無効状態を読み込む"""
    config = {
        'market_regime_detection': False,
        'seasonality_based_positioning': False,
        'volatility_filter': False
    }
    
    try:
        parser = configparser.ConfigParser()
        parser.read(CONFIG_FILE, encoding='utf-8')
        
        if parser.has_option('MarketRegime', 'enable_market_regime_detection'):
            config['market_regime_detection'] = int(parser.get('MarketRegime', 'enable_market_regime_detection')) == 1
        
        if parser.has_option('Seasonality', 'enable_seasonality_based_positioning'):
            config['seasonality_based_positioning'] = int(parser.get('Seasonality', 'enable_seasonality_based_positioning')) == 1
        
        if parser.has_option('EntryFilters', 'enable_volatility_filter'):
            config['volatility_filter'] = int(parser.get('EntryFilters', 'enable_volatility_filter')) == 1
    except Exception as e:
        print(f"⚠️  config.ini 読み込みエラー: {e}")
    
    return config


def get_latest_log_files():
    """各Qの最新ログファイルを取得"""
    log_files = glob.glob(os.path.join(QUARTERLY_LOGS_DIR, 'Q*_trade_log_*.json'))
    
    latest_files = {}
    for f in log_files:
        basename = os.path.basename(f)
        # Q1_2024_trade_log_20260105083735.json から Q1_2024 を抽出
        prefix = '_'.join(basename.split('_')[:2])
        
        if prefix not in latest_files:
            latest_files[prefix] = f
        else:
            # ファイル名のタイムスタンプで比較（より新しいものを保持）
            current_timestamp = basename.split('_')[-1].replace('.json', '')
            existing_timestamp = os.path.basename(latest_files[prefix]).split('_')[-1].replace('.json', '')
            
            if current_timestamp > existing_timestamp:
                latest_files[prefix] = f
    
    return latest_files


def load_trade_log(filepath):
    """Trade Log JSON を読み込む"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"エラー: {filepath} の読み込みに失敗しました: {e}")
        return None


def analyze_volatility_filter(trades):
    """Volatility フィルター分析"""
    if not trades:
        return None
    
    pass_trades = []
    fail_trades = []
    
    for trade in trades:
        volatility_filter = trade['entry']['filters'].get('volatility', {})
        is_pass = volatility_filter.get('pass', False)
        pnl = trade['result']['pnl_usd']
        
        if is_pass:
            pass_trades.append(pnl)
        else:
            fail_trades.append(pnl)
    
    result = {
        'total': len(trades),
        'pass': {
            'count': len(pass_trades),
            'ratio': len(pass_trades) / len(trades) * 100 if trades else 0,
            'win_rate': sum(1 for x in pass_trades if x > 0) / len(pass_trades) * 100 if pass_trades else 0,
            'avg_pnl': statistics.mean(pass_trades) if pass_trades else 0,
            'total_pnl': sum(pass_trades)
        },
        'fail': {
            'count': len(fail_trades),
            'ratio': len(fail_trades) / len(trades) * 100 if trades else 0,
            'win_rate': sum(1 for x in fail_trades if x > 0) / len(fail_trades) * 100 if fail_trades else 0,
            'avg_pnl': statistics.mean(fail_trades) if fail_trades else 0,
            'total_pnl': sum(fail_trades)
        }
    }
    
    return result


def analyze_market_regime(trades):
    """Market Regime Detection 分析"""
    if not trades:
        return None
    
    regime_distribution = defaultdict(lambda: {'count': 0, 'pnls': []})
    
    for trade in trades:
        regime = trade['entry']['market'].get('regime', 'UNKNOWN')
        pnl = trade['result']['pnl_usd']
        
        regime_distribution[regime]['count'] += 1
        regime_distribution[regime]['pnls'].append(pnl)
    
    result = {}
    for regime, data in regime_distribution.items():
        pnls = data['pnls']
        result[regime] = {
            'count': len(pnls),
            'ratio': len(pnls) / len(trades) * 100,
            'win_rate': sum(1 for x in pnls if x > 0) / len(pnls) * 100 if pnls else 0,
            'avg_pnl': statistics.mean(pnls) if pnls else 0,
            'total_pnl': sum(pnls)
        }
    
    return result


def analyze_strategy_signal(trades):
    """Strategy Signal 検出 分析"""
    if not trades:
        return None
    
    signal_distribution = defaultdict(lambda: {'count': 0, 'pnls': []})
    
    for trade in trades:
        signal = trade['entry']['signals'].get('strategy_signal', 'NONE')
        pnl = trade['result']['pnl_usd']
        
        signal_distribution[signal]['count'] += 1
        signal_distribution[signal]['pnls'].append(pnl)
    
    result = {}
    for signal, data in signal_distribution.items():
        pnls = data['pnls']
        result[signal] = {
            'count': len(pnls),
            'ratio': len(pnls) / len(trades) * 100,
            'win_rate': sum(1 for x in pnls if x > 0) / len(pnls) * 100 if pnls else 0,
            'avg_pnl': statistics.mean(pnls) if pnls else 0,
            'total_pnl': sum(pnls)
        }
    
    return result


def analyze_filter_combinations(trades):
    """フィルター組み合わせ分析"""
    if not trades:
        return None
    
    filter_combos = defaultdict(lambda: {'count': 0, 'pnls': []})
    
    for trade in trades:
        filters = trade['entry']['filters']
        pvo_pass = filters.get('pvo', {}).get('pass', False)
        adx_pass = filters.get('adx', {}).get('pass', False)
        volume_pass = filters.get('volume', {}).get('pass', False)
        volatility_pass = filters.get('volatility', {}).get('pass', False)
        pnl = trade['result']['pnl_usd']
        
        combo = f"PVO:{pvo_pass} ADX:{adx_pass} VOL:{volume_pass} VOLA:{volatility_pass}"
        filter_combos[combo]['count'] += 1
        filter_combos[combo]['pnls'].append(pnl)
    
    result = {}
    for combo, data in sorted(filter_combos.items(), key=lambda x: x[1]['count'], reverse=True):
        pnls = data['pnls']
        result[combo] = {
            'count': len(pnls),
            'win_rate': sum(1 for x in pnls if x > 0) / len(pnls) * 100 if pnls else 0,
            'avg_pnl': statistics.mean(pnls) if pnls else 0
        }
    
    return result


def print_quarterly_summary(q_prefix, log_data, analyses, config):
    """四半期別サマリーを表示"""
    metadata = log_data.get('metadata', {})
    trades = log_data.get('trades', [])
    
    print(f"\n{'=' * 100}")
    print(f"📊 {q_prefix} の分析結果")
    print(f"{'=' * 100}")
    print(f"\n【基本統計】")
    print(f"  総トレード数: {len(trades)}")
    print(f"  勝利: {sum(1 for t in trades if t['result']['pnl_usd'] > 0)} (勝率: {sum(1 for t in trades if t['result']['pnl_usd'] > 0) / len(trades) * 100:.1f}%)")
    print(f"  総PnL: {sum(t['result']['pnl_usd'] for t in trades):.2f} USD")
    print(f"  平均PnL: {statistics.mean([t['result']['pnl_usd'] for t in trades]):.2f} USD")
    
    # Volatility フィルター分析
    if 'volatility' in analyses:
        vol_analysis = analyses['volatility']
        print(f"\n【Volatility フィルター分析】")
        if config['volatility_filter']:
            print(f"  ステータス: ✅ 有効")
        else:
            print(f"  ステータス: ⚪ 無効化（実装は存在するが enable=0）")
        print(f"  PASS ({vol_analysis['pass']['count']} トレード):")
        print(f"    - 比率: {vol_analysis['pass']['ratio']:.1f}%")
        print(f"    - 勝率: {vol_analysis['pass']['win_rate']:.1f}%")
        print(f"    - 平均PnL: {vol_analysis['pass']['avg_pnl']:.2f} USD")
        print(f"  FAIL ({vol_analysis['fail']['count']} トレード):")
        print(f"    - 比率: {vol_analysis['fail']['ratio']:.1f}%")
        print(f"    - 勝率: {vol_analysis['fail']['win_rate']:.1f}%")
        print(f"    - 平均PnL: {vol_analysis['fail']['avg_pnl']:.2f} USD")
        
        # 矛盾の有無を判定
        if vol_analysis['fail']['avg_pnl'] > vol_analysis['pass']['avg_pnl']:
            print(f"  ⚠️ 異常: FAIL トレードの方が好成績（逆説的）")
        else:
            print(f"  ✓ 正常: PASS トレードの方が好成績")
    
    # Market Regime Detection 分析
    if 'regime' in analyses:
        regime_analysis = analyses['regime']
        print(f"\n【Market Regime Detection 分析】")
        if config['market_regime_detection']:
            print(f"  ステータス: ✅ 有効")
        else:
            print(f"  ステータス: ⚫ 無効化（config.ini で enable=0）")
        print(f"  レジーム分布:")
        for regime, stats in regime_analysis.items():
            print(f"    {regime}: {stats['count']} (比率: {stats['ratio']:.1f}%, 勝率: {stats['win_rate']:.1f}%)")
        
        if not config['market_regime_detection']:
            print(f"  📌 注記: 機能が無効化されているため TRANSITION のみが記録されている可能性")
        elif len(regime_analysis) == 1:
            print(f"  ⚠️ 警告: すべてのトレードが同じレジーム（機能していない可能性）")
        else:
            print(f"  ✓ 正常: 複数のレジームに分散")
    
    # Strategy Signal 分析
    if 'signal' in analyses:
        signal_analysis = analyses['signal']
        print(f"\n【Strategy Signal 検出分析】")
        print(f"  シグナル分布:")
        for signal, stats in signal_analysis.items():
            print(f"    {signal}: {stats['count']} (比率: {stats['ratio']:.1f}%, 勝率: {stats['win_rate']:.1f}%)")
        
        none_ratio = signal_analysis.get('NONE', {}).get('ratio', 0)
        if none_ratio == 100:
            print(f"  ⚠️ 警告: すべてのトレードでシグナルが NONE（機能していない可能性）")
        elif none_ratio > 50:
            print(f"  ⚠️ 注意: NONE シグナルが {none_ratio:.1f}% と高い")
        else:
            print(f"  ✓ 正常: シグナルが検出されている")


def main():
    print("\n" + "=" * 100)
    print("🚀 フェーズ4: Core Logic Validation")
    print("=" * 100)
    
    # config.ini を読み込む
    config = load_config()
    print(f"\n⚙️ Config状態:")
    print(f"  Volatility Filter: {'✅ 有効' if config['volatility_filter'] else '⚪ 無効'}")
    print(f"  Market Regime Detection: {'✅ 有効' if config['market_regime_detection'] else '⚪ 無効'}")
    print(f"  Seasonality: {'✅ 有効' if config['seasonality_based_positioning'] else '⚪ 無効'}")
    
    # ログファイルを取得
    latest_files = get_latest_log_files()
    
    if not latest_files:
        print("❌ エラー: ログファイルが見つかりません")
        print(f"   検索パス: {QUARTERLY_LOGS_DIR}")
        return
    
    print(f"\n📂 検出されたQ別ログファイル ({len(latest_files)} 個):")
    for q_prefix in sorted(latest_files.keys()):
        f = latest_files[q_prefix]
        basename = os.path.basename(f)
        print(f"  ✓ {q_prefix}: {basename}")
    
    # 全体的な分析結果を保存
    all_analyses = {}
    
    # 各Q別にログファイルを分析
    print(f"\n🔍 各四半期の分析を開始します...\n")
    
    for q_prefix in sorted(latest_files.keys()):
        filepath = latest_files[q_prefix]
        log_data = load_trade_log(filepath)
        
        if not log_data:
            print(f"⚠️  {q_prefix}: ログ読み込み失敗\n")
            continue
        
        trades = log_data.get('trades', [])
        if not trades:
            print(f"⚠️  {q_prefix}: トレードなし\n")
            continue
        
        # 各分析を実行
        analyses = {
            'volatility': analyze_volatility_filter(trades),
            'regime': analyze_market_regime(trades),
            'signal': analyze_strategy_signal(trades),
            'filters': analyze_filter_combinations(trades)
        }
        
        all_analyses[q_prefix] = analyses
        
        # サマリーを表示
        print_quarterly_summary(q_prefix, log_data, analyses, config)
    
    # 全体的な集計
    print_overall_summary(all_analyses, latest_files, config)
    
    # 結果をJSONに保存
    save_phase4_results(all_analyses)


def print_overall_summary(all_analyses, latest_files, config):
    """全体的なサマリーを表示"""
    print(f"\n{'=' * 100}")
    print("📈 全体的な傾向分析")
    print(f"{'=' * 100}")
    
    # Volatility フィルターの全体傾向
    print(f"\n【Volatility フィルターの全体傾向】")
    all_vol_pass_avg = []
    all_vol_fail_avg = []
    
    for q_prefix, analyses in all_analyses.items():
        if 'volatility' in analyses:
            vol = analyses['volatility']
            all_vol_pass_avg.append(vol['pass']['avg_pnl'])
            all_vol_fail_avg.append(vol['fail']['avg_pnl'])
    
    if all_vol_pass_avg and all_vol_fail_avg:
        pass_avg = statistics.mean(all_vol_pass_avg)
        fail_avg = statistics.mean(all_vol_fail_avg)
        print(f"  PASS 平均: {pass_avg:.2f} USD")
        print(f"  FAIL 平均: {fail_avg:.2f} USD")
        
        if fail_avg > pass_avg:
            print(f"  🔴 結論: Volatility FAIL 環境の方が好成績（逆説的）")
            print(f"           フィルター実装ロジックを再検証する必要があります")
        else:
            print(f"  🟢 結論: Volatility PASS 環境の方が好成績（正常）")
    
    # Market Regime Detection の全体傾向
    print(f"\n【Market Regime Detection の全体傾向】")
    regime_counts = defaultdict(int)
    for q_prefix, analyses in all_analyses.items():
        if 'regime' in analyses:
            regime = analyses['regime']
            for r, stats in regime.items():
                regime_counts[r] += stats['count']
    
    if regime_counts:
        for regime, count in sorted(regime_counts.items()):
            print(f"  {regime}: {count} トレード")
        
        if not config['market_regime_detection']:
            print(f"  ⚫ 結論: 機能が無効化されている（config.ini enable=0）")
            print(f"           有効化する場合は設定ファイルを更新してください")
        elif len(regime_counts) == 1:
            print(f"  🔴 結論: すべてのトレードが 1 つのレジーム")
            print(f"           Market Regime Detection が機能していない可能性が高い")
        else:
            print(f"  🟢 結論: 複数のレジーム検出（正常）")
    
    # Strategy Signal の全体傾向
    print(f"\n【Strategy Signal の全体傾向】")
    signal_counts = defaultdict(int)
    for q_prefix, analyses in all_analyses.items():
        if 'signal' in analyses:
            signal = analyses['signal']
            for s, stats in signal.items():
                signal_counts[s] += stats['count']
    
    if signal_counts:
        for signal, count in sorted(signal_counts.items()):
            print(f"  {signal}: {count} トレード")
        
        none_count = signal_counts.get('NONE', 0)
        total_count = sum(signal_counts.values())
        none_ratio = none_count / total_count * 100 if total_count > 0 else 0
        
        if none_ratio == 100:
            print(f"  🔴 結論: すべてのシグナルが NONE（Strategy Signal が機能していない）")
        elif none_ratio > 80:
            print(f"  🟡 結論: ほとんどのシグナルが NONE（機能が限定的）")
        else:
            print(f"  🟢 結論: Strategy Signal が検出されている（正常）")


def save_phase4_results(all_analyses):
    """分析結果をJSONに保存"""
    output_file = os.path.join(
        os.path.dirname(__file__),
        '..',
        'logs',
        f'phase4_analysis_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    )
    
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(all_analyses, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 分析結果を保存: {output_file}")
    except Exception as e:
        print(f"\n⚠️  保存エラー: {e}")


if __name__ == '__main__':
    main()
