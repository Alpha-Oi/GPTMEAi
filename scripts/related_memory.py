import sys
from core.memory_engine import MemoryEngine
from core.graph_engine import GraphMemory

def main():
    if len(sys.argv) < 2:
        print("ERROR: memory id is required")
        return

    try:
        block_id = int(sys.argv[1])
    except ValueError:
        print("ERROR: memory id must be an integer")
        return

    memory_engine = MemoryEngine()
    graph_engine = GraphMemory(memory_engine)
    related = graph_engine.get_related(block_id)

    print("related_memory OK")
    print("source_id:", block_id)
    print("matches:", len(related))

    for item in related:
        shared_tags = ", ".join(item.get("shared_tags", [])) if item.get("shared_tags") else "-"
        shared_words = ", ".join(item.get("shared_words", [])) if item.get("shared_words") else "-"
        print(
            f"[{item.get('id')}] "
            f"(score={item.get('relation_score', 0)} | shared_tags={shared_tags} | shared_words={shared_words} | importance={item.get('importance', 0)}) "
            f"{item.get('text')}"
        )

if __name__ == "__main__":
    main()
