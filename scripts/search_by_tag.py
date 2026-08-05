import sys
from core.memory_engine import MemoryEngine
from core.retrieval_engine import RetrievalEngine

def main():
    tag = " ".join(sys.argv[1:]).strip().lower()

    if not tag:
        print("ERROR: empty tag")
        return

    memory_engine = MemoryEngine()
    retrieval_engine = RetrievalEngine(memory_engine)
    matches = retrieval_engine.search_by_tag(tag)

    print("search_by_tag OK")
    print("tag:", tag)
    print("matches:", len(matches))

    for block in matches:
        tags = ", ".join(block.get("tags", [])) if block.get("tags") else "-"
        print(f"[{block.get('id')}] (importance={block.get('importance', 0)} | tags={tags}) {block.get('text')}")

if __name__ == "__main__":
    main()
