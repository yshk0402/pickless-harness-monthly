from __future__ import annotations

import html
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from .core import HarnessError, _fmt_metric, _pct, dump_json, load_json


SECTION_TITLES = {
    "executive_summary": "エグゼクティブサマリ",
    "kpi_overview": "主要KPI",
    "product_breakdown": "商材別実績",
    "campaign_breakdown": "キャンペーン別実績",
    "search_query_review": "検索語句レビュー",
    "actions": "改善候補・次アクション",
    "questions": "確認事項",
}


def _metric_table(item: Mapping[str, Any]) -> list[str]:
    lines = ["| KPI | 当月 | 前月 | 前月比 |", "| --- | ---: | ---: | ---: |"]
    for key in ("impressions", "clicks", "cost", "platform_conversions", "platform_cpa", "ga4_conversions", "ga4_cpa"):
        lines.append(
            f"| {key} | {_fmt_metric(key, item['current'][key])} | {_fmt_metric(key, item['previous'][key])} | {_pct(item['changes'][key])} |"
        )
    return lines


def render_markdown(
    manifest: Mapping[str, Any],
    facts: Mapping[str, Any],
    comments: Mapping[str, Any],
    approved: bool,
) -> str:
    label = "FINAL / HUMAN APPROVED" if approved else "DRAFT / HUMAN REVIEW REQUIRED"
    lines = [
        f"# 月次レポート — {manifest['client_key']}",
        "",
        f"> **{label}**",
        "",
        f"対象期間: {facts['period']['current']} / 比較期間: {facts['period']['previous']}",
        "",
    ]
    sections: Sequence[str] = manifest["selected_sections"]
    if "executive_summary" in sections:
        lines.extend(["## エグゼクティブサマリ", ""])
        for item in comments["facts"]:
            lines.append(f"- {item['text']}  ")
            lines.append(f"  根拠: `{', '.join(item['evidence_refs'])}`")
        lines.extend(["", "> 原因解釈は担当者確認前の仮説です。", ""])
        for item in comments["hypotheses"]:
            lines.append(f"- {item['text']}（確度: {item['confidence']}）")
    if "kpi_overview" in sections:
        lines.extend(["", "## 主要KPI", ""])
        lines.extend(_metric_table(facts["overall"]))
        lines.extend(["", "媒体CVとGA4 CVは別経路のため、値を統合していません。", ""])
    for section, fact_key in (("product_breakdown", "by_product"), ("campaign_breakdown", "by_campaign")):
        if section in sections:
            lines.extend(["", f"## {SECTION_TITLES[section]}", ""])
            for item in facts[fact_key]:
                lines.extend([f"### {item['name']}", ""])
                lines.extend(_metric_table(item))
                lines.append("")
    if "search_query_review" in sections:
        lines.extend(["", "## 検索語句レビュー", "", "以下は除外の確定ではなく、人間が確認する候補です。", ""])
        candidates = facts["query_exclusion_candidates"]
        if candidates:
            lines.extend(["| 検索語句 | キャンペーン | クリック | 費用 | 状態 |", "| --- | --- | ---: | ---: | --- |"])
            for item in candidates:
                lines.append(f"| {item['query']} | {item['campaign']} | {item['clicks']:.0f} | {item['cost']:,.0f}円 | 候補・要判断 |")
        else:
            lines.append("設定閾値に該当する候補はありません。")
    if "actions" in sections:
        lines.extend(["", "## 改善候補・次アクション", ""])
        for item in comments["proposals"]:
            lines.append(f"- [ ] {item['text']}")
    if "questions" in sections:
        lines.extend(["", "## 確認事項", ""])
        if comments["questions"]:
            lines.extend(f"- {item}" for item in comments["questions"])
        else:
            lines.append("- 追加確認事項なし")
    lines.extend(["", "---", "", "このレポートは自動送付されません。媒体設定も変更しません。", ""])
    return "\n".join(lines)


def markdown_to_html(markdown: str) -> str:
    # Deliberately small, dependency-free preview renderer. The Markdown remains the source.
    escaped = html.escape(markdown)
    return f"""<!doctype html>
<html lang=\"ja\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width\">
<title>Monthly report draft</title>
<style>
body{{margin:0;background:#f3f4f6;color:#172033;font-family:-apple-system,BlinkMacSystemFont,'Noto Sans JP',sans-serif;line-height:1.65}}
main{{max-width:1060px;margin:40px auto;background:#fff;padding:56px 64px;box-shadow:0 8px 28px #0002}}
pre{{white-space:pre-wrap;font:inherit;margin:0}} @media(max-width:700px){{main{{margin:0;padding:28px 20px}}}}
</style></head><body><main><pre>{escaped}</pre></main></body></html>"""


def render_run(run_dir: Path, final: bool = False) -> Dict[str, str]:
    manifest = load_json(run_dir / "manifest.json")
    facts = load_json(run_dir / "facts.json")
    comments = load_json(run_dir / "comment-drafts.json")
    review_path = run_dir / "review.json"
    review: Optional[Dict[str, Any]] = load_json(review_path) if review_path.exists() else None
    approved = bool(review and review.get("decision") == "approved")
    if final and not approved:
        raise HarnessError("finalize blocked: an approved review.json is required")
    stem = "final-report" if final else "report"
    markdown = render_markdown(manifest, facts, comments, approved=approved and final)
    markdown_path = run_dir / f"{stem}.md"
    html_path = run_dir / f"{stem}.html"
    markdown_path.write_text(markdown, encoding="utf-8")
    html_path.write_text(markdown_to_html(markdown), encoding="utf-8")
    if final:
        manifest["approval_status"] = "approved"
        manifest["final_outputs"] = [markdown_path.name, html_path.name]
        dump_json(run_dir / "manifest.json", manifest)
    return {"markdown": str(markdown_path), "html": str(html_path)}
