from pathlib import Path

html_file = Path(r"C:\Development GPTMEAi\dashboard\index.html")
text = html_file.read_text(encoding="utf-8")

block = """
  <h3>Snapshot</h3>
  <button onclick="exportSnapshot()">Экспорт snapshot</button>
"""

func = """
    function exportSnapshot() {
      show("/snapshot/export", {
        method: "POST",
        headers: { "Content-Type": "application/json; charset=utf-8" },
        body: "{}"
      });
    }
"""

anchor_block = '<pre id="out"'
anchor_func = '    function buildGraph() {'

if 'Экспорт snapshot' not in text and anchor_block in text:
    text = text.replace(anchor_block, block + "\n\n  " + anchor_block, 1)

if 'function exportSnapshot()' not in text and anchor_func in text:
    text = text.replace(anchor_func, func + "\n\n" + anchor_func, 1)

html_file.write_text(text, encoding="utf-8")
print("dashboard snapshot button added")