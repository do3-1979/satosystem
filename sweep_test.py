#!/usr/bin/env python3
"""
パラメータスイープテストを実行し、最適なパラメータを探索するスクリプト
"""
import os
import json
import subprocess
import configparser
from pathlib import Path
from datetime import datetime

# プロジェクトルート
PROJECT_ROOT = Path(__file__).parent
CONFIG_PATH = PROJECT_ROOT / "src" / "config.ini"
RESULTS_DIR = PROJECT_ROOT / "report_tmp" / "sweep_test"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# テスト対象パラメータ
TEST_PARAMS = {
    "entry_range": [0.3, 0.5, 1.0, 1.5, 2.0],
    "stop_range": [0.5, 1.0, 1.5, 2.0, 2.5],
    "volatility_term": [14, 20, 28, 35, 50],
    "donchian_term": [20, 25, 32, 40, 50],  # buy/sell 両方に適用
    "pvo_threshold": [2, 5, 8, 10, 15],
}

def read_config():
    """現在の設定を読み込む"""
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH)
    return config

def update_config_param(config, param_name, value):
    """設定を更新"""
    if param_name == "donchian_term":
        config.set("Strategy", "donchian_buy_term", str(value))
        config.set("Strategy", "donchian_sell_term", str(value))
    else:
        section = "RiskManagement" if param_name in ["entry_range", "stop_range"] else "Strategy"
        config.set(section, param_name, str(value))
    
    with open(CONFIG_PATH, "w") as f:
        config.write(f)

def run_quarterly_backtest():
    """四半期別バックテストを実行"""
    try:
        result = subprocess.run(
            ["python3", "run_quarterly_backtest.py"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=600
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Timeout"
    except Exception as e:
        return False, "", str(e)

def extract_total_pnl(stdout):
    """標準出力から総PnLを抽出"""
    lines = stdout.split('\n')
    for line in lines:
        if 'Total' in line and 'PnL' in line:
            # "Total PnL: +374.95" などのフォーマットを想定
            try:
                parts = line.split(':')
                if len(parts) >= 2:
                    value_str = parts[-1].strip().replace('$', '').replace('+', '')
                    return float(value_str)
            except ValueError:
                pass
    
    # バックアップ: ファイルから直接取得を試みる
    return None

def test_parameter(param_name, values):
    """指定パラメータのスイープテスト実行"""
    print(f"\n{'='*60}")
    print(f"Testing: {param_name}")
    print(f"Values: {values}")
    print(f"{'='*60}")
    
    results = []
    config = read_config()
    original_value = None
    
    for value in values:
        print(f"\n▶ Testing {param_name} = {value}")
        
        # 現在の値を保存（初回のみ）
        if original_value is None:
            if param_name == "donchian_term":
                original_value = config.get("Strategy", "donchian_buy_term")
            else:
                section = "RiskManagement" if param_name in ["entry_range", "stop_range"] else "Strategy"
                original_value = config.get(section, param_name)
        
        # パラメータを更新
        update_config_param(config, param_name, value)
        
        # テスト実行
        success, stdout, stderr = run_quarterly_backtest()
        
        if success:
            # 結果を抽出（ファイルから読み込み）
            try:
                latest_log = sorted(
                    (RESULTS_DIR.parent.parent / "logs").glob("*.json"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True
                )[0]
                with open(latest_log) as f:
                    log_data = json.load(f)
                    pnl = log_data.get("summary", {}).get("total_profit_and_loss", None)
            except:
                pnl = extract_total_pnl(stdout)
            
            print(f"  ✓ Success | PnL: {pnl}")
            results.append({"value": value, "pnl": pnl, "success": True})
        else:
            print(f"  ✗ Failed")
            results.append({"value": value, "pnl": None, "success": False})
    
    # 結果をソート
    valid_results = [r for r in results if r["success"]]
    if valid_results:
        best = max(valid_results, key=lambda x: x["pnl"] if x["pnl"] is not None else float('-inf'))
        print(f"\n✓ Best value: {param_name} = {best['value']} (PnL: {best['pnl']})")
    else:
        print(f"\n✗ No successful results for {param_name}")
        best = None
    
    return {
        "param_name": param_name,
        "results": results,
        "best": best
    }

def main():
    """メイン実行"""
    print(f"Parameter Sweep Test Started at {datetime.now()}")
    print(f"Config: {CONFIG_PATH}")
    print(f"Results will be saved to: {RESULTS_DIR}")
    
    all_results = {}
    
    # 各パラメータのテストを実行
    for param_name, values in TEST_PARAMS.items():
        result = test_parameter(param_name, values)
        all_results[param_name] = result
    
    # 最適パラメータをまとめる
    optimal_params = {}
    for param_name, result in all_results.items():
        if result["best"]:
            optimal_params[param_name] = result["best"]["value"]
    
    # 結果をファイルに保存
    summary = {
        "timestamp": datetime.now().isoformat(),
        "results": all_results,
        "optimal_parameters": optimal_params,
    }
    
    output_file = RESULTS_DIR / f"sweep_test_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'='*60}")
    print(f"Sweep Test Completed!")
    print(f"Results saved to: {output_file}")
    print(f"\nOptimal Parameters:")
    for param, value in optimal_params.items():
        print(f"  {param}: {value}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
