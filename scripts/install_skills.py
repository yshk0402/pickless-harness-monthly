#!/usr/bin/env python3
"""Install project skills into Claude Code and/or Codex user skill folders."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_NAME = "monthly-report-drafting"


def install(target: str, destination_root: Path | None = None) -> Path:
    if target == "claude":
        source = REPO_ROOT / ".claude" / "skills" / SKILL_NAME
        root = destination_root or Path.home() / ".claude" / "skills"
    elif target == "codex":
        source = REPO_ROOT / ".agents" / "skills" / SKILL_NAME
        root = destination_root or Path.home() / ".codex" / "skills"
    else:
        raise ValueError(f"unsupported target: {target}")

    destination = root / SKILL_NAME
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination, dirs_exist_ok=True)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=("claude", "codex", "both"), default="both")
    parser.add_argument("--destination-root", type=Path)
    args = parser.parse_args()

    targets = ("claude", "codex") if args.target == "both" else (args.target,)
    for target in targets:
        destination = install(target, args.destination_root)
        print(f"installed {target}: {destination}")


if __name__ == "__main__":
    main()
