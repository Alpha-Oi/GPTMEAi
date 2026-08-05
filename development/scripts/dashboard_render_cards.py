from pathlib import Path
import re

p = Path(r"C:\Development GPTMEAi\dashboard\index.html")
text = p.read_text(encoding="utf-8")

new_render = r"""
function render(d){
  const esc = (v) => String(v ?? "").replaceAll("<","&lt;").replaceAll(">","&gt;");

  const itemCard = (x) => `
    <div class="card">
      <div><b>[${esc(x.id)}]</b> ${esc(x.text)}</div>
      ${x.importance !== undefined ? `<div class="small">importance: ${esc(x.importance)}</div>` : ""}
      ${Array.isArray(x.tags) ? `<div class="small">tags: ${x.tags.length ? x.tags.map(esc).join(", ") : "-"}</div>` : ""}
      ${x.created_at ? `<div class="small">created_at: ${esc(x.created_at)}</div>` : ""}
      ${x.shared_tags ? `<div class="small">shared_tags: ${x.shared_tags.length ? x.shared_tags.map(esc).join(", ") : "-"}</div>` : ""}
      ${x.shared_words ? `<div class="small">shared_words: ${x.shared_words.length ? x.shared_words.map(esc).join(", ") : "-"}</div>` : ""}
      ${x.relation_score !== undefined ? `<div class="small">relation_score: ${esc(x.relation_score)}</div>` : ""}
    </div>`;

  if (d && d.status === "ok" && d.service) {
    return `
      <div class="card">
        <div><b>Сервис:</b> ${esc(d.service)}</div>
        <div><b>Статус:</b> ${esc(d.status)}</div>
        <div><b>Памяти:</b> ${esc(d.memory_count)}</div>
      </div>`;
  }

  if (d && d.name && d.data && d.data.snapshot_created_at) {
    const s = d.data;
    return `
      <div class="card">
        <div><b>Файл:</b> ${esc(d.name)}</div>
        <div><b>Создан:</b> ${esc(s.snapshot_created_at)}</div>
        <div><b>Памяти:</b> ${esc(s.memory_count)}</div>
        <div><b>Узлов графа:</b> ${esc(s.graph_nodes)}</div>
        <div><b>Связей графа:</b> ${esc(s.graph_relations_total)}</div>
      </div>
      <div class="card"><b>Последние записи</b></div>
      ${(s.recent_blocks || []).map(itemCard).join("") || '<div class="card">-</div>'}
      <div class="card"><b>Top по запросу "память"</b></div>
      ${(s.memory_query_top || []).map(itemCard).join("") || '<div class="card">-</div>'}`;
  }

  if (d && typeof d.count === "number" && Array.isArray(d.items)) {
    return `
      <div class="card"><b>Snapshot-файлы:</b> ${esc(d.count)}</div>
      ${d.items.map(x => `
        <div class="card">
          <div><b>${esc(x.name)}</b></div>
          <div class="small">${esc(x.size)} bytes</div>
        </div>`).join("") || '<div class="card">-</div>'}`;
  }

  if (d && typeof d.memory_count === "number" && Array.isArray(d.items)) {
    return `
      <div class="card"><b>Всего записей памяти:</b> ${esc(d.memory_count)}</div>
      ${d.items.map(itemCard).join("") || '<div class="card">-</div>'}`;
  }

  if (d && typeof d.matches === "number" && Array.isArray(d.items)) {
    return `
      <div class="card"><b>Совпадений:</b> ${esc(d.matches)}</div>
      ${d.items.map(itemCard).join("") || '<div class="card">-</div>'}`;
  }

  if (d && d.status === "ok" && d.message) {
    return `
      <div class="card">
        <div><b>${esc(d.message)}</b></div>
        ${d.file ? `<div class="small">${esc(d.file)}</div>` : ""}
        ${d.memory_count !== undefined ? `<div class="small">memory_count: ${esc(d.memory_count)}</div>` : ""}
        ${d.graph_nodes !== undefined ? `<div class="small">graph_nodes: ${esc(d.graph_nodes)}</div>` : ""}
        ${d.graph_relations_total !== undefined ? `<div class="small">graph_relations_total: ${esc(d.graph_relations_total)}</div>` : ""}
      </div>
      ${d.item ? itemCard(d.item) : ""}`;
  }

  return `<pre>${JSON.stringify(d, null, 2)}</pre>`;
}
""".strip()

text, n = re.subn(r"function render\(d\)\s*\{.*?\n\}", new_render, text, count=1, flags=re.DOTALL)
if n != 1:
    raise RuntimeError("render(d) not found")

p.write_text(text, encoding="utf-8")
print("dashboard render cards enabled")