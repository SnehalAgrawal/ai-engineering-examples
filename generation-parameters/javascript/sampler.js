// The sampling steps, written out so you can see what each setting does.
// Same logic as ../python/sampler.py, which explains the order in detail:
// Ollama's server log shows llama.cpp applying top-k, then top-p, then min-p,
// and only then temperature, before picking a token at random.

// Ollama's defaults, as printed in its server log.
export const DEFAULTS = { temperature: 0.8, top_k: 40, top_p: 0.9, min_p: 0.0 };

/**
 * probabilities: [token, probability] pairs from the model, at temperature 1.
 * Returns a Map of the chance of each token being picked under these settings.
 * Only the tokens the API returned are known, so a setting that keeps more
 * than that can't be predicted exactly.
 */
export function predict(probabilities, { temperature, top_k, top_p, min_p }) {
  let candidates = [...probabilities].sort((a, b) => b[1] - a[1]);

  // 1. top-k: keep the k most likely tokens, and renormalize.
  candidates = candidates.slice(0, top_k);
  let total = candidates.reduce((sum, [, p]) => sum + p, 0);
  candidates = candidates.map(([token, p]) => [token, p / total]);

  // 2. top-p (nucleus): keep the most likely tokens until their probabilities add up to top_p.
  let kept = [];
  let cumulative = 0;
  for (const [token, p] of candidates) {
    kept.push([token, p]);
    cumulative += p;
    if (cumulative >= top_p) break;
  }

  // 3. min-p: drop tokens less likely than min_p times the most likely token.
  const floor = min_p * kept[0][1];
  kept = kept.filter(([, p]) => p >= floor);

  // 4. temperature: 0 means always take the most likely token.
  if (temperature <= 0) return new Map([[kept[0][0], 1]]);
  // Dividing the logits by the temperature is the same as raising each
  // probability to the power 1/temperature, then renormalizing.
  const weights = kept.map(([token, p]) => [token, p ** (1 / temperature)]);
  total = weights.reduce((sum, [, w]) => sum + w, 0);
  return new Map(weights.map(([token, w]) => [token, w / total]));
}
