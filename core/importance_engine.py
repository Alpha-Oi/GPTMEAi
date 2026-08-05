class ImportanceEngine:
    def __init__(self):
        self.keyword_weights = {
            "важно": 3,
            "критично": 4,
            "ошибка": 3,
            "ядро": 2,
            "память": 2,
            "api": 2,
            "ai-os": 2,
            "retrieval": 2,
            "memory": 2
        }

    def evaluate(self, text: str) -> int:
        text = str(text).strip().lower()
        if not text:
            return 0

        score = 1

        for keyword, weight in self.keyword_weights.items():
            if keyword in text:
                score += weight

        if len(text) >= 40:
            score += 1

        return score
