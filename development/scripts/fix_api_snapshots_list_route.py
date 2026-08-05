from pathlib import Path

api_file = Path(r"C:\Development GPTMEAi\scripts\api_server.py")
text = api_file.read_text(encoding="utf-8")

route_block = '''
        if path == "/snapshots":
            snapshot_dir = BASE_DIR / "storage" / "snapshots"
            snapshot_dir.mkdir(parents=True, exist_ok=True)

            items = []
            for p in sorted(snapshot_dir.glob("project_snapshot_*.json"), reverse=True):
                items.append({
                    "name": p.name,
                    "file": str(p),
                    "size": p.stat().st_size
                })

            self._send_json({
                "count": len(items),
                "items": items
            })
            return
'''.strip("\n")

anchor = '        self._send_json({\n            "error": "not found",'

if 'if path == "/snapshots":' not in text:
    pos = text.find(anchor)
    if pos == -1:
        raise RuntimeError("Не найден конец do_GET")
    text = text[:pos] + route_block + "\n\n" + text[pos:]

if '"GET /snapshots"' not in text:
    old = '"GET /memory/related?id=4",'
    new = '"GET /memory/related?id=4",\n                "GET /snapshots",'
    if old in text:
        text = text.replace(old, new, 1)

api_file.write_text(text, encoding="utf-8")
print("snapshots list route added")