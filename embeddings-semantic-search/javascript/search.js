import { createEmbedding, createEmbeddings } from "./embeddings.js";

// A tiny help-center "knowledge base".
const DOCUMENTS = [
  "Customers can request a refund within 30 days of purchase.",
  "To cancel your subscription, go to Settings > Billing > Cancel.",
  "If you forgot your password, click 'Forgot Password' on the login page.",
  "Our support team is available 24/7 via live chat.",
  "Billing issues can be resolved by contacting our accounting department.",
];

// Queries used when none is passed on the command line.
const DEFAULT_QUERIES = [
  "How do I get my money back?",
  "I want to stop paying for this every month",
  "I can't log in to my account",
];

// Very small stopword list so the keyword baseline ignores filler words.
const STOPWORDS = new Set([
  "a", "an", "and", "are", "can", "do", "for", "get", "how", "i", "in",
  "is", "it", "my", "of", "on", "or", "the", "this", "to", "via", "want",
  "what", "with", "within", "you", "your",
]);

// Some embedding models are trained with different prefixes for queries and
// documents (for example nomic-embed-text expects "search_query: " and
// "search_document: "). Leave these empty for models that don't use them.
const QUERY_PREFIX = process.env.QUERY_PREFIX || "";
const DOCUMENT_PREFIX = process.env.DOCUMENT_PREFIX || "";

function cosineSimilarity(vec1, vec2) {
  // Mismatched dimensions usually mean vectors from two different models.
  // Without this check, the loop would read undefined values and return NaN.
  if (vec1.length !== vec2.length) {
    throw new Error(`Dimension mismatch: ${vec1.length} vs ${vec2.length}`);
  }

  let dotProduct = 0;
  let mag1 = 0;
  let mag2 = 0;
  for (let i = 0; i < vec1.length; i++) {
    dotProduct += vec1[i] * vec2[i];
    mag1 += vec1[i] * vec1[i];
    mag2 += vec2[i] * vec2[i];
  }
  // A zero vector has no direction, so the angle is undefined.
  const magnitude = Math.sqrt(mag1) * Math.sqrt(mag2);
  if (magnitude === 0) {
    throw new Error("Cosine similarity is undefined for a zero vector");
  }
  return dotProduct / magnitude;
}

/** Lowercase words with stopwords removed. */
function keywords(text) {
  const words = text.toLowerCase().match(/[a-z0-9]+/g) || [];
  return new Set(words.filter((word) => !STOPWORDS.has(word)));
}

/**
 * Naive keyword baseline: how many query keywords appear in the document.
 * Real keyword search (for example BM25) is smarter, but it still depends
 * on the query and the document sharing terms.
 */
function keywordScore(query, document) {
  const docWords = keywords(document);
  return [...keywords(query)].filter((word) => docWords.has(word)).length;
}

async function main() {
  const queries = process.argv.slice(2).length ? process.argv.slice(2) : DEFAULT_QUERIES;

  // Index time: embed every document once.
  console.log(`Embedding ${DOCUMENTS.length} documents...`);
  const docEmbeddings = await createEmbeddings(DOCUMENTS.map((doc) => DOCUMENT_PREFIX + doc));
  console.log(`Each embedding has ${docEmbeddings[0].length} dimensions.\n`);

  for (const query of queries) {
    console.log("=".repeat(72));
    console.log(`Query: ${query}\n`);

    // Keyword baseline
    const keywordResults = DOCUMENTS.map((doc) => ({ doc, score: keywordScore(query, doc) }))
      .filter(({ score }) => score > 0)
      .sort((a, b) => b.score - a.score);

    console.log("Keyword search (shared words):");
    if (keywordResults.length === 0) {
      console.log("  No document shares a meaningful keyword with the query.");
    } else {
      keywordResults.forEach(({ doc, score }) => console.log(`  ${score} shared | ${doc}`));
    }

    // Query time: embed the query with the same model, then compare.
    const queryEmbedding = await createEmbedding(QUERY_PREFIX + query);
    const semanticResults = DOCUMENTS.map((doc, i) => ({
      doc,
      score: cosineSimilarity(queryEmbedding, docEmbeddings[i]),
    })).sort((a, b) => b.score - a.score);

    console.log("\nSemantic search (cosine similarity):");
    semanticResults.forEach(({ doc, score }) => console.log(`  ${score.toFixed(4)} | ${doc}`));
    console.log();
  }
}

main().catch((error) => {
  console.error("Error:", error.message);
  process.exit(1);
});
