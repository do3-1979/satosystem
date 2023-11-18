#!/bin/bash

# clear log
rm -f logs/*.json
rm -f logs/*.zip

rm -f log.txt
rm -f err.log

echo "### clear log done"

python3 bot.py
