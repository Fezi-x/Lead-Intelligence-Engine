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

    def retrieve(self, query_text, limit=3):
        """Simple keyword-based retrieval with basic ranking."""
        if not self.corpus:
            return []

        scored_docs = []
        # Support searching for common variations
        query_text = query_text.lower()
        query_words = set(query_text.split())

        for doc in self.corpus:
            doc_content = doc["content"].lower()
            doc_words = set(doc_content.split())
            
            # Intersection score
            intersection = query_words.intersection(doc_words)
            score = len(intersection)
            
            # Boost if exact matches for long words exist in content
            for word in query_words:
                if len(word) > 4 and word in doc_content:
                    score += 0.5

            if score > 0:
                scored_docs.append((score, doc))

        # If zero matches, try a broader search for high-value words
        if not scored_docs:
            for doc in self.corpus:
                doc_content = doc["content"].lower()
                for word in ["yangon", "mandalay", "bangkok", "medical", "education", "marketing", "digital"]:
                    if word in doc_content and word in query_text:
                        scored_docs.append((1, doc))
                        break

        # Sort by score descending
        scored_docs.sort(key=lambda x: x[0], reverse=True)
        
        # Unique contents only
        seen = set()
        results = []
        for score, doc in scored_docs:
            if doc["content"] not in seen:
                results.append(doc["content"])
                seen.add(doc["content"])
            if len(results) >= limit:
                break
                
        return results

if __name__ == "__main__":
    # Test retrieval
    rag = RAG()
    test_query = "We need more efficiency and automation in our sales process."
    results = rag.retrieve(test_query)
    print(f"Retrieved {len(results)} items:")
    for i, res in enumerate(results):
        print(f"--- Result {i+1} ---")
        print(res[:100] + "...")
