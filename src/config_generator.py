import itertools
import os
import numpy as np

def generate_configs(base_config, output_directory):
    # Remove previously generated config files
    existing_files = [f for f in os.listdir(output_directory) if f.startswith("config_") and f.endswith(".ini")]
    for file in existing_files:
        file_path = os.path.join(output_directory, file)
        os.remove(file_path)
    
    # RiskManagement セクション
    risk_percentage_start = base_config['RiskManagement']['risk_percentage']
    account_balance_start = base_config['RiskManagement']['account_balance']
    leverage_start = base_config['RiskManagement']['leverage']
    entry_times_start = base_config['RiskManagement']['entry_times']
    entry_range_start = base_config['RiskManagement']['entry_range']
    stop_range_start = base_config['RiskManagement']['stop_range']
    stop_AF_start = base_config['RiskManagement']['stop_AF']
    stop_AF_add_start = base_config['RiskManagement']['stop_AF_add']
    stop_AF_max_start = base_config['RiskManagement']['stop_AF_max']
    surge_follow_price_ratio_start = base_config['RiskManagement']['surge_follow_price_ratio']
    psar_time_frame_start = base_config['RiskManagement']['psar_time_frame']
    # Strategyセクション
    volatility_term_start = base_config['Strategy']['volatility_term']
    donchian_buy_term_start = base_config['Strategy']['donchian_buy_term']
    donchian_sell_term_start = base_config['Strategy']['donchian_sell_term']
    pvo_s_term_start = base_config['Strategy']['pvo_s_term']
    pvo_l_term_start = base_config['Strategy']['pvo_l_term']
    pvo_threshold_start = base_config['Strategy']['pvo_threshold']    
    # Potfolioセクション
    lot_limit_lower_start = base_config['Potfolio']['lot_limit_lower']   
    balance_tether_limit_start = base_config['Potfolio']['balance_tether_limit']   
    # Settingセクション
    server_retry_wait_start = base_config['Setting']['server_retry_wait']   
    bot_operation_cycle_start = base_config['Setting']['bot_operation_cycle']   

    # 変化させない場合はstartとendを同じにしておく
    # RiskManagement セクション
    risk_percentage_end = risk_percentage_start
    account_balance_end = account_balance_start
    leverage_end = leverage_start
    entry_times_end = entry_times_start
    entry_range_end = entry_range_start
    stop_range_end = stop_range_start
    stop_AF_end = stop_AF_start
    stop_AF_add_end = stop_AF_add_start
    stop_AF_max_end = stop_AF_max_start
    surge_follow_price_ratio_end = surge_follow_price_ratio_start
    psar_time_frame_end = psar_time_frame_start
    # Strategyセクション
    volatility_term_end = volatility_term_start
    donchian_buy_term_end = donchian_buy_term_start
    donchian_sell_term_end = donchian_sell_term_start
    pvo_s_term_end = pvo_s_term_start    
    pvo_l_term_end = pvo_l_term_start
    pvo_threshold_end = pvo_threshold_start
    # Potfolioセクション
    lot_limit_lower_end = lot_limit_lower_start
    balance_tether_limit_end = balance_tether_limit_start
    # Settingセクション
    server_retry_wait_end = server_retry_wait_start
    bot_operation_cycle_end = bot_operation_cycle_start

    # 変化させない場合も1とする
    # RiskManagement セクション
    risk_percentage_step = 1
    account_balance_step = 0.001
    leverage_step = 1
    entry_times_step = 1
    entry_range_step = 1
    stop_range_step = 1
    stop_AF_step = 1
    stop_AF_add_step = 0.01
    stop_AF_max_step = 0.01
    surge_follow_price_ratio_step = 1
    psar_time_frame_step = 1
    # Strategyセクション
    volatility_term_step = 1
    donchian_buy_term_step = 1
    donchian_sell_term_step = 1
    pvo_s_term_step = 1
    pvo_l_term_step = 1
    pvo_threshold_step = 1
    # Potfolioセクション
    lot_limit_lower_step = 1
    balance_tether_limit_step = 1
    # Settingセクション
    server_retry_wait_step = 1
    bot_operation_cycle_step = 1

    risk_percentage_list = np.arange(risk_percentage_start, risk_percentage_end + risk_percentage_step, risk_percentage_step)
    account_balance_list = np.arange(account_balance_start, account_balance_end + account_balance_step, account_balance_step)
    leverage_list = np.arange(leverage_start, leverage_end + leverage_step, leverage_step)
    entry_times_list = np.arange(entry_times_start, entry_times_end + entry_times_step, entry_times_step)
    entry_range_list = np.arange(entry_range_start, entry_range_end + entry_range_step, entry_range_step)
    stop_range_list = np.arange(stop_range_start, stop_range_end + stop_range_step, stop_range_step)
    stop_AF_list = np.arange(stop_AF_start, stop_AF_end + stop_AF_step, stop_AF_step)
    stop_AF_add_list = np.arange(stop_AF_add_start, stop_AF_add_end + stop_AF_add_step, stop_AF_add_step)
    stop_AF_max_list = np.arange(stop_AF_max_start, stop_AF_max_end + stop_AF_max_step, stop_AF_max_step)
    surge_follow_price_ratio_list = np.arange(surge_follow_price_ratio_start, surge_follow_price_ratio_end + surge_follow_price_ratio_step, surge_follow_price_ratio_step)
    psar_time_frame_list = np.arange(psar_time_frame_start, psar_time_frame_end + psar_time_frame_step, psar_time_frame_step)
    volatility_term_list = np.arange(volatility_term_start, volatility_term_end + volatility_term_step, volatility_term_step)
    donchian_buy_term_list = np.arange(donchian_buy_term_start, donchian_buy_term_end + donchian_buy_term_step, donchian_buy_term_step)
    donchian_sell_term_list = np.arange(donchian_sell_term_start, donchian_sell_term_end + donchian_sell_term_step, donchian_sell_term_step)
    pvo_s_term_list = np.arange(pvo_s_term_start, pvo_s_term_end + pvo_s_term_step, pvo_s_term_step)
    pvo_l_term_list = np.arange(pvo_l_term_start, pvo_l_term_end + pvo_l_term_step, pvo_l_term_step)
    pvo_threshold_list = np.arange(pvo_threshold_start, pvo_threshold_end + pvo_threshold_step, pvo_threshold_step)
    lot_limit_lower_list = np.arange(lot_limit_lower_start, lot_limit_lower_end + lot_limit_lower_step, lot_limit_lower_step)
    balance_tether_limit_list = np.arange(balance_tether_limit_start, balance_tether_limit_end + balance_tether_limit_step, balance_tether_limit_step)
    server_retry_wait_list = np.arange(server_retry_wait_start, server_retry_wait_end + server_retry_wait_step, server_retry_wait_step)
    bot_operation_cycle_list = np.arange(bot_operation_cycle_start, bot_operation_cycle_end + bot_operation_cycle_step, bot_operation_cycle_step)

    # RiskManagement セクション
    #total_configs = (risk_percentage_end - risk_percentage_start) // risk_percentage_step + 1
    total_configs = len(risk_percentage_list)
    total_configs *= len(account_balance_list)
    total_configs *= len(leverage_list)
    total_configs *= len(entry_times_list)
    total_configs *= len(entry_range_list)
    total_configs *= len(stop_range_list)
    total_configs *= len(stop_AF_list)
    total_configs *= len(stop_AF_add_list)
    total_configs *= len(stop_AF_max_list)
    total_configs *= len(surge_follow_price_ratio_list)
    total_configs *= len(psar_time_frame_list)
    # Strategyセクション
    total_configs *= len(volatility_term_list)
    total_configs *= len(donchian_buy_term_list)
    total_configs *= len(donchian_sell_term_list)
    total_configs *= len(pvo_s_term_list)
    total_configs *= len(pvo_l_term_list)
    total_configs *= len(pvo_threshold_list)
    # Potfolioセクション
    total_configs *= len(lot_limit_lower_list)
    total_configs *= len(balance_tether_limit_list)
    # Settingセクション
    total_configs *= len(server_retry_wait_list)
    total_configs *= len(bot_operation_cycle_list)
    # Strategyセクション
    
    output_count = 0

    for risk_percentage, \
        account_balance, \
        leverage, \
        entry_times, \
        entry_range, \
        stop_range, \
        stop_AF, \
        stop_AF_add, \
        stop_AF_max, \
        surge_follow_price_ratio, \
        psar_time_frame, \
        volatility_term, \
        donchian_buy_term, \
        donchian_sell_term, \
        pvo_s_term, \
        pvo_l_term, \
        pvo_threshold, \
        lot_limit_lower, \
        balance_tether_limit, \
        server_retry_wait, \
        bot_operation_cycle \
        in itertools.product(
            risk_percentage_list,
            account_balance_list,
            leverage_list,
            entry_times_list,
            entry_range_list,
            stop_range_list,
            stop_AF_list,
            stop_AF_add_list,
            stop_AF_max_list,
            surge_follow_price_ratio_list,
            psar_time_frame_list,
            volatility_term_list,
            donchian_buy_term_list,
            donchian_sell_term_list,
            pvo_s_term_list,
            pvo_l_term_list,
            pvo_threshold_list,
            lot_limit_lower_list,
            balance_tether_limit_list,
            server_retry_wait_list,
            bot_operation_cycle_list
    ):
        config_copy = base_config.copy()
        # RiskManagement セクション
        config_copy['RiskManagement']['risk_percentage'] = risk_percentage
        config_copy['RiskManagement']['account_balance'] = account_balance
        config_copy['RiskManagement']['leverage'] = leverage
        config_copy['RiskManagement']['entry_times'] = entry_times
        config_copy['RiskManagement']['entry_range'] = entry_range
        config_copy['RiskManagement']['stop_range'] = stop_range
        config_copy['RiskManagement']['stop_AF'] = stop_AF
        config_copy['RiskManagement']['stop_AF_add'] = stop_AF_add
        config_copy['RiskManagement']['stop_AF_max'] = stop_AF_max
        config_copy['RiskManagement']['surge_follow_price_ratio'] = surge_follow_price_ratio        
        config_copy['RiskManagement']['psar_time_frame'] = psar_time_frame        
        # Strategyセクション
        config_copy['Strategy']['volatility_term'] = volatility_term       
        config_copy['Strategy']['donchian_buy_term'] = donchian_buy_term       
        config_copy['Strategy']['donchian_sell_term'] = donchian_sell_term       
        config_copy['Strategy']['pvo_s_term'] = pvo_s_term       
        config_copy['Strategy']['pvo_l_term'] = pvo_l_term       
        config_copy['Strategy']['pvo_threshold'] = pvo_threshold       
        # Potfolioセクション
        config_copy['Potfolio']['lot_limit_lower'] = lot_limit_lower       
        config_copy['Potfolio']['balance_tether_limit'] = balance_tether_limit       
        # Settingセクション
        config_copy['Setting']['server_retry_wait'] = server_retry_wait       
        config_copy['Setting']['bot_operation_cycle'] = bot_operation_cycle       

        output_file_name = f"config_{output_count + 1:07d}.ini"
        output_path = os.path.join(output_directory, output_file_name)

        with open(output_path, 'w') as output_file:
            for section, options in config_copy.items():
                output_file.write(f"[{section}]\n")
                for key, value in options.items():
                    output_file.write(f"{key} = {value}\n")

        output_count += 1
        progress_percentage = (output_count / total_configs) * 100
        print(f"Progress: {output_count}/{total_configs} ({progress_percentage:.2f}%)", end = '\r')

    print("")
    print("Generation completed.")

