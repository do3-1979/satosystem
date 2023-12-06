#!/bin/bash

# clear log
rm -f logs/*.json
rm -f logs/*.zip

rm -f log.txt
rm -f err.log

echo "### clear log done"

# 単純実行
python3 bot.py

# 標準出力とエラー出力を一つにファイルに出力
# python3 bot.py &> err.log &
