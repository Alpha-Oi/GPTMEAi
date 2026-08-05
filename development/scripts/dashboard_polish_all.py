from pathlib import Path
import re

p = Path(r"C:\Development GPTMEAi\dashboard\index.html")
t = p.read_text(encoding="utf-8")

# 1) CSS: делаем правую колонку уже, карточки компактнее, секции чище
t = re.sub(
    r"\.wrap\{[^}]*\}",
    ".wrap{display:grid;grid-template-columns:320px minmax(620px,820px);gap:18px;padding:18px;align-items:start;justify-content:start}",
    t
)
t = re.sub(
    r"\.panel,\.out\{[^}]*\}",
    ".panel,.out{background:#111827;border:1px solid #334155;border-radius:14px;padding:16px}",
    t
)
t = re.sub(
    r"\.out\{[^}]*\}",
    ".out{min-height:84vh;max-width:820px;overflow:auto}",
    t
)
t = re.sub(
    r"\.card\{[^}]*\}",
    ".card{border:1px solid #334155;border-radius:12px;padding:12px 14px;margin:0 0 12px;background:#0b1220;max-width:760px;box-shadow:0 0 0 1px rgba(255,255,255,.02) inset}",
    t
)
t = re.sub(
    r"\.small\{[^}]*\}",
    ".small{opacity:.72;font-size:11px;line-height:1.4;margin-top:3px}",
    t
)
if ".sectionTitle{" not in t:
    t = t.replace(
        "</style>",
        ".sectionTitle{font-size:14px;font-weight:700;margin:4px 0 10px;color:#f8fafc;opacity:.95}\n"
        ".metaGrid{display:grid;grid-template-columns:repeat(2,minmax(180px,1fr));gap:6px 14px;margin-top:2px}\n"
        ".metaItem{font-size:12px;opacity:.88}\n"
        ".muted{opacity:.7}\n"
        ".divider{height:1px;background:#233047;margin:10px 0 2px}\n"
        "</style>"
    )

