"""Isolated smoke test for the crash-safe storage layer (ai_os.atomic_store).

Covers the failure mode the storage P0 was written to kill: a truncated /
corrupt state file must never silently become an empty document that the next
save then makes permanent.

Run:
    python development/scripts/smoke_atomic_store.py
    python development/scripts/smoke_atomic_store.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai_os.atomic_store import (  # noqa: E402
    StoreCorruptionError,
    atomic_write_json,
    backup_paths,
    ensure_free_space,
    read_json_resilient,
    rotate_dir,
)


class CheckFailed(AssertionError):
    pass


def check(cond: bool, label: str) -> None:
    if not cond:
        raise CheckFailed(label)


def case_atomic_write_and_backup_rotation(work: Path) -> None:
    target = work / "runtime.json"

    atomic_write_json(target, {"v": 1})
    atomic_write_json(target, {"v": 2})
    atomic_write_json(target, {"v": 3})

    check(json.loads(target.read_text("utf-8"))["v"] == 3, "primary holds newest write")

    bak, bak2, bak3 = backup_paths(target, 3)
    check(json.loads(bak.read_text("utf-8"))["v"] == 2, ".bak holds previous generation")
    check(json.loads(bak2.read_text("utf-8"))["v"] == 1, ".bak2 holds older generation")
    check(not bak3.exists(), ".bak3 not created yet (only 3 writes)")

    # No stray temp files left behind.
    leftovers = list(work.glob(".runtime.json.*.tmp"))
    check(not leftovers, f"no leftover temp files ({[p.name for p in leftovers]})")


def case_recover_from_backup(work: Path) -> None:
    target = work / "state.json"
    atomic_write_json(target, {"good": "first"})
    atomic_write_json(target, {"good": "second"})  # primary=second, .bak=first

    target.write_text("{ this is not valid json", encoding="utf-8")  # corrupt primary

    data = read_json_resilient(target, default_factory=dict, on_unrecoverable="raise")
    check(data == {"good": "first"}, "recovered previous good value from .bak")


def case_raise_when_unrecoverable(work: Path) -> None:
    target = work / "precious.json"
    target.write_text("<<truncated", encoding="utf-8")  # exists, corrupt, no backups

    raised = False
    try:
        read_json_resilient(target, default_factory=dict, on_unrecoverable="raise")
    except StoreCorruptionError:
        raised = True
    check(raised, "raises StoreCorruptionError instead of returning empty dict")


def case_default_on_fresh(work: Path) -> None:
    target = work / "does-not-exist.json"
    data = read_json_resilient(target, default_factory=lambda: {"fresh": True})
    check(data == {"fresh": True}, "absent file yields default_factory result")


def case_preserve_corrupt(work: Path) -> None:
    target = work / "control-plane.json"
    target.write_text("not json at all", encoding="utf-8")

    data = read_json_resilient(
        target,
        default_factory=lambda: {"reset": True},
        on_unrecoverable="default",
        preserve_corrupt=True,
    )
    check(data == {"reset": True}, "on_unrecoverable=default returns defaults")
    check(not target.exists(), "corrupt primary was moved aside")
    wrecks = list(work.glob("control-plane.json.corrupt-*"))
    check(len(wrecks) == 1, "corrupt bytes preserved as .corrupt-<ts>")


def case_runtime_store_never_wipes(work: Path) -> None:
    """End-to-end: scripts.runtime_store must not lose memory blocks on a
    truncated file when a backup exists, and must refuse to load (not blank)
    when nothing is recoverable."""

    import scripts.runtime_store as rs

    original = rs.RUNTIME_FILE
    rs.RUNTIME_FILE = work / "GPTMemory_runtime.yaml"
    try:
        rs.save_runtime({"memory_blocks": [{"id": 1, "text": "alpha"}], "last_updated": "t1"})
        rs.save_runtime(
            {
                "memory_blocks": [{"id": 1, "text": "alpha"}, {"id": 2, "text": "beta"}],
                "last_updated": "t2",
            }
        )

        # Simulate a truncated write landing on the primary file.
        rs.RUNTIME_FILE.write_text('{"memory_blocks": [', encoding="utf-8")

        recovered = rs.load_runtime()
        check(
            [b["id"] for b in recovered["memory_blocks"]] == [1],
            "load_runtime recovered the last good backup, not an empty doc",
        )

        # Now wipe the backups too: nothing recoverable -> must raise.
        for p in backup_paths(rs.RUNTIME_FILE, 3):
            if p.exists():
                p.unlink()
        rs.RUNTIME_FILE.write_text("garbage", encoding="utf-8")

        raised = False
        try:
            rs.load_runtime()
        except StoreCorruptionError:
            raised = True
        check(raised, "load_runtime raises rather than returning empty memory")
    finally:
        rs.RUNTIME_FILE = original


def case_rotate_dir(work: Path) -> None:
    d = work / "snaps"
    d.mkdir()
    for i in range(8):
        p = d / f"project_snapshot_{i:02d}.json"
        p.write_text("{}", encoding="utf-8")
        # stagger mtimes so "newest" is well defined
        import os
        os.utime(p, (1_700_000_000 + i, 1_700_000_000 + i))

    removed = rotate_dir(d, "project_snapshot_*.json", keep=3)
    remaining = sorted(p.name for p in d.glob("project_snapshot_*.json"))
    check(len(remaining) == 3, "rotate_dir kept exactly 3 files")
    check(
        remaining == ["project_snapshot_05.json", "project_snapshot_06.json", "project_snapshot_07.json"],
        "rotate_dir kept the newest 3",
    )
    check(len(removed) == 5, "rotate_dir reported 5 deletions")


def case_free_space_guard(work: Path) -> None:
    raised = False
    try:
        ensure_free_space(work, 10 ** 18)  # ~1 EiB, no volume has this
    except OSError:
        raised = True
    check(raised, "ensure_free_space raises OSError when space is short")


CASES = [
    case_atomic_write_and_backup_rotation,
    case_recover_from_backup,
    case_raise_when_unrecoverable,
    case_default_on_fresh,
    case_preserve_corrupt,
    case_runtime_store_never_wipes,
    case_rotate_dir,
    case_free_space_guard,
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit a JSON result blob")
    args = parser.parse_args()

    results: list[dict] = []
    ok = True
    with tempfile.TemporaryDirectory(prefix="smoke_atomic_store_") as tmp:
        for case in CASES:
            sub = Path(tmp) / case.__name__
            sub.mkdir()
            try:
                case(sub)
                results.append({"case": case.__name__, "status": "ok"})
            except Exception as exc:  # noqa: BLE001 - smoke test reports everything
                ok = False
                results.append({"case": case.__name__, "status": "fail", "error": repr(exc)})

    if args.json:
        print(json.dumps({"service": "atomic_store smoke", "ok": ok, "cases": results}, indent=2))
    else:
        for item in results:
            mark = "ok  " if item["status"] == "ok" else "FAIL"
            line = f"[{mark}] {item['case']}"
            if item["status"] != "ok":
                line += f"  -> {item['error']}"
            print(line)
        print("RESULT:", "PASS" if ok else "FAIL")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
