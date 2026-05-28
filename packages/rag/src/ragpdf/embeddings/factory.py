from ragpdf.embeddings.base import EmbeddingBackend


class EmbeddingFactory:
    @staticmethod
    def create() -> EmbeddingBackend:
        from ragpdf.config.settings import (
            OPENAI_API_KEY,
            RAGPDF_EMBEDDING_BACKEND,
            RAGPDF_LITELLM_EMBEDDING_MODEL,
            RAGPDF_OPENAI_EMBEDDING_MODEL,
            RAGPDF_ST_MODEL,
        )

        if RAGPDF_EMBEDDING_BACKEND == "openai":
            from ragpdf.embeddings.openai_embeddings import OpenAIEmbeddingBackend

            return OpenAIEmbeddingBackend(
                api_key=OPENAI_API_KEY, model=RAGPDF_OPENAI_EMBEDDING_MODEL
            )

        if RAGPDF_EMBEDDING_BACKEND == "litellm":
            from ragpdf.embeddings.litellm_embeddings import LiteLLMEmbeddingBackend

            return LiteLLMEmbeddingBackend(model=RAGPDF_LITELLM_EMBEDDING_MODEL)

        if RAGPDF_EMBEDDING_BACKEND == "noop":
            from ragpdf.embeddings.noop_embeddings import NoOpEmbeddingBackend

            return NoOpEmbeddingBackend()

        from ragpdf.embeddings.sentence_transformer import SentenceTransformerBackend

        return SentenceTransformerBackend(model=RAGPDF_ST_MODEL)
