from pathlib import Path

html_file = Path(r"C:\Development GPTMEAi\dashboard\index.html")
text = html_file.read_text(encoding="utf-8")

block = """
  <h3>Список snapshot</h3>
  <button onclick="getSnapshots()">Показать snapshot</button>
"""

func = """
    function getSnapshots() {
      show("/snapshots");
    }
"""

anchor_block = '<h3>Snapshot</h3>'
anchor_func = '    function exportSnapshot() {'

if 'Показать snapshot' not in text and anchor_block in text:
    text = text.replace(anchor_block, block + "\n\n  " + anchor_block, 1)

if 'function getSnapshots()' not in text and anchor_func in text:
    text = text.replace(anchor_func, func + "\n\n" + anchor_func, 1)

html_file.write_text(text, encoding="utf-8")
print("dashboard snapshots list added")