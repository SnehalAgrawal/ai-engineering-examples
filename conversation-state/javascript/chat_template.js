// The request as the model reads it: llama3.2:3b's chat template from Ollama 0.40.16, rendered and counted.
// Same as ../python/chat_template.py, where the template is described.
import { Tokenizer } from "./tokens.js";

let tokenizerInstance = null;
export const tokenizer = () => (tokenizerInstance ??= new Tokenizer());

// The request as a list of pieces: special tokens as '<|...|>' strings, and plain text.
export function render(messages) {
  const system = messages.filter((m) => m.role === "system").map((m) => m.content).join("\n\n");
  const rest = messages.filter((m) => m.role !== "system");
  const pieces = ["<|begin_of_text|>", "<|start_header_id|>", "system", "<|end_header_id|>",
    `\n\nCutting Knowledge Date: December 2023\n\n${system}`, "<|eot_id|>"];
  rest.forEach((m, i) => {
    const last = i === rest.length - 1;
    if (m.role === "user") {
      pieces.push("<|start_header_id|>", "user", "<|end_header_id|>", `\n\n${m.content}`, "<|eot_id|>");
      if (last) pieces.push("<|start_header_id|>", "assistant", "<|end_header_id|>", "\n\n");
    } else if (m.role === "assistant") {
      pieces.push("<|start_header_id|>", "assistant", "<|end_header_id|>", `\n\n${m.content}`);
      if (!last) pieces.push("<|eot_id|>");
    } else throw new Error(`unexpected role ${m.role}`);
  });
  return pieces;
}

export function count(messages) {
  const tok = tokenizer();
  return render(messages).reduce((n, p) => n + (tok.special.has(p) ? 1 : tok.count(p)), 0);
}
