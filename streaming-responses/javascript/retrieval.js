// Retrieval as in Article #18. Same behaviour as ../python/retrieval.py.
import * as chunkers from "./chunkers.js";
import * as ollama from "./ollama.js";
import * as search from "./search.js";
import { Tokenizer } from "./tokens.js";

export class Index {
  async init(settings, documents) {
    this.r = settings.retrieval;
    this.chunks = chunkers.chunk(this.r.chunking, documents, new Tokenizer());
    const texts = this.chunks.map((c) => c.text);
    this.vectors = await this.embed(texts.map((t) => this.r.embedding.document_prefix + t));
    this.bm25 = new search.BM25(texts, this.r.bm25.analyzer, this.r.bm25.k1, this.r.bm25.b);
    return this;
  }

  async embed(texts) {
    const size = this.r.embedding.batch_size;
    const vectors = [];
    for (let i = 0; i < texts.length; i += size) vectors.push(...await ollama.embed(texts.slice(i, i + size)));
    return vectors;
  }

  ranking(question, vector) {
    const byVector = search.rank(this.vectors.map((v) => chunkers.cosine(vector, v)));
    const byKeyword = search.rank(this.bm25.scores(question), true);
    return search.rank(search.rrf([byVector, byKeyword], this.r.rrf_k, this.chunks.length));
  }

  // Chunk indexes for an email's questions, in the order they were chosen.
  async retrieve(questions) {
    const vectors = await this.embed(questions.map((q) => this.r.embedding.query_prefix + q));
    const chosen = [];
    let total = 0;
    questions.forEach((question, k) => {
      const budget = Math.min(this.r.budget_per_question, this.r.budget_per_email - total);
      let used = 0;
      for (const i of this.ranking(question, vectors[k])) {
        const { tokens } = this.chunks[i];
        if (!chosen.includes(i) && used + tokens <= budget) {
          chosen.push(i);
          used += tokens;
        }
      }
      total += used;
    });
    return chosen;
  }

  async excerpts(questions) {
    return (await this.retrieve(questions)).map((i) => ({ id: this.chunks[i].id, document: this.chunks[i].document, text: this.chunks[i].text }));
  }
}
