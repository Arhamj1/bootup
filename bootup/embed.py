"""Embedding models.

The real model is all-MiniLM-L6-v2 through sentence-transformers.

HashingEmbedder is an OFFLINE STAND-IN used only to test the code where the
real model cannot be downloaded. It is a bag-of-words hash, so it behaves
much like keyword search. Results produced with it must never be reported.
"""
from __future__ import annotations

import hashlib
import os

import numpy as np

from .textutil import tokenize

STANDIN_NAME = "hashing-standin-384"


class SentenceTransformerEmbedder:
    is_standin = False

    def __init__(self, model_name: str):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is not installed. Run: pip install -r requirements.txt"
            ) from exc
        self.name = model_name
        self.model = SentenceTransformer(model_name)
        get_dim = (getattr(self.model, "get_embedding_dimension", None)
                   or self.model.get_sentence_embedding_dimension)
        self.dim = get_dim()

    def encode(self, texts: list[str]) -> np.ndarray:
        vecs = self.model.encode(texts, normalize_embeddings=True,
                                 show_progress_bar=False, batch_size=32)
        return np.asarray(vecs, dtype=np.float32)


class OnnxEmbedder:
    """The same all-MiniLM-L6-v2 model run through ONNX Runtime instead of PyTorch.

    Uses a fraction of the memory (for small free servers). Reproduces sentence-transformers'
    output: mean pooling over the attention mask, then L2 normalisation, inputs cut at 256 tokens.
    It reports the same name as the PyTorch embedder because the vectors are the same, so an
    index built with either one works with both (checked by tests/test_onnx_embedder.py).
    """
    is_standin = False
    MAX_TOKENS = 256

    def __init__(self, model_name: str):
        import onnxruntime as ort
        from huggingface_hub import hf_hub_download
        from tokenizers import Tokenizer

        self.name = model_name
        self.tok = Tokenizer.from_file(hf_hub_download(model_name, "tokenizer.json"))
        self.tok.enable_truncation(max_length=self.MAX_TOKENS)
        self.tok.enable_padding()
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1  # small servers: avoid oversubscribing one shared core
        self.session = ort.InferenceSession(hf_hub_download(model_name, "onnx/model.onnx"), opts,
                                            providers=["CPUExecutionProvider"])
        self.inputs = {i.name for i in self.session.get_inputs()}
        self.dim = self.session.get_outputs()[0].shape[-1]

    def encode(self, texts: list[str]) -> np.ndarray:
        out = []
        for s in range(0, len(texts), 32):
            enc = self.tok.encode_batch(texts[s:s + 32])
            ids = np.array([e.ids for e in enc], dtype=np.int64)
            mask = np.array([e.attention_mask for e in enc], dtype=np.int64)
            feed = {"input_ids": ids, "attention_mask": mask}
            if "token_type_ids" in self.inputs:
                feed["token_type_ids"] = np.zeros_like(ids)
            hidden = self.session.run(None, feed)[0]
            m = mask[..., None].astype(np.float32)
            pooled = (hidden * m).sum(1) / np.clip(m.sum(1), 1e-9, None)
            out.append(pooled / np.clip(np.linalg.norm(pooled, axis=1, keepdims=True), 1e-12, None))
        return np.concatenate(out).astype(np.float32) if out else np.zeros((0, self.dim), np.float32)


class HashingEmbedder:
    is_standin = True
    name = STANDIN_NAME

    def __init__(self, dim: int = 384):
        self.dim = dim

    def encode(self, texts: list[str]) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for row, text in enumerate(texts):
            toks = tokenize(text)
            feats = toks + [f"{a}_{b}" for a, b in zip(toks, toks[1:])]
            for f in feats:
                h = int(hashlib.md5(f.encode()).hexdigest(), 16)
                out[row, h % self.dim] += 1.0 if (h >> 64) % 2 == 0 else -1.0
        norms = np.linalg.norm(out, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return out / norms


def get_embedder(name: str):
    """Return an embedder. 'standin' gives the offline test stand-in.

    There is deliberately no silent fallback: if the real model cannot load,
    this raises instead of quietly switching to the stand-in.
    """
    if name in ("standin", STANDIN_NAME):
        return HashingEmbedder()
    if os.getenv("BOOTUP_EMBED_BACKEND") == "onnx":
        return OnnxEmbedder(name)
    return SentenceTransformerEmbedder(name)
