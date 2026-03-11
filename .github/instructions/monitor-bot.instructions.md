---
description: BOTのリアルタイム稼働状態をターミナルまたはブラウザでモニタリングするスキル。「BOTの状態を見たい」「リアルタイム監視」「モニター起動」を依頼されたときに使用する。
applyTo: "**"
---

# BOTリアルタイム監視スキル

## 目的

稼働中のBOTの現在状態（価格・ポジション・損益・指標）を30秒ごとにリフレッシュしてモニタリングする。

## 2種類のモニター

| モニター | コマンド | 特徴 |
|---|---|---|
| ターミナル版 | `monitor_bot` | SSH先でも確認可、カラー表示 |
| Web版 | `monitor_web` | ブラウザでチャート表示、ローソク足確認可 |

---

## ターミナルモニター（monitor_bot）

### ローカルで実行

```bash
cd /home/satoshi/work/satosystem
./commands/monitor_bot
```

### Raspberry Pi（本番BOT）を監視

```bash
cd /home/satoshi/work/satosystem
./commands/monitor_bot --host raspberry_pi
```

表示内容：
- **プロセス状態**: PID・CPU・MEM・起動時刻
- **最新データ**: BTC終値・DC帯（上限/下限）・PSAR
- **判断**: decision（NONE/ENTRY等）・side・ポジション側
- **損益**: みなし損益・累計損益
- **指標**: ボラティリティ/ADX/PVO・出来高
- **エラー**: recent_errors（直近3件）
- **ローソク足履歴**: 直近5本

更新間隔: 30秒 / 終了: `Ctrl+C`

### 表示色の判断基準

| 指標 | 緑（良好） | 黄（注意） | 赤（警戒） |
|---|---|---|---|
| ボラティリティ | < 2000 | 2000〜2500 | ≥ 2500 |
| ADX | ≥ 31（トレンド） | < 31（レンジ） | — |
| PVO | ≥ 10（出来高十分） | < 10（出来高不足） | — |
| ポジション | BUY（緑）/ SELL（赤）/ NONE（灰） | — | — |
| 損益 | プラス | — | マイナス |

---

## Web版モニター（monitor_web）

### Raspberry Pi のBOTをブラウザで監視

```bash
cd /home/satoshi/work/satosystem
./commands/monitor_web --host raspberry_pi --port 8080
```

→ ブラウザで `http://localhost:8080` を開く

### ローカルのBOT状態を確認（`src/logs/latest_status.json` を直接読む）

```bash
cd /home/satoshi/work/satosystem
./commands/monitor_web --local
```

### ポート指定

```bash
./commands/monitor_web --host raspberry_pi --port 9090
```

起動時に同ポートを使用中のプロセスは自動終了される。

---

## データソース

どちらのモニターも `latest_status.json` を読み取る：

- **SSH経由（--host指定時）**: `~/work/satosystem/src/logs/latest_status.json` をSSHで取得
- **ローカル（--local）**: `src/logs/latest_status.json` を直接読む

`latest_status.json` の更新間隔 = BOTのメインループ間隔（通常60秒）

---

## 注意事項

- `latest_status.json` が更新されない場合、BOTが停止している可能性がある
- その場合はログ確認スキル（`check-rpi-logs.instructions.md`）で詳細を確認する
- Web版モニターはポート8080をデフォルト使用：他のサービスと競合する場合は `--port` で変更
