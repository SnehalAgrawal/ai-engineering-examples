"""
The sampling steps, written out so you can see what each setting does.

Ollama 0.40.1 runs these models through llama.cpp. Its server log
(~/.ollama/logs/server.log) prints the sampler chain it applies:

    logits -> penalties -> ... -> top-k -> typical -> top-p -> min-p -> xtc -> temp-ext -> dist

So the order is: keep the top_k tokens, then keep the smallest set whose
probabilities add up to top_p, then drop tokens below min_p x (the top
token's probability), and only then apply temperature and pick one at random.
Penalties are disabled at Ollama's defaults and are not modelled here.

predict() applies the same steps to the probabilities the model reported,
so its output can be compared with what the model actually picks.
"""

# Ollama's defaults, as printed in its server log.
DEFAULTS = {"temperature": 0.8, "top_k": 40, "top_p": 0.9, "min_p": 0.0}


def predict(probabilities: list[tuple[str, float]], temperature: float, top_k: int, top_p: float, min_p: float) -> dict[str, float]:
    """
    probabilities: (token, probability) pairs from the model, at temperature 1.
    Returns the chance of each token being picked under these settings.

    Only the tokens the API returned are known (20 here, covering about 99.8%
    of the probability in the examples), so a setting that keeps more than
    that can't be predicted exactly.
    """
    candidates = sorted(probabilities, key=lambda pair: -pair[1])

    # 1. top-k: keep the k most likely tokens, and renormalize.
    candidates = candidates[:top_k]
    total = sum(p for _, p in candidates)
    candidates = [(token, p / total) for token, p in candidates]

    # 2. top-p (nucleus): keep the most likely tokens until their probabilities add up to top_p.
    kept, cumulative = [], 0.0
    for token, p in candidates:
        kept.append((token, p))
        cumulative += p
        if cumulative >= top_p:
            break

    # 3. min-p: drop tokens less likely than min_p times the most likely token.
    floor = min_p * kept[0][1]
    kept = [(token, p) for token, p in kept if p >= floor]

    # 4. temperature: 0 means always take the most likely token.
    if temperature <= 0:
        return {kept[0][0]: 1.0}
    # Dividing the logits by the temperature is the same as raising each
    # probability to the power 1/temperature, then renormalizing.
    weights = [(token, p ** (1 / temperature)) for token, p in kept]
    total = sum(w for _, w in weights)
    return {token: w / total for token, w in weights}
