"""
Retrieval as in Article #18: structure-headings chunks, embedded once, and each question's chunks ranked by
RRF of vector and BM25 and filled into its budget. The excerpts for every email are computed once, saved, and
reused by every experiment (data/settings.json, "retrieval").
"""
import chunkers
import ollama
import search
from tokens import Tokenizer


class Index:
    def __init__(self, settings: dict, documents: dict[str, str]):
        self.r = settings["retrieval"]
        self.chunks = chunkers.chunk(self.r["chunking"], documents, Tokenizer())
        texts = [c.text for c in self.chunks]
        self.vectors = self.embed([self.r["embedding"]["document_prefix"] + t for t in texts])
        bm25 = self.r["bm25"]
        self.bm25 = search.BM25(texts, bm25["analyzer"], bm25["k1"], bm25["b"])

    def embed(self, texts: list[str]) -> list[list[float]]:
        size, vectors = self.r["embedding"]["batch_size"], []
        for i in range(0, len(texts), size):
            vectors += ollama.embed(texts[i:i + size])
        return vectors

    def ranking(self, question: str, vector: list[float]) -> list[int]:
        by_vector = search.rank([chunkers.cosine(vector, v) for v in self.vectors])
        by_keyword = search.rank(self.bm25.scores(question), matched_only=True)
        return search.rank(search.rrf([by_vector, by_keyword], self.r["rrf_k"], len(self.chunks)))

    def retrieve(self, questions: list[str]) -> list[int]:
        """Chunk indexes for an email's questions, in the order they were chosen."""
        vectors = self.embed([self.r["embedding"]["query_prefix"] + q for q in questions])
        chosen: list[int] = []
        total = 0
        for question, vector in zip(questions, vectors):
            budget = min(self.r["budget_per_question"], self.r["budget_per_email"] - total)
            used = 0
            for i in self.ranking(question, vector):
                tokens = self.chunks[i].tokens
                if i not in chosen and used + tokens <= budget:
                    chosen.append(i)
                    used += tokens
            total += used
        return chosen

    def excerpts(self, questions: list[str]) -> list[dict]:
        return [{"id": self.chunks[i].id, "document": self.chunks[i].document, "text": self.chunks[i].text}
                for i in self.retrieve(questions)]
