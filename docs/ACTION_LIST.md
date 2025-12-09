# ACTION LIST

このファイルでは `DEVELOPMENT_RULES.md` に基づいて、現在の gen2 ブランチの課題をTODO/PROGRESS/DONE で管理します。

## TODO

| ジャンル                | No. | タスク内容                                                                                       | 関連コミット/備考             | 優先度 |
|------------------------|-----|--------------------------------------------------------------------------------------------------|----------------------------------|--------|
| **戦略最適化**          | 18  | **[完了]** 2025年成績悪化の根本原因分析・四半期別分析 → Stage 1-4 改善戦略策定                  | QUARTERLY_STRATEGY_IMPROVEMENT_PLAN | ★★★★★ |
| **個別トレード改善**    | 19  | **[完了]** 出口戦略の複合指標化（PSAR + PVO + ADX） → MFE失われた利益を75%削減               | INDIVIDUAL_TRADE_EXIT_OPTIMIZATION  | ★★★★★ |
| **個別トレード改善**    | 19a | **[完了]** ExitStrategyV2 統合 - Q4 2025 で -2.63 → +368.20 USD に改善、勝率 100%達成        | BACKTEST_COMPARISON_V2_INTEGRATION  | ★★★★★ |
| **戦略最適化**          | 20  | ウォークフォワード分析の実装・マーケット環境変化への対応力向上                                  | docs/QUARTERLY_BACKTEST_ANALYSIS | ★★★★☆ |
| ログ制御・出力          | 3   | drawdown計算の統一・修正                                                                         | 71efcfe, 7e9c659, 68a51dc        | ★★★★☆ |
| ログ制御・出力          | 4   | PnL時系列エクスポート機能の実装                                                                  | 6efcedc                          | ★★★★☆ |
| ログ制御・出力          | 6   | ログファイル自動整理・定期クリーンアップ機能の実装                                              | QUARTERLY_BACKTEST分析参照       | ★★★☆☆ |
| ログ制御・出力          | 5   | full-loggingオプションのBot反映                                                                  | bff567b                          | ★★★☆☆ |
| doc/test整備           | 10  | ドキュメント統合・体系化                                                                         | 814ec47, 2e5e837, 1dd7658        | ★★★☆☆ |
| doc/test整備           | 11  | テストランナー統合・verify_all.py追加                                                            | 35508c6, 5ce4761                 | ★★★☆☆ |
| doc/test整備           | 12  | ドキュメント構造テスト追加                                                                       | 5ce4761                          | ★★★☆☆ |
| doc/test整備           | 13  | analysis/project_structure.json・ARCHITECTURE_OVERVIEW.mdにクラス・メソッド一覧を反映             | 本分析                           | ★★★☆☆ |
| config/キャッシュ管理   | 13  | config.iniのプレースホルダ化・コメント整形                                                       | 38b761d, d6c7da3, 26c9f48        | ★★★☆☆ |
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

11. OHLCV SQLiteキャッシュ統合 ✅ **完了**
    - ohlcv_cache.py を新規作成: SQLiteベースのOHLCVキャッシュマネージャー
    - 機能: キャッシュの読み書き、JSON→SQLite移行ツール、キャッシュ統計情報取得
    - price_data_management.py を更新: JSONファイルベース→SQLiteに切り替え
    - JSONからSQLiteへの自動移行機能を実装（migrate_from_json）
    - レグレッションテストで動作を検証: すべてのテスト項目が [OK]
    - 効果: OHLCVキャッシュを効率的なSQLiteデータベースで管理、将来の拡張性向上

12. OHLCV キャッシュ検査ツール追加 ✅ **完了**
    - src/ohlcv_cache_inspector.py を新規作成: キャッシュの内容を確認・管理するツール
    - 機能:
      * キャッシュサマリー表示: 総レコード数、ファイルサイズ、パラメータ一覧
      * データ範囲分析: 取得データの期間、セグメント（連続したデータ）を表示
      * 断絶検出: データに途中ギャップがある場合、そのギャップを表示
      * 詳細分析: すべてのパラメータについて詳細情報を表示
    - ohlcv_cache_info.sh ラッパースクリプト: 簡単に実行可能
      * ./ohlcv_cache_info.sh - サマリー表示（デフォルト）
      * ./ohlcv_cache_info.sh coverage - データ範囲と断絶を表示
      * ./ohlcv_cache_info.sh all - 詳細分析
      * ./ohlcv_cache_info.sh help - ヘルプ表示
    - docs/OHLCV_CACHE_TOOL.md ドキュメント追加
    - 効果: キャッシュの内容をいつでも確認でき、データの蓄積状況を把握可能

