"""The light backend used on small servers must give the same results as the default one."""
import numpy as np
import pytest

from bootup.build import run_build
from bootup.embed import HashingEmbedder
from bootup.index import Index, NumpyCollection
from bootup.retrieve import Retriever

QUERIES = ["conditions for deadlock", "banker's algorithm safety", "round robin time quantum",
           "mutex lock", "paging fragmentation", "semaphore wait signal"]


def test_build_saves_vectors_matching_chunks(corpus, tmp_path):
    index_dir = tmp_path / "index"
    run_build(corpus, index_dir, HashingEmbedder())
    vecs = np.load(index_dir / "vectors.npy")
    n = sum(1 for _ in open(index_dir / "chunks.jsonl", encoding="utf-8"))
    assert vecs.shape == (n, 384)


def test_numpy_backend_matches_chroma(corpus, tmp_path, monkeypatch):
    index_dir = tmp_path / "index"
    emb = HashingEmbedder()
    run_build(corpus, index_dir, emb)
    monkeypatch.delenv("BOOTUP_VECTOR_BACKEND", raising=False)
    chroma = Retriever(Index(index_dir, emb), emb)
    monkeypatch.setenv("BOOTUP_VECTOR_BACKEND", "numpy")
    light = Retriever(Index(index_dir, emb), emb)
    assert isinstance(light.index.col, NumpyCollection)
    assert not isinstance(chroma.index.col, NumpyCollection)
    for q in QUERIES:
        assert [h.chunk.id for h in chroma.search(q, k_final=4)] == [h.chunk.id for h in light.search(q, k_final=4)]


def test_numpy_collection_rejects_mismatched_files():
    with pytest.raises(RuntimeError, match="Rebuild"):
        NumpyCollection(["a", "b"], np.zeros((3, 4), dtype=np.float32))


def test_onnx_embedder_matches_sentence_transformers():
    """Needs the real model (downloaded on first use); skipped when it is not available."""
    from bootup.embed import OnnxEmbedder, SentenceTransformerEmbedder
    name = "sentence-transformers/all-MiniLM-L6-v2"
    try:
        a = SentenceTransformerEmbedder(name)
        b = OnnxEmbedder(name)
    except Exception as exc:  # offline or model not cached
        pytest.skip(f"real model not available: {exc}")
    texts = ["What is thrashing?", "Banker's algorithm safety check", "x" * 3000]
    cos = (a.encode(texts) * b.encode(texts)).sum(1)
    assert np.all(cos > 0.9999)
