import tempfile
import unittest
from pathlib import Path

from scripts.install_skills import install


class SkillInstallTest(unittest.TestCase):
    def test_installs_both_skill_variants(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            for target in ("claude", "codex"):
                destination = install(target, root / target)
                skill = destination / "SKILL.md"
                self.assertTrue(skill.exists())
                text = skill.read_text(encoding="utf-8")
                self.assertIn("自然", text)
                self.assertIn("月次レポート", text)


if __name__ == "__main__":
    unittest.main()
