#!/usr/bin/env python3
"""
Keltnerパラメータスイープ用config生成
押し目買いロジックの効果を検証するため、以下のパラメータ組み合わせをテスト:
- keltner_ema_period: [10, 20, 30]
- keltner_atr_multiplier: [1.5, 2.0, 2.5, 3.0]
"""
from pathlib import Path
import shutil

def generate_keltner_configs():
    """Generate Keltner parameter sweep configs."""
    template_path = Path("output_configs/ab_test_keltner_enabled.ini")
    output_dir = Path("output_configs/keltner_sweep")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if not template_path.exists():
        print(f"Error: Template not found: {template_path}")
        return
    
    # Parameter combinations
    ema_periods = [10, 20, 30]
    atr_multipliers = [1.5, 2.0, 2.5, 3.0]
    
    configs = []
    
    for ema in ema_periods:
        for atr_mult in atr_multipliers:
            config_name = f"keltner_ema{ema}_atr{atr_mult:.1f}.ini"
            config_path = output_dir / config_name
            
            # Copy template
            shutil.copy(template_path, config_path)
            
            # Read and modify
            with open(config_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Replace parameters
            modified = []
            for line in lines:
                if line.startswith('keltner_ema_period'):
                    modified.append(f'keltner_ema_period = {ema}\n')
                elif line.startswith('keltner_atr_multiplier'):
                    modified.append(f'keltner_atr_multiplier = {atr_mult}\n')
                else:
                    modified.append(line)
            
            # Write back
            with open(config_path, 'w', encoding='utf-8') as f:
                f.writelines(modified)
            
            configs.append({
                'name': config_name,
                'ema': ema,
                'atr_mult': atr_mult
            })
    
    print(f"Generated {len(configs)} Keltner sweep configs in {output_dir}")
    print("\nParameter combinations:")
    for cfg in configs:
        print(f"  {cfg['name']}: EMA={cfg['ema']}, ATR×{cfg['atr_mult']}")
    
    return configs

if __name__ == "__main__":
    generate_keltner_configs()
