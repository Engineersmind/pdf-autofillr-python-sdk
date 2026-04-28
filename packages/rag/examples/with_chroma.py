"""
Example 5 — ChromaDB vector store plugin (local, no external service).
Great for local production deployments.

Install:
    pip install ragpdf-sdk[transformers,chroma]
"""
from ragpdf import RAGPDFClient, LocalStorage, SentenceTransformerBackend
from ragpdf.vector_stores import ChromaStore

client = RAGPDFClient(
    storage=LocalStorage("./data/rag"),
    vector_store=ChromaStore(
        path="./chroma_data",
        collection="ragpdf_vectors",
    ),
    embedding_backend=SentenceTransformerBackend("all-MiniLM-L6-v2"),
)
print("Client ready with ChromaDB vector store")
