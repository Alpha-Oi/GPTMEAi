import json
from pathlib import Path

from ai_os.atomic_store import atomic_write_text, ensure_free_space
from ai_os.config import get_project_paths

MEMORY_DIR = get_project_paths().memory_dir
PARSED_FILE = MEMORY_DIR / "parsed" / "parsed_chats.json"
VECTOR_FILE = MEMORY_DIR / "embeddings" / "vector_memory.json"

MODEL_NAME = "all-MiniLM-L6-v2"


def build_vector_memory():
    from sentence_transformers import SentenceTransformer

    print("Loading embedding model...")

    model = SentenceTransformer(MODEL_NAME)

    chats = json.loads(PARSED_FILE.read_text(encoding="utf-8"))

    vectors = []

    print("Processing chats...")

    for chat in chats:

        for msg in chat["messages"]:

            text = str(msg)

            if len(text) < 20:
                continue

            embedding = model.encode(text).tolist()

            vectors.append({

                "chat_file": chat["chat_file"],

                "text": text[:500],

                "embedding": embedding

            })

    VECTOR_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(vectors, ensure_ascii=False)
    # This file is large (hundreds of MB). Fail loudly *before* touching the
    # existing copy if the volume cannot hold the new file plus its .bak.
    needed = len(payload.encode("utf-8")) * 3
    ensure_free_space(VECTOR_FILE.parent, needed)
    atomic_write_text(VECTOR_FILE, payload, min_free_bytes=needed)

    print("Vector memory created")

    print("Vectors:", len(vectors))


if __name__ == "__main__":

    build_vector_memory()
