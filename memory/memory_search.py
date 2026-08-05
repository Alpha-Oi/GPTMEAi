import json
from pathlib import Path

from ai_os.config import get_project_paths

PARSED_FILE = get_project_paths().memory_dir / "parsed" / "parsed_chats.json"


def search(query):

    chats = json.loads(Path(PARSED_FILE).read_text(encoding="utf-8"))

    results = []

    for chat in chats:

        for msg in chat["messages"]:

            text = str(msg)

            if query.lower() in text.lower():

                results.append(text[:500])

    return results


if __name__ == "__main__":

    q = input("Search memory: ")

    res = search(q)

    print("Results:", len(res))

    for r in res[:5]:

        print("\n---\n", r)
