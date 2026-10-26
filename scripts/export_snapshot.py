from pathlib import Path
from datetime import datetime, UTC
from ai_os.atomic_store import atomic_write_json, rotate_dir
from scripts.runtime_store import load_runtime

SNAPSHOT_RETENTION = 50
from core.memory_engine import MemoryEngine
from core.retrieval_engine import RetrievalEngine
from core.temporal_engine import TemporalMemory
from core.graph_engine import GraphMemory

def main():
    runtime = load_runtime()
    memory_engine = MemoryEngine()
    retrieval_engine = RetrievalEngine(memory_engine)
    temporal_engine = TemporalMemory(memory_engine)
    graph_engine = GraphMemory(memory_engine)

    snapshot_dir = Path(__file__).resolve().parent.parent / "storage" / "snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    snapshot_path = snapshot_dir / f"project_snapshot_{stamp}.json"

    all_blocks = memory_engine.get_all()
    recent_blocks = temporal_engine.get_recent(3)
    memory_matches = retrieval_engine.search("память")
    graph = graph_engine.build_graph()

    snapshot = {
        "snapshot_created_at": datetime.now(UTC).isoformat(),
        "memory_count": len(all_blocks),
        "last_updated": runtime.get("last_updated"),
        "recent_blocks": recent_blocks,
        "memory_query_top": memory_matches,
        "graph_nodes": len(graph),
        "graph_relations_total": sum(len(items) for items in graph.values())
    }

    atomic_write_json(snapshot_path, snapshot)
    rotate_dir(snapshot_dir, "project_snapshot_*.json", SNAPSHOT_RETENTION)

    print("export_snapshot OK")
    print("file:", str(snapshot_path))
    print("memory_count:", snapshot["memory_count"])
    print("graph_nodes:", snapshot["graph_nodes"])
    print("graph_relations_total:", snapshot["graph_relations_total"])

if __name__ == "__main__":
    main()
