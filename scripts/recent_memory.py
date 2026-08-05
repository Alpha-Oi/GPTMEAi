import sys
from core.memory_engine import MemoryEngine
from core.temporal_engine import TemporalMemory

def main():
    limit = 5

    if len(sys.argv) > 1:
        try:
            limit = int(sys.argv[1])
        except ValueError:
            print("ERROR: limit must be an integer")
            return

    memory_engine = MemoryEngine()
    temporal_engine = TemporalMemory(memory_engine)
    blocks = temporal_engine.get_recent(limit)

    print("recent_memory OK")
    print("limit:", limit)
    print("matches:", len(blocks))

    for block in blocks:
        tags = ", ".join(block.get("tags", [])) if block.get("tags") else "-"
        print(
            f"[{block.get('id')}] "
            f"(importance={block.get('importance', 0)} | tags={tags} | created_at={block.get('created_at', '-')}) "
            f"{block.get('text')}"
        )

if __name__ == "__main__":
    main()
