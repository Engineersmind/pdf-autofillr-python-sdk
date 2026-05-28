"""
Example 1 — Basic usage.
Local storage, sentence-transformers embeddings, no cloud dependencies.

Install:
    pip install ragpdf-sdk[transformers]
"""

from ragpdf import (
    LocalStorage,
    LocalVectorStore,
    RAGPDFClient,
    SentenceTransformerBackend,
)

client = RAGPDFClient(
    storage=LocalStorage("./data/rag"),
    vector_store=LocalVectorStore("./data/rag"),
    embedding_backend=SentenceTransformerBackend("all-MiniLM-L6-v2"),
)

fields = [
    {
        "field_id": "f001",
        "field_name": "Investor Name",
        "context": "Full legal name of the investor as it appears on government-issued ID",
        "section_context": "Investor Identity",
        "headers": ["Section 1", "Personal Information"],
    },
    {
        "field_id": "f002",
        "field_name": "Tax ID",
        "context": "Social Security Number or Employer Identification Number",
        "section_context": "Tax Information",
        "headers": ["Section 3"],
    },
]

result = client.get_predictions(
    user_id="user_001",
    session_id="session_abc",
    pdf_id="pdf_xyz",
    fields=fields,
    pdf_hash="md5hashofpdffile",
    pdf_category={
        "category": "Private Markets",
        "sub_category": "Private Equity",
        "document_type": "LP Subscription Agreement",
    },
)
print("Predictions:", result)
