# --------------------------------------------
# Скрипт: integrate_memory.py
# Назначение: [КОРОТКОЕ ОПИСАНИЕ ФАЙЛА, УКАЖИ ЧТО ДЕЛАЕТ]
# Автор: Crown Aliy
# Дата создания/обновления: 2026-03-12 18:32:23
# --------------------------------------------
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory_engine import MemoryEngine
from core.importance_engine import ImportanceEngine
from core.retrieval_engine import RetrievalEngine
from core.graph_engine import GraphMemory
from core.temporal_engine import TemporalMemory
from core.storage_engine import StorageEngine

# Инициализация всех компонентов
memory_engine = MemoryEngine()
importance_engine = ImportanceEngine()
retrieval_engine = RetrievalEngine()
graph_memory = GraphMemory()
temporal_memory = TemporalMemory()
storage_engine = StorageEngine()

# Простейший тест добавления и поиска данных
memory_engine.data.append({'id':1, 'content':'Test fact', 'importance':0.9})
retrieval_engine_entry = memory_engine.data[-1]
graph_memory.nodes.append({'id':retrieval_engine_entry['id'], 'connections':[]})
temporal_memory.timeline.append({'event':'Test fact added', 'time':'2026-03-09T16:00:00'})
storage_engine.files.append('Test file placeholder')

print('Integration Test Complete')
print('MemoryEngine data:', memory_engine.data)
print('GraphMemory nodes:', graph_memory.nodes)
print('TemporalMemory timeline:', temporal_memory.timeline)
print('StorageEngine files:', storage_engine.files)





