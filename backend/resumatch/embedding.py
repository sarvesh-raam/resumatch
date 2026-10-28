from __future__ import annotations

import os
from functools import lru_cache

import numpy as np


class Embedder:
    name = "base"
    # Cosine similarity cut-offs. Below `weak` a line is treated as unrelated,
    # at `strong` or above it counts as full evidence. Linear in between.
    weak = 0.3
    strong = 0.6

    def encode(self, texts: list[str]) -> np.ndarray:
        raise NotImplementedError


class MiniLMEmbedder(Embedder):
    name = "all-MiniLM-L6-v2"
    # From eval/: unrelated resume lines peak around 0.18, lines a human would
    # call relevant sit around 0.35-0.47.
    weak = 0.2
    strong = 0.45

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        # ONNX export of the same model through fastembed. Embeddings match
        # sentence-transformers to ~1e-7, but it needs no torch, so the whole
        # app fits in a 512 MB free-tier instance.
        from fastembed import TextEmbedding

        self.model = TextEmbedding(model_name)

    def encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, 384), dtype=np.float32)
        vecs = np.array(list(self.model.embed(texts, batch_size=64)), dtype=np.float32)
        return vecs / np.linalg.norm(vecs, axis=1, keepdims=True)


class HashingEmbedder(Embedder):
    """Bag of words + bigrams. No model download, used in tests and CI.

    Much worse than MiniLM at paraphrases ("built REST services" vs "API
    development"), which is the whole point of the eval comparison.
    """

    name = "hashing"
    weak = 0.05
    strong = 0.3

    def __init__(self):
        from sklearn.feature_extraction.text import HashingVectorizer

        self.vec = HashingVectorizer(
            n_features=2**14, ngram_range=(1, 2), stop_words="english", alternate_sign=False, norm="l2"
        )

    def encode(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, 2**14), dtype=np.float32)
        return self.vec.transform(texts).toarray().astype(np.float32)


@lru_cache(maxsize=2)
def get_embedder(kind: str | None = None) -> Embedder:
    kind = kind or os.getenv("RESUMATCH_EMBEDDER", "minilm")
    if kind == "hashing":
        return HashingEmbedder()
    if kind == "minilm":
        return MiniLMEmbedder()
    raise ValueError(f"unknown embedder {kind!r} (expected 'minilm' or 'hashing')")
