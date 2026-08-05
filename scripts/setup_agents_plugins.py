# --------------------------------------------
# Скрипт: setup_agents_plugins.py
# Назначение: [КОРОТКОЕ ОПИСАНИЕ ФАЙЛА, УКАЖИ ЧТО ДЕЛАЕТ]
# Автор: Crown Aliy
# Дата создания/обновления: 2026-03-12 18:32:23
# --------------------------------------------
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory_engine import MemoryEngine
from core.retrieval_engine import RetrievalEngine

# Создаём структуры папок
os.makedirs('../agents', exist_ok=True)
os.makedirs('../plugins', exist_ok=True)

# Placeholder Agent
class TestAgent:
    def __init__(self, memory, retrieval):
        self.memory = memory
        self.retrieval = retrieval
    def add_fact(self, fact):
        self.memory.data.append(fact)
    def get_last_fact(self):
        return self.memory.data[-1] if self.memory.data else None

# Placeholder Plugin
class TestPlugin:
    def __init__(self, memory):
        self.memory = memory
    def read_memory(self):
        return self.memory.data

# Инициализация
memory_engine = MemoryEngine()
retrieval_engine = RetrievalEngine()
agent = TestAgent(memory_engine, retrieval_engine)
plugin = TestPlugin(memory_engine)

# Тестовое добавление и чтение
agent.add_fact({'id': 101, 'content': 'Agent test fact', 'importance': 0.95})
last_fact = agent.get_last_fact()
plugin_data = plugin.read_memory()

print('Agent last fact:', last_fact)
print('Plugin memory data count:', len(plugin_data))





