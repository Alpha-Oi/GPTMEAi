import json
from datetime import datetime

from ai_os.config import get_project_paths

MEMORY_DIR = get_project_paths().memory_dir
CHATS_PATH = MEMORY_DIR / "chats"
INDEX_PATH = MEMORY_DIR / "index"
INDEX_FILE = INDEX_PATH / "memory_index.json"


def scan_chats():

    chats = []

    for full_path in CHATS_PATH.rglob("*"):
        if full_path.is_file() and full_path.suffix.lower() in {".json", ".yml", ".yaml", ".txt"}:
            file = full_path.name
            chats.append({
                "file": file,
                "path": str(full_path),
                "size_kb": round(full_path.stat().st_size / 1024, 2),
                "loaded_at": str(datetime.now())
            })

    return chats


def build_index():

    print("Scanning chat memory...")

    chats = scan_chats()

    index_data = {

        "project": "GPTMemory AI",

        "created": str(datetime.now()),

        "chat_files_found": len(chats),

        "chat_files": chats
    }

    INDEX_PATH.mkdir(parents=True, exist_ok=True)
    INDEX_FILE.write_text(
        json.dumps(index_data, indent=4, ensure_ascii=False),
        encoding="utf-8"
    )

    print("Memory index created")

    print("Chats indexed:", len(chats))

    print("Index file:", INDEX_FILE)


if __name__ == "__main__":
    build_index()
