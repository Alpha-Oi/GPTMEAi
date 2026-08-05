from core.memory_engine import MemoryEngine

def main():
    engine = MemoryEngine()
    blocks = engine.normalize_all()

    print("normalize_memory OK")
    print("total_blocks:", len(blocks))

    for block in blocks:
        tags = ", ".join(block.get("tags", [])) if block.get("tags") else "-"
        print(f"[{block.get('id')}] (importance={block.get('importance', 0)} | tags={tags}) {block.get('text')}")

if __name__ == "__main__":
    main()
