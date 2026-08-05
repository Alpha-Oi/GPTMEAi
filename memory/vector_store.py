# --------------------------------------------
# Скрипт: vector_store.py
# Назначение: [КОРОТКОЕ ОПИСАНИЕ ФАЙЛА, УКАЖИ ЧТО ДЕЛАЕТ]
# Автор: Crown Aliy
# Дата создания/обновления: 2026-03-12 18:32:23
# --------------------------------------------
import os
import json

class VectorStore:
    def __init__(self, db_path='memory/db.json'):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        if not os.path.exists(db_path):
            with open(db_path, 'w', encoding='utf-8') as f:
                json.dump({}, f)

    def save(self, key, data):
        db = self.load_all()
        db[key] = data
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(db, f, ensure_ascii=False, indent=2)

    def load(self, key):
        db = self.load_all()
        return db.get(key, None)

    def load_all(self):
        with open(self.db_path, 'r', encoding='utf-8') as f:
            return json.load(f)





