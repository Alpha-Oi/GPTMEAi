from pathlib import Path

html_file = Path(r"C:\Development GPTMEAi\dashboard\index.html")
text = html_file.read_text(encoding="utf-8")

block = """
  <h3>Поиск по тегу</h3>
  <input id="tagQuery" placeholder="тег: memory">
  <button onclick="searchTag()">Искать тег</button>
"""

func = """
    function searchTag() {
      const tag = document.getElementById("tagQuery").value;
      show("/memory/tag?tag=" + encodeURIComponent(tag));
    }
"""

anchor_block = '<h3>Последние записи</h3>'
anchor_func = '    function getRecent() {'

if 'id="tagQuery"' not in text and anchor_block in text:
    text = text.replace(anchor_block, block + "\n  " + anchor_block, 1)

if 'function searchTag()' not in text and anchor_func in text:
    text = text.replace(anchor_func, func + "\n" + anchor_func, 1)

html_file.write_text(text, encoding="utf-8")
print("dashboard index.html updated")