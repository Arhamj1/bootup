"""Answer generation through the Groq API (default model: openai/gpt-oss-20b, see config)."""
from __future__ import annotations

import os
import re
from collections.abc import Iterator

from . import config

SYSTEM_PROMPT = (
    "You are BootUp, a study assistant for an Operating Systems course.\n"
    "Answer the student's question using ONLY the numbered context passages provided.\n"
    "- If the passages do not contain the answer, say so plainly instead of guessing.\n"
    "- Cite the passages you used inline as [1], [2], and so on.\n"
    "- Keep the explanation clear and exam-oriented; use short paragraphs or numbered steps."
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
    """Numbers cited in the answer as [n], in order of first appearance."""
    seen: list[int] = []
    for m in re.finditer(r"\[(\d+)\]", answer):
        n = int(m.group(1))
        if n not in seen:
            seen.append(n)
    return seen


def make_client():
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise MissingKeyError(
            "GROQ_API_KEY is not set. Get a free key from the Groq console and set it "
            "as an environment variable (never paste it into code or chat).")
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
    """Grounded answer: the model only sees the retrieved passages."""
    if not hits:
        return NO_CONTEXT
    return _chat(client or make_client(), model, build_messages(question, hits))


def generate_baseline(question: str, client=None, model: str = config.LLM_MODEL) -> str:
    """Same model with no retrieved passages, for side-by-side comparison."""
    messages = [{"role": "system", "content": BASELINE_PROMPT},
                {"role": "user", "content": question}]
    return _chat(client or make_client(), model, messages)
