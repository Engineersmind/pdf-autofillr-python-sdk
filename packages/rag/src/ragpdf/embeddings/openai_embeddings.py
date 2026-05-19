# src/ragpdf/embeddings/openai_embeddings.py
import logging
from ragpdf.embeddings.base import EmbeddingBackend

logger = logging.getLogger(__name__)


class OpenAIEmbeddingBackend(EmbeddingBackend):
    """
    OpenAI Embeddings backend.

    Install: pip install ragpdf-sdk[openai]

    Usage:
        backend = OpenAIEmbeddingBackend(
            api_key="sk-...",
            model="text-embedding-3-small"   # or text-embedding-3-large
        )

    Note: Each embed() call uses OpenAI API credits. Batch via embed_batch()
    to reduce API calls significantly.
    """

    def __init__(self, api_key: str = "", model: str = "text-embedding-3-small"):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "OpenAIEmbeddingBackend requires openai. "
                "Install with: pip install ragpdf-sdk[openai]"
            )
        from ragpdf.config.settings import OPENAI_API_KEY
        self._client = OpenAI(api_key=api_key or OPENAI_API_KEY)
        self._model = model
        logger.info(f"OpenAI embedding backend initialized: {model}")

    def embed(self, text: str) -> list:
        text = text.replace("\n", " ").strip()
        response = self._client.embeddings.create(input=[text], model=self._model)
        return response.data[0].embedding

    def embed_batch(self, texts: list) -> list:
        texts = [t.replace("\n", " ").strip() for t in texts]
        response = self._client.embeddings.create(input=texts, model=self._model)
        return [d.embedding for d in response.data]
