"""Crash-safe JSON persistence helpers for the AI OS storage layer.

Every state file in this project is a JSON document that is read whole into
memory and rewritten whole on each change. A process killed mid-write (disk
full, power loss, OOM) used to leave a truncated file that the next load
silently treated as an *empty* document -- and the following save then made
that data loss permanent.

This module removes that failure mode:

* :func:`atomic_write_text` / :func:`atomic_write_json` never touch the real
  file until a complete copy is on disk and ``fsync``-ed: write a temp file in
  the same directory, ``flush`` + ``os.fsync``, then ``os.replace`` (atomic on
  Windows and POSIX).
* Before each replace the current good file is rotated to ``<name>.bak``,
  ``<name>.bak2`` ... keeping ``backups`` generations.
* :func:`read_json_resilient` walks that ``.bak`` chain when the primary file
  is missing / empty / corrupt, and (by default) raises
  :class:`StoreCorruptionError` rather than returning a silent empty document
  when nothing is recoverable.
* :func:`ensure_free_space` guards large rewrites; :func:`rotate_dir` caps
  ever-growing snapshot / export directories.

Pure standard library, no project imports -- safe to import from anywhere.

Known limitation (tracked for the storage P1): ``os.replace`` makes every
*reader* see a complete file, but concurrent *writers* to the same path still
race (last writer wins). Real multi-process safety needs a lock or a database
(SQLite WAL) and is out of scope here.
"""

from __future__ import annotations

import errno
import json
import logging
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

__all__ = [
    "StoreCorruptionError",
    "atomic_write_text",
    "atomic_write_json",
    "read_json_resilient",
    "ensure_free_space",
    "rotate_dir",
    "backup_paths",
    "DEFAULT_BACKUPS",
]

log = logging.getLogger("ai_os.atomic_store")

DEFAULT_BACKUPS = 3
# Always leave at least this much headroom on the target volume, on top of the
# space needed for the payload itself.
_MIN_FREE_HEADROOM = 16 * 1024 * 1024  # 16 MiB
# Opportunistically delete our own leftover temp files older than this.
_STALE_TMP_AGE_S = 3600


class StoreCorruptionError(RuntimeError):
    """A JSON store and every one of its backups were unreadable."""


def backup_paths(path: str | os.PathLike[str], backups: int = DEFAULT_BACKUPS) -> list[Path]:
    """Return the backup slots for *path*, newest generation first.

    ``foo.json`` -> ``[foo.json.bak, foo.json.bak2, foo.json.bak3]``
    """

    path = Path(path)
    slots: list[Path] = []
    for i in range(1, max(0, backups) + 1):
        suffix = ".bak" if i == 1 else f".bak{i}"
        slots.append(path.with_name(path.name + suffix))
    return slots


def _first_existing_dir(path: Path) -> Path:
    for candidate in (path, *path.parents):
        if candidate.exists():
            return candidate
    return Path(path.anchor or ".")


def ensure_free_space(target: str | os.PathLike[str], needed_bytes: int) -> None:
    """Raise ``OSError(ENOSPC)`` if *target*'s volume cannot hold *needed_bytes*.

    *needed_bytes* should already include any headroom the caller wants; this
    function additionally enforces :data:`_MIN_FREE_HEADROOM`.
    """

    probe = _first_existing_dir(Path(target))
    try:
        free = shutil.disk_usage(probe).free
    except OSError:  # pragma: no cover - disk_usage should not fail on a real dir
        return

    required = int(needed_bytes) + _MIN_FREE_HEADROOM
    if free < required:
        raise OSError(
            errno.ENOSPC,
            "not enough free disk space for a safe write: "
            f"need ~{required / 1_048_576:.1f} MiB, "
            f"have {free / 1_048_576:.1f} MiB free on {probe}",
        )


def _sweep_stale_tmp(directory: Path, keep_name: str) -> None:
    cutoff = time.time() - _STALE_TMP_AGE_S
    try:
        candidates = list(directory.glob(".*.tmp"))
    except OSError:
        return
    for tmp in candidates:
        if tmp.name == keep_name:
            continue
        try:
            if tmp.stat().st_mtime < cutoff:
                tmp.unlink()
        except OSError:
            pass


def _fsync_dir(directory: Path) -> None:
    # Directory fsync is a POSIX notion; on Windows there is no handle to sync
    # and os.open() on a directory fails outright.
    if os.name != "posix":
        return
    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _rotate_backups(path: Path, backups: int) -> None:
    """Shift ``path`` into ``path.bak`` and age the older generations down."""

    if backups <= 0:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        return

    slots = backup_paths(path, backups)

    # Drop the oldest generation.
    try:
        slots[-1].unlink()
    except FileNotFoundError:
        pass

    # .bak2 -> .bak3, then .bak -> .bak2  (oldest move first).
    for newer, older in reversed(list(zip(slots[:-1], slots[1:]))):
        try:
            os.replace(newer, older)
        except FileNotFoundError:
            pass

    # Current good file -> .bak
    try:
        os.replace(path, slots[0])
    except FileNotFoundError:
        pass