if __name__ == "__main__":
    base_config = {
        'API': {'api_key': 'YOUR_API_KEY',
                'api_secret': 'YOUR_API_SECRET'},
        'Market': {'market': 'BTC/USD',
                   'time_frame': 120},
        'RiskManagement': {'risk_percentage': 0.85,
                           'account_balance': 0.007,
                           'leverage': 100,
                           'entry_times': 10,
                           'entry_range': 2,
                           'stop_range': 2,
                           'stop_AF': 0.02,
                           'stop_AF_add': 0.02,
                           'stop_AF_max': 0.20,
                           'surge_follow_price_ratio': 0.011,
                           'psar_time_frame': 30},
        'Market': {'market': 'BTC/USD',
                   'time_frame': 120},
        'Period': {'start_time': '2023/12/25 1:00',
                   'end_time': None},
        'Strategy': {'volatility_term': 6,
                     'donchian_buy_term': 22,
                     'donchian_sell_term': 29,
                     'pvo_s_term': 5,
                     'pvo_l_term': 70,
                     'pvo_threshold': 20},
        'Potfolio': {'lot_limit_lower': 0.0001,
                     'balance_tether_limit': 0},
        'Setting': {'server_retry_wait': 120, 
                    'bot_operation_cycle': 60},
        'Log': {'log_file': 'log.txt',
                'log_directory': 'logs'},
        'Backtest': {'back_test': 0},
        'OtherSettings': {}
    }

    output_directory = "output_configs"

    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    generate_configs(base_config, output_directory)
