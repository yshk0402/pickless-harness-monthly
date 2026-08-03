# 入力契約

## campaign_performance.csv

| 列 | 内容 |
| --- | --- |
| date | `YYYY-MM-DD`。MVPでは月末日で月次1行でもよい |
| platform | データ元識別子 |
| campaign | 広告キャンペーン名。プロファイルとの完全一致 |
| impressions / clicks / cost | 非負数 |
| platform_conversions | 広告管理画面のCV |
| ga4_conversions | GA4由来のCV。platform CVと統合しない |

`date + platform + campaign` の重複はエラー。クリックが表示回数を超える場合もエラー。

## search_queries.csv

`date,campaign,query,clicks,cost,conversions` を必須とする。閾値を満たしたCVなしクエリは候補になるが、除外確定にはならない。

## context.json

対象月、比較月、目標、ターゲット、期間中施策、外部要因、主要CVソース、レビュー担当者、候補抽出閾値を保持する。不足文脈はAIの推測対象ではなく確認事項になる。

## profile.json

顧客を直接特定しない `client_key`、キャンペーン→商材の確定分類、使用するレポートパートを保持する。翌月再利用する設定正本であり、変更は人間が確認する。
