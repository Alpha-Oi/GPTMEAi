import sys
from core.memory_engine import MemoryEngine

def main():
    text = " ".join(sys.argv[1:]).strip()

    if not text:
        print("ERROR: empty memory text")
        return

    engine = MemoryEngine()
    block = engine.add(text)

    print("add_memory OK")
    print("saved_id:", block["id"])
    print("saved_text:", block["text"])
    print("importance:", block["importance"])
    print("tags:", ", ".join(block["tags"]) if block["tags"] else "-")
    print("total_blocks:", engine.count())

if __name__ == "__main__":
    main()
