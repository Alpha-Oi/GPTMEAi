from pathlib import Path

api_file = Path(r"C:\Development GPTMEAi\scripts\api_server.py")
text = api_file.read_text(encoding="utf-8")

route_block = '''
        if path == "/memory/tag":
            tag = query.get("tag", [""])[0]
            items = retrieval_engine.search_by_tag(tag)
            self._send_json({
                "tag": tag,
                "matches": len(items),
                "items": items
            })
            return
'''.strip("\n")

anchor = '''
        if path == "/memory/recent":
'''.strip("\n")

if 'if path == "/memory/tag":' not in text:
    if anchor in text:
        text = text.replace(anchor, route_block + "\n\n" + anchor, 1)
    else:
        raise RuntimeError('Не найден блок if path == "/memory/recent":')

if 'GET /memory/tag?tag=memory' not in text:
    old = '"GET /memory/search?q=память",'
    new = '"GET /memory/search?q=память",\n                "GET /memory/tag?tag=memory",'
    if old in text:
        text = text.replace(old, new, 1)

api_file.write_text(text, encoding="utf-8")
print("api_server.py updated")