"""
Example 2 — S3 storage + S3 vector store.

Install:
    pip install ragpdf-sdk[transformers,s3]

Set env vars:
    RAGPDF_S3_BUCKET=my-ragpdf-bucket
    RAGPDF_S3_REGION=us-east-1
"""
import os
from ragpdf import RAGPDFClient, S3Storage, S3VectorStore, SentenceTransformerBackend

client = RAGPDFClient(
    storage=S3Storage(
        bucket=os.environ["RAGPDF_S3_BUCKET"],
        region=os.environ.get("RAGPDF_S3_REGION", "us-east-1"),
    ),
    vector_store=S3VectorStore(
        bucket=os.environ["RAGPDF_S3_BUCKET"],
        region=os.environ.get("RAGPDF_S3_REGION", "us-east-1"),
    ),
    embedding_backend=SentenceTransformerBackend("all-MiniLM-L6-v2"),
)
print("Client ready with S3 backends")
