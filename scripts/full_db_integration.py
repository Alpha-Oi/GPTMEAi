# --------------------------------------------
# Скрипт: full_db_integration.py
# Назначение: [КОРОТКОЕ ОПИСАНИЕ ФАЙЛА, УКАЖИ ЧТО ДЕЛАЕТ]
# Автор: Crown Aliy
# Дата создания/обновления: 2026-03-12 18:32:23
# --------------------------------------------
import sys
import os
import yaml
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.memory_engine import MemoryEngine
from core.retrieval_engine import RetrievalEngine
from core.graph_engine import GraphMemory
from core.temporal_engine import TemporalMemory

# Placeholder для полноценных DB
vector_db = RetrievalEngine(); vector_db.vectors = []
graph_db = GraphMemory(); graph_db.nodes = []; graph_db.edges = []

# Agents/Plugins
class TestAgent:
    def __init__(self, memory, retrieval, graph):
        self.memory = memory
        self.retrieval = retrieval
        self.graph = graph
    def add_fact(self, fact):
        # Добавление в Memory
        self.memory.data.append(fact)
        # Добавление в Graph
        node_id = len(self.graph.nodes) + 1
        self.graph.nodes.append({'id': node_id, 'connections': []})
        # Добавление в Temporal
        fact['time'] = datetime.now().isoformat()
        temporal_memory.timeline.append({'event': fact['content'], 'time': fact['time']})
        # Добавление в Vector DB (placeholder)
        self.retrieval.vectors.append({'id': node_id, 'content': fact['content']})
class TestPlugin:
    def __init__(self, memory, graph):
        self.memory = memory
        self.graph = graph
    def read_memory(self):
        return self.memory.data
    def read_graph(self):
        return self.graph.nodes

# Инициализация всех модулей
memory_engine = MemoryEngine()
retrieval_engine = vector_db
graph_memory = graph_db
temporal_memory = TemporalMemory()
agent = TestAgent(memory_engine, retrieval_engine, graph_memory)
plugin = TestPlugin(memory_engine, graph_memory)

# Runtime YAML
runtime_file = '../GPTMemory_runtime.yaml'
if os.path.exists(runtime_file):
    with open(runtime_file, 'r', encoding='utf-8') as f:
        runtime_data = yaml.safe_load(f) or {}
else:
    runtime_data = {}

# Тестовое добавление факта
new_fact = {'id': 303, 'content': 'Full DB integration test fact', 'importance': 0.97}
agent.add_fact(new_fact)

# Обновление runtime YAML
runtime_data['memory'] = memory_engine.data
runtime_data['graph'] = graph_memory.nodes
runtime_data['temporal'] = temporal_memory.timeline
with open(runtime_file, 'w', encoding='utf-8') as f:
    yaml.safe_dump(runtime_data, f, allow_unicode=True)

# Проверка
print('Full DB integration complete')
print('Memory count:', len(memory_engine.data))
print('Graph nodes count:', len(graph_memory.nodes))
print('Temporal timeline count:', len(temporal_memory.timeline))
print('Vector DB count:', len(retrieval_engine.vectors))





