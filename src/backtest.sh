#!/bin/bash

# 開始時間の取得
start_time=$(date +%s)

# ステップ 0: logs_* ディレクトリと中のファイルの削除
for log_dir in logs_*; do
    if [ -d "$log_dir" ]; then
        rm -rf "$log_dir"
    fi
done

# ログファイルの削除
for log_file in logs_*.txt; do
    if [ -f "$log_file" ]; then
        rm "$log_file"
    fi
done

# ステップ 2: output_configs 内の config ファイルを順番に処理
for config_file in output_configs/config_*.ini; do
    # ステップ 1: 現在の config.ini をバックアップ
    mv config.ini config_bak.ini

    # パスを除いてファイル名のみを取得
    filename=$(basename -- "$config_file")
    
    # 現在の config ファイル、進捗率、処理の経過時間を表示
    current_time=$(date +%s)
    elapsed_time=$((current_time - start_time))
    elapsed_hours=$((elapsed_time / 3600))
    elapsed_minutes=$((elapsed_time % 3600 / 60))
    elapsed_seconds=$((elapsed_time % 60))
    
    echo "処理中: $filename - $(echo "$filename" | sed 's/[^0-9]//g') 完了 (経過時間: ${elapsed_hours}h ${elapsed_minutes}m ${elapsed_seconds}s)"

    # config ファイルを config.ini にコピー
    cp "$config_file" config.ini

    # APIキーとシークレットを置換
    ./replace_api_key.sh

    # ステップ 3: bot.py を実行
    python bot.py

    # ステップ 4: 元の config.ini に戻す
    mv config_bak.ini config.ini

    # 進捗を表示するために一時停止
    sleep 1
done

# ステップ 5: 完了メッセージと処理時間を表示
end_time=$(date +%s)
total_time=$((end_time - start_time))
total_hours=$((total_time / 3600))
total_minutes=$((total_time % 3600 / 60))
total_seconds=$((total_time % 60))
echo "バックテストが正常に完了しました。 (処理時間: ${total_hours}h ${total_minutes}m ${total_seconds}s)"
