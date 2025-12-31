#!/bin/bash

# config.iniファイルが存在しない場合にエラーメッセージを表示して終了
if [ ! -f config.ini ]; then
    echo "Error: config.ini file not found."
    exit 1
fi

# restore オプション: APIキーをプレースホルダに戻す（ハイブリッド構成対応）
if [ "$1" = "restore" ]; then
    # ハイブリッド構成の場合
    if grep -q "^api_bitget_key" config.ini && grep -q "^api_bybit_key" config.ini; then
        sed -i "s/^api_bitget_key = .*/api_bitget_key = YOUR_BITGET_API_KEY/" config.ini
        sed -i "s/^api_bitget_secret = .*/api_bitget_secret = YOUR_BITGET_API_SECRET/" config.ini
        sed -i "s/^api_bitget_passphrase = .*/api_bitget_passphrase = YOUR_BITGET_PASSPHRASE/" config.ini
        sed -i "s/^api_bybit_key = .*/api_bybit_key = YOUR_BYBIT_API_KEY/" config.ini
        sed -i "s/^api_bybit_secret = .*/api_bybit_secret = YOUR_BYBIT_API_SECRET/" config.ini
        echo "✅ Hybrid config: API keys restored to placeholders in config.ini"
    # レガシーシングル取引所構成の場合
    elif grep -q "^api_key" config.ini; then
        sed -i "s/^api_key = .*/api_key = YOUR_API_KEY/" config.ini
        sed -i "s/^api_secret = .*/api_secret = YOUR_API_SECRET/" config.ini
        sed -i "s/^api_passphrase = .*/api_passphrase = YOUR_PASSPHRASE/" config.ini
        echo "✅ Legacy config: API keys restored to placeholders in config.ini"
    else
        echo "⚠️  Warning: No API key patterns found in config.ini"
    fi
    exit 0
fi

# .api_keyファイルの存在確認
if [ ! -f .api_key ]; then
    echo "Error: .api_key file not found."
    exit 1
fi

# ハイブリッド構成の場合
if grep -q "^api_bitget_key" .api_key && grep -q "^api_bybit_key" .api_key; then
    # .api_keyファイルから両取引所のAPIキーを読み込む
    api_bitget_key=$(awk -F' = ' '/^api_bitget_key/ {print $2}' .api_key)
    api_bitget_secret=$(awk -F' = ' '/^api_bitget_secret/ {print $2}' .api_key)
    api_bitget_passphrase=$(awk -F' = ' '/^api_bitget_passphrase/ {print $2}' .api_key)
    api_bybit_key=$(awk -F' = ' '/^api_bybit_key/ {print $2}' .api_key)
    api_bybit_secret=$(awk -F' = ' '/^api_bybit_secret/ {print $2}' .api_key)
    
    # 特殊文字のエスケープ
    api_bitget_key_escaped=$(printf '%s\n' "$api_bitget_key" | sed -e 's/[\/&]/\\&/g')
    api_bitget_secret_escaped=$(printf '%s\n' "$api_bitget_secret" | sed -e 's/[\/&]/\\&/g')
    api_bitget_passphrase_escaped=$(printf '%s\n' "$api_bitget_passphrase" | sed -e 's/[\/&]/\\&/g')
    api_bybit_key_escaped=$(printf '%s\n' "$api_bybit_key" | sed -e 's/[\/&]/\\&/g')
    api_bybit_secret_escaped=$(printf '%s\n' "$api_bybit_secret" | sed -e 's/[\/&]/\\&/g')
    
    # config.iniファイルを上書き
    sed -i "s/YOUR_BITGET_API_KEY/$api_bitget_key_escaped/" config.ini
    sed -i "s/YOUR_BITGET_API_SECRET/$api_bitget_secret_escaped/" config.ini
    sed -i "s/YOUR_BITGET_PASSPHRASE/$api_bitget_passphrase_escaped/" config.ini
    sed -i "s/YOUR_BYBIT_API_KEY/$api_bybit_key_escaped/" config.ini
    sed -i "s/YOUR_BYBIT_API_SECRET/$api_bybit_secret_escaped/" config.ini
    
    if [ $? -eq 0 ]; then
        echo "✅ Hybrid config: Bitget and Bybit API keys successfully replaced in config.ini"
    else
        echo "❌ Error: Failed to replace API keys in config.ini"
        exit 1
    fi
# レガシーシングル取引所構成の場合
else
    # .api_keyファイルからapi_key、api_secret、api_passphraseの値を読み込む
    api_key=$(awk -F' = ' '/^api_key/ {print $2}' .api_key)
    api_secret=$(awk -F' = ' '/^api_secret/ {print $2}' .api_key)
    api_passphrase=$(awk -F' = ' '/^api_passphrase/ {print $2}' .api_key)
    
    # 特殊文字のエスケープを適切に処理する
    api_key_escaped=$(printf '%s\n' "$api_key" | sed -e 's/[\/&]/\\&/g')
    api_secret_escaped=$(printf '%s\n' "$api_secret" | sed -e 's/[\/&]/\\&/g')
    api_passphrase_escaped=$(printf '%s\n' "$api_passphrase" | sed -e 's/[\/&]/\\&/g')
    
    # config.iniファイルを生成または上書きして値を書き込む
    sed -i "s/YOUR_API_KEY/$api_key_escaped/" config.ini
    sed -i "s/YOUR_API_SECRET/$api_secret_escaped/" config.ini
    sed -i "s/YOUR_PASSPHRASE/$api_passphrase_escaped/" config.ini
    
    if [ $? -eq 0 ]; then
        echo "✅ Legacy config: api_key, api_secret, and api_passphrase successfully replaced in config.ini"
    else
        echo "❌ Error: Failed to replace API keys in config.ini"
        exit 1
    fi
fi

