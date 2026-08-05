from scripts.runtime_store import load_runtime, save_runtime

class GraphMemory:
    def __init__(self, memory_engine):
        self.memory_engine = memory_engine
        self.stopwords = {
            "и", "в", "на", "для", "по", "с", "из", "это", "как", "что",
            "the", "and", "for", "with", "from", "this", "that"
        }

    def _extract_words(self, text):
        text = str(text).lower()
        cleaned = []

        for ch in text:
            if ch.isalnum() or ch in ("-", "_", " "):
                cleaned.append(ch)
            else:
                cleaned.append(" ")

        words = set()
        for word in "".join(cleaned).split():
            if len(word) < 4:
                continue
            if word in self.stopwords:
                continue
            words.add(word)

        return words

    def build_graph(self):
        blocks = self.memory_engine.get_all()
        graph = {str(int(block.get("id", 0))): [] for block in blocks}

        for i in range(len(blocks)):
            left = blocks[i]
            left_id = str(int(left.get("id", 0)))
            left_tags = set(str(tag).lower() for tag in left.get("tags", []))
            left_words = self._extract_words(left.get("text", ""))

            for j in range(i + 1, len(blocks)):
                right = blocks[j]
                right_id = str(int(right.get("id", 0)))
                right_tags = set(str(tag).lower() for tag in right.get("tags", []))
                right_words = self._extract_words(right.get("text", ""))

                shared_tags = sorted(left_tags & right_tags)
                shared_words = sorted(left_words & right_words)

                if not shared_tags and not shared_words:
                    continue

                relation_score = len(shared_tags) * 10 + len(shared_words)

                left_relation = {
                    "id": int(right_id),
                    "shared_tags": shared_tags,
                    "shared_words": shared_words,
                    "relation_score": relation_score,
                    "importance": int(right.get("importance", 0)),
                    "text": str(right.get("text", ""))
                }

                right_relation = {
                    "id": int(left_id),
                    "shared_tags": shared_tags,
                    "shared_words": shared_words,
                    "relation_score": relation_score,
                    "importance": int(left.get("importance", 0)),
                    "text": str(left.get("text", ""))
                }

                graph[left_id].append(left_relation)
                graph[right_id].append(right_relation)

        for block_id in graph:
            graph[block_id].sort(
                key=lambda item: (
                    int(item.get("relation_score", 0)),
                    int(item.get("importance", 0)),
                    int(item.get("id", 0))
                ),
                reverse=True
            )

        return graph

    def get_related(self, block_id):
        graph = self.build_graph()
        return graph.get(str(int(block_id)), [])

    def save_graph(self):
        runtime = load_runtime()
        graph = self.build_graph()
        runtime["graph_relations"] = graph
        save_runtime(runtime)
        return graph
