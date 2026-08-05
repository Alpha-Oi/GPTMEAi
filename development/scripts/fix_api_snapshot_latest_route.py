from pathlib import Path

api_file = Path(r"C:\Development GPTMEAi\scripts\api_server.py")
text = api_file.read_text(encoding="utf-8")

route_block = '''
        if path == "/snapshot/latest":
            snapshot_dir = BASE_DIR / "storage" / "snapshots"
            snapshot_dir.mkdir(parents=True, exist_ok=True)

            files = sorted(snapshot_dir.glob("project_snapshot_*.json"), reverse=True)
            if not files:
                self._send_json({"error": "no snapshots found"}, status=404)
                return

            latest = files[0]
            data = json.loads(latest.read_text(encoding="utf-8"))

            self._send_json({
                "name": latest.name,
                "file": str(latest),
                "data": data
            })
            return
'''.strip("\n")

if 'if path == "/snapshot/latest":' not in text:
    anchor = '        if path == "/snapshots":'
    if anchor in text:
        text = text.replace(anchor, route_block + "\n\n" + anchor, 1)
    else:
        raise RuntimeError('Не найден блок if path == "/snapshots":')

if '"GET /snapshot/latest"' not in text:
    old = '"GET /snapshots",'
    new = '"GET /snapshots",\n                "GET /snapshot/latest",'
    if old in text:
        text = text.replace(old, new, 1)

api_file.write_text(text, encoding="utf-8")
print("snapshot latest route added")