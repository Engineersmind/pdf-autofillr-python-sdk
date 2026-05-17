# pdf-autofillr-rag — Complete Usage Guide

> Self-learning RAG field prediction SDK for PDF form filling. Predicts field mappings using embeddings + a dual-model ensemble, and gets smarter with every document processed.

---

## Table of Contents

1. [PyPI Install — Quick Start (for Users)](#1-pypi-install--quick-start-for-users)
2. [Python Library Usage — The 6 APIs](#2-python-library-usage--the-6-apis)
3. [Plugin System](#3-plugin-system)
4. [CLI Usage](#4-cli-usage)
5. [API Server](#5-api-server)
6. [API Endpoint Reference & Testing](#6-api-endpoint-reference--testing)
7. [FastAPI — Mount in Existing App](#7-fastapi--mount-in-existing-app)
8. [Cloud Entrypoints](#8-cloud-entrypoints)
9. [From Source — Dev Mode](#9-from-source--dev-mode)
10. [Run Tests](#10-run-tests)
11. [Docker](#11-docker)
12. [Configuration Reference](#12-configuration-reference)

---

## 1. PyPI Install — Quick Start (for Users)

### Install

```bash
# Minimal (numpy + scikit-learn — bring your own embeddings)
pip install pdf-autofillr-rag

# With sentence-transformers (recommended default — local, no API key)
pip install "pdf-autofillr-rag[transformers]"

# With OpenAI embeddings + GPT-4 corrector
pip install "pdf-autofillr-rag[openai]"

# With Anthropic Claude corrector
pip install "pdf-autofillr-rag[anthropic]"

# With LiteLLM (any provider)
pip install "pdf-autofillr-rag[litellm]"

# With AWS S3 storage
pip install "pdf-autofillr-rag[s3]"

# With Pinecone vector store
pip install "pdf-autofillr-rag[pinecone]"

# With ChromaDB vector store (local, embedded, no server)
pip install "pdf-autofillr-rag[chroma]"

# With Weaviate vector store
pip install "pdf-autofillr-rag[weaviate]"

# With FastAPI server
pip install "pdf-autofillr-rag[server]"

# Everything
pip install "pdf-autofillr-rag[all]"
```

### First-time setup (run once after install)

```bash
# 1. Create config and data directories
ragpdf-setup
# → Creates .env, config.ini, data/rag/ with sample vectors

# 2. Edit .env
cp .env.example .env
# Set: RAGPDF_EMBEDDING_BACKEND, RAGPDF_CORRECTOR_BACKEND, and API keys
```

### Verify installation

```bash
# Quick check (no API keys needed)
RAGPDF_EMBEDDING_BACKEND=noop RAGPDF_CORRECTOR_BACKEND=noop ragpdf system-info

# Windows PowerShell
$env:RAGPDF_EMBEDDING_BACKEND="noop"; $env:RAGPDF_CORRECTOR_BACKEND="noop"
ragpdf system-info
```

---

## 2. Python Library Usage — The 6 APIs

### Setup: build the client

```python
from ragpdf import (
    RAGPDFClient,
    LocalStorage,
    LocalVectorStore,
    SentenceTransformerBackend,
    NoOpCorrectorBackend,
)

client = RAGPDFClient(
    storage=LocalStorage("./data/rag"),
    vector_store=LocalVectorStore("./data/rag"),
    embedding_backend=SentenceTransformerBackend("all-MiniLM-L6-v2"),
    corrector=NoOpCorrectorBackend(),  # swap for OpenAI/Anthropic in production
)

# Or load everything from .env:
client = RAGPDFClient.from_env()
```

---

### API 1 — `get_predictions()` — Get RAG predictions for PDF fields

```python
result = client.get_predictions(
    user_id="user_001",
    session_id="session_abc",
    pdf_id="pdf_xyz",
    fields=[
        {
            "field_id": "f001",                    # required — unique ID for this field
            "field_name": "Investor Name Box",     # optional — improves accuracy
            "context": "Full legal name as it appears on government-issued ID",
            "section_context": "Investor Identity",
            "headers": ["Section 1", "Personal Information"],
        },
        {
            "field_id": "f002",
            "field_name": "Email Address",
            "context": "Email for correspondence",
            "section_context": "Contact Details",
            "headers": ["Section 2"],
        },
    ],
    pdf_hash="md5hashofthepdffile",    # MD5/SHA of the PDF (used for dedup)
    pdf_category={
        "category":      "Private Markets",
        "sub_category":  "Private Equity",
        "document_type": "LP Subscription Agreement",
    },
)

print(result["summary"])
# {'total_fields': 2, 'predicted_fields': 1, 'unpredicted_fields': 1, 'avg_confidence': 0.82}

print(result["submission_id"])   # unique ID for this submission
print(result["frequency"])       # how many times this PDF hash has been seen
print(result["is_duplicate"])    # True if this exact PDF+session was submitted before
```

RAG predictions are saved to:
`data/rag/predictions/{user_id}/{session_id}/{pdf_id}/predictions/rag_predictions.json`

---

### API 2 — `save_filled_pdf()` — Record LLM + final predictions, update vector DB

Called after your backend fills the PDF. Runs the full learning pipeline:
case classification → metrics → vector DB update → time series.

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
            },
            "f002": {
                "predicted_field_name": "email_address",
                "confidence": 0.88,
            },
        }
    },
    final_predictions={
        "final_predictions": {
            "f001": {
                "selected_field_name": "investor_full_legal_name",
                "selected_from": "llm",   # "rag" | "llm"
                "rag_confidence": 0.0,
                "llm_confidence": 0.92,
            },
            "f002": {
                "selected_field_name": "email_address",
                "selected_from": "rag",
                "rag_confidence": 0.85,
                "llm_confidence": 0.88,
            },
        }
    },
)
# Runs: CaseClassifier → MetricsService → VectorDB update → TimeSeriesService
print(result["case_counts"])   # {"CASE_A": 1, "CASE_B": 0, "CASE_C": 1, ...}
```

---

### API 4 — `submit_feedback()` — Report wrong predictions (triggers learning)

Called when a user corrects a wrong field mapping after reviewing the filled PDF.

```python
result = client.submit_feedback(
    user_id="user_001",
    session_id="session_abc",
    pdf_id="pdf_xyz",
    errors=[
        {
            "error_type":  "wrong_field_name",
            "field_name":  "investor_name",        # what was predicted (wrong)
            "field_type":  "text",
            "value":       "John Smith",
            "feedback":    "Should be full_legal_name",
            "page_number": 1,
            "corners":     [[10, 20], [200, 20], [200, 40], [10, 40]],
        }
    ],
)
# Runs: LLM corrector → confidence decay → embedding regeneration → metric recalc
print(result["corrected_fields"])
```

---

### API 5 — `get_metrics()` — Accuracy, coverage, confidence at 5 levels

```python
# Per-PDF metrics
client.get_metrics("pdf",
    user_id="user_001", session_id="session_abc", pdf_id="pdf_xyz")

# Category time series
client.get_metrics("category", category="Private Markets")

# Subcategory time series
client.get_metrics("subcategory",
    category="Private Markets", subcategory="Private Equity")

# Document type time series
client.get_metrics("doctype",
    category="Private Markets",
    subcategory="Private Equity",
    doctype="LP Subscription Agreement")

# Global metrics — LLM vs RAG comparison + ensemble stats
client.get_metrics("global")

# Compare multiple PDFs side-by-side
client.get_metrics("compare", pdfs=[
    {"user_id": "u1", "session_id": "s1", "pdf_id": "p1"},
    {"user_id": "u2", "session_id": "s2", "pdf_id": "p2"},
])

# All submissions for a specific PDF hash (e.g. how well a specific form type performs)
client.get_metrics("pdf_hash", pdf_hash="md5hashofthepdffile")
```

---

### API 6 — `get_system_info()` — Vector DB stats

```python
info = client.get_system_info()
print(info)
# {
#   "total_pdfs": 42, "total_users": 10, "total_sessions": 56,
#   "total_vectors": 1250, "categories": ["Private Markets", ...],
#   "vector_sources": {"llm": 800, "rag": 450}
# }
```

---

### API 7 — `get_error_analytics()` — Error breakdown with filters

```python
analytics = client.get_error_analytics(
    date_from="2026-01-01T00:00:00Z",
    date_to="2026-12-31T23:59:59Z",
    category="Private Markets",           # optional filter
    subcategory="Private Equity",         # optional filter
    doctype="LP Subscription Agreement",  # optional filter
)
# Returns: total_errors + breakdown by category, subcategory, doctype, date, error_type
```

---

## 3. Plugin System

Every component is pluggable. Mix and match.

### Embedding backends

```python
from ragpdf import SentenceTransformerBackend, OpenAIEmbeddingBackend, LiteLLMEmbeddingBackend

# Sentence Transformers — local, no API key, great accuracy
backend = SentenceTransformerBackend(model="all-MiniLM-L6-v2")
# Other models: "all-mpnet-base-v2", "paraphrase-MiniLM-L6-v2"

# OpenAI
backend = OpenAIEmbeddingBackend(api_key="sk-...", model="text-embedding-3-small")

# LiteLLM (any provider)
backend = LiteLLMEmbeddingBackend(model="openai/text-embedding-3-small", api_key="sk-...")

# Custom — implement 2 methods
from ragpdf.embeddings.base import EmbeddingBackend
class MyEmbedder(EmbeddingBackend):
    def embed(self, text: str) -> list[float]:
        return my_model.encode(text).tolist()
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return my_model.encode(texts).tolist()
```

### Vector store backends

```python
from ragpdf import LocalVectorStore, S3VectorStore
from ragpdf.vector_stores.chroma_store import ChromaStore
from ragpdf.vector_stores.pinecone_store import PineconeStore
from ragpdf.vector_stores.weaviate_store import WeaviateStore

store = LocalVectorStore("./data/rag")                         # flat JSON on disk — dev
store = S3VectorStore(bucket="my-bucket", region="us-east-1") # flat JSON in S3 — production
store = PineconeStore(api_key="...", index_name="ragpdf-vectors", namespace="prod")
store = ChromaStore(path="./chroma_data", collection="ragpdf_vectors")
store = WeaviateStore(url="http://localhost:8080", class_name="RagpdfVector")
```

### LLM corrector backends

```python
from ragpdf import OpenAICorrectorBackend, AnthropicCorrectorBackend, NoOpCorrectorBackend

corrector = OpenAICorrectorBackend(api_key="sk-...", model="gpt-4-turbo-preview")
corrector = AnthropicCorrectorBackend(api_key="sk-ant-...", model="claude-3-5-haiku-20241022")
corrector = NoOpCorrectorBackend()   # no LLM — just cleans to snake_case

# Custom — implement 1 method
from ragpdf.correctors.base import FieldCorrectorBackend
class OllamaCorrector(FieldCorrectorBackend):
    def generate_corrected_field_name(self, error_data: dict) -> dict:
        return {"corrected_field_name": "name", "confidence": 0.9, "reasoning": "..."}
```

### Storage backends

```python
from ragpdf import LocalStorage, S3Storage

storage = LocalStorage("./data/rag")
storage = S3Storage(bucket="my-bucket", region="us-east-1", prefix="ragpdf/")
```

---

## 4. CLI Usage

```bash
# System info (no API keys needed with noop backends)
ragpdf system-info

# Global metrics
ragpdf metrics --type global

# Per-PDF metrics
ragpdf metrics --type pdf --user u1 --session s1 --pdf p1

# Get predictions (pass fields as JSON file)
ragpdf predict \
  --user u1 --session s1 --pdf p1 \
  --fields data/rag/input/fields/lp_subscription_fields.json \
  --hash abc123 \
  --category data/rag/input/pdf_category.json

# Submit feedback
ragpdf feedback \
  --user u1 --session s1 --pdf p1 \
  --errors data/rag/input/sample_errors.json

# Error analytics
ragpdf error-analytics --from 2026-01-01T00:00:00Z

# All commands
ragpdf --help
```

---

## 5. API Server

### Start the server

```bash
# Via installed command
ragpdf-server

# Via uvicorn (dev mode with auto-reload)
uvicorn ragpdf.entrypoints.fastapi_app:app --reload --port 8000

# Custom port
RAGPDF_SERVER_PORT=9000 ragpdf-server

# Production (multi-worker)
uvicorn ragpdf.entrypoints.fastapi_app:app --host 0.0.0.0 --port 8000 --workers 4
```

Server at: **http://localhost:8000**  
All endpoints require `X-API-Key: dev-key` header (set `RAGPDF_API_KEY` to change).

---

## 6. API Endpoint Reference & Testing

### `GET /health`

```bash
curl -H "X-API-Key: dev-key" http://localhost:8000/health
```

---

### `POST /predict` — API 1

```bash
curl -s -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-key" \
  -d '{
    "user_id": "u1",
    "session_id": "s1",
    "pdf_id": "p1",
    "fields": [
      {
        "field_id": "f001",
        "field_name": "Investor Name",
        "context": "Full legal name of the investor",
        "section_context": "Personal Details",
        "headers": ["Section 1"]
      }
    ],
    "pdf_hash": "abc123",
    "pdf_category": {
      "category": "Private Markets",
      "sub_category": "Private Equity",
      "document_type": "LP Subscription Agreement"
    }
  }' | python3 -m json.tool
```

---

### `POST /save-filled-pdf` — API 2

```bash
curl -s -X POST http://localhost:8000/save-filled-pdf \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-key" \
  -d '{
    "user_id": "u1", "session_id": "s1", "pdf_id": "p1",
    "llm_predictions": {"predictions": {"f001": {"predicted_field_name": "investor_full_legal_name", "confidence": 0.92}}},
    "final_predictions": {"final_predictions": {"f001": {"selected_field_name": "investor_full_legal_name", "selected_from": "llm", "rag_confidence": 0.0, "llm_confidence": 0.92}}}
  }' | python3 -m json.tool
```

---

### `POST /feedback` — API 4

```bash
curl -s -X POST http://localhost:8000/feedback \
  -H "Content-Type: application/json" \
  -H "X-API-Key: dev-key" \
  -d '{
    "user_id": "u1", "session_id": "s1", "pdf_id": "p1",
    "errors": [{"error_type": "wrong_field_name", "field_name": "investor_name", "field_type": "text", "value": "John", "feedback": "Should be full_legal_name", "page_number": 1, "corners": [[10,20],[200,20],[200,40],[10,40]]}]
  }' | python3 -m json.tool
```

---

### `POST /metrics` — API 5

```bash
# Global
curl -s -X POST http://localhost:8000/metrics \
  -H "Content-Type: application/json" -H "X-API-Key: dev-key" \
  -d '{"metric_type": "global"}' | python3 -m json.tool

# Per-PDF
curl -s -X POST http://localhost:8000/metrics \
  -H "Content-Type: application/json" -H "X-API-Key: dev-key" \
  -d '{"metric_type": "pdf", "user_id": "u1", "session_id": "s1", "pdf_id": "p1"}' \
  | python3 -m json.tool
```

---

### `GET /system-info` — API 6

```bash
curl -H "X-API-Key: dev-key" http://localhost:8000/system-info | python3 -m json.tool
```

---

### `POST /error-analytics` — API 7

```bash
curl -s -X POST http://localhost:8000/error-analytics \
  -H "Content-Type: application/json" -H "X-API-Key: dev-key" \
  -d '{"date_from": "2026-01-01T00:00:00Z", "date_to": "2026-12-31T23:59:59Z"}' \
  | python3 -m json.tool
```

---

### All endpoints summary

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Health check + vector count |
| `/predict` | POST | API 1 — get RAG predictions |
| `/save-filled-pdf` | POST | API 2 — record results, update vector DB |
| `/feedback` | POST | API 4 — submit user corrections |
| `/metrics` | POST | API 5 — get metrics at any level |
| `/system-info` | GET | API 6 — vector DB stats |
| `/error-analytics` | POST | API 7 — error breakdown with filters |

---

## 7. FastAPI — Mount in Existing App

```python
from fastapi import FastAPI
from ragpdf.entrypoints.fastapi_app import app as rag_app

main_app = FastAPI()
main_app.mount("/rag", rag_app)
# Routes at: POST /rag/predict, POST /rag/feedback, GET /rag/system-info, etc.
```

---

## 8. Cloud Entrypoints

### AWS Lambda

```python
from ragpdf.entrypoints.aws_lambda import lambda_handler
# Deploy lambda_handler as your Lambda handler
```

Expected event body (all calls via `api_name` dispatch):
```json
{"api_name": "get_predictions", "user_id": "u1", "session_id": "s1", "pdf_id": "p1", "fields": [...], "pdf_hash": "abc123", "pdf_category": {...}}
```

Required Lambda env vars:
```
RAGPDF_STORAGE=s3
RAGPDF_VECTOR_STORE=s3
RAGPDF_S3_BUCKET=your-bucket
RAGPDF_EMBEDDING_BACKEND=sentence_transformer
RAGPDF_CORRECTOR_BACKEND=openai
OPENAI_API_KEY=sk-...
RAGPDF_API_KEY=your-secret
```

Local Lambda test:
```bash
RAGPDF_EMBEDDING_BACKEND=noop RAGPDF_CORRECTOR_BACKEND=noop python -c "
from ragpdf.entrypoints.aws_lambda import lambda_handler
import json
event = {'headers': {'x-api-key': 'dev-key'}, 'body': json.dumps({'api_name': 'get_system_info'})}
print(lambda_handler(event, None))
"
```

### Azure Functions

```python
from ragpdf.entrypoints.azure_function import main
# Register main as your Azure Functions HTTP trigger
```

```bash
pip install "pdf-autofillr-rag[azure_func]"
func start
```

### GCP Cloud Functions

```python
# Entry point function: ragpdf_handler
from ragpdf.entrypoints.gcp_function import ragpdf_handler
```

```bash
pip install "pdf-autofillr-rag[gcp_func]"
functions-framework --target ragpdf_handler --port 8080
```

---

## 9. From Source — Dev Mode

```bash
git clone https://github.com/yourorg/pdf-autofillr-rag.git
cd pdf-autofillr-rag

python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install with transformers + server + dev deps
pip install -e ".[transformers,server,dev]"

# Create config and data dirs
ragpdf-setup

# Edit .env
cp .env.example .env
# Set RAGPDF_EMBEDDING_BACKEND, RAGPDF_CORRECTOR_BACKEND, API keys

# Run API server with auto-reload
uvicorn ragpdf.entrypoints.fastapi_app:app --reload --port 8000

# Or CLI
ragpdf system-info
```

---

## 10. Run Tests

```bash
pip install "pdf-autofillr-rag[dev]"
# or from source: pip install -e ".[dev]"

# Unit tests (no API keys, no network)
pytest tests/unit/ -v

# Integration tests (no API keys — uses DummyEmbeddingBackend)
pytest tests/integration/ -v -m integration

# All tests
pytest -v

# With coverage
pytest tests/unit/ --cov=src/ragpdf --cov-report=term-missing

# Specific test files
pytest tests/unit/test_case_classifier.py -v
pytest tests/unit/test_vector_store.py -v
pytest tests/unit/test_metrics_service.py -v
```

---

## 11. Docker

```bash
# Build
docker build -t ragpdf-module .

# Run — local storage, sentence-transformers
docker run -p 8000:8000 \
  -e RAGPDF_EMBEDDING_BACKEND=sentence_transformer \
  -e RAGPDF_CORRECTOR_BACKEND=noop \
  -e RAGPDF_API_KEY=dev-key \
  ragpdf-module

# Run — from .env file
docker run -p 8000:8000 --env-file .env ragpdf-module

# Run — S3 storage + OpenAI
docker run -p 8000:8000 \
  -e RAGPDF_STORAGE=s3 \
  -e RAGPDF_VECTOR_STORE=s3 \
  -e RAGPDF_S3_BUCKET=my-bucket \
  -e RAGPDF_EMBEDDING_BACKEND=sentence_transformer \
  -e RAGPDF_CORRECTOR_BACKEND=openai \
  -e OPENAI_API_KEY=sk-... \
  -e RAGPDF_API_KEY=your-secret \
  ragpdf-module

curl -H "X-API-Key: dev-key" http://localhost:8000/health
```

---

## 12. Configuration Reference

### Storage

| Variable | Default | Description |
|---|---|---|
| `RAGPDF_STORAGE` | `local` | `local`, `s3`, `azure`, `gcs` |
| `RAGPDF_DATA_PATH` | `./data/rag` | Local data directory |
| `RAGPDF_S3_BUCKET` | — | S3 bucket (when `RAGPDF_STORAGE=s3`) |
| `RAGPDF_S3_REGION` | `us-east-1` | AWS region |
| `RAGPDF_S3_PREFIX` | `ragpdf/` | S3 key prefix |
| `RAGPDF_AZURE_CONN_STR` | — | Azure connection string |
| `RAGPDF_GCS_BUCKET` | — | GCS bucket |

### Embedding

| Variable | Default | Description |
|---|---|---|
| `RAGPDF_EMBEDDING_BACKEND` | `sentence_transformer` | `sentence_transformer`, `openai`, `litellm`, `noop` |
| `RAGPDF_ST_MODEL` | `all-MiniLM-L6-v2` | Sentence-transformer model name |
| `OPENAI_API_KEY` | — | For `openai` embedding backend |
| `RAGPDF_OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | OpenAI embedding model |
| `RAGPDF_LITELLM_EMBEDDING_MODEL` | — | LiteLLM model string (e.g. `openai/text-embedding-3-small`) |

### Vector Store

| Variable | Default | Description |
|---|---|---|
| `RAGPDF_VECTOR_STORE` | `local` | `local`, `s3`, `azure`, `gcs`, `pinecone`, `chroma`, `weaviate` |
| `PINECONE_API_KEY` | — | Pinecone API key |
| `RAGPDF_PINECONE_INDEX` | `ragpdf-vectors` | Pinecone index name |
| `RAGPDF_CHROMA_PATH` | `./chroma_data` | ChromaDB data path |
| `RAGPDF_WEAVIATE_URL` | `http://localhost:8080` | Weaviate URL |

### LLM Corrector

| Variable | Default | Description |
|---|---|---|
| `RAGPDF_CORRECTOR_BACKEND` | `noop` | `noop`, `openai`, `anthropic`, `litellm` |
| `RAGPDF_OPENAI_MODEL` | `gpt-4-turbo-preview` | OpenAI model for corrections |
| `ANTHROPIC_API_KEY` | — | Anthropic key |
| `RAGPDF_ANTHROPIC_MODEL` | `claude-3-5-haiku-20241022` | Anthropic model |

### Prediction Tuning

| Variable | Default | Description |
|---|---|---|
| `RAGPDF_PREDICTION_THRESHOLD` | `0.75` | Min cosine similarity to count as a match |
| `RAGPDF_TOP_K` | `5` | Number of candidate vectors to return |
| `RAGPDF_CONFIDENCE_DECAY_RATE` | `0.95` | Multiply confidence on error |
| `RAGPDF_CONFIDENCE_GROWTH_RATE` | `1.05` | Multiply confidence on correct |
| `RAGPDF_MAX_CONFIDENCE` | `0.99` | Max confidence cap |
| `RAGPDF_MIN_CONFIDENCE` | `0.50` | Min confidence floor |

### Server & Auth

| Variable | Default | Description |
|---|---|---|
| `RAGPDF_API_KEY` | `dev-key` | All endpoints require `X-API-Key: <value>` |
| `RAGPDF_SERVER_HOST` | `0.0.0.0` | Server host |
| `RAGPDF_SERVER_PORT` | `8000` | Server port |
| `RAGPDF_LOG_LEVEL` | `INFO` | Log level |
| `RAGPDF_DEBUG` | `false` | Enable debug mode |

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'sentence_transformers'`**
```bash
pip install "pdf-autofillr-rag[transformers]"
```

**`No API key found` (openai corrector)**
```bash
export OPENAI_API_KEY=sk-your-actual-key
```

**`ModuleNotFoundError: No module named 'fastapi'`**
```bash
pip install "pdf-autofillr-rag[server]"
```

**First run — predictions always empty**  
Normal. The vector DB is empty on first run. After you call `save_filled_pdf()` a few times, the DB learns and predictions improve automatically.

**Unit tests failing with embedding errors**
```bash
# Use noop backend for tests — no model download needed
RAGPDF_EMBEDDING_BACKEND=noop RAGPDF_CORRECTOR_BACKEND=noop pytest tests/unit/ -v
```