# 2) render(d): полный аккуратный вывод карточками
new_render = r"""
function render(d){
  const esc = (v) => String(v ?? "").replaceAll("<","&lt;").replaceAll(">","&gt;");

  const itemCard = (x) => `
    <div class="card">
      <div style="font-size:16px;line-height:1.35;font-weight:700;margin-bottom:6px;">
        <span class="muted">[${esc(x.id)}]</span> ${esc(x.text)}
      </div>
      <div class="metaGrid">
        ${x.importance !== undefined ? `<div class="metaItem"><b>importance:</b> ${esc(x.importance)}</div>` : ""}
        ${Array.isArray(x.tags) ? `<div class="metaItem"><b>tags:</b> ${x.tags.length ? x.tags.map(esc).join(" · ") : "-"}</div>` : ""}
        ${x.created_at ? `<div class="metaItem"><b>created_at:</b> ${esc(x.created_at)}</div>` : ""}
        ${x.shared_tags ? `<div class="metaItem"><b>shared_tags:</b> ${x.shared_tags.length ? x.shared_tags.map(esc).join(" · ") : "-"}</div>` : ""}
        ${x.shared_words ? `<div class="metaItem"><b>shared_words:</b> ${x.shared_words.length ? x.shared_words.map(esc).join(" · ") : "-"}</div>` : ""}
        ${x.relation_score !== undefined ? `<div class="metaItem"><b>relation_score:</b> ${esc(x.relation_score)}</div>` : ""}
      </div>
    </div>`;

  if (d && d.status === "ok" && d.service) {
    return `
      <div class="card">
        <div class="sectionTitle">Состояние сервиса</div>
        <div class="metaGrid">
          <div class="metaItem"><b>service:</b> ${esc(d.service)}</div>
          <div class="metaItem"><b>status:</b> ${esc(d.status)}</div>
          <div class="metaItem"><b>memory_count:</b> ${esc(d.memory_count)}</div>
        </div>
      </div>`;
  }

  if (d && d.name && d.data && d.data.snapshot_created_at) {
    const s = d.data;
    return `
      <div class="card">
        <div class="sectionTitle">Последний snapshot</div>
        <div class="metaGrid">
          <div class="metaItem"><b>file:</b> ${esc(d.name)}</div>
          <div class="metaItem"><b>created:</b> ${esc(s.snapshot_created_at)}</div>
          <div class="metaItem"><b>memory_count:</b> ${esc(s.memory_count)}</div>
          <div class="metaItem"><b>graph_nodes:</b> ${esc(s.graph_nodes)}</div>
          <div class="metaItem"><b>graph_relations:</b> ${esc(s.graph_relations_total)}</div>
          <div class="metaItem"><b>last_updated:</b> ${esc(s.last_updated || "-")}</div>
        </div>
      </div>
      <div class="sectionTitle">Последние записи</div>
      ${(s.recent_blocks || []).map(itemCard).join("") || '<div class="card">-</div>'}
      <div class="sectionTitle">Top по запросу "память"</div>
      ${(s.memory_query_top || []).map(itemCard).join("") || '<div class="card">-</div>'}`;
  }

  if (d && typeof d.count === "number" && Array.isArray(d.items)) {
    return `
      <div class="card">
        <div class="sectionTitle">Список snapshot</div>
        <div class="metaItem"><b>count:</b> ${esc(d.count)}</div>
      </div>
      ${d.items.map(x => `
        <div class="card">
          <div style="font-size:15px;font-weight:700;">${esc(x.name)}</div>
          <div class="small">${esc(x.size)} bytes</div>
        </div>`).join("") || '<div class="card">-</div>'}`;
  }

  if (d && typeof d.memory_count === "number" && Array.isArray(d.items)) {
    return `
      <div class="card">
        <div class="sectionTitle">Все записи памяти</div>
        <div class="metaItem"><b>memory_count:</b> ${esc(d.memory_count)}</div>
      </div>
      ${d.items.map(itemCard).join("") || '<div class="card">-</div>'}`;
  }

  if (d && typeof d.matches === "number" && Array.isArray(d.items)) {
    const label = d.query ? `Результаты поиска: ${esc(d.query)}` :
                  d.tag ? `Результаты по тегу: ${esc(d.tag)}` :
                  d.id ? `Связанные записи для #${esc(d.id)}` :
                  d.limit ? `Последние записи (limit=${esc(d.limit)})` :
                  "Результаты";
    return `
      <div class="card">
        <div class="sectionTitle">${label}</div>
        <div class="metaItem"><b>matches:</b> ${esc(d.matches)}</div>
      </div>
      ${d.items.map(itemCard).join("") || '<div class="card">-</div>'}`;
  }

  if (d && d.status === "ok" && d.message) {
    return `
      <div class="card">
        <div class="sectionTitle">${esc(d.message)}</div>
        ${d.file ? `<div class="small">${esc(d.file)}</div>` : ""}
        <div class="metaGrid">
          ${d.memory_count !== undefined ? `<div class="metaItem"><b>memory_count:</b> ${esc(d.memory_count)}</div>` : ""}
          ${d.graph_nodes !== undefined ? `<div class="metaItem"><b>graph_nodes:</b> ${esc(d.graph_nodes)}</div>` : ""}
          ${d.graph_relations_total !== undefined ? `<div class="metaItem"><b>graph_relations_total:</b> ${esc(d.graph_relations_total)}</div>` : ""}
        </div>
      </div>
      ${d.item ? itemCard(d.item) : ""}`;
  }

  return `<pre>${JSON.stringify(d, null, 2)}</pre>`;
}
""".strip()

t, n = re.subn(r"function render\(d\)\s*\{.*?\n\}", new_render, t, count=1, flags=re.DOTALL)
if n != 1:
    raise RuntimeError("render(d) not found")

# 3) Левую панель делаем чуть аккуратнее
t = t.replace('<div class="small">Локальная панель памяти</div>', '<div class="small">Локальная панель памяти</div><div class="divider"></div>')

p.write_text(t, encoding="utf-8")
print("dashboard polished")