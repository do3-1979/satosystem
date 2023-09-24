#!/bin/bash

# clear log
rm logs/*.json
rm logs/*.zip

rm log.txt

echo "### clear log done"

python bot.py
