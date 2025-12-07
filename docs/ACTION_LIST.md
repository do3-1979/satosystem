# ACTION LIST

このファイルでは `DEVELOPMENT_RULES.md` に基づいて、現在の gen2 ブランチの課題をTODO/PROGRESS/DONE で管理します。

## TODO

| ジャンル                | No. | タスク内容                                                                                       | 関連コミット/備考             | 優先度 |
|------------------------|-----|--------------------------------------------------------------------------------------------------|----------------------------------|--------|
| 実行パス・環境管理      | 0   | **[抜本解決]** 実行ディレクトリ統一（src/ 固定）・パス管理の一元化                               | regression_test_suite.py改修     | ★★★★★ |
| ログ制御・出力          | 3   | drawdown計算の統一・修正                                                                         | 71efcfe, 7e9c659, 68a51dc        | ★★★★☆ |
| ログ制御・出力          | 4   | PnL時系列エクスポート機能の実装                                                                  | 6efcedc                          | ★★★★☆ |
| ログ制御・出力          | 5   | full-loggingオプションのBot反映                                                                  | bff567b                          | ★★★☆☆ |
| ログ制御・出力          | 6   | ログパイプライン自動化・データ保持ポリシー更新                                                   | cbabd9d                          | ★★★☆☆ |
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

3. Backtest optimization No.2 (コミット 9f6f0da)
   - `price_data_management.py`: 1分刻みループから2時間足刻み進行に変更（progress_time を直接進行）
   - `trading_strategy.py`: ストップ判定を close_price から low_price/high_price ベースに変更、スリッページ (±0.5%) を考慮
   - 検証: レグレッションテスト実行、変更前後で[OK][OK][OK][FAIL]一致→回帰なし確認

4. Cleanup local assets and verify deletions
   - 非追跡のキャッシュ/バックアップ（`.api_key.secure_backup_*`、`cache.db`、`output_configs/`、`ohlcv_data/` など）の削除は意図的であることを確認。`ohlcv_data/` を `.gitignore` に追加し、リポジトリに含めずローカルキャッシュとして扱う方針を明記。

5. **[実行パス抜本解決]** 実行ディレクトリ統一（src/ 固定）
   - `regression_test_suite.py`: 実行ディレクトリを WORKSPACE_ROOT から **src/** に変更、sys.path に src/ を追加
   - `bot.py`: sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))) で src/ を明示的に追加
   - `bot_run.sh`: BOT_SCRIPT に絶対パス指定、どのディレクトリから呼び出されても bot.py を正しく参照
   - 効果: ENTRY=0 エラー解消、すべてのレグレッションテスト項目が [OK] に
   - 根本原因: test フォルダからの相対実行で WORKSPACE_ROOT ベースの参照が失敗 → src/ 実行により一貫性確保

6. PSAR初期化期間拡張 (コミット b9f5cc1, 01ed699他)
   - `config.ini` に `psar_lookback_term = 100` を追加（100バー = 8.3日の履歴でトレンド判定精度向上）
   - `config.py` で `get_test_initial_max_term()` を修正、psar_lookback_term を優先的に取得
   - PSAR初期トレンド判定精度向上により、Close > STOP比率が65% → 51%に正常化
   - Sharpe 1.021、利益因子 2.41維持

7. インタラクティブグラフ生成と統合 (Plotlyベース) ✅ **完了**
   - `visualizer.py`: JSONファイル自動検出、Plotlyでインタラクティブグラフ生成
   - グラフ構成: Row1(価格+Donchian+PSAR) / Row2(ボリューム) / Row3(指標) / Row4(PnL)
   - ズーム/パン、凡例切り替え、ホバー情報、PNG出力機能完備
   - `backtest_and_visualize.sh`: bot_run.sh + visualizer.py を統合したワンコマンド実行スクリプト

8. EXIT/ADDアクションの可視化 ✅ **完了**
   - `visualizer.py` に ENTRY/ADD/EXIT マーカー表示機能実装
   - マーカー表示：ENTRY(🔼ライムグリーン), ADD(🔴イエロー), EXIT(🔽赤)
   - ポジション区間を背景色でハイライト（BUY=淡緑/SELL=淡赤）

9. Keltnerチャネル・その他未実装指標削除 ❌ **削除（非実装のため）**
   - visualizer.pyからケルトナーチャネル（43行）、ADX（13行）、ATR（12行）を削除
   - グラフ構成を実装済み指標のみに整理（Donchian、PSAR、Volatility、PVO）
   - **理由**: Keltnerはconfig.ini で `keltner_enabled=False`（本実装なし）、ADX/ATR未実装

10. ドキュメント統合とクリーンアップ ✅ **完了**
    - VISUALIZATION_GUIDE.md を ARCHITECTURE_OVERVIEW.md に統合（「## バックテスト結果の可視化」として追加）
    - REGRESSION_TEST_POLICY.md 削除（regression_test_suite.py実装済み、ACTION_LISTで管理）
    - BACKTEST_OPTIMIZATION_NO2_REPORT.md 削除（完了レポート、参考資料として不要）
    - docs/ ディレクトリ整理完了（206行削除）
