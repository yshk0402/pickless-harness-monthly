import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from monthly_report.core import HarnessError, dump_json, load_json, run_pipeline
from monthly_report.render import render_run


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures" / "sanitized-complex"


class CliAndRenderTest(unittest.TestCase):
    def make_run(self, temp: str) -> Path:
        out = Path(temp) / "run"
        run_pipeline(
            FIXTURE / "profile.json",
            FIXTURE / "context.json",
            FIXTURE / "campaign_performance.csv",
            FIXTURE / "search_queries.csv",
            out,
        )
        return out

    def test_finalize_requires_human_approval(self):
        with tempfile.TemporaryDirectory() as temp:
            run = self.make_run(temp)
            with self.assertRaisesRegex(HarnessError, "approved review"):
                render_run(run, final=True)
            self.assertFalse((run / "final-report.md").exists())

    def test_approved_run_can_finalize(self):
        with tempfile.TemporaryDirectory() as temp:
            run = self.make_run(temp)
            dump_json(run / "review.json", {"decision": "approved", "reviewer": "human"})
            output = render_run(run, final=True)
            self.assertTrue(Path(output["markdown"]).exists())
            self.assertIn("FINAL / HUMAN APPROVED", Path(output["markdown"]).read_text(encoding="utf-8"))

    def test_selected_sections_control_output(self):
        with tempfile.TemporaryDirectory() as temp:
            run = self.make_run(temp)
            manifest = load_json(run / "manifest.json")
            manifest["selected_sections"] = ["kpi_overview", "questions"]
            dump_json(run / "manifest.json", manifest)
            output = render_run(run)
            report = Path(output["markdown"]).read_text(encoding="utf-8")
            self.assertIn("主要KPI", report)
            self.assertNotIn("商材別実績", report)
            self.assertNotIn("検索語句レビュー", report)

    def test_cli_vertical_slice(self):
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp) / "run"
            command = [
                sys.executable,
                "-m",
                "monthly_report.cli",
                "run",
                "--profile",
                str(FIXTURE / "profile.json"),
                "--context",
                str(FIXTURE / "context.json"),
                "--campaigns",
                str(FIXTURE / "campaign_performance.csv"),
                "--queries",
                str(FIXTURE / "search_queries.csv"),
                "--out",
                str(run),
            ]
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            render = subprocess.run(
                [sys.executable, "-m", "monthly_report.cli", "render", "--run", str(run)],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(render.returncode, 0, render.stderr)
            self.assertTrue((run / "report.html").exists())


if __name__ == "__main__":
    unittest.main()
