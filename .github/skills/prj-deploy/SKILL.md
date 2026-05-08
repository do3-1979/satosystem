---
name: prj-deploy
description: "Use when deploying code to Raspberry Pi BOT. Trigger words: deploy, デプロイ, RPiに反映, push and restart, BOT再起動してデプロイ."
---

# prj-deploy

## Purpose
git push → RPi BOT停止 → git pull → BOT再起動 → 稼働状態確認 を一括実行する。

## Command

### 通常デプロイ（push + 再起動 + 状態確認）
```bash
cd /home/satoshi/work/satosystem
./commands/prj-deploy
```

### 状態確認のみ（デプロイなし）
```bash
./commands/prj-deploy --status-only
```

### push + pull のみ（BOT再起動なし）
```bash
./commands/prj-deploy --no-restart
```

## 状態確認の出力内容
- CPU負荷・温度（閾値超えで警告色）
- メモリ利用可能量
- ディスク使用率
- BTC/XAUT BOT プロセス稼働状況（PID・CPU・MEM）
- 両BOTの最新ログ3行

## ⚠️ config.ini 更新時の注意（必須）

RPiの本番BOTは起動時に `src/config.ini` を読み込む。
`prj-deploy` は config.ini をそのままデプロイするが、**RPi上には本番用の設定が手動で施されている場合がある**（`enabled=1` への変更など）。

### config.ini に変更がある場合の手順

1. デプロイ前に差分を確認する
```bash
git diff HEAD~1 src/config.ini
```

2. デプロイ後に RPi 上で本番設定を手動復元する
```bash
# 例: RiskOverlay を本番有効化する場合
ssh raspberry_pi "cd ~/work/satosystem && sed -i 's/^enabled = 0/enabled = 1/' src/config.ini"
```

3. 復元後に BOT を再起動する（BOT停止→確認→再起動）
```bash
ssh raspberry_pi "cd ~/work/satosystem && ./src/start_bot.sh"
```

### 本番BOT で config.ini を上書きしてはいけない設定

| パラメータ | 開発デフォルト | 本番設定 |
|---|---|---|
| `[General] back_test` | 1 | 0 |
| `[General] dummy` | 1 | 0（実取引時） |
| `[RiskOverlay] enabled` | 0 | 1（有効化する場合） |
