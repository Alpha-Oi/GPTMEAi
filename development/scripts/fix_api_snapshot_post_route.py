from pathlib import Path

api_file = Path(r"C:\Development GPTMEAi\scripts\api_server.py")
text = api_file.read_text(encoding="utf-8")

route_block = '''
        if path == "/snapshot/export":
            retrieval_engine = RetrievalEngine(memory_engine)
            temporal_engine = TemporalMemory(memory_engine)

            snapshot_dir = BASE_DIR / "storage" / "snapshots"
            snapshot_dir.mkdir(parents=True, exist_ok=True)

            stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            snapshot_path = snapshot_dir / f"project_snapshot_{stamp}.json"

            runtime = load_runtime()
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

            snapshot_path.write_text(
                json.dumps(snapshot, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )

            self._send_json({
                "status": "ok",
                "message": "snapshot exported",
                "file": str(snapshot_path),
                "memory_count": snapshot["memory_count"],
                "graph_nodes": snapshot["graph_nodes"],
                "graph_relations_total": snapshot["graph_relations_total"]
            })
            return
'''.strip("\n")

marker = '        self._send_json({"error": "not found"}, status=404)'

if 'if path == "/snapshot/export":' not in text:
    pos = text.rfind(marker)
    if pos == -1:
        raise RuntimeError('Не найден конец do_POST')
    text = text[:pos] + route_block + "\n\n" + text[pos:]

api_file.write_text(text, encoding="utf-8")
print("snapshot POST route fixed")