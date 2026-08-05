from datetime import datetime

class TemporalMemory:
    def __init__(self, memory_engine):
        self.memory_engine = memory_engine

    def _parse_created_at(self, value):
        value = str(value).strip()
        if not value:
            return datetime.min

        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return datetime.min

    def get_timeline(self):
        blocks = self.memory_engine.get_all()
        return sorted(
            blocks,
            key=lambda block: self._parse_created_at(block.get("created_at", "")),
            reverse=True
        )

    def get_recent(self, limit=5):
        timeline = self.get_timeline()
        return timeline[:max(0, int(limit))]

    def search_by_date(self, date_prefix: str):
        date_prefix = str(date_prefix).strip()
        if not date_prefix:
            return []

        matches = []
        for block in self.get_timeline():
            created_at = str(block.get("created_at", ""))
            if created_at.startswith(date_prefix):
                matches.append(block)

        return matches
