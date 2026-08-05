from pathlib import Path

p = Path(r"C:\Development GPTMEAi\scripts\api_server.py")
t = p.read_text(encoding="utf-8")

if 'if path == "/favicon.ico":' not in t:
    anchor = '        if path in ["/", "/dashboard"]:'
    block = '''
        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
'''.strip("\n")
    t = t.replace(anchor, block + "\n\n" + anchor, 1)

if 'if "GET /favicon.ico" in msg:' not in t and 'def log_message(self, format, *args):' in t:
    t = t.replace(
        '    def log_message(self, format, *args):\n        msg = format % args\n',
        '    def log_message(self, format, *args):\n        msg = format % args\n        if "GET /favicon.ico" in msg:\n            return\n',
        1
    )

p.write_text(t, encoding="utf-8")
print("favicon 204 fix applied")