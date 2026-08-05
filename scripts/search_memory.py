import sys
from core.memory_engine import MemoryEngine
from core.retrieval_engine import RetrievalEngine

def main():
    query = " ".join(sys.argv[1:]).strip()

    if not query:
        print("ERROR: empty search query")
        return

    memory_engine = MemoryEngine()
    retrieval_engine = RetrievalEngine(memory_engine)
    matches = retrieval_engine.search(query)

    print("search_memory OK")
    print("query:", query)
    print("matches:", len(matches))

    for block in matches:
        tags = ", ".join(block.get("tags", [])) if block.get("tags") else "-"
        print(f"[{block.get('id')}] (importance={block.get('importance', 0)} | tags={tags}) {block.get('text')}")

if __name__ == "__main__":
    main()
