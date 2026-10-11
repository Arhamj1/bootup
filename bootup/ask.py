"""Ask one question from the command line.

    python -m bootup.ask "What are the four conditions for deadlock?"
    python -m bootup.ask "..." --mode bm25 --no-llm      # retrieval only
"""
from __future__ import annotations

import argparse

from . import config
from .embed import get_embedder
from .generate import MissingKeyError, extract_cited, generate_answer
from .index import Index
from .retrieve import MODES, Retriever


def show_hits(hits) -> None:
    for i, h in enumerate(hits, 1):
        c = h.chunk
        print(f"[{i}] {c.source_file} | {c.locator} | {c.source_type} | ranks={h.ranks}")
        print("    " + " ".join(c.text.split())[:220] + ("..." if len(c.text) > 220 else ""))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("question")
    ap.add_argument("--mode", choices=MODES, default="hybrid")
    ap.add_argument("--k", type=int, default=config.TOP_K_FINAL)
    ap.add_argument("--no-llm", action="store_true", help="show retrieved passages only")
    ap.add_argument("--embedder", default=config.EMBED_MODEL)
    args = ap.parse_args(argv)

    embedder = get_embedder(args.embedder)
    retriever = Retriever(Index(config.INDEX_DIR, embedder), embedder)
    hits = retriever.search(args.question, mode=args.mode, k_final=args.k)
    print(f"Retrieved {len(hits)} passages ({args.mode}):\n")
    show_hits(hits)
    if args.no_llm:
        return 0
    try:
        answer = generate_answer(args.question, hits)
    except MissingKeyError as exc:
        print(f"\n{exc}")
        return 2
    print("\nAnswer:\n" + answer)
    cited = extract_cited(answer)
    if cited:
        print("\nCited passages:", ", ".join(f"[{n}]" for n in cited))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
