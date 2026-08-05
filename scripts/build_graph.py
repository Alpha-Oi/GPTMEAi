from core.memory_engine import MemoryEngine
from core.graph_engine import GraphMemory

def main():
    memory_engine = MemoryEngine()
    graph_engine = GraphMemory(memory_engine)
    graph = graph_engine.save_graph()

    edge_count = sum(len(items) for items in graph.values())

    print("build_graph OK")
    print("nodes:", len(graph))
    print("relations:", edge_count)

    for node_id, items in graph.items():
        print(f"node {node_id}: {len(items)} related")
        
if __name__ == "__main__":
    main()
