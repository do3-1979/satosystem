# ACTION LIST

このファイルでは `DEVELOPMENT_RULES.md` に基づいて、現在の gen2 ブランチの課題をTODO/PROGRESS/DONE で管理します。

## TODO
- 現時点で新たに対応すべき TODO はありません。

## DONE
1. Document governance docs
	- `docs/DEVELOPMENT_RULES.md`、`docs/ACTION_LIST.md`、および `docs/analysis/project_structure.json` を整備し、gen2 で今後の設計・テストルールを明文化。
2. Update architecture overview
	- `docs/ARCHITECTURE_OVERVIEW.md` を gen2 現況（ルール、ドキュメント参照、ローカルキャッシュの扱いなど）に合わせて更新。
3. Capture working context
	- `nextarch` の `8e6e543` 以降のコミットを列挙し、ログ設定･visualizer拡張･doc/test整備などのカテゴリを整理した上で移植方針を検討し、ACTION_LIST に反映。
4. Cleanup local assets and verify deletions
	- 非追跡のキャッシュ/バックアップ（`.api_key.secure_backup_*`、`cache.db`、`output_configs/`、`ohlcv_data/` など）の削除は意図的であることを確認。`ohlcv_data/` を `.gitignore` に追加し、リポジトリに含めずローカルキャッシュとして扱う方針を明記。

```