import json
from pathlib import Path
from datetime import datetime, UTC
from scripts.runtime_store import load_runtime

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
        export_path.write_text(
            json.dumps(runtime, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

        self.files.append(str(export_path))
        return str(export_path)
