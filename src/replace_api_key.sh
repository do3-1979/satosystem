#!/bin/bash

# config.iniファイルが存在しない場合にエラーメッセージを表示して終了
if [ ! -f config.ini ]; then
    echo "Error: config.ini file not found."
    exit 1
fi

# restore オプション: APIキーをプレースホルダに戻す
if [ "$1" = "restore" ]; then
    sed -i "s/api_key = .*/api_key = YOUR_API_KEY/" config.ini
    sed -i "s/api_secret = .*/api_secret = YOUR_API_SECRET/" config.ini
    sed -i "s/api_passphrase = .*/api_passphrase = YOUR_PASSPHRASE/" config.ini
    echo "API keys restored to placeholders in config.ini"
    exit 0
fi

# .api_keyファイルからapi_key、api_secret、api_passphraseの値を読み込む
api_key=$(awk -F' = ' '/api_key/ {print $2}' .api_key)
api_secret=$(awk -F' = ' '/api_secret/ {print $2}' .api_key)
api_passphrase=$(awk -F' = ' '/api_passphrase/ {print $2}' .api_key)

# 特殊文字のエスケープを適切に処理する
api_key_escaped=$(printf '%s\n' "$api_key" | sed -e 's/[\/&]/\\&/g')
api_secret_escaped=$(printf '%s\n' "$api_secret" | sed -e 's/[\/&]/\\&/g')
api_passphrase_escaped=$(printf '%s\n' "$api_passphrase" | sed -e 's/[\/&]/\\&/g')

# config.iniファイルを生成または上書きして値を書き込む
sed -i "s/YOUR_API_KEY/$api_key_escaped/" config.ini
sed -i "s/YOUR_API_SECRET/$api_secret_escaped/" config.ini
sed -i "s/YOUR_PASSPHRASE/$api_passphrase_escaped/" config.ini

if [ $? -eq 0 ]; then
    echo "✅ api_key, api_secret, and api_passphrase successfully replaced in config.ini"
else
    echo "❌ Error: Failed to replace API keys in config.ini"
    exit 1
fi

