from pathlib import Path

p = Path(r"C:\Development GPTMEAi\dashboard\index.html")
t = p.read_text(encoding="utf-8")

block = """
    <h3>Редактировать память</h3>
    <input id="editId" placeholder="id записи">
    <input id="editText" placeholder="новый текст">
    <button onclick="editMemory()">Сохранить</button>

    <h3>Удалить память</h3>
    <input id="deleteId" placeholder="id записи">
    <button onclick="deleteMemory()">Удалить</button>
"""

funcs = """
async function editMemory(){
  const id = editId.value.trim();
  const text = editText.value.trim();
  if(!id) return warn("Введите id для редактирования");
  if(!text) return warn("Введите новый текст");
  await post('/memory/edit', {id:Number(id), text});
}

async function deleteMemory(){
  const id = deleteId.value.trim();
  if(!id) return warn("Введите id для удаления");
  await post('/memory/delete', {id:Number(id)});
}
"""

if "Редактировать память" not in t:
    anchor = "    <h3>Snapshot</h3>"
    t = t.replace(anchor, block + "\n\n" + anchor, 1)

if "async function editMemory()" not in t:
    anchor = "async function post(url, body){"
    t = t.replace(anchor, funcs + "\n" + anchor, 1)

p.write_text(t, encoding="utf-8")
print("dashboard edit/delete added")