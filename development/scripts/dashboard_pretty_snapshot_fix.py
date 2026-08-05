from pathlib import Path
import re

html_file = Path(r"C:\Development GPTMEAi\dashboard\index.html")
text = html_file.read_text(encoding="utf-8")

render_block = r'''
    function renderData(data) {
      if (data && data.name && data.data && data.data.snapshot_created_at) {
        const s = data.data;
        const recent = (s.recent_blocks || [])
          .map(x => `- [${x.id}] ${x.text}`)
          .join("\\n");

        const top = (s.memory_query_top || [])
          .map(x => `- [${x.id}] ${x.text}`)
          .join("\\n");

        return [
          "Последний snapshot",
          "-----------------",
          "Файл: " + data.name,
          "Создан: " + s.snapshot_created_at,
          "Памяти: " + s.memory_count,
          "Узлов графа: " + s.graph_nodes,
          "Связей графа: " + s.graph_relations_total,
          "",
          "Последние записи:",
          recent || "-",
          "",
          "Top по запросу 'память':",
          top || "-"
        ].join("\\n");
      }

      if (data && Array.isArray(data.items) && typeof data.count === "number") {
        return [
          "Список snapshot",
          "---------------",
          "Всего: " + data.count,
          "",
          ...data.items.map(x => `- ${x.name} (${x.size} bytes)`)
        ].join("\\n");
      }

      return JSON.stringify(data, null, 2);
    }
'''.strip("\n")

show_block = r'''
    async function show(url, options) {
      const r = await fetch(url, options);
      const data = await r.json();
      document.getElementById("out").textContent = renderData(data);
    }
'''.strip("\n")

if "function renderData(" not in text:
    m = re.search(r'async function show\s*\(', text)
    if not m:
        raise RuntimeError("Не найден блок async function show")
    text = text[:m.start()] + render_block + "\n\n" + text[m.start():]

pattern = r'async function show\s*\([^)]*\)\s*\{.*?\n\s*\}'
new_text, count = re.subn(pattern, show_block, text, count=1, flags=re.DOTALL)

if count == 0:
    raise RuntimeError("Не удалось заменить блок async function show")

html_file.write_text(new_text, encoding="utf-8")
print("dashboard pretty snapshot fixed")