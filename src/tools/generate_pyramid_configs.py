#!/usr/bin/env python3
"""
Pyramiding最適化用config生成
entry_times候補: 2, 3, 4, 5, 8, 10を10月期間でテスト
"""
from pathlib import Path
import shutil

def generate_pyramid_configs():
    """Generate pyramiding optimization configs."""
    # Use baseline October config as template
    template_path = Path("output_configs/config_2025_10.ini")
    output_dir = Path("output_configs/pyramid_sweep")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if not template_path.exists():
        print(f"Warning: Template not found: {template_path}")
        print("Using src/config.ini as fallback")
        template_path = Path("src/config.ini")
    
    if not template_path.exists():
        print(f"Error: No template available")
        return []
    
    # Pyramid candidates
    entry_times_list = [2, 3, 4, 5, 8, 10]
    
    configs = []
    
    for entry_times in entry_times_list:
        config_name = f"pyramid_entry{entry_times}.ini"
        config_path = output_dir / config_name
        
        # Copy template
        shutil.copy(template_path, config_path)
        
        # Read and modify
        with open(config_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Replace entry_times and ensure keltner_enabled=False
        modified = []
        for line in lines:
            if line.strip().startswith('entry_times'):
                modified.append(f'entry_times = {entry_times}\n')
            elif line.strip().startswith('keltner_enabled'):
                modified.append('keltner_enabled = False\n')
            else:
                modified.append(line)
        
        # Write back
        with open(config_path, 'w', encoding='utf-8') as f:
            f.writelines(modified)
        
        configs.append({
            'name': config_name,
            'entry_times': entry_times
        })
    
    print(f"Generated {len(configs)} pyramiding configs in {output_dir}")
    print("\nEntry times candidates:")
    for cfg in configs:
        print(f"  {cfg['name']}: entry_times={cfg['entry_times']}")
    
    return configs

if __name__ == "__main__":
    generate_pyramid_configs()
