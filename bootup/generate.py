"""Answer generation through the Groq API (default model: openai/gpt-oss-20b, see config)."""
from __future__ import annotations

import os
import re
from collections.abc import Iterator

from . import config

SYSTEM_PROMPT = (
    "You are BootUp, a study assistant for an Operating Systems course.\n"
    "Answer the student's question using the numbered context passages as your main source.\n"
    "- Cite the passages you use inline as [1], [2], and so on. Never cite a passage for something it does not say.\n"
    "- If the passages cover the question only partly, still give a complete answer: fill the gaps with standard "
    "operating-systems knowledge (as taught in Silberschatz, Operating System Concepts) and end each such sentence "
    "with \"(general knowledge)\".\n"
    "- For numerical problems or classifications, work the answer out step by step.\n"
    "- If the question is not about operating systems or computing, say that it is outside the course material.\n"
    "- Keep the explanation clear and exam-oriented; use short paragraphs or numbered steps."
)
# Used before searching: turns everyday wording ("one long job holds everyone up") into the
# textbook's terms ("convoy effect, FCFS"), so both retrievers can find the right section.
EXPAND_PROMPT = (
    "Rewrite the student's question as a short search query for an Operating Systems textbook "
    "(Silberschatz, Operating System Concepts). List the main textbook terms and the names of the concepts, "
    "algorithms or section topics an answer would cover. Reply with one line of keywords only."
)
NO_CONTEXT = "I couldn't find anything relevant to that in the loaded course material."
BASELINE_PROMPT = ("You are a helpful assistant. Answer the student's Operating Systems "
                   "question clearly and concisely.")


class MissingKeyError(RuntimeError):
    pass


def format_context(hits) -> str:
    blocks = []
    for i, h in enumerate(hits, 1):
        c = h.chunk
        blocks.append(f"[{i}] (source: {c.source_file}, {c.locator}, topic: {c.topic})\n{c.text}")
    return "\n\n".join(blocks)


def build_messages(question: str, hits) -> list[dict]:
    user = f"Context passages:\n\n{format_context(hits)}\n\nQuestion: {question}"
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


def extract_cited(answer: str) -> list[int]:
    """Numbers cited in the answer as [n] (or full-width 【n】), in order of first appearance."""
    seen: list[int] = []
    for m in re.finditer(r"\[(\d+)\]|【(\d+)[^】\n]*】", answer):
        n = int(m.group(1) or m.group(2))
        if n not in seen:
            seen.append(n)
    return seen


def make_client():
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise MissingKeyError(
            "GROQ_API_KEY is not set. Get a free key from the Groq console and set it "
            "as an environment variable.")
    from groq import Groq
    return Groq(api_key=key)


class IncompleteAnswerError(RuntimeError):
    """The model stopped (token limit) before writing any answer text."""


OUT_OF_TOKENS = ("The model used its whole token budget on reasoning and wrote no answer. "
                 "Try asking more specifically, or raise MAX_ANSWER_TOKENS in bootup/config.py.")
CUT_OFF_NOTE = "\n\n*(Answer cut off: the model reached its length limit.)*"


def _request(model: str, messages: list[dict], **extra) -> dict:
    args = dict(model=model, messages=messages, temperature=config.TEMPERATURE,
                max_tokens=config.MAX_ANSWER_TOKENS, **extra)
    if model.startswith(config.REASONING_MODEL_PREFIXES):
        args["reasoning_effort"] = config.REASONING_EFFORT
    return args


def _chat(client, model: str, messages: list[dict]) -> str:
    resp = client.chat.completions.create(**_request(model, messages))
    choice = resp.choices[0]
    text = (choice.message.content or "").strip()
    finish = getattr(choice, "finish_reason", None)
    if finish == "length":
        if not text:
            raise IncompleteAnswerError(OUT_OF_TOKENS)
        text += CUT_OFF_NOTE
    return text


def _chat_stream(client, model: str, messages: list[dict]) -> Iterator[str]:
    """Same request as _chat, but yields the answer text piece by piece as it arrives."""
    wrote, finish = False, None
    for part in client.chat.completions.create(**_request(model, messages, stream=True)):
        if not part.choices:
            continue
        finish = getattr(part.choices[0], "finish_reason", None) or finish
        delta = part.choices[0].delta.content
        if delta:
            wrote = True
            yield delta
    if finish == "length":
        if not wrote:
            raise IncompleteAnswerError(OUT_OF_TOKENS)
        yield CUT_OFF_NOTE


def expand_query(question: str, client=None, model: str = config.LLM_MODEL) -> str:
    """Textbook keywords for the question, or "" if expansion is off or the call fails.

    Expansion only helps retrieval, so any failure (no key, rate limit, empty reply) falls back
    to searching with the question alone instead of breaking the answer.
    """
    if not config.QUERY_EXPANSION:
        return ""
    try:
        messages = [{"role": "system", "content": EXPAND_PROMPT}, {"role": "user", "content": question}]
        args = {**_request(model, messages), "max_tokens": config.EXPAND_MAX_TOKENS}
        resp = (client or make_client()).chat.completions.create(**args)
        return " ".join((resp.choices[0].message.content or "").split())[:400]
    except Exception:
        return ""


def search_query(question: str, terms: str) -> str:
    return f"{question}\n{terms}" if terms else question


def stream_answer(question: str, hits, client=None, model: str = config.LLM_MODEL) -> Iterator[str]:
    """Streaming version of generate_answer."""
    if not hits:
        yield NO_CONTEXT
        return
    yield from _chat_stream(client or make_client(), model, build_messages(question, hits))


def stream_baseline(question: str, client=None, model: str = config.LLM_MODEL) -> Iterator[str]:
    """Streaming version of generate_baseline."""
    messages = [{"role": "system", "content": BASELINE_PROMPT},
                {"role": "user", "content": question}]
    yield from _chat_stream(client or make_client(), model, messages)


def generate_answer(question: str, hits, client=None, model: str = config.LLM_MODEL) -> str:
    """Answer from the retrieved passages (non-streaming)."""
    if not hits:
        return NO_CONTEXT
    return _chat(client or make_client(), model, build_messages(question, hits))


def generate_baseline(question: str, client=None, model: str = config.LLM_MODEL) -> str:
    """Same model without the passages, for the side-by-side comparison."""
    messages = [{"role": "system", "content": BASELINE_PROMPT},
                {"role": "user", "content": question}]
    return _chat(client or make_client(), model, messages)
