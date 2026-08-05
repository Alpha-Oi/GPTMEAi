import json
from datetime import datetime, UTC

from ai_os.config import get_project_paths

RUNTIME_FILE = get_project_paths().runtime_file

def utc_now():
    return datetime.now(UTC).isoformat()

def default_runtime():
    return {
        "memory_blocks": [],
        "last_updated": None
    }

def load_runtime():
    if not RUNTIME_FILE.exists():
        return default_runtime()

    raw = RUNTIME_FILE.read_text(encoding="utf-8").strip()
    if not raw:
        return default_runtime()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return default_runtime()

    if not isinstance(data, dict):
        return default_runtime()

    data.setdefault("memory_blocks", [])
    data.setdefault("last_updated", None)
    return data

def save_runtime(data):
    RUNTIME_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
