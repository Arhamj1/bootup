"""Compare dense-only, BM25-only and hybrid retrieval on a labelled question set.

    python -m bootup.evaluate

Question file (eval/questions.json) is a list of objects:
  {"id": "q01", "type": "concept" | "keyword" | "exam",
   "question": "...",
   "evidence_any": ["phrase that appears in the chunk that answers it", ...],
   "relevant_chunk_ids": ["optional exact chunk ids"]}

A retrieved chunk counts as relevant if its id is listed, or if it contains any
of the evidence phrases (case and whitespace insensitive). Phrases survive
re-chunking, ids do not.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from . import config
from .embed import get_embedder
from .index import Index
from .retrieve import MODES, Retriever
from .textutil import normalise

QUESTION_TYPES = ("concept", "keyword", "exam")
CUTOFF = 10


# ------------------------------------------------------------------- metrics
def first_relevant_rank(ranked_ids: list[str], relevant: set[str]) -> int | None:
    for r, cid in enumerate(ranked_ids, 1):
        if cid in relevant:
            return r
    return None


def hit_at_k(rank: int | None, k: int) -> bool:
    return rank is not None and rank <= k


def reciprocal_rank(rank: int | None, cutoff: int = CUTOFF) -> float:
    return 1.0 / rank if rank is not None and rank <= cutoff else 0.0


# ---------------------------------------------------------------- validation
def load_questions(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Question file not found: {path}")
    qs = json.loads(path.read_text(encoding="utf-8"))
    seen = set()
    for q in qs:
        for key in ("id", "question"):
            if not q.get(key):
                raise ValueError(f"Every question needs '{key}': {q}")
        if q["id"] in seen:
            raise ValueError(f"Duplicate question id: {q['id']}")
        seen.add(q["id"])
        if not q.get("evidence_any") and not q.get("relevant_chunk_ids"):
            raise ValueError(f"{q['id']}: give 'evidence_any' or 'relevant_chunk_ids'")
        if q.get("type") not in QUESTION_TYPES:
            raise ValueError(f"{q['id']}: 'type' must be one of {QUESTION_TYPES}")
    return qs


def relevant_set(q: dict, chunk_texts: dict[str, str]) -> set[str]:
    ids = set(q.get("relevant_chunk_ids", []))
    phrases = [normalise(p) for p in q.get("evidence_any", []) if p.strip()]
    rel = {cid for cid in ids if cid in chunk_texts}
    for cid, text in chunk_texts.items():
        if any(p in text for p in phrases):
            rel.add(cid)
    return rel


def find_leaks(questions, index) -> list[str]:
    """Held-out questions must not appear verbatim in the index."""
    warnings = []
    for q in questions:
        nq = normalise(q["question"])
        for c in index.chunk_list:
            if nq in normalise(c.text):
                warnings.append(f"{q['id']}: question text appears in indexed chunk {c.id} "
                                f"({c.source_file}, {c.locator})")
    return warnings


# ---------------------------------------------------------------------- main
def evaluate(retriever, questions) -> dict:
    index = retriever.index
    texts = {c.id: normalise(c.text) for c in index.chunk_list}
    results = {m: [] for m in MODES}
    unlabelled, used = [], []

    for q in questions:
        rel = relevant_set(q, texts)
        if not rel:
            unlabelled.append(q["id"])
            continue
        used.append(q)
        for mode in MODES:
            hits = retriever.search(q["question"], mode=mode, k_each=config.TOP_K_EACH,
                                    k_final=CUTOFF)
            rank = first_relevant_rank([h.chunk.id for h in hits], rel)
            results[mode].append({"id": q["id"], "type": q["type"], "rank": rank,
                                  "hit@3": hit_at_k(rank, 3), "hit@5": hit_at_k(rank, 5),
                                  "rr": reciprocal_rank(rank)})

    def summarise(rows):
        n = len(rows)
        return {"n": n,
                "hit@3": sum(r["hit@3"] for r in rows), "hit@5": sum(r["hit@5"] for r in rows),
                "mrr@10": round(sum(r["rr"] for r in rows) / n, 3) if n else 0.0}

    summary = {m: summarise(rows) for m, rows in results.items()}
    by_type = {t: {m: summarise([r for r in results[m] if r["type"] == t]) for m in MODES}
               for t in QUESTION_TYPES if any(q["type"] == t for q in used)}
    return {"summary": summary, "by_type": by_type, "per_question": results,
            "n_questions_used": len(used), "unlabelled": unlabelled}


def format_table(res: dict) -> str:
    n = res["n_questions_used"]
    lines = [f"Retrieval comparison on {n} questions (counts out of {n}):", "",
             f"{'method':<8} {'hit@3':>8} {'hit@5':>8} {'MRR@10':>8}"]
    for m in MODES:
        s = res["summary"][m]
        lines.append(f"{m:<8} {str(s['hit@3']) + '/' + str(s['n']):>8} "
                     f"{str(s['hit@5']) + '/' + str(s['n']):>8} {s['mrr@10']:>8.3f}")
    for t, per in res["by_type"].items():
        lines += ["", f"  {t} questions:"]
        for m in MODES:
            s = per[m]
            lines.append(f"    {m:<8} hit@5 {s['hit@5']}/{s['n']}   MRR@10 {s['mrr@10']:.3f}")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--questions", type=Path, default=config.EVAL_FILE)
    ap.add_argument("--index-dir", type=Path, default=config.INDEX_DIR)
    ap.add_argument("--embedder", default=config.EMBED_MODEL)
    ap.add_argument("--allow-standin", action="store_true",
                    help="run with the offline stand-in embedder (code testing only)")
    args = ap.parse_args(argv)

    embedder = get_embedder(args.embedder)
    if embedder.is_standin and not args.allow_standin:
        print("Refusing to evaluate with the offline stand-in embedder: its numbers are not "
              "reportable. Use the real model, or pass --allow-standin for a code test.")
        return 2
    questions = load_questions(args.questions)
    index = Index(args.index_dir, embedder)
    retriever = Retriever(index, embedder)

    if embedder.is_standin:
        print("*** STAND-IN EMBEDDER: results below are NOT reportable. ***\n")
    for w in find_leaks(questions, index):
        print("WARNING (held-out leak):", w)
    res = evaluate(retriever, questions)
    if res["unlabelled"]:
        print("WARNING: no chunk matches the labels for these questions, so they were left "
              "out (fix the evidence phrases): " + ", ".join(res["unlabelled"]) + "\n")
    print(format_table(res))

    res["meta"] = {"embedder": embedder.name, "standin": bool(embedder.is_standin),
                   "reportable": not embedder.is_standin, "index": index.meta,
                   "settings": {"top_k_each": config.TOP_K_EACH, "rrf_k": config.RRF_K,
                                "chunk_tokens": config.CHUNK_TOKENS},
                   "run_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    config.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = config.RESULTS_DIR / f"results_{time.strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(res, indent=2))
    print(f"\nSaved {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
