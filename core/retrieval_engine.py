class RetrievalEngine:
    def __init__(self, memory_engine):
        self.memory_engine = memory_engine

    def _sort_matches(self, matches):
        matches.sort(
            key=lambda block: (
                int(block.get("importance", 0)),
                int(block.get("id", 0))
            ),
            reverse=True
        )
        return matches

    def search(self, query: str):
        query = str(query).strip().lower()
        if not query:
            return []

        blocks = self.memory_engine.get_all()
        matches = []

        for block in blocks:
            text = str(block.get("text", ""))
            if query in text.lower():
                matches.append(block)

        return self._sort_matches(matches)

    def search_by_tag(self, tag: str):
        tag = str(tag).strip().lower()
        if not tag:
            return []

        blocks = self.memory_engine.get_all()
        matches = []

        for block in blocks:
            tags = [str(x).lower() for x in block.get("tags", [])]
            if tag in tags:
                matches.append(block)

        return self._sort_matches(matches)
