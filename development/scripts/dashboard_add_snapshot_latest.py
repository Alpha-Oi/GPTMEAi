from pathlib import Path

html_file = Path(r"C:\Development GPTMEAi\dashboard\index.html")
text = html_file.read_text(encoding="utf-8")

block = """
  <h3>Последний snapshot</h3>
  <button onclick="getLatestSnapshot()">Показать последний snapshot</button>
"""

func = """
    function getLatestSnapshot() {
      show("/snapshot/latest");
    }
"""

anchor_block = '<h3>Список snapshot</h3>'
anchor_func = '    function getSnapshots() {'

if 'Показать последний snapshot' not in text and anchor_block in text:
    text = text.replace(anchor_block, block + "\n\n  " + anchor_block, 1)

if 'function getLatestSnapshot()' not in text and anchor_func in text:
    text = text.replace(anchor_func, func + "\n\n" + anchor_func, 1)

html_file.write_text(text, encoding="utf-8")
print("dashboard latest snapshot button added")