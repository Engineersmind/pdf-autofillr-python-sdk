# ragpdf/embeddings/noop_embeddings.py
from ragpdf.embeddings.base import EmbeddingBackend


class NoOpEmbeddingBackend(EmbeddingBackend):
    """
    Embedding backend that returns zero vectors.
    Useful for unit testing pipeline logic without a real model.
    Do NOT use in production — cosine similarity will be undefined.
    """

    def __init__(self, dim: int = 384):
        self._dim = dim

    def embed(self, text: str) -> list[float]:
        return [0.0] * self._dim

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * self._dim for _ in texts]

    @property
    def dimension(self) -> int:
        return self._dim
