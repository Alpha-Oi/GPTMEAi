from pathlib import Path

p = Path(r"C:\Development GPTMEAi\dashboard\index.html")
t = p.read_text(encoding="utf-8")

old_edit = """async function editMemory(){
  const id = editId.value.trim();
  const text = editText.value.trim();
  if(!id) return warn("Введите id для редактирования");
  if(!text) return warn("Введите новый текст");
  await post('/memory/edit', {id:Number(id), text});
}"""

new_edit = """async function editMemory(){
  const id = document.getElementById('editId').value.trim();
  const text = document.getElementById('editText').value.trim();
  if(!id) return warn("Введите id для редактирования");
  if(!/^\\d+$/.test(id)) return warn("id должен быть числом");
  if(!text) return warn("Введите новый текст");
  await post('/memory/edit', {id: parseInt(id, 10), text});
}"""

old_delete = """async function deleteMemory(){
  const id = deleteId.value.trim();
  if(!id) return warn("Введите id для удаления");
  await post('/memory/delete', {id:Number(id)});
}"""

new_delete = """async function deleteMemory(){
  const id = document.getElementById('deleteId').value.trim();
  if(!id) return warn("Введите id для удаления");
  if(!/^\\d+$/.test(id)) return warn("id должен быть числом");
  await post('/memory/delete', {id: parseInt(id, 10)});
}"""

t = t.replace(old_edit, new_edit)
t = t.replace(old_delete, new_delete)

p.write_text(t, encoding="utf-8")
print("dashboard edit/delete id fix applied")