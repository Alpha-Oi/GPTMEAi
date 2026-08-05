import sys
from core.memory_engine import MemoryEngine
from core.temporal_engine import TemporalMemory

def main():
    date_prefix = " ".join(sys.argv[1:]).strip()

    if not date_prefix:
        print("ERROR: empty date prefix")
        return

    memory_engine = MemoryEngine()
    temporal_engine = TemporalMemory(memory_engine)
    blocks = temporal_engine.search_by_date(date_prefix)

    print("search_by_date OK")
    print("date_prefix:", date_prefix)
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
