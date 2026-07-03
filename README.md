# satosystem next-gen: 分散CTAボット

分散トレンドフォロー + ボラティリティ・ターゲティングの暗号通貨/金 自動取引ボット。
前身（gen2, `master`ブランチ）の徹底検証で得た教訓をゼロベース設計に反映している。

トレード専門用語に詳しくない人向けの解説は [docs/guide.html](docs/guide.html) を参照
（仕組み・エッジの根拠・バックテストレポートの読み方・用語集）。

## 設計原則（gen2の失敗の構造的修正）

| gen2の失敗 | 本プロジェクトの対策 |
|---|---|
| バックテストとライブで別々の約定処理 → 静かに乖離 | fill/costロジックを `cta/execution.py` に一本化し両者で共有 |
| ストップが実際は4H終値約定（死にコード） | シグナルは必ず**次足始値±slippage**で約定。同足約定は構造的に不可能 |
| 50+パラメータを8四半期に適合（過学習） | 自由パラメータ最小（トレンドホライズン3組+vol窓のみ）+感応度分析必須 |
| 単一四半期（2024Q4）依存の宝くじ的利益 | 複数資産・逆vol配分で収益源を分散、利益集中度をレポートで常時監視 |
| 3.5ヶ月ゼロ取引に気づけず | signal価格 vs fill価格の乖離を全取引でロギング |

## 構成

```
cta/
  data.py       OHLCVキャッシュ読込 + バックオフ付き追加取得 + funding履歴
  execution.py  約定・コストモデル（バックテスト/ライブ共有・最重要モジュール）
  strategy.py   トレンドシグナル + 逆vol配分 + volターゲティング + サーキットブレーカー
  engine.py     バックテストエンジン（連続運用・資本リセットなし）
  validate.py   walk-forward OOS / コストストレス / パラメータ感応度
  report.py     HTMLレポート生成
  paper.py      ペーパートレーダー（engine と同一の execution/strategy を使用）
tests/          回帰テストスイート
config/         設定（結果は使用configとコミットハッシュと共に保存）
```

## 使い方

```bash
pip install -r requirements.txt
python run_backtest.py                 # バックテスト + HTMLレポート(out/report.html)
python run_validation.py               # Phase 3 検証ゲート一式
python run_paper.py --once             # ペーパートレード1サイクル（発注なし）
pytest tests/                          # 回帰テスト
```

## 安全原則

- **実発注コードはユーザーの明示的承認まで有効化しない**（ペーパーまで）
- API鍵・秘密情報はコミットしない（`.gitignore`参照）
- サーキットブレーカー: DD35%でデレバレッジ、DD40%で全クローズ+停止
