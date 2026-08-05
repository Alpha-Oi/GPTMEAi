import sys
from core.storage_engine import StorageEngine

def main():
    filename = " ".join(sys.argv[1:]).strip() if len(sys.argv) > 1 else ""
    engine = StorageEngine()
    path = engine.export_runtime(filename if filename else None)

    print("export_memory OK")
    print("file:", path)

if __name__ == "__main__":
    main()
