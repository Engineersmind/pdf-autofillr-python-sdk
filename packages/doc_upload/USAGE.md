# pdf-autofillr-doc-upload — Complete Usage Guide

> Extract structured data from any document (PDF, DOCX, PPTX, XLSX, CSV, JSON, MD, TXT, HTML, XML) using an LLM, then optionally fill a blank PDF via the mapper module.

---

## Table of Contents

1. [PyPI Install — Quick Start (for Users)](#1-pypi-install--quick-start-for-users)
2. [Python Library Usage](#2-python-library-usage)
3. [CLI Usage](#3-cli-usage)
4. [API Server](#4-api-server)
5. [API Endpoint Reference & Testing](#5-api-endpoint-reference--testing)
6. [FastAPI — Mount in Existing App](#6-fastapi--mount-in-existing-app)
7. [Cloud Entrypoints](#7-cloud-entrypoints)
8. [From Source — Dev Mode](#8-from-source--dev-mode)
9. [Run Tests](#9-run-tests)
10. [Docker](#10-docker)
11. [Configuration Reference](#11-configuration-reference)

---

## 1. PyPI Install — Quick Start (for Users)

### Install

```bash
# Core package + CLI
pip install pdf-autofillr-doc-upload

# With API server support
pip install "pdf-autofillr-doc-upload[server]"

# With AWS S3 storage
pip install "pdf-autofillr-doc-upload[s3]"

# With GCP storage
pip install "pdf-autofillr-doc-upload[gcp]"

# With Azure storage
pip install "pdf-autofillr-doc-upload[azure]"

# Everything
pip install "pdf-autofillr-doc-upload[full]"
```

### First-time setup (run once after install)

```bash
# 1. Copy sample config files into your working directory
python -c "import pdf_autofillr_doc_upload; pdf_autofillr_doc_upload.copy_sample_configs('.')"
# → Creates ./configs/ with form_keys.json and mapper_config.ini

# 2. Create your .env file
cat > .env << 'EOF'
DOC_UPLOAD_LLM_MODEL=openai/gpt-4.1-mini
DOC_UPLOAD_LLM_API_KEY=sk-your-key-here

DOC_UPLOAD_STORAGE=local
DOC_UPLOAD_DATA_PATH=./data/doc_upload
DOC_UPLOAD_CONFIG_PATH=./configs

DOC_UPLOAD_PDF_FILLER=none
DOC_UPLOAD_PDF_PATH=

MAPPER_API_URL=
MAPPER_API_KEY=

DOC_UPLOAD_LOG_LEVEL=INFO
DOC_UPLOAD_DEBUG_LOGGING=false
EOF
```

### Run

```bash
doc-upload-cli --document investor.pdf --schema configs/form_keys.json
doc-upload-server    # REST API on http://localhost:8001
```

---

## 2. Python Library Usage

### Minimal — extract only, no PDF filling

```python
from pdf_autofillr_doc_upload import DocUploadClient

client = DocUploadClient()
# Reads all config from env vars / .env automatically

result = client.run(
    document_path="investor_profile.pdf",
    schema_path="configs/form_keys.json",
    output_path="output/extracted.json",   # optional — save to file
)

print(result["output_flat"])    # flat dot-notation dict: {"full_name": "Alice", ...}
print(result["output_nested"])  # nested dict matching schema structure
print(result["job_id"])         # auto-generated UUID
```

### Supported document formats

`.pdf`, `.docx`, `.pptx`, `.xlsx`, `.xls`, `.csv`, `.json`, `.md`, `.markdown`, `.txt`, `.html`, `.htm`, `.xml`

### With PDF filling — in-process mapper (local dev, no separate server)

```python
import os
os.environ["DOC_UPLOAD_PDF_FILLER"] = "mapper"
os.environ["DOC_UPLOAD_PDF_PATH"] = "./data/input/blank_form.pdf"
os.environ["MAPPER_API_URL"] = ""   # empty = in-process

from pdf_autofillr_doc_upload import DocUploadClient

client = DocUploadClient()
result = client.run(
    document_path="investor_profile.pdf",
    schema_path="configs/form_keys.json",
    investor_type="Individual",
)

print(result["filled_pdf_path"])  # path to the filled PDF
```

### With PDF filling — HTTP mapper server

```python
import os
os.environ["DOC_UPLOAD_PDF_FILLER"] = "mapper"
os.environ["MAPPER_API_URL"] = "http://localhost:8000"   # mapper server
os.environ["MAPPER_API_KEY"] = ""

result = client.run(
    document_path="investor_profile.pdf",
    schema_path="configs/form_keys.json",
    investor_type="Individual",
    user_id="user_42",
    pdf_doc_id="99",
    session_id="sess_abc",
)
```

### Convenience method — local extract + fill in one call

```python
result = client.run_local_with_pdf(
    document_path="investor_profile.pdf",
    schema_path="configs/form_keys.json",
    pdf_path="./data/input/blank_form.pdf",
    investor_type="Individual",
    output_json_path="./output/extracted.json",   # optional
    output_pdf_path="./output/filled.pdf",        # optional
)
print(result["filled_pdf_path"])
```

### With explicit storage backend

```python
from pdf_autofillr_doc_upload import DocUploadClient
from pdf_autofillr_doc_upload.storage.local_storage import LocalStorage

client = DocUploadClient(
    storage=LocalStorage(
        data_path="./data/doc_upload",
        config_path="./configs",
    )
)
```

### With S3 storage

```python
from pdf_autofillr_doc_upload.storage.s3_storage import S3Storage

client = DocUploadClient(
    storage=S3Storage(
        output_bucket="my-doc-upload-output",
        config_bucket="my-doc-upload-config",
    )
)

result = client.run(
    document_path="s3://my-bucket/investor_profile.pdf",
    schema_path="s3://my-config-bucket/form_keys.json",
)
```

### Using a different LLM model

```python
import os

# Anthropic Claude
os.environ["DOC_UPLOAD_LLM_MODEL"] = "anthropic/claude-3-5-haiku-20241022"
os.environ["ANTHROPIC_API_KEY"] = "sk-ant-..."

# Groq (fast + cheap)
os.environ["DOC_UPLOAD_LLM_MODEL"] = "groq/llama-3.1-8b-instant"
os.environ["GROQ_API_KEY"] = "gsk_..."

# AWS Bedrock (no key needed — uses IAM role)
os.environ["DOC_UPLOAD_LLM_MODEL"] = "bedrock/anthropic.claude-3-haiku-20240307-v1:0"

# Local Ollama (no key needed)
os.environ["DOC_UPLOAD_LLM_MODEL"] = "ollama/llama3.1"
```

Supported model prefixes via LiteLLM: `openai/`, `anthropic/`, `groq/`, `gemini/`, `azure/`, `bedrock/`, `vertex_ai/`, `ollama/`

### With explicit extractor settings

```python
from pdf_autofillr_doc_upload.extraction.llm_client import LLMClient
from pdf_autofillr_doc_upload.extraction.extractor import Extractor

extractor = Extractor(
    llm_client=LLMClient(
        model="openai/gpt-4o",
        temperature=0.0,
        max_tokens=8192,
        timeout=120,
        max_retries=3,
    )
)

client = DocUploadClient(extractor=extractor)
```

---

## 3. CLI Usage

```bash
# Basic extraction
doc-upload-cli --document investor.pdf --schema configs/form_keys.json

# Save extracted data to JSON file
doc-upload-cli --document investor.pdf --schema configs/form_keys.json --output filled.json

# Print job report at end
doc-upload-cli --document investor.pdf --schema configs/form_keys.json --report

# Provide a specific job ID
doc-upload-cli --document investor.pdf --schema configs/form_keys.json --job-id my-job-001

# All options together
doc-upload-cli \
  --document investor_profile.docx \
  --schema configs/form_keys.json \
  --output ./output/extracted.json \
  --job-id job_001 \
  --report \
  --log-level INFO
```

### CLI flags

| Flag | Short | Default | Description |
|---|---|---|---|
| `--document` | `-d` | _(required)_ | Path to source document |
| `--schema` | `-s` | `configs/form_keys.json` | Path to form_keys.json |
| `--output` | `-o` | _(none)_ | Save extracted JSON to this path |
| `--job-id` | — | _(auto UUID)_ | Job identifier |
| `--report` | — | off | Print job stats at end |
| `--log-level` | — | `WARNING` | Terminal log level |

---

## 4. API Server

### Start the server

```bash
# Via installed command
doc-upload-server

# Via uvicorn directly (with auto-reload for dev)
uvicorn pdf_autofillr_doc_upload.entrypoints.fastapi_app:app --reload --port 8001

# Custom port
DOC_UPLOAD_PORT=9000 doc-upload-server

# Production (multi-worker)
uvicorn pdf_autofillr_doc_upload.entrypoints.fastapi_app:app \
  --host 0.0.0.0 --port 8001 --workers 4
```

Server starts at: **http://localhost:8001**
Interactive API docs: **http://localhost:8001/docs**

---

## 5. API Endpoint Reference & Testing

### `GET /health` — Health check

```bash
curl http://localhost:8001/health
```

```json
{"status": "ok", "service": "pdf-autofillr-doc-upload"}
```

---

### `POST /extract` — Run extraction

```bash
# Basic extraction
curl -s -X POST http://localhost:8001/extract \
  -H "Content-Type: application/json" \
  -d '{
    "document_path": "./data/input/sample_investor.pdf",
    "schema_path": "configs/form_keys.json"
  }' | python3 -m json.tool

# With investor type and job ID
curl -s -X POST http://localhost:8001/extract \
  -H "Content-Type: application/json" \
  -d '{
    "document_path": "./data/input/sample_investor.pdf",
    "schema_path": "configs/form_keys.json",
    "investor_type": "Individual",
    "job_id": "job_001"
  }' | python3 -m json.tool

# With PDF filling (remote mapper)
curl -s -X POST http://localhost:8001/extract \
  -H "Content-Type: application/json" \
  -d '{
    "document_path": "s3://my-bucket/investor.pdf",
    "schema_path": "configs/form_keys.json",
    "investor_type": "Individual",
    "user_id": "user_42",
    "pdf_doc_id": "99",
    "session_id": "sess_abc",
    "filled_doc_pdf_id": "99"
  }' | python3 -m json.tool

# With API key auth (when AUTH_TOKEN is set)
curl -s -X POST http://localhost:8001/extract \
  -H "Content-Type: application/json" \
  -H "X-API-Key: my-secret-token" \
  -d '{"document_path": "./investor.pdf", "schema_path": "configs/form_keys.json"}' \
  | python3 -m json.tool
```

**Request body:**

| Field | Type | Required | Description |
|---|---|---|---|
| `document_path` | string | ✅ | Path or S3/GCS URI to source document |
| `schema_path` | string | — | Path to form_keys.json (default: `configs/form_keys.json`) |
| `job_id` | string | — | Job identifier. Auto-generated if not provided |
| `output_path` | string | — | Where to save extracted JSON |
| `investor_type` | string | — | e.g. `Individual`, `Corporation`, `LLC` (default: `Individual`) |
| `user_id` | string | — | Required only for remote Lambda PDF filling |
| `pdf_doc_id` | string | — | Required only for remote Lambda PDF filling |
| `session_id` | string | — | Required only for remote Lambda PDF filling |
| `filled_doc_pdf_id` | string | — | Required only for remote Lambda PDF filling |

**Response:**

```json
{
  "status": "success",
  "job_id": "a3f2b1c4-...",
  "output_flat": {
    "full_name": "Alice Johnson",
    "email": "alice@example.com",
    "address_registered.address_registered_country_id": "USA"
  },
  "output_path": null
}
```

---

### `GET /jobs/{job_id}/output` — Get nested output

```bash
curl http://localhost:8001/jobs/a3f2b1c4-.../output | python3 -m json.tool
```

### `GET /jobs/{job_id}/output-flat` — Get flat output

```bash
curl http://localhost:8001/jobs/a3f2b1c4-.../output-flat | python3 -m json.tool
```

---

### Full extraction via Python (httpx)

```python
import httpx

BASE = "http://localhost:8001"

r = httpx.post(f"{BASE}/extract", json={
    "document_path": "./data/input/sample_investor.pdf",
    "schema_path": "configs/form_keys.json",
    "investor_type": "Individual",
})
r.raise_for_status()
data = r.json()

print(f"Job ID: {data['job_id']}")
print(f"Fields extracted: {len(data['output_flat'])}")
print(data["output_flat"])

# Fetch output later
r2 = httpx.get(f"{BASE}/jobs/{data['job_id']}/output-flat")
print(r2.json())
```

---

## 6. FastAPI — Mount in Existing App

```python
from fastapi import FastAPI
from pdf_autofillr_doc_upload.entrypoints.fastapi_app import app as extractor_app

main_app = FastAPI()
main_app.mount("/extractor", extractor_app)
# Routes now at: POST /extractor/extract, GET /extractor/jobs/{id}/output, etc.
```

---

## 7. Cloud Entrypoints

### AWS Lambda

```python
# lambda_function.py
from pdf_autofillr_doc_upload.entrypoints.aws_lambda import handler
# Deploy handler as your Lambda function handler
```

Expected event body:
```json
{
  "user_id": "42",
  "session_id": "sess_abc",
  "filled_doc_pdf_id": "99",
  "pdf_doc_id": "99",
  "pdf_location": "s3://bucket/path/to/investor.pdf",
  "investor_type": "Individual"
}
```

Required Lambda env vars:
```
DOC_UPLOAD_LLM_MODEL=openai/gpt-4.1-mini
DOC_UPLOAD_LLM_API_KEY=sk-...
DOC_UPLOAD_STORAGE=s3
AWS_OUTPUT_BUCKET=my-output-bucket
AWS_CONFIG_BUCKET=my-config-bucket
DOC_UPLOAD_PDF_FILLER=mapper        # optional
MAPPER_API_URL=https://...          # optional
```

### Azure Functions

```python
from pdf_autofillr_doc_upload.entrypoints.azure_function import main
# Register main as your Azure Functions HTTP trigger
```

Required app settings:
```
DOC_UPLOAD_LLM_MODEL, DOC_UPLOAD_LLM_API_KEY
DOC_UPLOAD_STORAGE=azure
AZURE_OUTPUT_CONTAINER, AZURE_CONFIG_CONTAINER
AZURE_STORAGE_CONNECTION_STRING
```

### GCP Cloud Functions

```python
from pdf_autofillr_doc_upload.entrypoints.gcp_function import handler
```

Deploy:
```bash
gcloud functions deploy extractor \
  --runtime python311 \
  --trigger-http \
  --entry-point handler \
  --source . \
  --set-env-vars DOC_UPLOAD_LLM_MODEL=openai/gpt-4.1-mini,DOC_UPLOAD_STORAGE=gcp,...
```

---

## 8. From Source — Dev Mode

```bash
git clone https://github.com/yourorg/pdf-autofillr-doc-upload.git
cd pdf-autofillr-doc-upload

python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -e ".[server,dev]"

python -c "import pdf_autofillr_doc_upload; pdf_autofillr_doc_upload.copy_sample_configs('.')"

cp .env.example .env
# Edit .env: set DOC_UPLOAD_LLM_API_KEY=sk-your-actual-key

# API server with auto-reload
uvicorn pdf_autofillr_doc_upload.entrypoints.fastapi_app:app --reload --port 8001

# Or CLI
doc-upload-cli --document data/input/sample_investor.pdf --schema configs/form_keys.json
```

---

## 9. Run Tests

```bash
pip install "pdf-autofillr-doc-upload[dev]"
# or from source: pip install -e ".[dev]"

pytest tests/unit/ -v
pytest tests/functional/ -v
pytest -v
pytest tests/unit/ --cov=src/pdf_autofillr_doc_upload --cov-report=term-missing
pytest tests/unit/test_extractor.py -v
pytest -m unit -v
pytest tests/unit/ -v -x   # stop on first failure
```

---

## 10. Docker

```bash
# Build
docker build -t doc-upload-module .

# Run — local, extract only
docker run -p 8001:8001 \
  -e DOC_UPLOAD_LLM_API_KEY=sk-your-key \
  doc-upload-module

# Run — from .env file
docker run -p 8001:8001 --env-file .env doc-upload-module

# Run — S3 + mapper
docker run -p 8001:8001 \
  -e DOC_UPLOAD_LLM_API_KEY=sk-your-key \
  -e DOC_UPLOAD_STORAGE=s3 \
  -e AWS_OUTPUT_BUCKET=my-output \
  -e AWS_CONFIG_BUCKET=my-config \
  -e DOC_UPLOAD_PDF_FILLER=mapper \
  -e MAPPER_API_URL=http://mapper-service:8000 \
  doc-upload-module

# Run — with local documents mounted
docker run -p 8001:8001 \
  -e DOC_UPLOAD_LLM_API_KEY=sk-your-key \
  -e DOC_UPLOAD_PDF_PATH=/data/blank_form.pdf \
  -v /local/documents:/data \
  doc-upload-module

curl http://localhost:8001/health
```

---

## 11. Configuration Reference

### LLM

| Variable | Default | Description |
|---|---|---|
| `DOC_UPLOAD_LLM_MODEL` | `openai/gpt-4.1-mini` | LiteLLM model string |
| `DOC_UPLOAD_LLM_API_KEY` | — | Universal API key override |
| `OPENAI_API_KEY` | — | OpenAI key |
| `ANTHROPIC_API_KEY` | — | Anthropic key |
| `GROQ_API_KEY` | — | Groq key |
| `AZURE_API_KEY` | — | Azure key (also set `AZURE_API_BASE`) |
| `DOC_UPLOAD_LLM_TEMPERATURE` | `0` | Sampling temperature |
| `DOC_UPLOAD_LLM_MAX_TOKENS` | `4096` | Max tokens per LLM call |
| `DOC_UPLOAD_LLM_TIMEOUT` | `120` | Seconds before timeout |
| `DOC_UPLOAD_LLM_MAX_RETRIES` | `3` | Retry attempts on failure |

### Storage

| Variable | Default | Description |
|---|---|---|
| `DOC_UPLOAD_STORAGE` | `local` | `local`, `s3`, `gcp`, or `azure` |
| `DOC_UPLOAD_DATA_PATH` | `./data/doc_upload` | Local job data directory |
| `DOC_UPLOAD_CONFIG_PATH` | `./configs` | Config files directory |

### PDF Filling

| Variable | Default | Description |
|---|---|---|
| `DOC_UPLOAD_PDF_FILLER` | `none` | `none`, `mapper`, or `managed` |
| `DOC_UPLOAD_PDF_PATH` | — | Path/URI to blank PDF (`./path`, `s3://`, `gs://`) |
| `MAPPER_API_URL` | — | Mapper server URL. Empty = in-process mode |
| `MAPPER_API_KEY` | — | Mapper API key |
| `DOC_UPLOAD_PDF_POLL_INTERVAL` | `10` | Seconds between embed-ready checks |
| `DOC_UPLOAD_PDF_POLL_TIMEOUT` | `150` | Max seconds to wait for embed |
| `DOC_UPLOAD_PDF_MAX_RETRIES` | `3` | Fill retry attempts |

### Server & Auth

| Variable | Default | Description |
|---|---|---|
| `DOC_UPLOAD_HOST` | `0.0.0.0` | API server host |
| `DOC_UPLOAD_PORT` | `8001` | API server port |
| `DOC_UPLOAD_RELOAD` | `false` | uvicorn auto-reload |
| `AUTH_TOKEN` | — | When set, requires `X-API-Key: <AUTH_TOKEN>` on all endpoints |

### AWS S3 (`DOC_UPLOAD_STORAGE=s3`)

| Variable | Description |
|---|---|
| `AWS_OUTPUT_BUCKET` | S3 bucket for job output |
| `AWS_CONFIG_BUCKET` | S3 bucket for config files |
| `AWS_REGION` | AWS region (default: `us-east-1`) |
| `AWS_ACCESS_KEY_ID` | AWS credentials (or use IAM role) |
| `AWS_SECRET_ACCESS_KEY` | AWS credentials |

### GCP (`DOC_UPLOAD_STORAGE=gcp`)

| Variable | Description |
|---|---|
| `GCP_OUTPUT_BUCKET` | GCS bucket for job output |
| `GCP_CONFIG_BUCKET` | GCS bucket for config files |
| `GCP_PROJECT_ID` | GCP project ID |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to service account JSON |

### Azure (`DOC_UPLOAD_STORAGE=azure`)

| Variable | Description |
|---|---|
| `AZURE_STORAGE_CONNECTION_STRING` | Azure Storage connection string |
| `AZURE_OUTPUT_CONTAINER` | Container for job output |
| `AZURE_CONFIG_CONTAINER` | Container for config files |

---

## Troubleshooting

**`No API key found for model 'openai/gpt-4.1-mini'`**
```bash
export DOC_UPLOAD_LLM_API_KEY=sk-your-actual-key
```

**`ModuleNotFoundError: No module named 'fastapi'`**
```bash
pip install "pdf-autofillr-doc-upload[server]"
```

**`ModuleNotFoundError: No module named 'pdf_autofillr_mapper'`**
```bash
pip install pdf-autofillr-mapper
```

**`DOC_UPLOAD_PDF_PATH is missing`**
```bash
# Add to .env:
DOC_UPLOAD_PDF_PATH=./data/input/blank_form.pdf
```

**Configs not found after pip install**
```bash
python -c "import pdf_autofillr_doc_upload; pdf_autofillr_doc_upload.copy_sample_configs('.')"
```