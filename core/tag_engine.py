class TagEngine:
    def __init__(self):
        self.rules = {
            "memory": ["память", "memory", "gptmemory"],
            "core": ["ядро", "core"],
            "api": ["api"],
            "retrieval": ["retrieval", "поиск", "search"],
            "ai-os": ["ai-os", "ai os"],
            "error": ["ошибка", "error"],
            "engine": ["engine", "движок"]
        }

    def extract(self, text: str):
        text = str(text).strip().lower()
        tags = []

        if not text:
            return tags

        for tag, keywords in self.rules.items():
            for keyword in keywords:
                if keyword in text:
                    tags.append(tag)
                    break

        return sorted(set(tags))
