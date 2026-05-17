# src/ragpdf/embeddings/sentence_transformer.py
import logging
from ragpdf.embeddings.base import EmbeddingBackend

logger = logging.getLogger(__name__)


class SentenceTransformerBackend(EmbeddingBackend):
    """
    Sentence Transformers embedding backend (default).
    Runs entirely locally — no external API calls.

    Install: pip install ragpdf-sdk[transformers]

    Usage:
        backend = SentenceTransformerBackend(model="all-MiniLM-L6-v2")
        # Other good models:
        # "all-mpnet-base-v2"         — higher quality, slower
        # "paraphrase-MiniLM-L6-v2"  — good for short phrases
        # "multi-qa-MiniLM-L6-cos-v1" — optimised for QA tasks
    """

    _instance = None
    _model = None

    def __new__(cls, model: str = "all-MiniLM-L6-v2"):
        # Singleton — model is loaded once per process
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, model: str = "all-MiniLM-L6-v2"):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError:
                raise ImportError(
                    "SentenceTransformerBackend requires sentence-transformers. "
                    "Install with: pip install ragpdf-sdk[transformers]"
                )
            self._model_name = model
            self._model = SentenceTransformer(model)
            logger.info(f"Loaded SentenceTransformer: {model}")

    def embed(self, text: str) -> list:
        text = text.replace("\n", " ").strip()
        return self._model.encode(text, convert_to_numpy=True).tolist()

    def embed_batch(self, texts: list) -> list:
        texts = [t.replace("\n", " ").strip() for t in texts]
        return self._model.encode(texts, convert_to_numpy=True, show_progress_bar=False).tolist()
