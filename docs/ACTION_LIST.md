# ACTION LIST

このファイルでは `DEVELOPMENT_RULES.md` に基づいて、現在の gen2 ブランチの課題をTODO/PROGRESS/DONE で管理します。

## TODO
- [ ] `nextarch` の `8e6e543` 以降のコミットを一覧化し、移植可能な Logic/Config の改修点を整理する。
- [ ] ARCHITECTURE_OVERVIEW に gen2 ブランチの構成と分析結果を記載し、知見をアーカイブする。
- [ ] docs/analysis 配下に JSON を追加し、現行のファイル構造・役割の分析結果を残す（ソースコード変更前の基準資料として活用）。
- [ ] レグレッションテストの観点から最低限必要と判断したシナリオを抽出し、`report_tmp/` に骨子を記録後、`ARCHITECTURE_OVERVIEW` に参照先を明記する。
- [ ] `nextarch` で追加された変更群（ログ設定、visualizer 強化、config キャッシュ、ドキュメント整理、テスト強化など）をカテゴリごとに整理し、gen2 に必要な修正だけを移植する。
- [ ] gen2 に不要な大容量ファイルやキャッシュ（`.api_key.secure_backup_*`, `ohlcv_data/`, `cache.db`, `output_configs/`など）が混在しているため、削除対象を特定し、コマンドを整理したうえで `ACTION_LIST` に明記する。

## PROGRESS
- [ ] コミットの確認と優先順位化: `ae38b9d` までの改善は「config/log adjustments」「visualizer/plot fixes」「doc/test structure」「OHLCV cache cleanup」「logging/error handling」「indicator/strategy robustness」の6つのグループに分けられると仮定し、移植方針を検討中。
- [ ] プロジェクトルール文書を整備し、今後のドキュメント更新ガイドとして共有する（進行中）。

## DONE
- [ ] 指定ハッシュ `8e6e543` に復帰し、新規ブランチ `gen2` を作成済み。

```