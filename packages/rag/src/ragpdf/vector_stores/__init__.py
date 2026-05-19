# src/ragpdf/vector_stores/__init__.py
from ragpdf.vector_stores.local_vector_store import LocalVectorStore
from ragpdf.vector_stores.s3_vector_store import S3VectorStore

# Optional plugins — imported lazily to avoid hard dependency errors
def __getattr__(name):
    if name == "PineconeStore":
        from ragpdf.vector_stores.pinecone_store import PineconeStore
        return PineconeStore
    if name == "ChromaStore":
        from ragpdf.vector_stores.chroma_store import ChromaStore
        return ChromaStore
    if name == "WeaviateStore":
        from ragpdf.vector_stores.weaviate_store import WeaviateStore
        return WeaviateStore
    raise AttributeError(f"module 'ragpdf.vector_stores' has no attribute {name!r}")

__all__ = ["LocalVectorStore", "S3VectorStore", "PineconeStore", "ChromaStore", "WeaviateStore"]
