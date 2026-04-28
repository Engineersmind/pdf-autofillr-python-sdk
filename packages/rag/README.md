<div align="center">

# ragpdf-sdk

**Self-learning RAG field prediction for PDF form filling.**

A fully open-source Python SDK that predicts PDF form field mappings using sentence-transformer embeddings and a dual-model ensemble (RAG + LLM). The vector database learns from every prediction — getting smarter with every document processed.

[![PyPI version](https://badge.fury.io/py/ragpdf-sdk.svg)](https://badge.fury.io/py/ragpdf-sdk)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://github.com/yourorg/ragpdf-sdk/actions/workflows/test.yml/badge.svg)](https://github.com/yourorg/ragpdf-sdk/actions)

</div>

---

## What It Does

When filling a PDF form, every field box has **context** — surrounding text, section headers, position. This SDK learns to predict which standardized field name (e.g. `investor_full_legal_name`) maps to which field box, by:

1. **Embedding** field context using sentence-transformers (or OpenAI embeddings)
2. **Matching** against a vector database via cosine similarity
3. **Combining** RAG predictions with your LLM predictions into a 5-case ensemble
4. **Learning** from every outcome — boosting correct vectors, decaying wrong ones, regenerating embeddings on errors
5. **Tracking** accuracy, coverage, and confidence at 5 levels (per-PDF, per-category, global)

Everything runs on your own infrastructure. No external services. No data leaves your environment.

---

## Installation

```bash
# Minimal (numpy + scikit-learn only — bring your own embeddings)
pip install ragpdf-sdk

# With sentence-transformers (recommended default)
pip install ragpdf-sdk[transformers]

# With OpenAI embeddings + GPT-4 corrector
pip install ragpdf-sdk[openai]

# With Anthropic Claude corrector
pip install ragpdf-sdk[anthropic]

# With AWS S3 storage
pip install ragpdf-sdk[s3]

# With Pinecone vector store
pip install ragpdf-sdk[pinecone]

# With ChromaDB vector store (local, embedded)
pip install ragpdf-sdk[chroma]

# With Weaviate vector store
pip install ragpdf-sdk[weaviate]

# With FastAPI dev server
pip install ragpdf-sdk[server]

# Everything
pip install ragpdf-sdk[all]
```

---

## Quick Start

```python
from ragpdf import RAGPDFClient, LocalStorage, LocalVectorStore, SentenceTransformerBackend

client = RAGPDFClient(
    storage=LocalStorage("./ragpdf_data"),
    vector_store=LocalVectorStore("./ragpdf_data"),
    embedding_backend=SentenceTransformerBackend("all-MiniLM-L6-v2"),
)

# API 1 — Get RAG predictions for your PDF fields
result = client.get_predictions(
    user_id="user_001",
    session_id="session_abc",
    pdf_id="pdf_xyz",
    fields=[
        {
            "field_id": "f001",
            "field_name": "Investor Name",
            "context": "Full legal name of the investor as it appears on government-issued ID",
            "section_context": "Investor Identity",
            "headers": ["Section 1", "Personal Information"],
        },
    ],
    pdf_hash="md5hashofthepdffile",
    pdf_category={
        "category": "Private Markets",
        "sub_category": "Private Equity",
        "document_type": "LP Subscription Agreement",
    },
)
print(result["summary"])
# {'total_fields': 1, 'predicted_fields': 0, 'unpredicted_fields': 1, 'avg_confidence': 0.0}
# (empty on first run — vector DB learns from each submission)
```

Or use environment variables:

```bash
cp .env.example .env
# Fill in your settings
```

```python
client = RAGPDFClient.from_env()
```

---

## The 6 APIs

### API 1 — `get_predictions()`

Generate RAG predictions for a set of PDF form fields. Saves results to storage.

```python
result = client.get_predictions(
    user_id="user_001",
    session_id="session_abc",
    pdf_id="pdf_xyz",
    fields=[
        {
            "field_id": "f001",           # required: unique ID for this field
            "field_name": "Name Box",     # optional but improves accuracy
            "context": "...",             # surrounding text in the PDF
            "section_context": "...",     # section/heading this field belongs to
            "headers": ["..."],           # list of headers above this field
        }
    ],
    pdf_hash="abc123",                    # MD5/SHA of the PDF (used for dedup + frequency)
    pdf_category={
        "category":      "Private Markets",
        "sub_category":  "Private Equity",
        "document_type": "LP Subscription Agreement",
    },
)
# Returns: submission_id, frequency, is_duplicate, summary
# RAG predictions are saved to: predictions/{user_id}/{session_id}/{pdf_id}/predictions/rag_predictions.json
```

### API 2 — `save_filled_pdf()`

After your backend fills the PDF (using its own LLM predictions), call this to run the full processing pipeline: case classification → metrics → vector DB update → time series.

```python
result = client.save_filled_pdf(
    user_id="user_001",
    session_id="session_abc",
    pdf_id="pdf_xyz",
    llm_predictions={
        "predictions": {
            "f001": {
                "predicted_field_name": "investor_full_legal_name",
                "confidence": 0.92,
            }
        }
    },
    final_predictions={
        "final_predictions": {
            "f001": {
                "selected_field_name": "investor_full_legal_name",
                "selected_from": "llm",       # "rag" | "llm"
                "rag_confidence": 0.0,
                "llm_confidence": 0.92,
            }
        }
    },
)
# Runs: CaseClassifier → MetricsService → VectorDB update → TimeSeriesService
```

### API 4 — `submit_feedback()`

When a user reports a wrong field name after reviewing the filled PDF:

```python
result = client.submit_feedback(
    user_id="user_001",
    session_id="session_abc",
    pdf_id="pdf_xyz",
    errors=[
        {
            "error_type":  "wrong_field_name",
            "field_name":  "investor_name",        # what was predicted
            "field_type":  "text",
            "value":       "John Smith",
            "feedback":    "Should be full_legal_name",
            "page_number": 1,
            "corners":     [[10, 20], [200, 20], [200, 40], [10, 40]],
        }
    ],
)
# Runs: LLM corrector → negative confidence update → embedding regen → metric recalc
```

### API 5 — `get_metrics()`

```python
# Per-PDF metrics
client.get_metrics("pdf", user_id="u1", session_id="s1", pdf_id="p1")

# Category time series
client.get_metrics("category", category="Private Markets")

# Subcategory time series
client.get_metrics("subcategory", category="Private Markets", subcategory="Private Equity")

# Document type time series
client.get_metrics("doctype", category="Private Markets", subcategory="Private Equity", doctype="LP Subscription Agreement")

# Global metrics — full LLM vs RAG comparison + ensemble stats
client.get_metrics("global")

# Compare multiple PDFs
client.get_metrics("compare", pdfs=[
    {"user_id": "u1", "session_id": "s1", "pdf_id": "p1"},
    {"user_id": "u2", "session_id": "s2", "pdf_id": "p2"},
])

# All submissions for a specific PDF hash
client.get_metrics("pdf_hash", pdf_hash="abc123")
```

### API 6 — `get_system_info()`

```python
info = client.get_system_info()
# Returns: total PDFs, users, sessions, categories, vectors, breakdown by source
```

### API 7 — `get_error_analytics()`

```python
analytics = client.get_error_analytics(
    date_from="2026-01-01T00:00:00Z",
    date_to="2026-03-31T23:59:59Z",
    category="Private Markets",          # optional filter
    subcategory="Private Equity",        # optional filter
    doctype="LP Subscription Agreement", # optional filter
)
# Returns: total_errors + breakdown by category, subcategory, doctype, date, error_type, case_type
```

---

## Plugin System

Every component is pluggable. Mix and match to fit your stack.

### Embedding Backends

| Backend | Install | Best For |
|---------|---------|----------|
| `SentenceTransformerBackend` (default) | `[transformers]` | Local, no API calls, great accuracy |
| `OpenAIEmbeddingBackend` | `[openai]` | Highest quality, uses API credits |
| Custom (`EmbeddingBackend`) | — | Any model — Ollama, HuggingFace, Cohere |

```python
# Sentence Transformers (runs locally, no API key)
from ragpdf import SentenceTransformerBackend
backend = SentenceTransformerBackend(model="all-MiniLM-L6-v2")
# Other models: "all-mpnet-base-v2", "paraphrase-MiniLM-L6-v2"

# OpenAI
from ragpdf import OpenAIEmbeddingBackend
backend = OpenAIEmbeddingBackend(api_key="sk-...", model="text-embedding-3-small")

# Custom — implement 2 methods
from ragpdf.embeddings.base import EmbeddingBackend
class MyEmbedder(EmbeddingBackend):
    def embed(self, text: str) -> list[float]:
        return my_model.encode(text).tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return my_model.encode(texts).tolist()
```

### Vector Store Backends

| Backend | Install | Best For |
|---------|---------|----------|
| `LocalVectorStore` (default) | — | Dev/testing, single server |
| `S3VectorStore` | `[s3]` | Production, no extra deps |
| `PineconeStore` | `[pinecone]` | Large scale, managed |
| `ChromaStore` | `[chroma]` | Local production, embedded |
| `WeaviateStore` | `[weaviate]` | Self-hosted, full-featured |
| Custom (`VectorStoreBackend`) | — | pgvector, Qdrant, Milvus, Redis |

```python
from ragpdf import LocalVectorStore, S3VectorStore
from ragpdf.vector_stores import PineconeStore, ChromaStore, WeaviateStore

# Flat JSON on disk (dev)
store = LocalVectorStore(path="./ragpdf_data")

# Flat JSON in your S3 bucket (production)
store = S3VectorStore(bucket="my-bucket", region="us-east-1")

# Pinecone
store = PineconeStore(api_key="...", index_name="ragpdf-vectors", namespace="prod")

# ChromaDB (local, embedded, no external service)
store = ChromaStore(path="./chroma_data", collection="ragpdf_vectors")

# Weaviate
store = WeaviateStore(url="http://localhost:8080", class_name="RagpdfVector")

# Custom — implement 5 methods
from ragpdf.vector_stores.base import VectorStoreBackend
class PgVectorStore(VectorStoreBackend):
    def find_similar(self, embedding, threshold, top_k): ...
    def add_vector(self, field_name, context, section_context, headers, embedding, **meta): ...
    def update_confidence(self, vector_id, is_positive, error_info=None): ...
    def save(self): ...
    def count(self) -> int: ...
```

### LLM Corrector Backends

| Backend | Install | Best For |
|---------|---------|----------|
| `NoOpCorrectorBackend` (default) | — | No LLM call, offline |
| `OpenAICorrectorBackend` | `[openai]` | GPT-4, highest quality corrections |
| `AnthropicCorrectorBackend` | `[anthropic]` | Claude, fast + accurate |
| Custom (`FieldCorrectorBackend`) | — | Llama, Mistral, Ollama, any LLM |

```python
from ragpdf import OpenAICorrectorBackend, AnthropicCorrectorBackend, NoOpCorrectorBackend

# GPT-4
corrector = OpenAICorrectorBackend(api_key="sk-...", model="gpt-4-turbo-preview")

# Claude
corrector = AnthropicCorrectorBackend(api_key="sk-ant-...", model="claude-sonnet-4-20250514")

# No LLM (just cleans the field name to snake_case)
corrector = NoOpCorrectorBackend()

# Custom — implement 1 method
from ragpdf.correctors.base import FieldCorrectorBackend
class OllamaCorrector(FieldCorrectorBackend):
    def generate_corrected_field_name(self, error_data: dict) -> dict:
        # Call Ollama / any local LLM
        return {"corrected_field_name": "name", "confidence": 0.9, "reasoning": "..."}
```

### Storage Backends

```python
from ragpdf import LocalStorage, S3Storage
from ragpdf.storage.base import StorageBackend

# Local filesystem
storage = LocalStorage("./ragpdf_data")

# AWS S3 (your own bucket)
storage = S3Storage(bucket="my-bucket", region="us-east-1", prefix="ragpdf/")

# Custom — implement 5 methods (PostgreSQL, MongoDB, GCS, Azure Blob, etc.)
class PostgresStorage(StorageBackend):
    def save_json(self, key, data): ...
    def load_json(self, key): ...
    def append_to_jsonl(self, key, data): ...
    def load_jsonl(self, key): ...
    def copy_file(self, source, dest): ...
```

---

## How the Learning Loop Works

```
PDF fields submitted
       ↓
EmbeddingBackend.embed(field_context)
       ↓
VectorStoreBackend.find_similar(embedding)
       → RAG prediction + confidence score
       ↓
Your backend runs LLM prediction independently
       ↓
save_filled_pdf(rag_preds, llm_preds, final_preds)
       ↓
CaseClassifier assigns each field to one of 5 cases:
  CASE_A → Both agreed     → boost RAG vector confidence
  CASE_B → Conflict        → boost winner, create new vector if LLM selected
  CASE_C → LLM only        → create new vector from LLM prediction
  CASE_D → RAG only        → boost RAG vector confidence
  CASE_E → Neither         → do nothing
       ↓
MetricsService calculates accuracy/coverage/confidence
TimeSeriesService appends to 5 time series levels
       ↓
(optionally) submit_feedback(errors)
       ↓
FieldCorrectorBackend.generate_corrected_field_name(error)
       ↓
VectorStoreBackend.update_confidence(vector_id, is_positive=False)
  → confidence decayed
  → embedding regenerated: "original context corrected:right_field_name"
  → stability_score updated
MetricsService.recalculate_accuracy_after_errors()
TimeSeriesService updates all 5 levels again
```

Over time, CASE_A (both agreed) increases → LLM needed less → faster + cheaper predictions.

---

## Configuration Reference

Copy `.env.example` to `.env`:

```bash
# Storage
RAGPDF_STORAGE=local              # local | s3
RAGPDF_DATA_PATH=./ragpdf_data

# S3 (if RAGPDF_STORAGE=s3)
RAGPDF_S3_BUCKET=my-bucket
RAGPDF_S3_REGION=us-east-1

# Embedding
RAGPDF_EMBEDDING_BACKEND=sentence_transformer   # sentence_transformer | openai
RAGPDF_ST_MODEL=all-MiniLM-L6-v2
OPENAI_API_KEY=sk-...

# Vector store
RAGPDF_VECTOR_STORE=local         # local | s3 | pinecone | chroma | weaviate
PINECONE_API_KEY=...
RAGPDF_CHROMA_PATH=./chroma_data

# LLM Corrector
RAGPDF_CORRECTOR_BACKEND=openai   # openai | anthropic | noop
ANTHROPIC_API_KEY=sk-ant-...

# Prediction tuning
RAGPDF_PREDICTION_THRESHOLD=0.75  # min cosine similarity to count as a match
RAGPDF_TOP_K=5                    # how many candidates to return
RAGPDF_CONFIDENCE_DECAY_RATE=0.95 # multiply confidence on error
RAGPDF_CONFIDENCE_GROWTH_RATE=1.05 # multiply confidence on correct
```

---

## S3 Storage Layout

All paths below are relative to your bucket (or `RAGPDF_DATA_PATH` for local):

```
vectors/
└── vector_database.json                              # the vector DB

pdf_hash_mapping/
└── mapping.json                                      # dedup + frequency tracking

predictions/{user_id}/{session_id}/{pdf_id}/
├── metadata/
│   ├── submission_info.json                          # submission_id, frequency
│   └── pdf_info.json                                 # pdf_hash, pdf_category
├── predictions/
│   ├── input.json                                    # raw fields (for CASE_B/C vector creation)
│   ├── rag_predictions.json                          # API 1 output
│   ├── llm_predictions.json                          # provided by your backend
│   └── final_predictions.json                        # ensemble decisions
├── analysis/
│   ├── case_classification.json                      # A/B/C/D/E per field
│   ├── metrics_snapshot.json                         # initial metrics
│   └── vector_update_summary.json                    # what changed in vector DB
└── errors/
    ├── user_feedback_raw.jsonl                        # raw feedback events
    ├── error_analysis.json                            # processed error records
    ├── metrics_snapshot_updated.json                  # recalculated after errors
    └── error_log_{timestamp}.json                     # timestamped error log

metrics/time_series/
├── global/time_series.json
├── category/{category}/time_series.json
├── subcategory/{category}/{sub}/time_series.json
├── doctype/{category}/{sub}/{doc}/time_series.json
└── pdf_hash/{hash}/time_series.json
```

---

## Dev Server

```bash
pip install ragpdf-sdk[server]
uvicorn server.local_server:app --reload --port 8000
```

Endpoints:
- `POST /predict` — API 1
- `POST /save-filled-pdf` — API 2
- `POST /feedback` — API 4
- `POST /metrics` — API 5
- `GET  /system-info` — API 6
- `POST /error-analytics` — API 7
- `GET  /health` — vector count

All endpoints require `X-API-Key: dev-key` header (set `RAGPDF_API_KEY` to change).

---

## Testing

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Unit tests (no API keys, no network)
pytest tests/unit/ -v

# With coverage
pytest tests/unit/ --cov=ragpdf --cov-report=html

# Integration tests (no API keys — uses DummyEmbeddingBackend)
pytest tests/integration/ -v -m integration

# All tests
pytest
```

---

## Publishing

```bash
# Increment version in pyproject.toml
# Update CHANGELOG.md

git commit -am "Release v0.2.3"
git tag v0.2.3
git push origin main --tags
# GitHub Actions publishes to PyPI automatically
```

Versioning policy:
- `PATCH` (0.1.x) — bug fixes, no API changes
- `MINOR` (0.x.0) — new backends/features, backwards compatible
- `MAJOR` (x.0.0) — breaking changes to `RAGPDFClient` or plugin interfaces

---

## License

MIT — see [LICENSE](LICENSE)
