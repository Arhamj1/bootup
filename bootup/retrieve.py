"""Dense, BM25 and hybrid (Reciprocal Rank Fusion) retrieval."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np

from . import config
from .ingest import Chunk
from .textutil import tokenize

MODES = ("hybrid", "dense", "bm25")


@dataclass
class Hit:
    chunk: Chunk
    score: float
    ranks: dict = field(default_factory=dict)  # e.g. {"dense": 2, "bm25": 5}


def rrf_fuse(ranked_lists: list[list[str]], k: int = config.RRF_K) -> list[tuple[str, float]]:
    """score(d) = sum over lists of 1 / (k + rank), rank starting at 1."""
    scores: dict[str, float] = defaultdict(float)
    for lst in ranked_lists:
        for rank, cid in enumerate(lst, start=1):
            scores[cid] += 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))


class Retriever:
    def __init__(self, index, embedder):
        self.index = index
        self.embedder = embedder

    def dense_ids(self, query: str, k: int) -> list[str]:
        n = min(k, self.index.col.count())
        if n == 0:
            return []
        vec = self.embedder.encode([query])[0]
        res = self.index.col.query(query_embeddings=[vec.tolist()], n_results=n)
        return list(res["ids"][0])

    def bm25_ids(self, query: str, k: int) -> list[str]:
        toks = tokenize(query)
        if not toks:
            return []
        scores = self.index.bm25.get_scores(toks)
        order = np.argsort(-scores, kind="stable")[:k]
        return [self.index.chunk_list[i].id for i in order if scores[i] > 0]

    def search(self, query: str, mode: str = "hybrid", k_each: int = config.TOP_K_EACH,
               k_final: int = config.TOP_K_FINAL) -> list[Hit]:
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        dense = self.dense_ids(query, k_each) if mode in ("hybrid", "dense") else []
        bm25 = self.bm25_ids(query, k_each) if mode in ("hybrid", "bm25") else []
        d_rank = {cid: r for r, cid in enumerate(dense, 1)}
        b_rank = {cid: r for r, cid in enumerate(bm25, 1)}

        if mode == "hybrid":
            fused = rrf_fuse([dense, bm25])[:k_final]
        else:
            fused = [(cid, 1.0 / r) for r, cid in enumerate((dense or bm25)[:k_final], 1)]

        hits = []
        for cid, score in fused:
            ranks = {}
            if cid in d_rank:
                ranks["dense"] = d_rank[cid]
            if cid in b_rank:
                ranks["bm25"] = b_rank[cid]
            hits.append(Hit(self.index.chunks[cid], score, ranks))
        return hits
