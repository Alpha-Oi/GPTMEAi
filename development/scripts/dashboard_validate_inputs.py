from pathlib import Path

p = Path(r"C:\Development GPTMEAi\dashboard\index.html")
t = p.read_text(encoding="utf-8")

if "function warn(" not in t:
    t = t.replace(
        "const enc = encodeURIComponent;",
        """const enc = encodeURIComponent;

function warn(msg){
  out.innerHTML = `<div class="card"><b>Ошибка</b><div class="small">${msg}</div></div>`;
}""",
        1
    )

t = t.replace(
    'show("/memory/search?q="+enc(q.value))',
    'q.value.trim() ? show("/memory/search?q="+enc(q.value.trim())) : warn("Введите текст для поиска")'
)

t = t.replace(
    'show("/memory/tag?tag="+enc(tag.value))',
    'tag.value.trim() ? show("/memory/tag?tag="+enc(tag.value.trim())) : warn("Введите тег")'
)

t = t.replace(
    'show("/memory/recent?limit="+enc(recent.value))',
    'recent.value.trim() ? show("/memory/recent?limit="+enc(recent.value.trim())) : warn("Введите limit")'
)

t = t.replace(
    'show("/memory/related?id="+enc(rel.value))',
    'rel.value.trim() ? show("/memory/related?id="+enc(rel.value.trim())) : warn("Введите id записи")'
)

t = t.replace(
    "post('/memory/add', {text:add.value})",
    "add.value.trim() ? post('/memory/add', {text:add.value.trim()}) : warn('Введите текст новой памяти')"
)

p.write_text(t, encoding="utf-8")
print("dashboard input validation enabled")