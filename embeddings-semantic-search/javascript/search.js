import { createEmbedding } from "./embeddings.js";

function cosineSimilarity(vec1, vec2) {
  let dotProduct = 0;
  let mag1 = 0;
  let mag2 = 0;
  for (let i = 0; i < vec1.length; i++) {
    dotProduct += vec1[i] * vec2[i];
    mag1 += vec1[i] * vec1[i];
    mag2 += vec2[i] * vec2[i];
  }
  const magnitude = Math.sqrt(mag1) * Math.sqrt(mag2);
  return magnitude === 0 ? 0 : dotProduct / magnitude;
}

async function main() {
  const documents = [
    "Customers can request a refund within 30 days of purchase.",
    "To cancel your subscription, go to Settings > Billing > Cancel.",
    "If you forgot your password, click 'Forgot Password' on the login page.",
    "Our support team is available 24/7 via live chat.",
    "Billing issues can be resolved by contacting our accounting department.",
  ];

  const query = "How do I get my money back?";
  console.log(`Query: ${query}\n`);

  try {
    console.log("Generating document embeddings...");
    const docEmbeddings = await Promise.all(documents.map(createEmbedding));

    console.log("Generating query embedding...");
    const queryEmbedding = await createEmbedding(query);

    const results = documents.map((doc, i) => ({
      doc,
      score: cosineSimilarity(queryEmbedding, docEmbeddings[i]),
    }));

    results.sort((a, b) => b.score - a.score);

    console.log("\nTop Results:");
    results.forEach(({ doc, score }) => {
      console.log(`Score: ${score.toFixed(4)} | Document: ${doc}`);
    });
  } catch (error) {
    console.error("Error:", error.message);
    process.exit(1);
  }
}

main();
