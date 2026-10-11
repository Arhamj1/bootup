"""Small text helpers shared by indexing, retrieval and evaluation."""
import re

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "is",
    "it", "of", "on", "or", "that", "the", "this", "to", "was", "were", "with",
    "what", "which", "how", "why", "does", "do", "can",
}
_TOKEN = re.compile(r"[a-z0-9_]+")


def tokenize(text: str) -> list[str]:
    """Lower-case word tokens for BM25.

    Identifiers such as ``pthread_mutex_lock`` are kept whole *and* split into
    their parts, so a query for "mutex lock" can still find them.
    """
    text = text.lower().replace("\u2019", "'").replace("'s", "")
    out: list[str] = []
    for tok in _TOKEN.findall(text):
        if tok in STOPWORDS or (len(tok) == 1 and tok.isalpha()):
            continue
        out.append(tok)
        if "_" in tok:
            out.extend(p for p in tok.split("_") if p and p not in STOPWORDS)
    return out


def normalise(text: str) -> str:
    """Lower-case and collapse whitespace, for substring matching."""
    return " ".join(text.lower().replace("\u2019", "'").split())
