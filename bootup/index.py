"""Build and load the two indexes: ChromaDB (dense) and BM25 (keywords)."""
from __future__ import annotations

import json
import os
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np

from . import config
from .ingest import Chunk
from .textutil import tokenize

COLLECTION = "bootup"
PRIORITY = {"course": 0, "qa_bank": 1, "open": 2}


def dedupe(chunks: list[Chunk], vecs: np.ndarray, threshold: float):
    """Drop near-duplicate chunks, preferring course material over open resources.

    Returns (kept_indices_in_original_order, [(dropped_id, kept_id), ...]).
    """
    order = sorted(range(len(chunks)), key=lambda i: (PRIORITY.get(chunks[i].source_type, 3), i))
    kept: list[int] = []
    mat = np.empty_like(vecs)
    dropped = []
    for i in order:
        if kept:
            sims = mat[: len(kept)] @ vecs[i]
            j = int(sims.argmax())
            if sims[j] >= threshold:
                dropped.append((chunks[i].id, chunks[kept[j]].id))
                continue
        mat[len(kept)] = vecs[i]
        kept.append(i)
    return sorted(kept), dropped


def build_index(chunks: list[Chunk], embedder, index_dir: Path,
                threshold: float = config.DEDUPE_THRESHOLD) -> dict:
    import chromadb

    if not chunks:
        raise ValueError("No chunks to index. Put files under data/raw/ first.")
    index_dir.mkdir(parents=True, exist_ok=True)
    vecs = embedder.encode([c.text for c in chunks])
    keep, dropped = dedupe(chunks, vecs, threshold)
    chunks = [chunks[i] for i in keep]
    vecs = vecs[keep]

    client = chromadb.PersistentClient(path=str(index_dir / "chroma"))
    try:
        client.delete_collection(COLLECTION)
    except Exception:
        pass
    col = client.create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})
    for s in range(0, len(chunks), 500):
        part = chunks[s:s + 500]
        col.add(
            ids=[c.id for c in part],
            embeddings=vecs[s:s + 500].tolist(),
            documents=[c.text for c in part],
            metadatas=[{"source_file": c.source_file, "source_type": c.source_type,
                        "topic": c.topic, "locator": c.locator,
                        "exam": c.exam, "year": c.year} for c in part],
        )
    with open(index_dir / "chunks.jsonl", "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(asdict(c), ensure_ascii=False) + "\n")
    # Same vectors as a plain array (row i = line i of chunks.jsonl), for the light backend.
    np.save(index_dir / "vectors.npy", vecs.astype(np.float32))
    meta = {
        "embedder": embedder.name,
        "standin": bool(embedder.is_standin),
        "dim": int(vecs.shape[1]),
        "n_chunks": len(chunks),
        "n_duplicates_dropped": len(dropped),
        "built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    (index_dir / "meta.json").write_text(json.dumps(meta, indent=2))
    meta["dropped"] = dropped
    return meta


class NumpyCollection:
    """Exact cosine search over the saved vectors, with the two ChromaDB methods the retriever
    uses. For a few thousand chunks this is fast and needs far less memory than ChromaDB."""

    def __init__(self, ids: list[str], vecs: np.ndarray):
        if len(ids) != len(vecs):
            raise RuntimeError("vectors.npy does not match chunks.jsonl. Rebuild the index.")
        self.ids, self.vecs = ids, vecs

    def count(self) -> int:
        return len(self.ids)

    def query(self, query_embeddings, n_results: int) -> dict:
        sims = self.vecs @ np.asarray(query_embeddings[0], dtype=np.float32)
        top = np.argsort(-sims, kind="stable")[:n_results]
        return {"ids": [[self.ids[i] for i in top]], "distances": [[float(1 - sims[i]) for i in top]]}


def use_numpy_backend(index_dir: Path) -> bool:
    """BOOTUP_VECTOR_BACKEND=numpy (set on small servers) or no ChromaDB installed."""
    if not (index_dir / "vectors.npy").exists():
        return False
    if os.getenv("BOOTUP_VECTOR_BACKEND") == "numpy":
        return True
    try:
        import chromadb  # noqa: F401
    except ImportError:
        return True
    return False


class Index:
    """A loaded index: chunk store, dense vector collection (ChromaDB, or NumpyCollection on
    small servers) and BM25 model."""

    def __init__(self, index_dir: Path, embedder):
        from rank_bm25 import BM25Okapi

        meta_path = index_dir / "meta.json"
        if not meta_path.exists():
            raise FileNotFoundError(
                f"No index found in {index_dir}. Build it first: python -m bootup.build")
        self.meta = json.loads(meta_path.read_text())
        if self.meta["embedder"] != embedder.name:
            raise RuntimeError(
                f"Index was built with '{self.meta['embedder']}' but the query embedder is "
                f"'{embedder.name}'. Rebuild the index or use the same model.")
        with open(index_dir / "chunks.jsonl", encoding="utf-8") as f:
            self.chunk_list = [Chunk(**json.loads(line)) for line in f if line.strip()]
        self.chunks = {c.id: c for c in self.chunk_list}
        if use_numpy_backend(index_dir):
            self.col = NumpyCollection([c.id for c in self.chunk_list], np.load(index_dir / "vectors.npy"))
        else:
            import chromadb
            self.col = chromadb.PersistentClient(path=str(index_dir / "chroma")).get_collection(COLLECTION)
        self.bm25 = BM25Okapi([tokenize(c.text) for c in self.chunk_list])
