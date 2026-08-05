"""Official bridge between the AI OS runtime and memory ingestion assets."""

from __future__ import annotations

import json
from pathlib import Path

from ai_os.config import get_project_paths


PATHS = get_project_paths()
MEMORY_DIR = PATHS.memory_dir
CHATS_DIR = MEMORY_DIR / "chats"
INDEX_FILE = MEMORY_DIR / "index" / "memory_index.json"
PARSED_FILE = MEMORY_DIR / "parsed" / "parsed_chats.json"
KNOWLEDGE_FILE = MEMORY_DIR / "knowledge" / "knowledge_graph.json"
VECTOR_FILE = MEMORY_DIR / "embeddings" / "vector_memory.json"
SUPPORTED_CHAT_SUFFIXES = {".json", ".yml", ".yaml", ".txt"}


def _load_json(path: Path):
    if not path.exists():
        return None

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def corpus_status() -> dict:
    chat_files = []
    if CHATS_DIR.exists():
        chat_files = [p for p in CHATS_DIR.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_CHAT_SUFFIXES]

    parsed = _load_json(PARSED_FILE)
    knowledge = _load_json(KNOWLEDGE_FILE)
    vectors = _load_json(VECTOR_FILE)

    return {
        "status": "ok",
        "service": "AI OS Memory Pipeline",
        "paths": {
            "memory_dir": str(MEMORY_DIR),
            "chats_dir": str(CHATS_DIR),
            "index_file": str(INDEX_FILE),
            "parsed_file": str(PARSED_FILE),
            "knowledge_file": str(KNOWLEDGE_FILE),
            "vector_file": str(VECTOR_FILE),
        },
        "counts": {
            "chat_files": len(chat_files),
            "parsed_chats": len(parsed) if isinstance(parsed, list) else 0,
            "knowledge_topics": len(knowledge) if isinstance(knowledge, dict) else 0,
            "vector_items": len(vectors) if isinstance(vectors, list) else 0,
        },
        "available": {
            "index": INDEX_FILE.exists(),
            "parsed": PARSED_FILE.exists(),
            "knowledge": KNOWLEDGE_FILE.exists(),
            "vectors": VECTOR_FILE.exists(),
        },
    }


def rebuild_index() -> dict:
    from memory.chat_loader import build_index

    build_index()
    return corpus_status()


def rebuild_parsed() -> dict:
    from memory.chat_parser import run_parser

    run_parser()
    return corpus_status()


def rebuild_knowledge() -> dict:
    from memory.knowledge_builder import build_graph

    build_graph()
    return corpus_status()


def rebuild_vectors() -> dict:
    from memory.vector_memory import build_vector_memory

    build_vector_memory()
    return corpus_status()
