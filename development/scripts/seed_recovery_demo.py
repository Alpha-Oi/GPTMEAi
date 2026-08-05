"""Seed demo recovery workflows into the live planner runtime for dashboard visualization."""

from __future__ import annotations

import argparse
import json

from planning.runtime import PLANNER_RUNTIME


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Seed demo recovery workflows into the live AI OS planner runtime."
    )
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="Keep existing demo recovery plans instead of replacing them.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON output instead of a short human-readable summary.",
    )
    args = parser.parse_args()

    result = PLANNER_RUNTIME.seed_demo_recovery_state(reset_existing=not args.no_reset)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print(result.get("message", "demo recovery seed completed"))
    print(
        "seeded_workflows={0} seeded_branches={1}".format(
            result.get("seeded_workflow_count", 0),
            result.get("seeded_branch_count", 0),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
