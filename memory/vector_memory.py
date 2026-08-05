import json
from pathlib import Path

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
    VECTOR_FILE.write_text(
        json.dumps(vectors, ensure_ascii=False),
        encoding="utf-8"
    )

    print("Vector memory created")

    print("Vectors:", len(vectors))


if __name__ == "__main__":

    build_vector_memory()
