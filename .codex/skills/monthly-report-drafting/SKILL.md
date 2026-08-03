---
name: monthly-report-drafting
description: 「先月と今月の広告CSVから月次レポートを作りたい」などの自然な依頼を受け、入力確認、検証済み集計、コメント下書き、人間レビューまで案内する。
---

# 月次レポート作成支援

Codexでの正本は `.agents/skills/monthly-report-drafting/SKILL.md`。ユーザーにはCLI名や専門Agent名を要求せず、自然な日本語から処理を進める。入力不足時の質問は最大3つとする。

## 実行前

- `validation.json.status == passed` を確認する。
- 正本は `facts.json`。LLMが数値を再計算・上書きしない。
- `llm-packet.json` の制約と案件文脈を読む。

## 作業

- 事実、仮説、提案、未確認事項を別オブジェクトにする。
- 数値の文には `evidence_refs`、仮説には `confidence` と反証条件を付ける。
- 顧客向けコメントは短く、社内向け仮説は検証順序まで書く。
- 検索語句は除外候補まで。人間判断を求める。
- `render` 後、人間レビューへ渡す。

## ゲート

人間が数値・解釈・顧客表現・改善候補を明示承認するまで `finalize` しない。社外送付と媒体変更はこのSkillの外である。
