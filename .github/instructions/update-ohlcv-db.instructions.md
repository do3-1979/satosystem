---
description: OHLCVキャッシュDBを更新するスキル。「OHLCVデータ更新」「バックテスト用データ取得」「価格データが古い」を依頼されたときに使用する。
applyTo: "**"
---

# OHLCVキャッシュDB更新スキル

## 目的

`ohlcv_data/ohlcv_cache.db` に Bybit APIから4H足BTC/USDTデータを取得・追記し、バックテストに使用するデータを最新化する。

## コマンド早見表

```bash
cd /home/satoshi/work/satosystem

# 最新日以降を追記（通常はこれだけでOK）
./commands/prj-update-ohlcv-db

# DB統計確認（何年分のデータが入っているか確認）
./commands/prj-update-ohlcv-db --stats

# 特定年のデータを取得
./commands/prj-update-ohlcv-db --year 2024
./commands/prj-update-ohlcv-db --year 2025
./commands/prj-update-ohlcv-db --year 2026

# 2023年11月以降を全件取得（初期構築・再構築用）
./commands/prj-update-ohlcv-db --full
```

## 使い分けガイド

| 状況 | 使用コマンド |
|---|---|
| 通常のバックテスト前 | `./commands/prj-update-ohlcv-db`（差分追記） |
| 最新データがない | `./commands/prj-update-ohlcv-db`（差分追記） |
| 何年分あるか確認したい | `./commands/prj-update-ohlcv-db --stats` |
| 特定年のデータが欠けている | `./commands/prj-update-ohlcv-db --year <年>` |
| DBを最初から作り直したい | `./commands/prj-update-ohlcv-db --full`（時間がかかる） |

## データ仕様

| 項目 | 内容 |
|---|---|
| 取引所 | Bybit |
| 市場 | BTC/USDT |
| 時間足 | 4H（240分） |
| 保存先 | `ohlcv_data/ohlcv_cache.db` |
| 最古データ | 2023-11〜 |

## バックテスト設定との関係

`config.ini` の以下の設定と一致したデータが使われる：

```ini
[GENERAL]
use_cached_data_for_hot_test = 1   # 1=SQLiteキャッシュ使用（高速）
start_time = 2025/01/01 00:00
end_time   = 2025/12/31 23:59
time_frame = 240
```

バックテスト前にDBに対象期間のデータが存在することを確認すること。

## 確認手順

```bash
# 1. DB統計で期間確認
./commands/prj-update-ohlcv-db --stats

# 2. 不足があれば追記
./commands/prj-update-ohlcv-db

# 3. バックテスト実行
./commands/prj-run-regression --full
```
