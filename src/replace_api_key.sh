#!/bin/bash

# config.iniファイルが存在しない場合にエラーメッセージを表示して終了
if [ ! -f config.ini ]; then
    echo "Error: config.ini file not found."
    exit 1
fi

# .api_keyファイルからapi_keyとapi_secretの値を読み込む
api_key=$(awk -F' = ' '/api_key/ {print $2}' .api_key)
api_secret=$(awk -F' = ' '/api_secret/ {print $2}' .api_key)

# config.iniファイルを生成または上書きして値を書き込む
sed -i "s/YOUR_API_KEY/$api_key/" config.ini
sed -i "s/YOUR_API_SECRET/$api_secret/" config.ini

echo "api_key and api_secret replace at config.ini"
