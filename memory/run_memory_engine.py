"""
GPTMemory AI
Module: Memory Engine Runner

Полный запуск системы памяти:
1 — Сканирование чатов
2 — Парсинг
3 — Построение Knowledge Graph
4 — Проверка файлов
5 — Тестовый поиск
"""

import os
import subprocess
import json
from pathlib import Path

from ai_os.config import get_project_paths

PROJECT_ROOT = get_project_paths().project_root
MEMORY_PATH = PROJECT_ROOT / "memory"

INDEX_FILE = MEMORY_PATH / "index" / "memory_index.json"
PARSED_FILE = MEMORY_PATH / "parsed" / "parsed_chats.json"
KNOWLEDGE_FILE = MEMORY_PATH / "knowledge" / "knowledge_graph.json"


def run_script(script):

    print("\n==============================")
    print("RUNNING:", script)
    print("==============================")

    subprocess.run(["python", str(script)])


def check_file(path):

    path = Path(path)
    if path.exists():

        size = round(path.stat().st_size / 1024, 2)

        print("OK:", path, " | ", size, "KB")

        return True

    else:

        print("MISSING:", path)

        return False


def run_memory_engine():

    print("\nGPTMemory AI — MEMORY ENGINE START\n")

    # 1 scan chats
    run_script(MEMORY_PATH / "chat_loader.py")

    # 2 parse chats
    run_script(MEMORY_PATH / "chat_parser.py")

    # 3 build knowledge
    run_script(MEMORY_PATH / "knowledge_builder.py")

    print("\nChecking generated files...\n")

    check_file(INDEX_FILE)
    check_file(PARSED_FILE)
    check_file(KNOWLEDGE_FILE)

    print("\nMemory Engine finished.\n")


def test_search():

    print("\n=== MEMORY SEARCH TEST ===\n")

    query = input("Enter search term: ")

    parsed_path = PARSED_FILE

    if not Path(parsed_path).exists():

        print("Parsed chats not found")

        return

    chats = json.loads(Path(parsed_path).read_text(encoding="utf-8"))

    results = []

    for chat in chats:

        for msg in chat["messages"]:

            text = str(msg)

            if query.lower() in text.lower():

                results.append(text[:300])

    print("\nResults found:", len(results))

    for r in results[:5]:

        print("\n---\n", r)


if __name__ == "__main__":

    run_memory_engine()

    test = input("\nRun memory search test? (y/n): ")

    if test.lower() == "y":

        test_search()
