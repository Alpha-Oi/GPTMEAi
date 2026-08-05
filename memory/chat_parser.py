import json
from pathlib import Path

from ai_os.config import get_project_paths

MEMORY_DIR = get_project_paths().memory_dir
INDEX_FILE = MEMORY_DIR / "index" / "memory_index.json"
PARSED_FILE = MEMORY_DIR / "parsed" / "parsed_chats.json"


def parse_json_chat(path):

    messages = []

    try:

        data = json.loads(Path(path).read_text(encoding="utf-8"))

        if isinstance(data, list):

            for msg in data:

                messages.append(msg)

        else:

            messages.append(data)

    except Exception as e:

        messages.append({"error": str(e)})

    return messages


def parse_txt_chat(path):

    messages = []

    content = Path(path).read_text(encoding="utf-8")

    blocks = content.split("\n\n")

    for block in blocks:

        messages.append({

            "type": "text_block",

            "content": block.strip()

        })

    return messages


def run_parser():

    print("Loading memory index...")

    index = json.loads(INDEX_FILE.read_text(encoding="utf-8"))

    parsed = []

    for chat in index["chat_files"]:

        path = chat["path"]

        if path.endswith(".json"):

            msgs = parse_json_chat(path)

        elif path.endswith(".txt"):

            msgs = parse_txt_chat(path)

        else:

            continue

        parsed.append({

            "chat_file": chat["file"],

            "messages": msgs

        })

    PARSED_FILE.parent.mkdir(parents=True, exist_ok=True)
    PARSED_FILE.write_text(
        json.dumps(parsed, indent=4, ensure_ascii=False),
        encoding="utf-8"
    )

    print("Chats parsed:", len(parsed))


if __name__ == "__main__":
    run_parser()
