#!/usr/bin/env python3
"""
Q1～Q4 adaptive/baseline 設定ファイルを生成
Adaptive: regime_detection 機能を有効化
Baseline: regime_detection を無効化（従来の戦略）
"""

from pathlib import Path
import re
from datetime import datetime

QUARTERS = {
    'Q1': ((1, 1), (3, 31)),   # Jan 1 - Mar 31
    'Q2': ((4, 1), (6, 30)),   # Apr 1 - Jun 30
    'Q3': ((7, 1), (9, 30)),   # Jul 1 - Sep 30
    'Q4': ((10, 1), (12, 31)), # Oct 1 - Dec 31
}

def get_period_dates(year, quarter):
    """年とクォーターから期間を取得"""
    (start_month, start_day), (end_month, end_day) = QUARTERS[quarter]
    start = f"{year}/{start_month:02d}/{start_day:02d} 0:00"
    end = f"{year}/{end_month:02d}/{end_day:02d} 23:59"
    return start, end

def replace_config_value(lines, section, key, value):
    """指定セクション内のキーを置き換え"""
    in_section = False
    result = []
    found = False
    
    for line in lines:
        # セクションヘッダをチェック
        section_match = re.match(r'^\[(.+)\]\s*$', line.strip())
        if section_match:
            in_section = (section_match.group(1) == section)
            result.append(line)
            continue
        
        # 対象セクション内でキーを探す
        if in_section:
            key_match = re.match(r'\s*(\w+)\s*=.*', line)
            if key_match and key_match.group(1) == key:
                # コメント部分を削除して置き換え
                original_line = line.rstrip()
                if '#' in original_line:
                    comment_part = original_line.split('#', 1)[1]
                    result.append(f'{key} = {value}          # {comment_part}\n')
                else:
                    result.append(f'{key} = {value}\n')
                found = True
                continue
        
        result.append(line)
    
    return result, found

def generate_quarterly_configs(template_path, output_dir, years_quarters):
    """
    年とクォーターのリストから adaptive/baseline 設定ファイルを生成
    
    Args:
        template_path: テンプレート config.ini のパス
        output_dir: 出力ディレクトリ
        years_quarters: [(year, quarter), ...] のリスト
    """
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    template_text = template_path.read_text(encoding='utf-8')
    # テンプレートはすでに %% エスケープされているため追加処理は不要
    template_lines = template_text.splitlines(keepends=True)
    
    generated_count = 0
    
    for year, quarter in years_quarters:
        start_time, end_time = get_period_dates(year, quarter)
        config_name = f"{year}_{quarter.lower()}"
        
        # ベースライン設定生成
        baseline_lines = list(template_lines)
        
        # Period セクションを更新
        baseline_lines, _ = replace_config_value(baseline_lines, 'Period', 'start_time', start_time)
        baseline_lines, _ = replace_config_value(baseline_lines, 'Period', 'end_time', end_time)
        
        # Regime detection を無効化
        baseline_lines, _ = replace_config_value(
            baseline_lines, 'Strategy', 'regime_detection_enabled', 'False'
        )
        
        baseline_path = output_dir / f'baseline_{config_name}.ini'
        # コメント部分を削除（configparser互換性）
        clean_content = remove_comments_from_values('\n'.join(baseline_lines))
        baseline_path.write_text(clean_content, encoding='utf-8')
        print(f'✅ Generated: {baseline_path.name}')
        generated_count += 1
        
        # アダプティブ設定生成
        adaptive_lines = list(template_lines)
        
        # Period セクションを更新
        adaptive_lines, _ = replace_config_value(adaptive_lines, 'Period', 'start_time', start_time)
        adaptive_lines, _ = replace_config_value(adaptive_lines, 'Period', 'end_time', end_time)
        
        # Regime detection を有効化
        adaptive_lines, _ = replace_config_value(
            adaptive_lines, 'Strategy', 'regime_detection_enabled', 'True'
        )
        
        # レジーム検出のパラメータを設定
        adaptive_lines, _ = replace_config_value(
            adaptive_lines, 'Strategy', 'regime_volatility_ratio_threshold', '1.2'
        )
        adaptive_lines, _ = replace_config_value(
            adaptive_lines, 'Strategy', 'regime_trend_strength_threshold', '0.05'
        )
        
        adaptive_path = output_dir / f'adaptive_{config_name}.ini'
        # コメント部分を削除（configparser互換性）
        clean_content = remove_comments_from_values('\n'.join(adaptive_lines))
        adaptive_path.write_text(clean_content, encoding='utf-8')
        print(f'✅ Generated: {adaptive_path.name}')
        generated_count += 1
    
    print(f'\n✨ Total {generated_count} config files generated in {output_dir}')
    return generated_count


def remove_comments_from_values(content):
    """
    設定ファイルの値部分に含まれるコメントを削除
    ただしセクション行とコメント行は保持
    """
    lines = content.split('\n')
    result = []
    
    for line in lines:
        # セクション行やコメント行は保持
        stripped = line.strip()
        if stripped.startswith('[') or stripped.startswith('#') or not stripped:
            result.append(line)
        # キー=値 行からコメントを削除
        elif '=' in line and '#' in line:
            key_value_part = line.split('#')[0]
            result.append(key_value_part.rstrip())
        else:
            result.append(line)
    
    return '\n'.join(result)

def main():
    import argparse
    
    ap = argparse.ArgumentParser(
        description='Generate quarterly adaptive/baseline config pairs'
    )
    ap.add_argument(
        '--template', 
        type=str, 
        default='src/config.ini',
        help='Template config.ini path'
    )
    ap.add_argument(
        '--outdir',
        type=str,
        default='output_configs',
        help='Output directory'
    )
    ap.add_argument(
        '--years',
        type=str,
        default='2024,2025',
        help='Comma-separated years (e.g., "2024,2025")'
    )
    ap.add_argument(
        '--quarters',
        type=str,
        default='Q1',
        help='Comma-separated quarters (e.g., "Q1,Q2,Q3,Q4")'
    )
    
    args = ap.parse_args()
    
    template_path = Path(args.template)
    if not template_path.exists():
        raise SystemExit(f'Template not found: {template_path}')
    
    years = [int(y.strip()) for y in args.years.split(',')]
    quarters = [q.strip() for q in args.quarters.split(',')]
    
    # 年とクォーターの組み合わせを作成
    years_quarters = [(y, q) for y in years for q in quarters]
    
    print("="*70)
    print("📋 Quarterly Config Generator (Adaptive vs Baseline)")
    print("="*70)
    print(f"Template: {template_path}")
    print(f"Output: {args.outdir}")
    print(f"Targets: {len(years_quarters)} configs")
    for year, quarter in years_quarters:
        start, end = get_period_dates(year, quarter)
        print(f"  - {year} {quarter}: {start} to {end}")
    print()
    
    generate_quarterly_configs(template_path, args.outdir, years_quarters)

if __name__ == '__main__':
    main()
