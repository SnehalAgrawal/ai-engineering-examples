"""
Article #18's value check, and the sentence splitter that experiment 4's sentence gate uses.

The value check finds the values a text states (email addresses; codes such as SSO-101; snake_case names; any
word containing digits, taken whole) and returns those that don't appear, as a whole word after
normalization, in any of the reference texts. The functions normalize, contains, and values are copied from
production-ai-patterns/01-reliable-llm-pipeline/python/steps.py unchanged. Here the references are all the
retrieved excerpts plus the customer's email (data/settings.json, experiment 4).
"""
import re


def normalize(text: str) -> str:
    """Lowercase, straight quotes, hyphens for dashes, no commas between digits, single spaces."""
    text = text.lower().replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(r"(?<=\d),(?=\d{3}\b)", "", text)
    return re.sub(r"\s+", " ", text)


def contains(text: str, phrase: str) -> bool:
    """The phrase appears in the text as a whole word or phrase: no letter or digit directly before or after."""
    pattern = r"(?<![a-z0-9])" + re.escape(normalize(phrase).strip()) + r"(?![a-z0-9])"
    return re.search(pattern, normalize(text)) is not None


EMAIL_ADDRESS = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
CODE = re.compile(r"\b[A-Z][A-Z0-9]*-[0-9]+\b")
SNAKE = re.compile(r"\b[a-z0-9]+(?:_[a-z0-9]+)+\b")
NUMBER = re.compile(r"[A-Za-z]*[0-9]+(?:[.,][0-9]+)*[A-Za-z]*")  # a word with digits, whole: "16th", "SHA256", "v2"


def values(reply: str) -> list[str]:
    """The values a text states. Citation markers such as [2] and list numbers at the start of a line are not values."""
    text = re.sub(r"\[[0-9]+(?:\s*,\s*[0-9]+)*\]", " ", reply)
    text = re.sub(r"(?m)^\s*[0-9]+[.)]\s", " ", text)
    found = []
    for pattern in (EMAIL_ADDRESS, CODE, SNAKE):
        found += pattern.findall(text)
        text = pattern.sub(" ", text)
    found += [re.sub(r"(?<=[0-9]),(?=[0-9]{3}\b)", "", n) for n in NUMBER.findall(text)]
    return list(dict.fromkeys(found))


def flagged(text: str, references: list[str]) -> list[str]:
    """The values in the text that appear in none of the references."""
    return [v for v in values(text) if not any(contains(r, v) for r in references)]


LIST_NUMBER = re.compile(r"\s*[0-9]+")


class Sentences:
    """Splits streamed text into sentences as it arrives (data/settings.json, experiment 4, sentence_boundary).

    A sentence ends at '.', '!', or '?' followed by whitespace, or at a newline. A period directly after a
    number at the start of a line (a list number such as '1.') is not a boundary. Joining the sentences gives
    back the text exactly.
    """

    def __init__(self):
        self.pending = ""

    def feed(self, text: str) -> list[str]:
        self.pending += text
        sentences = []
        while True:
            end = self.boundary()
            if end is None:
                return sentences
            sentences.append(self.pending[:end])
            self.pending = self.pending[end:]

    def finish(self) -> list[str]:
        """Whatever is left when the stream ends is the last sentence."""
        rest, self.pending = self.pending, ""
        return [rest] if rest else []

    def boundary(self) -> int | None:
        """The end (exclusive) of the first complete sentence in the pending text, or None if there isn't one yet."""
        text = self.pending
        for i, c in enumerate(text):
            if c == "\n":
                return i + 1
            if c in ".!?":
                if i + 1 == len(text):
                    return None  # the next character decides; wait for more text
                if not text[i + 1].isspace():
                    continue
                line_start = text.rfind("\n", 0, i) + 1
                if c == "." and LIST_NUMBER.fullmatch(text[line_start:i]):
                    continue
                return i + 1
        return None
