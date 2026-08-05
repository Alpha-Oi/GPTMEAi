from scripts.runtime_store import load_runtime, save_runtime, utc_now
from core.importance_engine import ImportanceEngine
from core.tag_engine import TagEngine

class MemoryEngine:
    def __init__(self):
        self.runtime = load_runtime()
        self.data = self.runtime.get("memory_blocks", [])
        self.importance_engine = ImportanceEngine()
        self.tag_engine = TagEngine()

    def reload(self):
        self.runtime = load_runtime()
        self.data = self.runtime.get("memory_blocks", [])
        return self.data

    def _normalize_block(self, block):
        text = str(block.get("text", "")).strip()

        if "importance" not in block or not isinstance(block.get("importance"), int):
            block["importance"] = self.importance_engine.evaluate(text)

        if "tags" not in block or not isinstance(block.get("tags"), list):
            block["tags"] = self.tag_engine.extract(text)

        return block

    def normalize_all(self):
        self.reload()
        normalized = []

        for block in self.data:
            normalized.append(self._normalize_block(block))

        self.data = normalized
        self.runtime["memory_blocks"] = self.data
        self.runtime["last_updated"] = utc_now()
        save_runtime(self.runtime)
        return self.data

    def count(self):
        self.reload()
        return len(self.data)

    def get_all(self):
        self.reload()
        normalized = [self._normalize_block(block) for block in self.data]
        return list(normalized)


    def delete(self, block_id):
        self.reload()

        try:
            block_id = int(block_id)
        except ValueError:
            raise ValueError("Memory id must be an integer")

        new_data = [x for x in self.data if int(x.get("id", 0)) != block_id]

        if len(new_data) == len(self.data):
            raise ValueError("Memory id not found")

        for i, item in enumerate(new_data, start=1):
            item["id"] = i

        self.data = new_data
        self.runtime["memory_blocks"] = self.data
        self.runtime["last_updated"] = utc_now()
        save_runtime(self.runtime)
        return self.data

    def add(self, text: str, *, tags=None, importance: int | None = None, metadata: dict | None = None):
        text = str(text).strip()
        if not text:
            raise ValueError("Memory text is empty")

        self.reload()
        next_id = len(self.data) + 1
        if importance is None:
            importance = self.importance_engine.evaluate(text)
        else:
            try:
                importance = int(importance)
            except (TypeError, ValueError):
                importance = self.importance_engine.evaluate(text)

        if tags is None:
            tags = self.tag_engine.extract(text)
        else:
            tags = [str(tag).strip() for tag in list(tags or []) if str(tag).strip()]

        block = {
            "id": next_id,
            "text": text,
            "importance": importance,
            "tags": tags,
            "created_at": utc_now()
        }
        if metadata:
            block["metadata"] = dict(metadata)

        self.data.append(block)
        self.runtime["memory_blocks"] = self.data
        self.runtime["last_updated"] = utc_now()
        save_runtime(self.runtime)
        return block

    def add_concept_node(self, payload: dict, *, tags=None, importance: int | None = None):
        from ai_os.concept_core import MemoryCommitValidator

        node = MemoryCommitValidator().validate(payload)
        metadata = {
            "concept_core": node.to_dict()
        }
        return self.add(node.content, tags=tags, importance=importance, metadata=metadata)
