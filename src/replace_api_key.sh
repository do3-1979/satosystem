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
    echo "API keys restored to placeholders in config.ini"
    exit 0
fi

# .api_keyファイルからapi_keyとapi_secretの値を読み込む
api_key=$(awk -F' = ' '/api_key/ {print $2}' .api_key)
api_secret=$(awk -F' = ' '/api_secret/ {print $2}' .api_key)

# config.iniファイルを生成または上書きして値を書き込む
sed -i "s/YOUR_API_KEY/$api_key/" config.ini
sed -i "s/YOUR_API_SECRET/$api_secret/" config.ini

echo "api_key and api_secret replace at config.ini"
