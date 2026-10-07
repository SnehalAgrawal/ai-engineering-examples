import os
import math
from embeddings import create_embedding

def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Calculates the cosine similarity between two vectors."""
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    magnitude1 = math.sqrt(sum(a * a for a in vec1))
    magnitude2 = math.sqrt(sum(b * b for b in vec2))
    
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0
    return dot_product / (magnitude1 * magnitude2)

def main():
    # 1. Tiny example document collection
    documents = [
        "Customers can request a refund within 30 days of purchase.",
        "To cancel your subscription, go to Settings > Billing > Cancel.",
        "If you forgot your password, click 'Forgot Password' on the login page.",
        "Our support team is available 24/7 via live chat.",
        "Billing issues can be resolved by contacting our accounting department."
    ]
    
    query = "How do I get my money back?"
    print(f"Query: {query}\n")
    
    # 2. Generate embeddings for documents
    print("Generating document embeddings...")
    doc_embeddings = [create_embedding(doc) for doc in documents]
    
    # 3. Generate query embedding
    print("Generating query embedding...")
    query_embedding = create_embedding(query)
    
    # 4. Calculate similarity and rank
    results = []
    for i, doc_emb in enumerate(doc_embeddings):
        score = cosine_similarity(query_embedding, doc_emb)
        results.append((documents[i], score))
    
    # Sort by score descending
    results.sort(key=lambda x: x[1], reverse=True)
    
    print("\nTop Results:")
    for doc, score in results:
        print(f"Score: {score:.4f} | Document: {doc}")

if __name__ == "__main__":
    main()
