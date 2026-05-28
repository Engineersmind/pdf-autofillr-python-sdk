"""
Example 4 — Pinecone vector store plugin.

Install:
    pip install ragpdf-sdk[transformers,pinecone]
"""

import os

from ragpdf import LocalStorage, RAGPDFClient, SentenceTransformerBackend
from ragpdf.vector_stores import PineconeStore

client = RAGPDFClient(
    storage=LocalStorage("./data/rag"),
    vector_store=PineconeStore(
        api_key=os.environ["PINECONE_API_KEY"],
        index_name="ragpdf-vectors",
        namespace="production",
        dimension=384,  # match your sentence-transformer model output dim
    ),
    embedding_backend=SentenceTransformerBackend("all-MiniLM-L6-v2"),
)
print("Client ready with Pinecone vector store")
