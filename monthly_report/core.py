from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


VERSION = "0.1.0"
REQUIRED_CAMPAIGN_COLUMNS = {
    "date",
    "platform",
    "campaign",
    "impressions",
    "clicks",
    "cost",
    "platform_conversions",
    "ga4_conversions",
}
REQUIRED_QUERY_COLUMNS = {
    "date",
    "campaign",
    "query",
    "clicks",
    "cost",
    "conversions",
}
DEFAULT_SECTIONS = [
    "executive_summary",
    "kpi_overview",
    "product_breakdown",
    "campaign_breakdown",
    "search_query_review",
    "actions",
    "questions",
]
ALLOWED_SECTIONS = set(DEFAULT_SECTIONS)


class HarnessError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> Dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise HarnessError(f"JSON root must be an object: {path}")
    return value


def dump_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


def read_csv(path: Path, required: set[str]) -> List[Dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        missing = sorted(required - columns)
        if missing:
            raise HarnessError(f"{path.name}: missing columns: {', '.join(missing)}")
        rows = [dict(row) for row in reader]
    if not rows:
        raise HarnessError(f"{path.name}: no data rows")
    return rows


def _number(row: Mapping[str, str], key: str, row_number: int) -> float:
    raw = row.get(key, "")
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise HarnessError(f"row {row_number}: {key} is not numeric: {raw!r}") from exc
    if value < 0:
        raise HarnessError(f"row {row_number}: {key} must be non-negative")
    return value


def _month(date_text: str, row_number: int) -> str:
    try:
        return datetime.strptime(date_text, "%Y-%m-%d").strftime("%Y-%m")
    except ValueError as exc:
        raise HarnessError(f"row {row_number}: invalid date: {date_text!r}") from exc


def normalize_campaign_rows(rows: Sequence[Mapping[str, str]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    seen: set[Tuple[str, str, str]] = set()
    for index, row in enumerate(rows, 2):
        key = (row["date"], row["platform"], row["campaign"])
        if key in seen:
            raise HarnessError(f"row {index}: duplicate date/platform/campaign: {key}")
        seen.add(key)
        item: Dict[str, Any] = {
            "date": row["date"],
            "month": _month(row["date"], index),
            "platform": row["platform"].strip(),
            "campaign": row["campaign"].strip(),
        }
        if not item["platform"] or not item["campaign"]:
            raise HarnessError(f"row {index}: platform and campaign are required")
        for key_name in (
            "impressions",
            "clicks",
            "cost",
            "platform_conversions",
            "ga4_conversions",
        ):
            item[key_name] = _number(row, key_name, index)
        if item["clicks"] > item["impressions"]:
            raise HarnessError(f"row {index}: clicks exceed impressions")
        normalized.append(item)
    return normalized


def normalize_query_rows(rows: Sequence[Mapping[str, str]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for index, row in enumerate(rows, 2):
        item: Dict[str, Any] = {
            "date": row["date"],
            "month": _month(row["date"], index),
            "campaign": row["campaign"].strip(),
            "query": row["query"].strip(),
        }
        if not item["campaign"] or not item["query"]:
            raise HarnessError(f"row {index}: campaign and query are required")
        for key_name in ("clicks", "cost", "conversions"):
            item[key_name] = _number(row, key_name, index)
        normalized.append(item)
    return normalized


def discover(campaign_csv: Path) -> Dict[str, Any]:
    rows = normalize_campaign_rows(read_csv(campaign_csv, REQUIRED_CAMPAIGN_COLUMNS))
    campaigns = sorted({row["campaign"] for row in rows})
    return {
        "schema_version": 1,
        "instructions": "各campaignのproduct_groupを人間が入力してください。名前から自動確定しません。",
        "client_key": "CHANGE-ME",
        "campaign_groups": [
            {"campaign": campaign, "product_group": None} for campaign in campaigns
        ],
        "sections": DEFAULT_SECTIONS,
        "questions": [
            "同じ商材としてまとめるキャンペーンはどれですか？",
            "顧客向けレポートに不要なパートはありますか？",
            "プラットフォームCVとGA4 CVのどちらを主要KPIとして説明しますか？",
        ],
    }


def validate_profile(profile: Mapping[str, Any], campaigns: Iterable[str]) -> Dict[str, str]:
    client_key = profile.get("client_key")
    if not isinstance(client_key, str) or not client_key.strip() or client_key == "CHANGE-ME":
        raise HarnessError("profile.client_key must be set")
    entries = profile.get("campaign_groups")
    if not isinstance(entries, list):
        raise HarnessError("profile.campaign_groups must be a list")
    mapping: Dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise HarnessError("campaign_groups entries must be objects")
        campaign = str(entry.get("campaign", "")).strip()
        product = str(entry.get("product_group", "")).strip()
        if not campaign or not product or product == "None":
            raise HarnessError(f"campaign grouping is unanswered: {campaign or '<blank>'}")
        if campaign in mapping:
            raise HarnessError(f"campaign appears twice in profile: {campaign}")
        mapping[campaign] = product
    missing = sorted(set(campaigns) - set(mapping))
    if missing:
        raise HarnessError("unclassified campaigns: " + ", ".join(missing))
    sections = profile.get("sections", DEFAULT_SECTIONS)
    if not isinstance(sections, list) or not sections:
        raise HarnessError("profile.sections must be a non-empty list")
    unknown = sorted(set(map(str, sections)) - ALLOWED_SECTIONS)
    if unknown:
        raise HarnessError("unknown report sections: " + ", ".join(unknown))
    return mapping


def _safe_div(numerator: float, denominator: float) -> Optional[float]:
    if denominator == 0:
        return None
    return numerator / denominator


def _change(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    if current is None or previous in (None, 0):
        return None
    return (current - previous) / previous


def _summarize(rows: Iterable[Mapping[str, Any]]) -> Dict[str, Optional[float]]:
    totals = {
        "impressions": 0.0,
        "clicks": 0.0,
        "cost": 0.0,
        "platform_conversions": 0.0,
        "ga4_conversions": 0.0,
    }
    for row in rows:
        for key in totals:
            totals[key] += float(row[key])
    return {
        **totals,
        "ctr": _safe_div(totals["clicks"], totals["impressions"]),
        "cpc": _safe_div(totals["cost"], totals["clicks"]),
        "platform_cvr": _safe_div(totals["platform_conversions"], totals["clicks"]),
        "platform_cpa": _safe_div(totals["cost"], totals["platform_conversions"]),
        "ga4_cvr": _safe_div(totals["ga4_conversions"], totals["clicks"]),
        "ga4_cpa": _safe_div(totals["cost"], totals["ga4_conversions"]),
    }


def _group_summary(
    rows: Sequence[Mapping[str, Any]],
    group_key: str,
    current_month: str,
    previous_month: str,
) -> List[Dict[str, Any]]:
    groups: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row[group_key])].append(row)
    result: List[Dict[str, Any]] = []
    for name in sorted(groups):
        current = _summarize(row for row in groups[name] if row["month"] == current_month)
        previous = _summarize(row for row in groups[name] if row["month"] == previous_month)
        result.append(
            {
                "name": name,
                "current": current,
                "previous": previous,
                "changes": {
                    key: _change(current.get(key), previous.get(key))
                    for key in current
                },
            }
        )
    return result


def build_facts(
    campaign_rows: Sequence[Dict[str, Any]],
    query_rows: Sequence[Dict[str, Any]],
    profile: Mapping[str, Any],
    context: Mapping[str, Any],
) -> Dict[str, Any]:
    months = sorted({row["month"] for row in campaign_rows})
    if len(months) < 2:
        raise HarnessError("campaign data must contain at least two months")
    current_month = str(context.get("current_month", months[-1]))
    previous_month = str(context.get("previous_month", months[-2]))
    if current_month not in months or previous_month not in months:
        raise HarnessError("context months must exist in campaign data")
    mapping = validate_profile(profile, (row["campaign"] for row in campaign_rows))
    enriched = [{**row, "product_group": mapping[row["campaign"]]} for row in campaign_rows]
    overall_current = _summarize(row for row in enriched if row["month"] == current_month)
    overall_previous = _summarize(row for row in enriched if row["month"] == previous_month)
    thresholds = context.get("query_candidate_thresholds", {})
    min_cost = float(thresholds.get("min_cost", 10000))
    min_clicks = float(thresholds.get("min_clicks", 3))
    query_candidates = []
    for index, row in enumerate(query_rows):
        if row["month"] != current_month:
            continue
        if row["cost"] >= min_cost and row["clicks"] >= min_clicks and row["conversions"] == 0:
            query_candidates.append(
                {
                    "candidate_id": f"query-{index + 1}",
                    "campaign": row["campaign"],
                    "query": row["query"],
                    "clicks": row["clicks"],
                    "cost": row["cost"],
                    "conversions": row["conversions"],
                    "status": "proposed",
                    "action": "human-review-required",
                    "reason": "閾値以上の費用・クリックがあり、当月CVが0件",
                }
            )
    return {
        "schema_version": 1,
        "period": {"current": current_month, "previous": previous_month},
        "metric_definitions": {
            "ctr": "clicks / impressions",
            "cpc": "cost / clicks",
            "platform_cvr": "platform_conversions / clicks",
            "platform_cpa": "cost / platform_conversions",
            "ga4_cvr": "ga4_conversions / clicks",
            "ga4_cpa": "cost / ga4_conversions",
        },
        "overall": {
            "current": overall_current,
            "previous": overall_previous,
            "changes": {
                key: _change(overall_current.get(key), overall_previous.get(key))
                for key in overall_current
            },
        },
        "by_product": _group_summary(enriched, "product_group", current_month, previous_month),
        "by_campaign": _group_summary(enriched, "campaign", current_month, previous_month),
        "query_exclusion_candidates": query_candidates,
        "warnings": [
            "platform_conversionsとga4_conversionsは取得経路が異なるため別指標として表示",
            "検索語句候補は商材・検索意図・ターゲットを確認するまで除外しない",
        ],
    }


def build_comment_drafts(facts: Mapping[str, Any], context: Mapping[str, Any]) -> Dict[str, Any]:
    changes = facts["overall"]["changes"]
    current = facts["overall"]["current"]
    facts_list = [
        {
            "id": "fact-overall-cost",
            "type": "fact",
            "text": f"当月費用は{current['cost']:,.0f}円、前月比{_pct(changes['cost'])}です。",
            "evidence_refs": ["facts.overall.current.cost", "facts.overall.changes.cost"],
        },
        {
            "id": "fact-overall-platform-cpa",
            "type": "fact",
            "text": f"媒体CV基準CPAは{_money(current['platform_cpa'])}、前月比{_pct(changes['platform_cpa'])}です。",
            "evidence_refs": ["facts.overall.current.platform_cpa", "facts.overall.changes.platform_cpa"],
        },
    ]
    hypotheses = [
        {
            "id": "hypothesis-1",
            "type": "hypothesis",
            "text": "商材別・検索語句別の内訳を確認し、CPA変化の寄与要因を特定する必要があります。",
            "confidence": "low",
            "evidence_refs": ["facts.by_product", "facts.query_exclusion_candidates"],
            "human_check": "期間中の施策変更・商材優先度と照合する",
        }
    ]
    proposals = [
        {
            "id": "proposal-query-review",
            "type": "proposal",
            "text": f"除外候補{len(facts['query_exclusion_candidates'])}件を担当者が検索意図・商材適合性と照合してください。",
            "confidence": "medium" if facts["query_exclusion_candidates"] else "low",
            "evidence_refs": ["facts.query_exclusion_candidates"],
            "requires_human_approval": True,
            "external_action_performed": False,
        }
    ]
    missing = []
    for key in ("goals", "target_audience", "changes_during_period", "reviewer"):
        if not context.get(key):
            missing.append(key)
    return {
        "schema_version": 1,
        "status": "draft",
        "facts": facts_list,
        "hypotheses": hypotheses,
        "proposals": proposals,
        "questions": [f"案件文脈が不足しています: {key}" for key in missing],
        "guardrails": {
            "facts_are_immutable": True,
            "automatic_keyword_exclusion": False,
            "automatic_external_send": False,
        },
    }


def build_llm_packet(
    facts: Mapping[str, Any],
    context: Mapping[str, Any],
    sections: Sequence[str],
) -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "task": "検証済み事実を変更せず、顧客向けコメント・内部仮説・改善候補・確認事項を下書きする",
        "context": dict(context),
        "selected_sections": list(sections),
        "verified_facts": facts,
        "rules": [
            "数値はverified_factsだけを引用し、evidence_refsを付ける",
            "事実、仮説、提案、未確認事項を分離する",
            "欠損文脈を推測しない",
            "除外キーワードは候補まで。実行済みと書かない",
            "媒体変更・社外送付を行わない",
            "人間承認前はDRAFTとして扱う",
        ],
        "expected_output": {
            "facts": "事実の短い要約",
            "hypotheses": "根拠・反証条件・confidence付き",
            "proposals": "期待効果・リスク・承認要否付き",
            "questions": "不足文脈の確認事項",
        },
        "guardrails": {
            "facts_are_immutable": True,
            "requires_human_approval": True,
            "automatic_keyword_exclusion": False,
            "automatic_external_send": False,
        },
    }


def _pct(value: Optional[float]) -> str:
    if value is None:
        return "算出不可"
    return f"{value:+.1%}"


def _money(value: Optional[float]) -> str:
    if value is None:
        return "算出不可"
    return f"{value:,.0f}円"


def _fmt_metric(key: str, value: Optional[float]) -> str:
    if value is None:
        return "—"
    if key in {"ctr", "platform_cvr", "ga4_cvr"}:
        return f"{value:.2%}"
    if key in {"cost", "cpc", "platform_cpa", "ga4_cpa"}:
        return f"{value:,.0f}円"
    return f"{value:,.0f}"


def facts_markdown(facts: Mapping[str, Any]) -> str:
    lines = [
        "# 検証済み事実表",
        "",
        f"対象: {facts['period']['current']} / 比較: {facts['period']['previous']}",
        "",
        "| KPI | 当月 | 前月 | 前月比 |",
        "| --- | ---: | ---: | ---: |",
    ]
    for key in ("impressions", "clicks", "cost", "platform_conversions", "platform_cpa", "ga4_conversions", "ga4_cpa"):
        lines.append(
            f"| {key} | {_fmt_metric(key, facts['overall']['current'][key])} | "
            f"{_fmt_metric(key, facts['overall']['previous'][key])} | {_pct(facts['overall']['changes'][key])} |"
        )
    lines.extend(["", "## 注意", ""])
    lines.extend(f"- {warning}" for warning in facts["warnings"])
    return "\n".join(lines) + "\n"


def run_pipeline(
    profile_path: Path,
    context_path: Path,
    campaigns_path: Path,
    queries_path: Path,
    out_dir: Path,
) -> Dict[str, Any]:
    profile = load_json(profile_path)
    context = load_json(context_path)
    campaign_rows = normalize_campaign_rows(read_csv(campaigns_path, REQUIRED_CAMPAIGN_COLUMNS))
    query_rows = normalize_query_rows(read_csv(queries_path, REQUIRED_QUERY_COLUMNS))
    facts = build_facts(campaign_rows, query_rows, profile, context)
    sections = profile.get("sections", DEFAULT_SECTIONS)
    out_dir.mkdir(parents=True, exist_ok=True)
    validation = {
        "status": "passed",
        "campaign_rows": len(campaign_rows),
        "query_rows": len(query_rows),
        "campaigns": sorted({row["campaign"] for row in campaign_rows}),
        "months": sorted({row["month"] for row in campaign_rows}),
        "checks": [
            "required_columns",
            "date_and_numeric_types",
            "non_negative_values",
            "duplicate_campaign_rows",
            "campaign_grouping_complete",
            "comparison_period_present",
        ],
    }
    manifest = {
        "schema_version": 1,
        "harness_version": VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "client_key": profile["client_key"],
        "period": facts["period"],
        "selected_sections": sections,
        "inputs": {
            "profile": {"name": profile_path.name, "sha256": sha256_file(profile_path)},
            "context": {"name": context_path.name, "sha256": sha256_file(context_path)},
            "campaigns": {"name": campaigns_path.name, "sha256": sha256_file(campaigns_path)},
            "queries": {"name": queries_path.name, "sha256": sha256_file(queries_path)},
        },
        "external_actions": [],
        "approval_status": "pending",
    }
    dump_json(out_dir / "manifest.json", manifest)
    dump_json(out_dir / "validation.json", validation)
    dump_json(out_dir / "facts.json", facts)
    (out_dir / "facts.md").write_text(facts_markdown(facts), encoding="utf-8")
    dump_json(out_dir / "llm-packet.json", build_llm_packet(facts, context, sections))
    dump_json(out_dir / "comment-drafts.json", build_comment_drafts(facts, context))
    return {"out": str(out_dir), "validation": validation, "facts": facts}
