from pathlib import Path
from datetime import datetime, UTC

from ai_os.atomic_store import atomic_write_json, rotate_dir
from scripts.runtime_store import load_runtime

EXPORT_RETENTION = 50


class StorageEngine:
    def __init__(self):
        self.base_dir = Path(__file__).resolve().parent.parent / "storage" / "exports"
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.files = []

    def export_runtime(self, filename=None):
        runtime = load_runtime()

        if not filename:
            stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            filename = f"memory_export_{stamp}.json"

        export_path = self.base_dir / filename
        atomic_write_json(export_path, runtime)
        rotate_dir(self.base_dir, "memory_export_*.json", EXPORT_RETENTION)

        self.files.append(str(export_path))
        return str(export_path)
