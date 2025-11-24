# 実行ルール (Execution Rules)

本プロジェクトにおけるバックテスト/ライブトレード実行の統一ルールを定義します。

## 基本原則

### 1. bot_run.sh の使用必須

**すべてのバックテスト/ライブ実行は `src/bot_run.sh` を経由すること。**

#### 理由
- **APIキー管理の統一**: `replace_api_key.sh` によるキー注入/復元の自動化
- **ログクリーンアップの自動化**: 実行前に古いログを削除し、ディスク容量を適切に管理
- **セキュリティ**: config.iniへのAPIキー残留を防止し、誤ってキーをコミットするリスクを排除
- **実行時間の計測**: バックテスト所要時間の自動記録

#### 禁止事項
❌ **直接 `python bot.py` を実行しないこと** (デバッグ時を除く)

理由:
- APIキーの手動管理が必要になり、キー漏洩リスク増加
- ログクリーンアップが実行されず、ディスク容量圧迫
- 実行時間が記録されず、パフォーマンス追跡不可

## 実行パターン

### A. 通常バックテスト
```bash
cd src
./bot_run.sh
```

動作:
1. logs/ 以下の `.json`, `.zip` ファイル削除
2. `log.txt`, `err.log` 削除
3. `replace_api_key.sh` で config.ini にAPIキー注入
4. `python bot.py` 実行
5. 実行時間を表示
6. `replace_api_key.sh restore` でAPIキーをプレースホルダに復元

### B. バックグラウンド実行 (ライブトレード)
```bash
cd src
./bot_run.sh bg
```

動作:
- `python bot.py` をバックグラウンドプロセスとして起動
- 標準出力/エラーは `err.log` に記録
- **注意**: APIキーは復元されず、プロセス終了まで config.ini に残留

### C. ログクリーンアップのみ
```bash
cd src
./bot_run.sh clear
```

動作:
- logs/ 以下の `.json`, `.zip` ファイル削除
- `log.txt`, `err.log` 削除
- Bot実行はスキップ

## 自動化スクリプトからの呼び出し

A/B実験、月次バックテスト、グリッドサーチなどの自動化ツールは、**必ず `bot_run.sh` を経由して Bot を実行すること。**

### Good: bot_run.sh を使用
```python
import subprocess
from pathlib import Path

src_dir = Path('/home/satoshi/work/satosystem/src')
result = subprocess.run(
    ['bash', 'bot_run.sh'],
    cwd=str(src_dir),
    capture_output=True,
    text=True,
    timeout=600
)
```

### Bad: bot.py を直接実行 (NG)
```python
# ❌ これは禁止
subprocess.run(['python', 'bot.py'], cwd=src_dir, ...)
```

理由:
- APIキー管理が不統一になる
- ログクリーンアップが実行されない
- 実行時間が記録されない

## 例外: デバッグ時の直接実行

開発時やデバッグ時に限り、`python bot.py` の直接実行を許可:

```bash
cd src
# 手動でAPIキー注入
./replace_api_key.sh

# デバッグ実行
python bot.py

# 手動でAPIキー復元
./replace_api_key.sh restore
```

**注意**: デバッグ後は必ず `replace_api_key.sh restore` を実行し、APIキーを復元すること。

## ファイル構成

```
src/
├── bot_run.sh              # Bot実行のエントリーポイント (必ず使用)
├── replace_api_key.sh      # APIキー注入/復元スクリプト
├── bot.py                  # Bot本体 (直接実行禁止)
└── config.ini              # 設定ファイル (APIキーはプレースホルダで管理)
```

## チェックリスト

バックテスト/ライブ実行前に以下を確認:

- [ ] `src/bot_run.sh` を使用しているか?
- [ ] 自動化スクリプトは `subprocess` で `bot_run.sh` を呼び出しているか?
- [ ] デバッグ後、`replace_api_key.sh restore` を実行したか?
- [ ] config.ini にAPIキーが残留していないか? (コミット前確認)

## 関連ドキュメント

- [ARCHITECTURE_OVERVIEW.md](./ARCHITECTURE_OVERVIEW.md): Component Responsibilities に "Execution Rules" を追記済み
- [Readme.md](../Readme.md): "実行方法" セクションに bot_run.sh 使用例を記載

## 最適化作業の実施記録

### 2025-11-21: Keltner Channel 検証 & Pyramiding 最適化

**実施タスク**:
1. Keltner Channel Filter の最終判定 (12パラメータスイープ)
2. Pyramiding (entry_times) パラメータの最適化 (5候補テスト)

**Keltner結果**: 全12設定で PnL -35.21 → **不採用決定**  
**Pyramiding結果**: entry_times=4 を採用 (PnL=107.10, DD=49.75%, Sharpe=0.343)

詳細は [ARCHITECTURE_OVERVIEW.md](./ARCHITECTURE_OVERVIEW.md) の "Strategy Optimization History" を参照。

## 改訂履歴

- 2025-11-21: 初版作成。A/B実験スクリプトでの直接実行を防止するため、ルールを明文化。最適化作業記録セクション追加。
