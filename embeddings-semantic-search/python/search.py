import math
import os
import re
import sys

from embeddings import create_embedding, create_embeddings

# A tiny help-center "knowledge base".
DOCUMENTS = [
    "Customers can request a refund within 30 days of purchase.",
    "To cancel your subscription, go to Settings > Billing > Cancel.",
    "If you forgot your password, click 'Forgot Password' on the login page.",
    "Our support team is available 24/7 via live chat.",
    "Billing issues can be resolved by contacting our accounting department.",
]

# Queries used when none is passed on the command line.
DEFAULT_QUERIES = [
    "How do I get my money back?",
    "I want to stop paying for this every month",
    "I can't log in to my account",
]

# Very small stopword list so the keyword baseline ignores filler words.
STOPWORDS = {
    "a", "an", "and", "are", "can", "do", "for", "get", "how", "i", "in",
    "is", "it", "my", "of", "on", "or", "the", "this", "to", "via", "want",
    "what", "with", "within", "you", "your",
}

# Some embedding models are trained with different prefixes for queries and
# documents (for example nomic-embed-text expects "search_query: " and
# "search_document: "). Leave these empty for models that don't use them.
QUERY_PREFIX = os.environ.get("QUERY_PREFIX", "")
DOCUMENT_PREFIX = os.environ.get("DOCUMENT_PREFIX", "")


def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Calculates the cosine similarity between two vectors."""
    # zip() silently stops at the shorter list, so mismatched dimensions
    # (usually vectors from two different models) would produce a
    # meaningless score instead of an error. Fail loudly instead.
    if len(vec1) != len(vec2):
        raise ValueError(f"Dimension mismatch: {len(vec1)} vs {len(vec2)}")

    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    magnitude1 = math.sqrt(sum(a * a for a in vec1))
    magnitude2 = math.sqrt(sum(b * b for b in vec2))

    # A zero vector has no direction, so the angle is undefined.
    if magnitude1 == 0 or magnitude2 == 0:
        raise ValueError("Cosine similarity is undefined for a zero vector")
    return dot_product / (magnitude1 * magnitude2)


def keywords(text: str) -> set[str]:
    """Lowercase words with stopwords removed."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {word for word in words if word not in STOPWORDS}


def keyword_score(query: str, document: str) -> int:
    """
    Naive keyword baseline: how many query keywords appear in the document.
    Real keyword search (for example BM25) is smarter, but it still depends
    on the query and the document sharing terms.
    """
    return len(keywords(query) & keywords(document))


def main():
    queries = sys.argv[1:] or DEFAULT_QUERIES

    # Index time: embed every document once.
    print(f"Embedding {len(DOCUMENTS)} documents...")
    doc_embeddings = create_embeddings([DOCUMENT_PREFIX + doc for doc in DOCUMENTS])
    print(f"Each embedding has {len(doc_embeddings[0])} dimensions.\n")

    for query in queries:
        print("=" * 72)
        print(f"Query: {query}\n")

        # Keyword baseline
        keyword_results = sorted(
            ((keyword_score(query, doc), doc) for doc in DOCUMENTS),
            reverse=True,
        )
        print("Keyword search (shared words):")
        if keyword_results[0][0] == 0:
            print("  No document shares a meaningful keyword with the query.")
        else:
            for score, doc in keyword_results:
                if score > 0:
                    print(f"  {score} shared | {doc}")

        # Query time: embed the query with the same model, then compare.
        query_embedding = create_embedding(QUERY_PREFIX + query)
        semantic_results = sorted(
            (
                (cosine_similarity(query_embedding, doc_emb), doc)
                for doc, doc_emb in zip(DOCUMENTS, doc_embeddings)
            ),
            reverse=True,
        )
        print("\nSemantic search (cosine similarity):")
        for score, doc in semantic_results:
            print(f"  {score:.4f} | {doc}")
        print()


if __name__ == "__main__":
    main()