def atomic_write_text(
    path: str | os.PathLike[str],
    text: str,
    *,
    encoding: str = "utf-8",
    backups: int = DEFAULT_BACKUPS,
    fsync: bool = True,
    check_free_space: bool = True,
    min_free_bytes: int | None = None,
) -> Path:
    """Write *text* to *path* so that readers only ever see a complete file.

    Steps: encode -> optional free-space check -> write a sibling temp file ->
    ``flush`` + ``os.fsync`` -> rotate existing file into ``.bak`` -> atomic
    ``os.replace`` -> best-effort directory ``fsync``.

    Returns the resolved :class:`~pathlib.Path`.
    """

    path = Path(path)
    data = text.encode(encoding)
    path.parent.mkdir(parents=True, exist_ok=True)

    if check_free_space:
        # Room for the new file plus, transiently, the .bak copy of the old one.
        needed = min_free_bytes if min_free_bytes is not None else len(data) * 2
        ensure_free_space(path.parent, needed)

    fd, tmp_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            if fsync:
                os.fsync(handle.fileno())
        _rotate_backups(path, backups)
        os.replace(tmp_path, path)
    except BaseException:
        try:
            tmp_path.unlink()
        except OSError:
            pass
        raise

    if fsync:
        _fsync_dir(path.parent)
    _sweep_stale_tmp(path.parent, tmp_path.name)
    return path


def atomic_write_json(
    path: str | os.PathLike[str],
    obj: Any,
    *,
    indent: int | None = 2,
    ensure_ascii: bool = False,
    sort_keys: bool = False,
    **write_kwargs: Any,
) -> Path:
    """Serialise *obj* to JSON and persist it via :func:`atomic_write_text`."""

    text = json.dumps(obj, indent=indent, ensure_ascii=ensure_ascii, sort_keys=sort_keys)
    return atomic_write_text(path, text, **write_kwargs)


def _load_one(path: Path, expect: tuple[type, ...] | None) -> tuple[bool, Any, str]:
    """Return ``(ok, value, reason)`` for a single candidate file."""

    if not path.exists():
        return False, None, "missing"
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        return False, None, f"unreadable ({exc})"
    if not raw.strip():
        return False, None, "empty"
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        return False, None, f"invalid JSON ({exc})"
    if expect is not None and not isinstance(value, expect):
        return False, None, f"unexpected type {type(value).__name__}"
    return True, value, "ok"


def read_json_resilient(
    path: str | os.PathLike[str],
    *,
    default_factory: Callable[[], Any] | None = None,
    backups: int = DEFAULT_BACKUPS,
    expect: type | tuple[type, ...] | None = dict,
    on_unrecoverable: str = "raise",
    preserve_corrupt: bool = False,
) -> Any:
    """Load JSON from *path*, falling back through its ``.bak`` chain.

    * Primary file good            -> return it.
    * Primary bad, a backup good   -> log a warning, return the backup.
    * Nothing exists anywhere      -> ``default_factory()`` if given, else raise.
    * Files exist but all corrupt  -> depends on *on_unrecoverable*:
        ``"raise"``   (default) -> :class:`StoreCorruptionError`
        ``"default"``           -> log an error, return ``default_factory()``

    With *preserve_corrupt* the unreadable primary is renamed to
    ``<name>.corrupt-<timestamp>`` before returning defaults, so the bytes are
    kept for forensics and the next (rotating) save starts a clean chain.
    """

    path = Path(path)
    if expect is not None and not isinstance(expect, tuple):
        expect = (expect,)

    candidates = [path, *backup_paths(path, backups)]
    any_present = False
    failures: list[str] = []

    for index, candidate in enumerate(candidates):
        ok, value, reason = _load_one(candidate, expect)
        if reason != "missing":
            any_present = True
        if ok:
            if index > 0:
                log.warning(
                    "atomic_store: %s unreadable, recovered from %s",
                    path.name,
                    candidate.name,
                )
            return value
        failures.append(f"{candidate.name}: {reason}")

    if not any_present:
        if default_factory is not None:
            return default_factory()
        raise StoreCorruptionError(f"{path}: no file and no default_factory")

    detail = "; ".join(failures)

    if preserve_corrupt and path.exists():
        wreck = path.with_name(f"{path.name}.corrupt-{time.strftime('%Y%m%d_%H%M%S')}")
        try:
            os.replace(path, wreck)
            log.error("atomic_store: preserved corrupt %s as %s", path.name, wreck.name)
        except OSError:
            pass

    if on_unrecoverable == "default" and default_factory is not None:
        log.error("atomic_store: %s unrecoverable (%s); using defaults", path.name, detail)
        return default_factory()

    raise StoreCorruptionError(f"{path}: unrecoverable ({detail})")


def rotate_dir(
    directory: str | os.PathLike[str],
    pattern: str,
    keep: int,
    *,
    min_keep: int = 1,
) -> list[str]:
    """Keep only the *keep* newest files matching *pattern*; unlink the rest.

    Returns the names that were deleted. Best-effort: files that cannot be
    removed (open handles, races) are skipped silently.
    """

    directory = Path(directory)
    keep = max(int(keep), int(min_keep), 0)
    try:
        matches = [p for p in directory.glob(pattern) if p.is_file()]
    except OSError:
        return []
    matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    removed: list[str] = []
    for stale in matches[keep:]:
        try:
            stale.unlink()
            removed.append(stale.name)
        except OSError:
            pass
    return removed