13. OHLCV キャッシュ部分一致機能追加 ✅ **完了**
    - 改善内容: キャッシュの期間部分一致検索機能を実装
    - ohlcv_cache.py:
      * get_ohlcv_data_partial() メソッドを新規追加
      * キャッシュの期間が要求期間を完全に含んでいる場合に取得
    - price_data_management.py を更新:
      * initialise_back_test_ohlcv_data() で get_ohlcv_data_partial() を使用
    - 効果:
      * 同じタイムフレームでキャッシュ期間の一部だけ必要な場合、サーバアクセスを削減
      * より効率的なキャッシュ利用が可能
      * 完全一致ではなく柔軟な期間マッチングに対応
    - テスト: レグレッションテスト [OK]

14. **四半期別バックテスト分析完了** ✅ **完了**
    - 実行日: 2025-12-09 / 対象期間: 2024/1Q ～ 2025/4Q（8四半期）
    - **成績**: 累積損益 +576.11 USD（2024年 +1,065.23 USD、2025年 -489.11 USD）
    - **ログファイル形式エラー修正**:
      * 問題：Q2 2024、Q3 2025 で `'list' object has no attribute 'get'` エラー
      * 原因：`backtest_summary_*.json`（dict）と詳細ログ（list）が混在
      * 対策：`backtest_summary_*.json` を優先検索、ファイル形式検証を追加
      * 結果：8/8 四半期すべてで成功
    - **主要指標**:
      * 最高利益：Q1 2024 +971.99 USD（利益因子 2.060、勝率 100%）
      * 最大損失：Q1 2025 -216.77 USD（利益因子 0.426、勝率 7.7%）
      * 平均勝率：51.6%、平均利益因子：1.011
    - **問題分析**：2025年の急激な悪化（Sharpe 0.204 → -1.316）は市場環境変化 or パラメータ最適性喪失の可能性
    - 文書化：`docs/QUARTERLY_BACKTEST_ANALYSIS.md` を新規作成、詳細分析とログファイル形式仕様を記載

15. **ホットテスト（ペーパートレード）実装完了** ✅ **完了**
    - 実装内容：ホットテストで本番 API 呼び出しをしつつ、売買注文と残高取得のみペーパー化
    - bybit_exchange.py の修正：
      * `log_info()` → `log()` に統一（Logger クラスに log_info メソッドが存在しないため）
      * ホットテスト時も exchange を初期化（本番 API 呼び出し可能）
      * 価格データ取得（fetch_ohlcv, fetch_latest_ohlcv, fetch_ticker）は本番同等
      * 口座残高取得（get_account_balance）と注文実行（execute_order）のみダミー化
    - 期待動作の達成：
      * 無限ループで 60 秒ごとに価格取得と判断を実行
      * 中断までホットテストが継続
      * 売買注文はペーパー化（実際には実行されない）
    - テスト方法：`./bot_run.sh` で起動（config.ini で API キー置換）

16. **レグレッションテスト固まり問題の解決** ✅ **完了**
    - 問題の原因：config.ini で `back_test = 1, hot_test_dummy_mode = 0` の矛盾した設定
    - 根本原因：back_test = 1（バックテスト）時、ホットテストのペーパートレード設定が無視されるべき
    - 修正内容：
      * config.ini で `back_test = 1` 時は `hot_test_dummy_mode = 1` に統一
      * bybit_exchange.py ですでに正しい判定ロジック実装（back_test = 1 の場合は常にダミーモード）
      * regression_test_suite.py で test_backtest() の複雑な config 置換ロジックを削除（config.ini が正しくなったため不要）
    - OHLCV キャッシュの複数出現について：
      * 確認結果：正常な動作（Q ごとの断絶なし、複数の quarterly_backtest 実行による蓄積）
      * 8つのパラメータ = 8 つの四半期別データセット
      * 各パラメータは 3～4 ヶ月分のデータ、隣同士で重複（想定通り）

17. **メインループエラー修復 - exchange初期化矛盾解決** ✅ **完了**
    - 問題のトリガー：最新のバックテスト実行ログに `'NoneType' object has no attribute 'fetch_ohlcv'` エラー
    - 根本原因：
      * bybit_exchange.py がバックテストモード時に `self.exchange = None` に設定
      * しかし price_data_management.py の update_price_data_backtest() は `self.exchange.fetch_ohlcv()` を呼び出す
      * 矛盾: ダミー取引でもキャッシュ取得に exchange が必須だが、設定では None に
    - 設計パターンの再整理：
      * **バックテストモード**: キャッシュ優先、exchange も初期化（ダミーAPI_KEY使用で実API呼び出し防止）
      * **ペーパートレード**: 本番API + ダミー売買
      * **本番モード**: 本番API + 本番売買
    - 修正内容：
      * bybit_exchange.py の初期化ロジック（lines 86-100）を修正
      * バックテスト時でも exchange インスタンスを生成（ダミーAPI_KEY で実API呼び出し抑制）
      * `is_backtest_mode` フラグを追加、制御を明確化
    - テスト結果：
      * bot.py 直接実行 ✅ エラーなし、バーが正常に進行
      * regression_test_suite.py::test_backtest() ✅ PASS (6.18秒)
      * メインループの処理が2時間足刻みで正常に進行、ENTRY/ADD/EXIT シグナル発火確認


