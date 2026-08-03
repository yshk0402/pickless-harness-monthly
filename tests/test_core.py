import csv
import json
import tempfile
import unittest
from pathlib import Path

from monthly_report.core import (
    HarnessError,
    build_facts,
    discover,
    load_json,
    normalize_campaign_rows,
    normalize_query_rows,
    read_csv,
    run_pipeline,
    validate_profile,
    REQUIRED_CAMPAIGN_COLUMNS,
    REQUIRED_QUERY_COLUMNS,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "sanitized-complex"


class CoreTest(unittest.TestCase):
    def fixture_facts(self):
        campaign_rows = normalize_campaign_rows(
            read_csv(FIXTURE / "campaign_performance.csv", REQUIRED_CAMPAIGN_COLUMNS)
        )
        query_rows = normalize_query_rows(
            read_csv(FIXTURE / "search_queries.csv", REQUIRED_QUERY_COLUMNS)
        )
        return build_facts(
            campaign_rows,
            query_rows,
            load_json(FIXTURE / "profile.json"),
            load_json(FIXTURE / "context.json"),
        )

    def test_deterministic_totals_and_cpa(self):
        facts = self.fixture_facts()
        self.assertEqual(facts["overall"]["current"]["cost"], 840900.0)
        self.assertEqual(facts["overall"]["current"]["platform_conversions"], 72.0)
        self.assertAlmostEqual(facts["overall"]["current"]["platform_cpa"], 11679.1666667)
        self.assertEqual(facts["period"], {"current": "2026-06", "previous": "2026-05"})

    def test_product_groups_are_reused(self):
        facts = self.fixture_facts()
        names = [item["name"] for item in facts["by_product"]]
        self.assertEqual(names, ["Carbon Suite", "Future Stage"])
        future = next(item for item in facts["by_product"] if item["name"] == "Future Stage")
        self.assertEqual(future["current"]["clicks"], 1050.0)

    def test_query_exclusions_are_only_proposals(self):
        facts = self.fixture_facts()
        self.assertEqual(len(facts["query_exclusion_candidates"]), 2)
        for candidate in facts["query_exclusion_candidates"]:
            self.assertEqual(candidate["status"], "proposed")
            self.assertEqual(candidate["action"], "human-review-required")

    def test_discovery_lists_every_campaign_without_guessing(self):
        result = discover(FIXTURE / "campaign_performance.csv")
        self.assertEqual(len(result["campaign_groups"]), 4)
        self.assertTrue(all(item["product_group"] is None for item in result["campaign_groups"]))

    def test_unclassified_campaign_stops_run(self):
        profile = load_json(FIXTURE / "profile.json")
        profile["campaign_groups"] = profile["campaign_groups"][:-1]
        with self.assertRaisesRegex(HarnessError, "unclassified campaigns"):
            validate_profile(profile, ["Carbon Display", "Carbon Search Core", "FS Search Core", "FS Search Longtail"])

    def test_pipeline_writes_traceable_outputs(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "run"
            run_pipeline(
                FIXTURE / "profile.json",
                FIXTURE / "context.json",
                FIXTURE / "campaign_performance.csv",
                FIXTURE / "search_queries.csv",
                out,
            )
            self.assertEqual(load_json(out / "validation.json")["status"], "passed")
            manifest = load_json(out / "manifest.json")
            self.assertEqual(manifest["approval_status"], "pending")
            self.assertEqual(len(manifest["inputs"]["campaigns"]["sha256"]), 64)
            packet = load_json(out / "llm-packet.json")
            self.assertIn("facts_are_immutable", json.dumps(packet, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
