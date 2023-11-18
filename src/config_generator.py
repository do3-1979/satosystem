import argparse
import configparser
import os

def generate_param_combinations(param_ranges):
    param_combinations = []

    for name, min_val, max_val, step, section in param_ranges:
        values = [min_val + step * i for i in range(int((max_val - min_val) / step) + 1)]
        param_combinations.append((name, values, section))

    print(param_combinations)

    return param_combinations

def generate_config_files(base_config_file, output_folder, param_combinations):
    base_config = configparser.ConfigParser()
    base_config.read(base_config_file)

    file_idx = 0
    for idx, (param_name, param_values, section) in enumerate(param_combinations):
        for value in param_values:
            config = configparser.ConfigParser()

            print(f"value: {value}")

            for sec in base_config.sections():
                config.add_section(sec)
                for (name, val) in base_config.items(sec):
                    print(f"sec: {sec} name: {name} val; {val}")
                    config.set(sec, name, val)

            config.set(section, param_name, str(value))
            file_idx += 1
            print(f"change config sec: {section} name: {param_name} val; {value}")

            output_file = os.path.join(output_folder, f'config_{file_idx:05d}.ini')
            print(output_file)
            with open(output_file, 'w') as configfile:
                config.write(configfile)

def main():
    parser = argparse.ArgumentParser(description="Config Generator")
    parser.add_argument("--config-file", type=str, help="Base config file", required=True)
    parser.add_argument("--output-folder", type=str, help="Output folder for generated configs", required=True)
    parser.add_argument("--param", nargs=5, action="append")

    args = parser.parse_args()
    
    base_config_file = args.config_file
    output_folder = args.output_folder
    
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    param_ranges = [(param[1], float(param[2]), float(param[3]), float(param[4]), param[0]) for param in args.param]
    param_combinations = generate_param_combinations(param_ranges)

    generate_config_files(base_config_file, output_folder, param_combinations)

if __name__ == "__main__":
    main()

"""
python config_generator.py --config-file config.ini --output-folder generated_configs \
--param RiskManagement entry_times 5 15 1 \
--param RiskManagement entry_range 1 5 1 \
--param RiskManagement stop_range 0 2 1 \
--param RiskManagement stop_af 0.01 0.2 0.01 \
--param RiskManagement stop_af_add 0.1 0.5 0.1 \
--param RiskManagement stop_af_max 0.2 0.5 0.1 \
--param Strategy volatility_term 1 10 1 \
--param Strategy donchian_buy_term 22 26 2 \
--param Strategy donchian_sell_term 25 30 1
"""