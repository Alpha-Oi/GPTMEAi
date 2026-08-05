# --------------------------------------------
# Скрипт: setup_db.py
# Назначение: [КОРОТКОЕ ОПИСАНИЕ ФАЙЛА, УКАЖИ ЧТО ДЕЛАЕТ]
# Автор: Crown Aliy
# Дата создания/обновления: 2026-03-12 18:32:23
# --------------------------------------------
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.retrieval_engine import RetrievalEngine
from core.graph_engine import GraphMemory

# Placeholder Vector DB и Graph DB
vector_db = RetrievalEngine()
graph_db = GraphMemory()

# Инициализация структуры DB
vector_db.vectors = []
graph_db.nodes = []
graph_db.edges = []

# Сохраняем как файлы placeholder
os.makedirs('../vector_db', exist_ok=True)
os.makedirs('../graph_db', exist_ok=True)

with open('../vector_db/vector_placeholder.txt', 'w', encoding='utf-8') as f:
    f.write('Vector DB placeholder')

with open('../graph_db/graph_placeholder.txt', 'w', encoding='utf-8') as f:
    f.write('Graph DB placeholder')

print('Vector DB и Graph DB созданы')





