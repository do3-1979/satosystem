# ACTION LIST

このファイルでは `DEVELOPMENT_RULES.md` に基づいて、現在の gen2 ブランチの課題をTODO/PROGRESS/DONE で管理します。

## TODO

| ジャンル                | No. | タスク内容                                                                                       | 関連コミット/備考                | 優先度 |
|------------------------|-----|--------------------------------------------------------------------------------------------------|----------------------------------|--------|
| バックテスト高速化      | 2   | バックテスト時に1分足を使わず、2時間足等の長い足で進行・集計するよう修正                         | 3161b0a                          | ★★★★★ |
| ログ制御・出力          | 3   | drawdown計算の統一・修正                                                                         | 71efcfe, 7e9c659, 68a51dc        | ★★★★☆ |
| ログ制御・出力          | 4   | PnL時系列エクスポート機能の実装                                                                  | 6efcedc                          | ★★★★☆ |
| ログ制御・出力          | 5   | full-loggingオプションのBot反映                                                                  | bff567b                          | ★★★☆☆ |
| ログ制御・出力          | 6   | ログパイプライン自動化・データ保持ポリシー更新                                                   | cbabd9d                          | ★★★☆☆ |
| visualizer拡張          | 7   | Plotlyインタラクティブ可視化・PnLサブプロット追加                                                | cbc3b18                          | ★★★★☆ |
| visualizer拡張          | 8   | EXIT/ADDアクションの可視化                                                                       | 50f6a33                          | ★★★★☆ |
| visualizer拡張          | 9   | Keltnerチャネル・Volume bars等の拡張                                                             | 1b67994, 14b1ece                 | ★★★☆☆ |
| doc/test整備           | 10  | ドキュメント統合・体系化                                                                         | 814ec47, 2e5e837, 1dd7658        | ★★★☆☆ |
| doc/test整備           | 11  | テストランナー統合・verify_all.py追加                                                            | 35508c6, 5ce4761                 | ★★★☆☆ |
| doc/test整備           | 12  | ドキュメント構造テスト追加                                                                       | 5ce4761                          | ★★★☆☆ |
| doc/test整備           | 13  | analysis/project_structure.json・ARCHITECTURE_OVERVIEW.mdにクラス・メソッド一覧を反映             | 本分析                           | ★★★☆☆ |
| config/キャッシュ管理   | 13  | config.iniのプレースホルダ化・コメント整形                                                       | 38b761d, d6c7da3, 26c9f48        | ★★★☆☆ |
| config/キャッシュ管理   | 14  | OHLCV SQLiteキャッシュ統合                                                                       | 53bab64, 631825e                 | ★★★☆☆ |
| config/キャッシュ管理   | 15  | path_utils.pyによるパス管理の一元化                                                              | bbd8514                          | ★★★☆☆ |
| スクリプト統合・運用    | 16  | backtest.pyへの機能統合                                                                          | 7bbbcf9, 604848c                 | ★★★☆☆ |
| スクリプト統合・運用    | 17  | bot_run.sh, replace_api_key.shの整理                                                             | d683227                          | ★★★☆☆ |

## PROGRESS

| ジャンル                | No. | タスク内容                                                                                       | 進捗                             |
|------------------------|-----|--------------------------------------------------------------------------------------------------|----------------------------------|
| テスト体制              | 1   | コミット前のレグレッションテスト作成                                                             | 370dd59, a103b69: pytest + 4項目 |

## DONE
1. Document governance docs
	- `docs/DEVELOPMENT_RULES.md`、`docs/ACTION_LIST.md`、および `docs/analysis/project_structure.json` を整備し、gen2 で今後の設計・テストルールを明文化。
2. Update architecture overview
	- `docs/ARCHITECTURE_OVERVIEW.md` を gen2 現況（ルール、ドキュメント参照、ローカルキャッシュの扱いなど）に合わせて更新。
4. Cleanup local assets and verify deletions
	- 非追跡のキャッシュ/バックアップ（`.api_key.secure_backup_*`、`cache.db`、`output_configs/`、`ohlcv_data/` など）の削除は意図的であることを確認。`ohlcv_data/` を `.gitignore` に追加し、リポジトリに含めずローカルキャッシュとして扱う方針を明記。

```