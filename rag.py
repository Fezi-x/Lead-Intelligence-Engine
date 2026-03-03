import os
import glob

class RAG:
    def __init__(self, knowledge_dir="knowledge"):
        self.knowledge_dir = knowledge_dir
        self.corpus = []
        self._load_corpus()

    def _load_corpus(self):
        """Loads all markdown files from the knowledge directory."""
        files = glob.glob(os.path.join(self.knowledge_dir, "*.md"))
        for file_path in files:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                self.corpus.append({
                    "source": os.path.basename(file_path),
                    "content": content
                })

    def retrieve(self, query_text, limit=2):
        """Simple keyword-based retrieval. Returns top matching documents from the corpus."""
        if not self.corpus:
            return []

        scored_docs = []
        query_words = set(query_text.lower().split())

        for doc in self.corpus:
            doc_words = set(doc["content"].lower().split())
            intersection = query_words.intersection(doc_words)
            score = len(intersection)
            if score > 0:
                scored_docs.append((score, doc))

        # Sort by score descending
        scored_docs.sort(key=lambda x: x[0], reverse=True)
        
        # Return top N content
        return [doc["content"] for score, doc in scored_docs[:limit]]

if __name__ == "__main__":
    # Test retrieval
    rag = RAG()
    test_query = "We need more efficiency and automation in our sales process."
    results = rag.retrieve(test_query)
    print(f"Retrieved {len(results)} items:")
    for i, res in enumerate(results):
        print(f"--- Result {i+1} ---")
        print(res[:100] + "...")
