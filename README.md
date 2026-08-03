# pickless-monthly-report-harness

ピクルス社の月次レポート作業を、`手動CSV入力 → 決定的集計 → 事実表 → AIコメント用パケット → 人間承認 → レポート下書き`まで一気通貫で再現するprivate前提のMVPです。

2026-07-27のヒアリングで確認した「キャンペーン数と商材数による物量」「BigQuery/GA4をまたぐ数値」「初回に分類を対話で決めて翌月再利用」「顧客ごとにパートを増減」「除外判断は候補まで」という境界を、まず合成CSVで検証できる形にしています。日立システムズ系の複雑なレポートを想定していますが、実顧客名・実データは含みません。

## できること

- CSVの必須列・型・期間・非負値・重複を検査
- キャンペーン一覧から、商材グルーピングの初回確認票を生成
- 人間が確定した分類と表示セクションを案件プロファイルとして再利用
- 当月・前月、商材別、キャンペーン別のKPIをPythonで集計
- プラットフォームCVとGA4 CVを別指標として保持し、混ぜずに表示
- 高コストかつCVなしの検索語句を「除外候補」として抽出（自動除外なし）
- 事実、提案、未確認事項を分離したLLM用JSONパケットを生成
- 人間承認前は明示的なDRAFT、承認後だけFINALを生成
- 選択したレポートパートだけをMarkdown/HTMLへ出力

## 5分で試す

Python 3.9以上、外部パッケージ不要です。

```bash
python3 -m monthly_report.cli discover \
  --campaigns fixtures/sanitized-complex/campaign_performance.csv \
  --out /tmp/monthly-report-demo/grouping-questions.json

# fixtureでは回答済みプロファイルを同梱しているため、そのまま実行できます
python3 -m monthly_report.cli run \
  --profile fixtures/sanitized-complex/profile.json \
  --context fixtures/sanitized-complex/context.json \
  --campaigns fixtures/sanitized-complex/campaign_performance.csv \
  --queries fixtures/sanitized-complex/search_queries.csv \
  --out /tmp/monthly-report-demo/run-001

python3 -m monthly_report.cli render \
  --run /tmp/monthly-report-demo/run-001
```

この時点の `report.md` / `report.html` は未承認ドラフトです。内容確認後に承認します。

```bash
python3 -m monthly_report.cli review \
  --run /tmp/monthly-report-demo/run-001 \
  --decision approved \
  --reviewer "案件責任者" \
  --note "数値、解釈、顧客表現を確認"

python3 -m monthly_report.cli finalize \
  --run /tmp/monthly-report-demo/run-001
```

`finalize` は承認がなければ失敗します。生成される主なファイルは次の通りです。

```text
run-001/
  manifest.json             入力ハッシュ、期間、コード版
  validation.json           入力検査結果
  facts.json                決定的な集計正本
  facts.md                  人間が確認しやすい事実表
  llm-packet.json           AIに渡してよい事実・制約・依頼
  comment-drafts.json       根拠参照つきのコメントたたき台
  review.json               人間の承認記録
  report.md / report.html   未承認ドラフト
  final-report.md/html      承認後だけ生成
```

## 初回の商材分類

`discover` の出力には、入力CSVで見つかった全キャンペーンが並びます。`product_group` を人間が埋め、次で再利用可能なプロファイルにします。

```bash
python3 -m monthly_report.cli configure \
  --answers /tmp/monthly-report-demo/grouping-answers.json \
  --profile profiles/sanitized-client.json
```

キャンペーンが翌月増えた場合、`run` は未分類キャンペーンをエラーにして止まります。名前から勝手に商材を推測しません。

## AIとの使い方

リポジトリをClaude CodeまたはCodexで開き、「先月と今月の広告CSVから月次レポートを作りたい」のように自然文で依頼できます。CLI名や専門Agent名を指定する必要はありません。不足している入力はAIが最大3問ずつ確認し、分類、集計、下書き、レビューの順に案内します。

`llm-packet.json` を使う段階では、AIが変更してよいのは解釈・文案・確認事項だけです。`facts.json` の値は変更しません。AIコメントには必ず `evidence_refs` と `confidence` を持たせ、事実・仮説・提案を分離します。

- Claude: `.claude/skills/monthly-report-drafting/SKILL.md`
- Codex: `.agents/skills/monthly-report-drafting/SKILL.md`

### Skillのインストール

ユーザー領域へ両方のSkillを配置する場合:

```bash
python3 scripts/install_skills.py --target both
```

Claude Codeは `~/.claude/skills/monthly-report-drafting`、Codexは `~/.codex/skills/monthly-report-drafting` に配置されます。インストール後も、実作業はこのリポジトリを開いて自然文で始めます。

## 現時点の境界と次段階

これは原型であり、本番接続はまだ行いません。次段階ではCSVと同じ正規化契約へ、BigQuery入力アダプターとGA4入力アダプターを追加します。認証は個人アカウントの恒常共有を避け、対象案件だけのread-only権限、実行時認証、監査ログ、失敗時のCSVフォールバックを前提にします。API取得失敗時に古いデータを黙って使う設計にはしません。

HTMLは顧客提出用デザインの完成版ではありません。既存スライドテンプレート、実レポート定義、近藤さんの分析プレイブック、過去修正例を受領後、編集可能スライド生成・PDFレンダリング・全ページ目視検査を追加します。

## 検証

```bash
python3 -m unittest discover -v
python3 -m monthly_report.cli --help
```
