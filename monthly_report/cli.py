from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .core import HarnessError, discover, dump_json, load_json, run_pipeline, validate_profile
from .render import render_run


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Pickless monthly-report drafting harness")
    commands = root.add_subparsers(dest="command", required=True)

    discover_cmd = commands.add_parser("discover", help="create campaign-grouping questions")
    discover_cmd.add_argument("--campaigns", required=True, type=Path)
    discover_cmd.add_argument("--out", required=True, type=Path)

    configure_cmd = commands.add_parser("configure", help="validate and save answered grouping profile")
    configure_cmd.add_argument("--answers", required=True, type=Path)
    configure_cmd.add_argument("--profile", required=True, type=Path)

    run_cmd = commands.add_parser("run", help="validate, aggregate, and create a review packet")
    run_cmd.add_argument("--profile", required=True, type=Path)
    run_cmd.add_argument("--context", required=True, type=Path)
    run_cmd.add_argument("--campaigns", required=True, type=Path)
    run_cmd.add_argument("--queries", required=True, type=Path)
    run_cmd.add_argument("--out", required=True, type=Path)

    render_cmd = commands.add_parser("render", help="render a human-review draft")
    render_cmd.add_argument("--run", required=True, type=Path)

    review_cmd = commands.add_parser("review", help="record an explicit human review")
    review_cmd.add_argument("--run", required=True, type=Path)
    review_cmd.add_argument("--decision", required=True, choices=("approved", "changes-requested", "rejected"))
    review_cmd.add_argument("--reviewer", required=True)
    review_cmd.add_argument("--note", default="")

    final_cmd = commands.add_parser("finalize", help="render final output after human approval")
    final_cmd.add_argument("--run", required=True, type=Path)
    return root


def main(argv: Optional[List[str]] = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "discover":
            result = discover(args.campaigns)
            dump_json(args.out, result)
            output = {"questions": str(args.out), "campaigns": len(result["campaign_groups"])}
        elif args.command == "configure":
            answers = load_json(args.answers)
            campaigns = [str(item.get("campaign", "")) for item in answers.get("campaign_groups", [])]
            validate_profile(answers, campaigns)
            answers["configured_at"] = datetime.now(timezone.utc).isoformat()
            dump_json(args.profile, answers)
            output = {"profile": str(args.profile), "status": "ready"}
        elif args.command == "run":
            output = run_pipeline(args.profile, args.context, args.campaigns, args.queries, args.out)
            output = {"run": output["out"], "status": "draft-ready"}
        elif args.command == "render":
            output = render_run(args.run, final=False)
        elif args.command == "review":
            if not (args.run / "manifest.json").exists():
                raise HarnessError("run directory does not contain manifest.json")
            record = {
                "decision": args.decision,
                "reviewer": args.reviewer,
                "note": args.note,
                "reviewed_at": datetime.now(timezone.utc).isoformat(),
                "scope": ["numbers", "interpretation", "client_wording", "proposals"],
            }
            dump_json(args.run / "review.json", record)
            output = record
        else:
            output = render_run(args.run, final=True)
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except (HarnessError, FileNotFoundError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
