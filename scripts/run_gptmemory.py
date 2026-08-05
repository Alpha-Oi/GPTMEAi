from scripts.runtime_store import load_runtime
from core.memory_engine import MemoryEngine
from core.importance_engine import ImportanceEngine
from core.retrieval_engine import RetrievalEngine
from core.graph_engine import GraphMemory
from core.temporal_engine import TemporalMemory
from core.storage_engine import StorageEngine

def main():
    me = MemoryEngine()
    ie = ImportanceEngine()
    re = RetrievalEngine(me)
    tm = TemporalMemory(me)
    gm = GraphMemory(me)
    se = StorageEngine()

    runtime = load_runtime()
    saved_graph = runtime.get("graph_relations", {})

    print("MemoryEngine OK", isinstance(me.data, list))
    print("Memory count:", me.count())
    print("Importance sample:", ie.evaluate("Критично: память ядра и API"))
    print("RetrievalEngine OK", isinstance(re.search("память"), list))
    print("TemporalMemory OK", isinstance(tm.get_recent(2), list))
    print("GraphMemory OK", isinstance(gm.get_related(1), list))
    print("Saved graph nodes:", len(saved_graph))
    print("StorageEngine OK", isinstance(se.files, list))

    for block in me.get_all():
        tags = ", ".join(block.get("tags", [])) if block.get("tags") else "-"
        related_count = len(gm.get_related(block.get("id")))
        print(
            f"[{block.get('id')}] "
            f"(importance={block.get('importance', 0)} | tags={tags} | related={related_count} | created_at={block.get('created_at', '-')}) "
            f"{block.get('text')}"
        )

if __name__ == "__main__":
    main()
