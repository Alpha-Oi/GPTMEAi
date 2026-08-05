from pathlib import Path

p = Path(r"C:\Development GPTMEAi\dashboard\index.html")
p.write_text("""<!doctype html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<title>GPTMemory Dashboard</title>
<style>
body{margin:0;font:14px Arial;background:#0f172a;color:#e5e7eb}
.wrap{display:grid;grid-template-columns:320px 1fr;gap:16px;padding:16px;align-items:start}
.panel,.out{background:#111827;border:1px solid #334155;border-radius:12px;padding:14px}
h1,h3{margin:0 0 10px} h3{margin-top:14px}
input,button{width:100%;box-sizing:border-box;margin:6px 0;padding:10px;border-radius:8px;border:1px solid #475569}
input{background:#0b1220;color:#e5e7eb}
button{background:#2563eb;color:#fff;border:none;cursor:pointer}
button:hover{background:#1d4ed8}
.row{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.out{min-height:80vh;overflow:auto}
.card{border:1px solid #475569;border-radius:10px;padding:12px;margin:0 0 12px;background:#0b1220;max-width:760px}
ul{margin:8px 0 0 18px;padding:0}
pre{white-space:pre-wrap}
.small{opacity:.8;font-size:12px}
</style>
</head>
<body>
<div class="wrap">
  <div class="panel">
    <h1>GPTMemory</h1>
    <div class="small">Локальная панель памяти</div>

    <h3>Система</h3>
    <div class="row">
      <button onclick="show('/health')">Health</button>
      <button onclick="show('/memory/all')">Память</button>
    </div>
    <button onclick="post('/memory/build_graph', {})">Пересобрать граф</button>

    <h3>Поиск</h3>
    <input id="q" placeholder="поиск: память">
    <button onclick="show('/memory/search?q='+enc(q.value))">Искать</button>

    <h3>Поиск по тегу</h3>
    <input id="tag" placeholder="тег: memory">
    <button onclick="show('/memory/tag?tag='+enc(tag.value))">Искать тег</button>

    <h3>Последние записи</h3>
    <input id="recent" value="3">
    <button onclick="show('/memory/recent?limit='+enc(recent.value))">Показать</button>

    <h3>Связанные записи</h3>
    <input id="rel" value="4">
    <button onclick="show('/memory/related?id='+enc(rel.value))">Показать</button>

    <h3>Добавить память</h3>
    <input id="add" placeholder="новая запись памяти">
    <button onclick="post('/memory/add', {text:add.value})">Добавить</button>

    <h3>Snapshot</h3>
    <div class="row">
      <button onclick="post('/snapshot/export', {})">Экспорт</button>
      <button onclick="show('/snapshot/latest')">Последний</button>
    </div>
    <button onclick="show('/snapshots')">Список snapshot</button>
  </div>

  <div id="out" class="out"></div>
</div>

<script>
const out = document.getElementById('out');
const enc = encodeURIComponent;

function list(items, fn){ return "<ul>"+(items?.length?items.map(fn).join(""):"<li>-</li>")+"</ul>"; }

function render(d){
  if(d?.name && d?.data?.snapshot_created_at){
    const s = d.data;
    return `
      <div class="card"><b>Файл:</b> ${d.name}<br><b>Создан:</b> ${s.snapshot_created_at}<br>
      <b>Памяти:</b> ${s.memory_count}<br><b>Узлов графа:</b> ${s.graph_nodes}<br>
      <b>Связей графа:</b> ${s.graph_relations_total}</div>
      <div class="card"><b>Последние записи</b>${list(s.recent_blocks, x=>`<li>[${x.id}] ${x.text}</li>`)}</div>
      <div class="card"><b>Top по запросу "память"</b>${list(s.memory_query_top, x=>`<li>[${x.id}] ${x.text}</li>`)}</div>`;
  }
  if(typeof d?.count==="number" && Array.isArray(d.items)){
    return `<div class="card"><b>Всего:</b> ${d.count}${list(d.items, x=>`<li>${x.name}${x.size?` — ${x.size} bytes`:""}</li>`)}</div>`;
  }
  if(typeof d?.memory_count==="number" && Array.isArray(d.items)){
    return `<div class="card"><b>Записей памяти:</b> ${d.memory_count}${list(d.items, x=>`<li>[${x.id}] ${x.text}</li>`)}</div>`;
  }
  if(typeof d?.matches==="number" && Array.isArray(d.items)){
    return `<div class="card"><b>Совпадений:</b> ${d.matches}${list(d.items, x=>`<li>[${x.id}] ${x.text}</li>`)}</div>`;
  }
  return `<pre>${JSON.stringify(d,null,2)}</pre>`;
}

async function show(url){
  const r = await fetch(url);
  out.innerHTML = render(await r.json());
}
async function post(url, body){
  const r = await fetch(url,{method:'POST',headers:{'Content-Type':'application/json; charset=utf-8'},body:JSON.stringify(body)});
  out.innerHTML = render(await r.json());
}

show('/health');
</script>
</body>
</html>
""", encoding="utf-8")
print("index.html layout rebuilt")