from pathlib import Path

html_file = Path(r"C:\Development GPTMEAi\dashboard\index.html")
text = html_file.read_text(encoding="utf-8")

text = text.replace(
    '<pre id="out" style="margin-top:16px; white-space:pre-wrap;"></pre>',
    '<div id="out" style="margin-top:16px; white-space:normal;"></div>'
)

if "function renderHtmlData(" not in text:
    marker = "async function show(url, options) {"
    block = """
    function renderHtmlData(data) {
      if (data && data.name && data.data && data.data.snapshot_created_at) {
        const s = data.data;
        const recent = (s.recent_blocks || [])
          .map(x => `<li>[${x.id}] ${x.text}</li>`)
          .join("");

        const top = (s.memory_query_top || [])
          .map(x => `<li>[${x.id}] ${x.text}</li>`)
          .join("");

        return `
          <div style="border:1px solid #475569;padding:12px;border-radius:8px;margin-bottom:12px;">
            <div><b>Файл:</b> ${data.name}</div>
            <div><b>Создан:</b> ${s.snapshot_created_at}</div>
            <div><b>Памяти:</b> ${s.memory_count}</div>
            <div><b>Узлов графа:</b> ${s.graph_nodes}</div>
            <div><b>Связей графа:</b> ${s.graph_relations_total}</div>
          </div>
          <div style="border:1px solid #475569;padding:12px;border-radius:8px;margin-bottom:12px;">
            <b>Последние записи</b>
            <ul>${recent || "<li>-</li>"}</ul>
          </div>
          <div style="border:1px solid #475569;padding:12px;border-radius:8px;">
            <b>Top по запросу 'память'</b>
            <ul>${top || "<li>-</li>"}</ul>
          </div>
        `;
      }

      if (data && Array.isArray(data.items) && typeof data.count === "number") {
        const items = data.items
          .map(x => `<li><b>${x.name}</b> — ${x.size} bytes</li>`)
          .join("");

        return `
          <div style="border:1px solid #475569;padding:12px;border-radius:8px;">
            <div><b>Всего snapshot:</b> ${data.count}</div>
            <ul>${items || "<li>-</li>"}</ul>
          </div>
        `;
      }

      return "<pre style=\\"white-space:pre-wrap;\\">" +
        JSON.stringify(data, null, 2) +
        "</pre>";
    }

""".strip("\n")
    text = text.replace(marker, block + "\n\n    " + marker, 1)

old = """    async function show(url, options) {
      const r = await fetch(url, options);
      const data = await r.json();
      document.getElementById("out").textContent = renderData(data);
    }"""

new = """    async function show(url, options) {
      const r = await fetch(url, options);
      const data = await r.json();
      document.getElementById("out").innerHTML = renderHtmlData(data);
    }"""

text = text.replace(old, new)

html_file.write_text(text, encoding="utf-8")
print("dashboard cards view enabled")