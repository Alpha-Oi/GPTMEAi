"""Clean up project-local temporary development artifacts with retries.

This script is intended for smoke-test leftovers in `development/tmp`
and similar project-local JSON artifacts. It prefers safe, in-workspace
cleanup over ad-hoc shell deletion.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TMP_DIR = PROJECT_ROOT / "development" / "tmp"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Remove project-local temporary artifacts with retry support."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Explicit file paths to remove. Relative paths are resolved from the project root.",
    )
    parser.add_argument(
        "--glob",
        action="append",
        default=[],
        help="Glob pattern relative to development/tmp, e.g. 'agent_runtime_*.json'.",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=5,
        help="How many retry attempts to make on locked files.",
    )
    parser.add_argument(
        "--delay-ms",
        type=int,
        default=600,
        help="Delay between retries in milliseconds.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be removed without deleting anything.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON summary.",
    )
    return parser.parse_args()


def resolve_project_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


def is_within_project(path: Path) -> bool:
    try:
        path.relative_to(PROJECT_ROOT)
        return True
    except ValueError:
        return False


def collect_targets(args: argparse.Namespace) -> list[Path]:
    items: list[Path] = []

    for raw_path in args.paths:
        resolved = resolve_project_path(raw_path)
        if resolved not in items:
            items.append(resolved)

    for pattern in args.glob:
        for match in sorted(TMP_DIR.glob(pattern)):
            resolved = match.resolve()
            if resolved not in items:
                items.append(resolved)

    return items


def delete_with_retries(path: Path, retries: int, delay_ms: int, dry_run: bool) -> dict:
    if not is_within_project(path):
        return {
            "path": str(path),
            "status": "blocked",
            "message": "path is outside the project root",
        }

    if path.exists() and path.is_dir():
        return {
            "path": str(path),
            "status": "blocked",
            "message": "directories are not removed by this script",
        }

    if not path.exists():
        return {
            "path": str(path),
            "status": "missing",
            "message": "file does not exist",
        }

    if dry_run:
        return {
            "path": str(path),
            "status": "dry_run",
            "message": "file would be removed",
        }

    attempts = max(0, int(retries)) + 1
    delay_seconds = max(0, int(delay_ms)) / 1000.0
    last_error = None

    for attempt in range(1, attempts + 1):
        try:
            path.unlink()
            return {
                "path": str(path),
                "status": "deleted",
                "message": f"removed on attempt {attempt}",
            }
        except FileNotFoundError:
            return {
                "path": str(path),
                "status": "missing",
                "message": "file disappeared before deletion",
            }
        except PermissionError as exc:
            last_error = str(exc)
            if attempt < attempts:
                time.sleep(delay_seconds)
        except OSError as exc:
            last_error = str(exc)
            if attempt < attempts:
                time.sleep(delay_seconds)

    return {
        "path": str(path),
        "status": "failed",
        "message": last_error or "unknown deletion error",
    }


def render_text(results: list[dict]) -> str:
    if not results:
        return "No targets provided."
    return "\n".join(
        f"{item['status']}: {item['path']} ({item['message']})"
        for item in results
    )


def main() -> int:
    args = parse_args()
    targets = collect_targets(args)
    results = [
        delete_with_retries(
            path=path,
            retries=args.retries,
            delay_ms=args.delay_ms,
            dry_run=args.dry_run,
        )
        for path in targets
    ]

    summary = {
        "status": "ok" if all(item["status"] != "failed" for item in results) else "partial_failure",
        "project_root": str(PROJECT_ROOT),
        "targets": results,
        "counts": {
            "deleted": sum(1 for item in results if item["status"] == "deleted"),
            "dry_run": sum(1 for item in results if item["status"] == "dry_run"),
            "missing": sum(1 for item in results if item["status"] == "missing"),
            "blocked": sum(1 for item in results if item["status"] == "blocked"),
            "failed": sum(1 for item in results if item["status"] == "failed"),
        },
    }

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(render_text(results))

    return 0 if summary["counts"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
