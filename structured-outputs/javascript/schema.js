// The output contract as a JSON schema, and a validator for it.
// Same rules as ../python/schema.py: `source_ids` may only contain the ids of
// the documents retrieval returned. A schema can express that rule; it can't
// express "the cited document actually supports the answer".

export function replySchema(retrievedIds) {
  return {
    type: "object",
    properties: {
      answered: { type: "boolean" },
      answer: { type: "string" },
      source_ids: { type: "array", items: { type: "string", enum: retrievedIds } },
    },
    required: ["answered", "answer", "source_ids"],
    additionalProperties: false,
  };
}

/** The reply as a JSON object, or null. No cleanup: a Markdown fence counts as invalid. */
export function parseStrict(reply) {
  try {
    const data = JSON.parse(reply);
    return data && typeof data === "object" && !Array.isArray(data) ? data : null;
  } catch {
    return null;
  }
}

/** True when the parsed reply has exactly the three fields, with the right types and allowed ids. */
export function matchesSchema(data, retrievedIds) {
  if (!data || typeof data !== "object") return false;
  const keys = Object.keys(data).sort().join(",");
  return (
    keys === "answer,answered,source_ids" &&
    typeof data.answered === "boolean" &&
    typeof data.answer === "string" &&
    Array.isArray(data.source_ids) &&
    data.source_ids.every((id) => typeof id === "string" && retrievedIds.includes(id))
  );
}
