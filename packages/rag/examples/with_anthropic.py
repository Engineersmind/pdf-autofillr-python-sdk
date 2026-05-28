"""
Example 7 — Anthropic Claude corrector backend.

Install:
    pip install ragpdf-sdk[transformers,anthropic]
"""

import os

from ragpdf import (
    AnthropicCorrectorBackend,
    LocalStorage,
    LocalVectorStore,
    RAGPDFClient,
    SentenceTransformerBackend,
)

client = RAGPDFClient(
    storage=LocalStorage("./data/rag"),
    vector_store=LocalVectorStore("./data/rag"),
    embedding_backend=SentenceTransformerBackend("all-MiniLM-L6-v2"),
    corrector=AnthropicCorrectorBackend(
        api_key=os.environ["ANTHROPIC_API_KEY"],
        model="claude-sonnet-4-20250514",
    ),
)
print("Client ready with Anthropic corrector")
