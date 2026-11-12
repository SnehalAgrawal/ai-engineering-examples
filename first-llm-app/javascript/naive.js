// The model as the whole product: the user's text goes straight to the model, and the
// model's reply goes straight back. No context, no checks. Same as ../python/naive.py.
import { chat } from "./llm.js";

export async function answer(text, url = null) {
  return (await chat([{ role: "user", content: text }], { url })).content;
}
