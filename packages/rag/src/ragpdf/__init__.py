"""
ragpdf-sdk — Self-learning RAG field prediction for PDF form filling.

Quick start:
    from ragpdf import RAGPDFClient
    client = RAGPDFClient.from_env()

Full plugin setup:
    from ragpdf import (
        RAGPDFClient,
        LocalStorage, S3Storage, AzureStorage, GCSStorage,
        LocalVectorStore, S3VectorStore,
        SentenceTransformerBackend, OpenAIEmbeddingBackend, LiteLLMEmbeddingBackend,
        OpenAICorrectorBackend, AnthropicCorrectorBackend, LiteLLMCorrectorBackend, NoOpCorrectorBackend,
    )
"""
from ragpdf.client import RAGPDFClient

# Storage backends
from ragpdf.storage.local_storage   import LocalStorage
from ragpdf.storage.s3_storage      import S3Storage
from ragpdf.storage.azure_storage   import AzureStorage
from ragpdf.storage.gcs_storage     import GCSStorage

# Embedding backends
from ragpdf.embeddings.sentence_transformer  import SentenceTransformerBackend
from ragpdf.embeddings.openai_embeddings     import OpenAIEmbeddingBackend
from ragpdf.embeddings.litellm_embeddings    import LiteLLMEmbeddingBackend
from ragpdf.embeddings.noop_embeddings       import NoOpEmbeddingBackend

# Vector store backends
from ragpdf.vector_stores.local_vector_store import LocalVectorStore
from ragpdf.vector_stores.s3_vector_store    import S3VectorStore

# Corrector backends
from ragpdf.correctors.openai_corrector    import OpenAICorrectorBackend
from ragpdf.correctors.anthropic_corrector import AnthropicCorrectorBackend
from ragpdf.correctors.litellm_corrector   import LiteLLMCorrectorBackend
from ragpdf.correctors.noop_corrector      import NoOpCorrectorBackend

__version__ = "0.2.3"
__all__ = [
    "RAGPDFClient",
    "LocalStorage", "S3Storage", "AzureStorage", "GCSStorage",
    "SentenceTransformerBackend", "OpenAIEmbeddingBackend", "LiteLLMEmbeddingBackend", "NoOpEmbeddingBackend",
    "LocalVectorStore", "S3VectorStore",
    "OpenAICorrectorBackend", "AnthropicCorrectorBackend", "LiteLLMCorrectorBackend", "NoOpCorrectorBackend",
]
