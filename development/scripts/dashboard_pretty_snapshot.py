from pathlib import Path

html_file = Path(r"C:\Development GPTMEAi\dashboard\index.html")
text = html_file.read_text(encoding="utf-8")

old_show = '''    function show(url, options) {
      const r = await fetch(url, options);
      const data = await r.json();
      document.getElementById("out").textContent =
        JSON.stringify(data, null, 2);
    }
'''

new_show = '''    function renderData(data) {
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

    async function show(url, options) {
      const r = await fetch(url, options);
      const data = await r.json();
      document.getElementById("out").textContent = renderData(data);
    }
'''

if old_show in text:
    text = text.replace(old_show, new_show, 1)
else:
    raise RuntimeError("Не найден блок function show")

html_file.write_text(text, encoding="utf-8")
print("dashboard pretty snapshot enabled")