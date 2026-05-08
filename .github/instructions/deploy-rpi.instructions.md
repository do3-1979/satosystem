---
description: RPiへのデプロイ（git push + BOT停止 + git pull + BOT再起動 + 稼働状態確認）を一括実行するスキル。「デプロイして」「RPiに反映して」「BOT再起動してデプロイ」を依頼されたときに使用する。
applyTo: "**"
---

# RPiデプロイスキル

## 目的

コード変更をRaspberry Piの本番BOTに反映する。以下を一括実行する：
1. `git push origin gen2` — GitHubへプッシュ
2. RPi側 `git pull origin gen2` — 最新コード取得
3. BTC・XAUT両BOTを停止 → 再起動
4. RPi稼働状態チェック（CPU・メモリ・温度・BOTプロセス・最新ログ）

## コマンド早見表

```bash
cd /home/satoshi/work/satosystem

# 通常デプロイ（push → RPi停止 → pull → BOT再起動 → 状態確認）
./commands/prj-deploy

# デプロイせず RPi 状態確認のみ
./commands/prj-deploy --status-only

# BOT再起動なし（push + pull のみ）
./commands/prj-deploy --no-restart
```

## 使い分けガイド

| 状況 | コマンド |
|---|---|
| コミット後にRPiへ反映したい | `./commands/prj-deploy` |
| BOTを止めずにコードだけ更新したい | `./commands/prj-deploy --no-restart` |
| RPiの状態だけ確認したい | `./commands/prj-deploy --status-only` |
| ログ確認も詳しくしたい | `prj-deploy --status-only` の後に `check-rpi-logs` スキルを使用 |

## 前提条件

- コミット済みであること（未コミットの変更は push されない）
- レグレッションテストが全 PASS であること（`./commands/prj-run-regression`）
- RPiへのSSH接続が有効であること（`ssh raspberry_pi` が通ること）
- **BTC・XAUT両BOTがポジションを持っていないこと**（下記「ポジション確認手順」参照）

## ポジション確認手順（デプロイ前に必須）

BOT停止時にポジションが存在すると損失が出る恐れがあるため、デプロイ前に必ずポジション状態を確認する。

```bash
# BTC・XAUT両BOTのポジション状態を確認
ssh raspberry_pi "
  echo '=== BTC BOT ポジション確認 ===' && \
  python3 -m json.tool ~/work/satosystem/src/logs/latest_status.json 2>/dev/null \
    | grep -E 'position_side|decision|side|pnl|updated_at' | head -10
  echo '=== XAUT BOT ポジション確認 ===' && \
  python3 -m json.tool ~/work/satosystem/src/logs/xaut/latest_status.json 2>/dev/null \
    | grep -E 'position_side|decision|side|pnl|updated_at' | head -10
"
```

### 判定基準

| position_side の値 | 判断 | 対応 |
|---|---|---|
| `NONE` | ✅ ポジションなし → デプロイ可 | そのまま進む |
| `LONG` または `SHORT` | ❌ ポジションあり → デプロイ停止 | ポジションがクローズされるまで待機 |

> ポジションを持っている場合は、BOTが自動でクローズするまで待つか、ユーザーに手動クローズを依頼すること。強制デプロイは絶対に行わない。

## 状態チェックの判定基準

| 指標 | 正常 | 警告 | 危険 |
|---|---|---|---|
| CPU負荷（1分平均） | < 2.0 | 2.0〜5.0 | > 5.0 |
| CPU温度 | < 60°C | 60〜75°C | > 75°C |
| ディスク使用率 | < 70% | 70〜85% | > 85% |
| BOTプロセス | 両BOT稼働中 | — | いずれかなし |

## ⚠️ config.ini 更新時の注意（必須）

`config.ini` に変更が含まれるコミットをデプロイする場合、RPi上の本番設定が上書きされる。
デプロイ前後に以下を必ず実施すること。

### デプロイ前: 差分確認

```bash
# ローカルで: config.ini に何が変わったか確認
git diff HEAD~1 src/config.ini | grep '^[+-]' | grep -v '^---\|^+++'
```

### デプロイ後: RPi上で本番設定を手動復元

```bash
# RPi上の config.ini を確認
ssh raspberry_pi "grep -E 'back_test|dummy|enabled' ~/work/satosystem/src/config.ini"

# 必要に応じて本番値に書き換え（例: RiskOverlay有効化）
ssh raspberry_pi "cd ~/work/satosystem && sed -i 's/^enabled = 0/enabled = 1/' src/config.ini"
```

### 本番BOTで保守すべき設定一覧

| パラメータ | 開発デフォルト | 本番設定 | 備考 |
|---|---|---|---|
| `[General] back_test` | 1 | **0** | 必須 |
| `[General] dummy` | 1 | **0**（実取引）/ 1（ペーパー） | 必須 |
| `[RiskOverlay] enabled` | 0 | **1**（有効化する場合） | 任意 |
| `[RiskOverlay] max_drawdown_pct` | 50 | 50（推奨値） | 確認のみ |
| `[RiskOverlay] dd_resume_bars` | 100 | 100（推奨値） | 確認のみ |

> config.ini 変更を含むデプロイ後は、必ず BOT の起動ログ先頭（`head -35`）で設定値が本番値になっているか確認すること。
