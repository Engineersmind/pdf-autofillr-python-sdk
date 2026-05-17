"""
LiteLLM embedding backend.

Supports any provider LiteLLM supports:
  openai/text-embedding-3-small
  azure/my-deployment
  cohere/embed-english-v3.0
  ollama/nomic-embed-text
  bedrock/amazon.titan-embed-text-v1
  vertex_ai/textembedding-gecko

Install: pip install ragpdf-sdk[litellm]

Usage:
    backend = LiteLLMEmbeddingBackend(model="openai/text-embedding-3-small")

Credentials: set the provider's env var (OPENAI_API_KEY, ANTHROPIC_API_KEY,
AZURE_API_KEY, COHERE_API_KEY, etc.) — LiteLLM reads them automatically.
"""
import logging
from ragpdf.embeddings.base import EmbeddingBackend

logger = logging.getLogger(__name__)


class LiteLLMEmbeddingBackend(EmbeddingBackend):
    """
    LiteLLM embedding backend — plug in any provider with one env var.
    """

    def __init__(self, model: str = ""):
        try:
            import litellm
            self._litellm = litellm
        except ImportError:
            raise ImportError(
                "LiteLLMEmbeddingBackend requires litellm. "
                "Install with: pip install ragpdf-sdk[litellm]"
            )
        from ragpdf.config.settings import RAGPDF_LITELLM_EMBEDDING_MODEL
        self._model = model or RAGPDF_LITELLM_EMBEDDING_MODEL
        logger.info(f"LiteLLMEmbeddingBackend initialized: model={self._model}")

    def embed(self, text: str) -> list:
        text = text.replace("\n", " ").strip()
        response = self._litellm.embedding(model=self._model, input=[text])
        return response.data[0]["embedding"]

    def embed_batch(self, texts: list) -> list:
        cleaned = [t.replace("\n", " ").strip() for t in texts]
        response = self._litellm.embedding(model=self._model, input=cleaned)
        return [item["embedding"] for item in response.data]
