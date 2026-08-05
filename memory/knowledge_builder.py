import json
from pathlib import Path

from ai_os.config import get_project_paths

MEMORY_DIR = get_project_paths().memory_dir
PARSED_FILE = MEMORY_DIR / "parsed" / "parsed_chats.json"
KNOWLEDGE_FILE = MEMORY_DIR / "knowledge" / "knowledge_graph.json"


KEYWORDS = [
    "AI Kernel",
    "Cognitive Loop",
    "Managers",
    "Workers",
    "AutoScale",
    "API",
    "Memory",
    "GPTMemory",
    "AI-OS"
]


def build_graph():

    data = json.loads(PARSED_FILE.read_text(encoding="utf-8"))

    graph = {}

    for keyword in KEYWORDS:

        graph[keyword] = []


    for chat in data:

        for msg in chat["messages"]:

            text = str(msg)

            for keyword in KEYWORDS:

                if keyword.lower() in text.lower():

                    graph[keyword].append(chat["chat_file"])


    KNOWLEDGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    KNOWLEDGE_FILE.write_text(
        json.dumps(graph, indent=4, ensure_ascii=False),
        encoding="utf-8"
    )

    print("Knowledge graph created")


if __name__ == "__main__":

    build_graph()
