import argparse
import configparser
import os

def generate_param_combinations(param_ranges):
    param_combinations = []

    for name, min_val, max_val, step, section in param_ranges:
        values = [min_val + step * i for i in range(int((max_val - min_val) / step) + 1)]
        param_combinations.append((name, values, section))

    return param_combinations

def generate_config_files(base_config_file, output_folder, param_combinations):
    base_config = configparser.ConfigParser()
    base_config.read(base_config_file)

    for idx, (param_name, param_values, section) in enumerate(param_combinations):
        for value in param_values:
            config = configparser.ConfigParser()

            print(f"value: {value}")

            for sec in base_config.sections():
                print(f"sec: {sec}")
                config.add_section(sec)
                for (name, val) in base_config.items(sec):
                    print(f"name: {sec} val; {val}")
                    config.set(sec, name, val)

            config.set(section, param_name, str(value))

            output_file = os.path.join(output_folder, f'config_{idx:05d}.ini')
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
