# pdf-autofillr-rag — How to Run

## Standalone (no mapper)

### Step 1 — Install

```bash
# Minimal: local storage, sentence-transformers embeddings
pip install -e ".[transformers]"

# With OpenAI embeddings + GPT-4 corrector
pip install -e ".[transformers,openai]"

# With LiteLLM (any provider)
pip install -e ".[transformers,litellm]"

# Everything
pip install -e ".[all]"
```

### Step 2 — Setup

```bash
ragpdf-setup
# Creates: .env, config.ini, data/rag/ with sample vectors + data
```

Edit `.env` — set `RAGPDF_EMBEDDING_BACKEND`, `RAGPDF_CORRECTOR_BACKEND`, keys.

### Step 3 — Verify

```bash
# Windows PowerShell
$env:RAGPDF_EMBEDDING_BACKEND="noop"; $env:RAGPDF_CORRECTOR_BACKEND="noop"
python -m ragpdf.entrypoints.cli system-info

# Linux/Mac
RAGPDF_EMBEDDING_BACKEND=noop RAGPDF_CORRECTOR_BACKEND=noop ragpdf system-info
```

---

## Entrypoints

### CLI
```bash
ragpdf system-info
ragpdf metrics --type global
ragpdf predict --user u1 --session s1 --pdf p1 \
    --fields data/rag/input/fields/lp_subscription_fields.json \
    --hash abc123 \
    --category data/rag/input/pdf_category.json
ragpdf feedback --user u1 --session s1 --pdf p1 \
    --errors data/rag/input/sample_errors.json
ragpdf error-analytics --from 2026-01-01T00:00:00Z
```

### FastAPI Server (Swagger at /docs)
```bash
pip install -e ".[server]"
ragpdf-server
# OR
uvicorn ragpdf.entrypoints.fastapi_app:app --reload --port 8000
```

### AWS Lambda
Handler: `ragpdf.entrypoints.aws_lambda.lambda_handler`
Required Lambda env vars:
```
RAGPDF_STORAGE=s3
RAGPDF_VECTOR_STORE=s3
RAGPDF_S3_BUCKET=your-bucket
RAGPDF_CORRECTOR_BACKEND=openai
OPENAI_API_KEY=sk-...
RAGPDF_API_KEY=your-secret
RAGPDF_EMBEDDING_BACKEND=sentence_transformer
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

### Azure Function
Entry point: `ragpdf.entrypoints.azure_function.main`
```bash
pip install -e ".[azure_func]"
func start
```

### GCP Cloud Function
Entry point: `ragpdf_handler`
```bash
pip install -e ".[gcp_func]"
functions-framework --target ragpdf_handler --port 8080
```

---

## With Mapper (RAG_MODE=inprocess)

The mapper calls the RAG SDK directly in-process when `RAG_ENABLED=true` and `RAG_MODE=inprocess`.

### Mapper `.env` additions
```env
RAG_ENABLED=true
RAG_MODE=inprocess
```

### Mapper `mapper_config.ini` additions
```ini
[rag]
enabled = true
mode = inprocess
api_url =
api_key =
```

The mapper reads header_file.json it generates itself, passes the fields directly
to `RAGPDFClient.get_predictions()`, and receives `rag_predictions.json` back — no HTTP.

### With RAG_MODE=http (remote Lambda)
```env
RAG_ENABLED=true
RAG_MODE=http
RAG_API_URL=https://your-lambda-url.lambda-url.us-east-1.on.aws/
RAG_API_KEY=your-rag-api-key
```

---

## File Locations (all storage backends)

All paths are relative to storage root:

| File | Key path | What it is |
|------|----------|------------|
| Header file (input from mapper) | `predictions/{user}/{session}/{pdf}/input_file/header_file.json` | Fields + context sent to RAG |
| RAG predictions | `predictions/{user}/{session}/{pdf}/predictions/rag_predictions.json` | RAG output |
| LLM predictions (from mapper) | `predictions/{user}/{session}/{pdf}/predictions/llm_predictions.json` | Mapper LLM output |
| Final predictions (from mapper) | `predictions/{user}/{session}/{pdf}/predictions/final_predictions.json` | Ensemble winner |
| Vector database | `vectors/vector_database.json` | Flat JSON stores only (local/s3/azure/gcs) |
| Feedback (raw) | `user_feedbacks/{user}/{session}/{pdf}/feedback.jsonl` | Appended by API 4 |
| Metrics snapshot | `predictions/{user}/{session}/{pdf}/analysis/metrics_snapshot.json` | Per-submission metrics |
| Time series (global) | `metrics/time_series/global/time_series.json` | All submissions over time |
| Time series (category) | `metrics/time_series/category/{cat}/time_series.json` | Per-category |
| PDF hash mapping | `pdf_hash_mapping/mapping.json` | Dedup + frequency registry |

**Local**: `{RAGPDF_DATA_PATH}/{key}`
**S3**: `s3://{RAGPDF_S3_BUCKET}/{RAGPDF_S3_PREFIX}{key}`
**Azure**: `https://{account}.blob.core.windows.net/{container}/{prefix}{key}`
**GCS**: `gs://{RAGPDF_GCS_BUCKET}/{RAGPDF_GCS_PREFIX}{key}`

---

## To Replicate rag-lambda Behaviour Locally

```env
RAGPDF_STORAGE=local
RAGPDF_DATA_PATH=./data/rag
RAGPDF_EMBEDDING_BACKEND=sentence_transformer
RAGPDF_ST_MODEL=all-MiniLM-L6-v2
RAGPDF_VECTOR_STORE=local
RAGPDF_CORRECTOR_BACKEND=openai
OPENAI_API_KEY=sk-...
RAGPDF_OPENAI_MODEL=gpt-4-turbo-preview
RAGPDF_PREDICTION_THRESHOLD=0.75
RAGPDF_CONFIDENCE_DECAY_RATE=0.95
RAGPDF_CONFIDENCE_GROWTH_RATE=1.05
RAGPDF_MAX_CONFIDENCE=0.99
RAGPDF_MIN_CONFIDENCE=0.50
RAGPDF_TOP_K=5
RAGPDF_API_KEY=dev-key
```
