# --------------------------------------------
# Скрипт: self_update_runtime.py
# Назначение: [КОРОТКОЕ ОПИСАНИЕ ФАЙЛА, УКАЖИ ЧТО ДЕЛАЕТ]
# Автор: Crown Aliy
# Дата создания/обновления: 2026-03-12 18:32:23
# --------------------------------------------
import sys
import os
import yaml
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory_engine import MemoryEngine
from core.retrieval_engine import RetrievalEngine
from core.graph_engine import GraphMemory
from core.temporal_engine import TemporalMemory

# Placeholder Agents/Plugins
class TestAgent:
    def __init__(self, memory):
        self.memory = memory
    def add_fact(self, fact):
        self.memory.data.append(fact)
class TestPlugin:
    def __init__(self, memory):
        self.memory = memory
    def read_memory(self):
        return self.memory.data

# Инициализация всех модулей
memory_engine = MemoryEngine()
retrieval_engine = RetrievalEngine()
graph_memory = GraphMemory()
temporal_memory = TemporalMemory()
agent = TestAgent(memory_engine)
plugin = TestPlugin(memory_engine)

# Файл runtime YAML
runtime_file = '../GPTMemory_runtime.yaml'

# Загружаем YAML, если существует
if os.path.exists(runtime_file):
    with open(runtime_file, 'r', encoding='utf-8') as f:
        runtime_data = yaml.safe_load(f) or {}
else:
    runtime_data = {}

# Тестовое добавление факта через Agent
new_fact = {'id': 202, 'content': 'Self-update test fact', 'importance': 0.99}
agent.add_fact(new_fact)

# Обновляем runtime YAML
runtime_data['memory'] = memory_engine.data
with open(runtime_file, 'w', encoding='utf-8') as f:
    yaml.safe_dump(runtime_data, f, allow_unicode=True)

# Проверка
print('Self-updating memory complete')
print('Last fact in memory:', memory_engine.data[-1])
print('Runtime YAML updated with memory count:', len(memory_engine.data))





