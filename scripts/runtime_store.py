from datetime import datetime, UTC

from ai_os.atomic_store import (
    StoreCorruptionError,
    atomic_write_json,
    read_json_resilient,
)
from ai_os.config import get_project_paths

RUNTIME_FILE = get_project_paths().runtime_file

# Re-exported so callers can catch a corrupt-store failure without importing
# ai_os.atomic_store directly.
__all__ = [
    "StoreCorruptionError",
    "utc_now",
    "default_runtime",
    "load_runtime",
    "save_runtime",
]


def utc_now():
    return datetime.now(UTC).isoformat()


def default_runtime():
    return {
        "memory_blocks": [],
        "last_updated": None
    }


def load_runtime():
    """Load the memory runtime document.

    A genuinely absent store (fresh install) yields an empty default. A store
    that exists but is unreadable is recovered from its ``.bak`` chain; if no
    backup is usable this raises :class:`StoreCorruptionError` instead of
    silently returning an empty document -- the old behaviour let one truncated
    write wipe every memory block on the next save.
    """

    data = read_json_resilient(
        RUNTIME_FILE,
        default_factory=default_runtime,
        expect=dict,
        on_unrecoverable="raise",
    )

    data.setdefault("memory_blocks", [])
    data.setdefault("last_updated", None)
    return data


def save_runtime(data):
    atomic_write_json(RUNTIME_FILE, data)
