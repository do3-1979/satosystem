---
description: ラズパイ本番BOTのログを取得・分析し、期待通りの動作かを確認するスキル。BOT稼働確認・ログ取得・エラー確認を依頼されたときに使用する。
applyTo: "**"
---

# RPi本番BOTログ確認スキル

## 目的

Raspberry Piで稼働中の本番BOTのログを取得し、以下を検証する：
- BOTが継続稼働しているか
- エラー・異常が発生していないか
- シグナルとエントリー条件が戦略通りか
- 現在のポジション・残高状態

## 手順

### 1. ログファイルの場所を確認

```bash
ssh raspberry_pi "ls -la ~/work/satosystem/src/logs/"
```

確認するファイル：
- `bot_YYYYMMDD_HHMMSS.log` — メインBOTログ（最も新しいもの）
- `latest_status.json` — 現在のBOT状態（ローソク足・指標・ポジション）
- `bot.pid` — プロセスID（ファイルがあれば起動中）

### 2. BOT設定と起動確認（ログ先頭）

```bash
ssh raspberry_pi "head -35 ~/work/satosystem/src/logs/<最新ログ>"
```

確認項目：
- `Back Test Mode: 0` — 本番モードか
- `Risk Percentage` / `Leverage` / `Market` — 設定値
- `BOT START` の日時 — いつから稼働しているか

### 3. 最新動作確認（ログ末尾）

```bash
ssh raspberry_pi "tail -100 ~/work/satosystem/src/logs/<最新ログ>"
```

確認項目：
- 直近のタイムスタンプが現在時刻に近いか（1分以内が正常）
- `合算証拠金モード` ログが毎分出力されているか
- `unionAvailable` の残高推移（大きな減少がないか）

### 4. エラー・シグナル抽出

```bash
ssh raspberry_pi "grep -E 'ERROR|WARNING|シグナル|エントリー|エグジット|LONG|SHORT|ポジション|注文|約定|利益|損失|BUY|SELL|entry|exit|signal|position|order|strategy_A|全Strategy' ~/work/satosystem/src/logs/<最新ログ> | tail -50"
```

確認項目：
- `ERROR` の種類と頻度
- `[新指標] strategy_A: BUY/SELL` — シグナル発生の記録
- `[新指標] 全Strategy: NONE` — シグナル消滅の記録
- `メインループエラー` — 致命的エラーの有無

### 5. エラー統計

```bash
ssh raspberry_pi "echo '=== ERRORカウント ===' && grep -c 'ERROR' ~/work/satosystem/src/logs/<最新ログ> && echo '=== RATE LIMIT回数 ===' && grep -c 'RATE LIMIT' ~/work/satosystem/src/logs/<最新ログ> && echo '=== メインループエラー ===' && grep 'メインループエラー' ~/work/satosystem/src/logs/<最新ログ>"
```

### 6. 最新ステータス確認

```bash
ssh raspberry_pi "cat ~/work/satosystem/src/logs/latest_status.json | python3 -m json.tool | head -40"
```

確認項目：
- `updated_at` — 最後の更新時刻（BOT稼働確認）
- `decision` / `side` / `position_side` — 現在のシグナル・ポジション
- `pnl` / `total_pnl` — 損益
- `pvo_val` — PVO値（マイナスなら出来高が少なく静観が正常）
- `adx` — ADX値（25以上でトレンド相場）
- `dc_h` / `dc_l` — ドンチャン上限/下限
- `close` vs `dc_h`/`dc_l` — エントリー条件の達成度

## 判定基準

### ✅ 正常の条件

| チェック項目 | 正常の目安 |
|---|---|
| ログのタイムスタンプ | 直近1〜2分以内のログがある |
| ERROR件数 | 少数（3日間で30件未満）かつ全て自動回復 |
| RATE LIMIT | 自動回復している（`ERROR - 最新価格取得エラー復帰`が続く） |
| メインループエラー | 0件 または 1件（連続ではない） |
| ポジション未保有 | ドンチャンにブレイクアウトなし＋PVO≦0 なら静観が正常 |
| 残高 | 開始残高から大きく減少していない |

### ⚠️ 要注意の条件

| 状況 | 対応 |
|---|---|
| ログが5分以上止まっている | BOTクラッシュの可能性 → `bot.pid`でプロセス確認 |
| RATE LIMIT が回復しない（連続ERROR） | APIキーの制限超過 → 取引所ダッシュボード確認 |
| `メインループエラー` が複数 | 例外の原因を確認・Task 40g（API耐障害性）参照 |
| pnl がマイナスで急拡大 | ポジション状態と価格を確認 |

### エントリーが発生しない理由（正常な場合）

Donchian Breakout戦略では以下が全て満たされて初めてエントリーする：
1. **ドンチャン上/下限突破**（`close > dc_h` または `close < dc_l`）
2. **PVO条件**（PVO > 閾値10）
3. **新指標（strategy_A）の方向一致**

`[新指標] strategy_A: BUY` だけではエントリーしない。
ドンチャン上限（dc_h）に価格が届いていない間は静観が正常動作。

## 出力フォーマット

分析後、以下の形式で報告する：

```
## ログ分析結果

### BOT稼働状況 ✅/⚠️/❌
| 稼働開始 | YYYY-MM-DD HH:MM |
| 最新ログ | YYYY-MM-DD HH:MM |
| 動作サイクル | 毎分1回 正常/異常 |
| 現在残高 | XX.XX USDT |

### シグナル履歴（直近）
| 日時 | シグナル |

### エラーサマリ
- ERROR件数: X件
- RATE LIMIT: X回（全て自動回復/未回復あり）
- メインループエラー: X件

### 現在の市場状況
- 現在価格: XX,XXX USD
- ドンチャン上限（dc_h）: XX,XXX USD  （上限まで +X,XXX USD, X.X%）
- ドンチャン下限（dc_l）: XX,XXX USD
- PVO: XX.XX （出来高十分/不足）
- ADX: XX.XX （トレンド/レンジ）

### 総合評価
BOTは期待通りに動作しています / 要確認事項あり...
```
