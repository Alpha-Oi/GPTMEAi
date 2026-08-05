from scripts.runtime_store import default_runtime, save_runtime, utc_now

def main():
    data = default_runtime()
    data["last_updated"] = utc_now()
    save_runtime(data)
    print("init_db OK")
    print("memory_blocks:", len(data["memory_blocks"]))

if __name__ == "__main__":
    main()
