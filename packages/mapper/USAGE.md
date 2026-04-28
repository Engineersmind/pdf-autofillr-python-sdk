# pdf-autofillr-mapper — Complete Usage Guide

> PDF field extraction, semantic mapping, embedding and filling engine. The core engine used by the chatbot and doc-upload modules.

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
pip install pdf-autofillr-mapper

# With API server support
pip install "pdf-autofillr-mapper[api]"

# With AWS support
pip install "pdf-autofillr-mapper[aws]"

# With Azure support
pip install "pdf-autofillr-mapper[azure]"

# With GCP support
pip install "pdf-autofillr-mapper[gcp]"

# Everything
pip install "pdf-autofillr-mapper[all]"
```

### First-time setup (run once after install)

```bash
# 1. Copy sample configs into your working directory
python -c "import pdf_autofillr_mapper; pdf_autofillr_mapper.copy_sample_configs('.')"
# → Creates ./configs/mapper_config.ini and ./configs/.env.mapper.example

# 2. Create your .env file
cp configs/.env.mapper.example .env
# Edit .env: set OPENAI_API_KEY=sk-your-key-here

# 3. Edit configs/mapper_config.ini
# Set your storage paths, LLM model, and options
```

### Run

```bash
pdf-mapper-server   # REST API on http://localhost:8000
pdf-mapper --help   # CLI
```

---

## 2. Python Library Usage

### Run the full pipeline (extract → map → embed → fill)

```python
import asyncio
from pdf_autofillr_mapper import PDFPipeline, MapperConfig

# Load config from your configs/ directory
cfg = MapperConfig.from_directory("./configs")

# Build and run the pipeline
pipeline = PDFPipeline(mapper_config=cfg)
result = asyncio.run(pipeline.run_all(
    input_pdf_path="./data/input/blank_form.pdf",
    input_data_path="./configs/form_keys.json",
))

print(result["final_output"])   # path to the filled PDF
print(result["mapped_fields"])  # dict of mapped field→value pairs
```

### Run individual pipeline stages

```python
from pdf_autofillr_mapper.handlers.operations import (
    handle_extract_operation,
    handle_map_operation,
    handle_embed_operation,
    handle_fill_operation,
    handle_run_all_operation,
)

user_id   = "user_001"
pdf_doc_id = "doc_001"
pdf_path  = "./data/input/blank_form.pdf"

# Stage 1 — Extract form fields from the PDF
extracted = handle_extract_operation(pdf_path, user_id, pdf_doc_id)

# Stage 2 — Map fields to your schema using LLM
mapped = handle_map_operation(user_id, pdf_doc_id)

# Stage 3 — Embed mapping metadata into the PDF
embedded_pdf_path = handle_embed_operation(pdf_path, user_id, pdf_doc_id)

# Stage 4 — Fill the embedded PDF with actual data
filled = handle_fill_operation(
    embedded_pdf_path=embedded_pdf_path,
    user_id=user_id,
    pdf_doc_id=pdf_doc_id,
    input_data={"full_name": "Alice Johnson", "email": "alice@example.com"},
)
print(filled["output_pdf_path"])
```

### In-process fill (used by chatbot and doc-upload)

```python
from pdf_autofillr_mapper import PDFPipeline, MapperConfig

cfg = MapperConfig.from_directory("./configs")
pipeline = PDFPipeline(mapper_config=cfg)

# Called by the chatbot/doc-upload after data collection
result = asyncio.run(pipeline.fill_pdf(
    pdf_path="./data/input/blank_form.pdf",
    data_flat={
        "full_name": "Alice Johnson",
        "email": "alice@example.com",
        "address_registered.address_registered_country_id": "USA",
    },
    investor_type="Individual",
))
print(result["output_path"])
```

### With AWS S3 storage

```python
# In mapper_config.ini set [general] source_type = aws
# And set AWS env vars: AWS_OUTPUT_BUCKET, AWS_CONFIG_BUCKET, AWS_REGION
cfg = MapperConfig.from_directory("./configs")
pipeline = PDFPipeline(mapper_config=cfg)
```

---

## 3. CLI Usage

```bash
# Extract form fields from a PDF
pdf-mapper extract --pdf ./data/input/blank_form.pdf --user-id u1 --pdf-doc-id d1

# Map extracted fields to schema using LLM
pdf-mapper map --user-id u1 --pdf-doc-id d1

# Embed mapping metadata into the PDF
pdf-mapper embed --pdf ./data/input/blank_form.pdf --user-id u1 --pdf-doc-id d1

# Fill the embedded PDF with data
pdf-mapper fill \
  --pdf ./data/output/u1/d1/blank_form_embedded.pdf \
  --user-id u1 --pdf-doc-id d1 \
  --data ./data/input/form_data.json

# One-step: extract + map + embed (make-embed)
pdf-mapper make-embed --pdf ./data/input/blank_form.pdf --user-id u1 --pdf-doc-id d1

# Full pipeline: extract + map + embed + fill
pdf-mapper run-all \
  --pdf ./data/input/blank_form.pdf \
  --data ./data/input/form_keys.json \
  --user-id u1 --pdf-doc-id d1

# Refresh (re-embed) an existing embedded PDF
pdf-mapper refresh --pdf ./data/output/u1/d1/blank_form_embedded.pdf

# View help
pdf-mapper --help
pdf-mapper run-all --help
```

---

## 4. API Server

### Start the server

```bash
# Via installed command
pdf-mapper-server

# Via uvicorn directly (auto-reload for dev)
uvicorn entrypoints.fastapi_app:app --reload --port 8000

# Custom port
PORT=9000 pdf-mapper-server

# Production (multi-worker)
uvicorn entrypoints.fastapi_app:app --host 0.0.0.0 --port 8000 --workers 4
```

Server starts at: **http://localhost:8000**
Interactive API docs: **http://localhost:8000/docs**

---

## 5. API Endpoint Reference & Testing

### `GET /health` — Health check

```bash
curl http://localhost:8000/health
```

```json
{"status": "ok", "version": "1.0.6"}
```

---

### `POST /mapper/extract` — Extract fields from PDF

```bash
curl -s -X POST http://localhost:8000/mapper/extract \
  -H "Content-Type: application/json" \
  -d '{
    "pdf_path": "./data/input/blank_form.pdf",
    "user_id": "u1",
    "pdf_doc_id": "d1"
  }' | python3 -m json.tool
```

---

### `POST /mapper/map` — Map fields to schema (LLM)

```bash
curl -s -X POST http://localhost:8000/mapper/map \
  -H "Content-Type: application/json" \
  -d '{"user_id": "u1", "pdf_doc_id": "d1"}' \
  | python3 -m json.tool
```

---

### `POST /mapper/embed` — Embed mapping into PDF

```bash
curl -s -X POST http://localhost:8000/mapper/embed \
  -H "Content-Type: application/json" \
  -d '{
    "pdf_path": "./data/input/blank_form.pdf",
    "user_id": "u1",
    "pdf_doc_id": "d1"
  }' | python3 -m json.tool
```

---

### `POST /mapper/make-embed` — Extract + Map + Embed in one call

```bash
curl -s -X POST http://localhost:8000/mapper/make-embed \
  -H "Content-Type: application/json" \
  -d '{
    "pdf_path": "./data/input/blank_form.pdf",
    "user_id": "u1",
    "pdf_doc_id": "d1",
    "investor_type": "Individual",
    "use_second_mapper": true
  }' | python3 -m json.tool
```

---

### `POST /mapper/fill` — Fill embedded PDF with data

```bash
curl -s -X POST http://localhost:8000/mapper/fill \
  -H "Content-Type: application/json" \
  -d '{
    "pdf_path": "./data/output/u1/d1/blank_form_embedded.pdf",
    "user_id": "u1",
    "pdf_doc_id": "d1",
    "input_data": {
      "full_name": "Alice Johnson",
      "email": "alice@example.com"
    }
  }' | python3 -m json.tool
```

---

### `POST /mapper/fill-pdf` — Fill with flat form data (used by chatbot/doc-upload)

```bash
curl -s -X POST http://localhost:8000/mapper/fill-pdf \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "u1",
    "session_id": "sess_abc",
    "pdf_doc_id": "d1",
    "use_profile_info": true
  }' | python3 -m json.tool
```

---

### `POST /mapper/check-embed-file` — Check if PDF has embeddings ready

```bash
curl -s -X POST http://localhost:8000/mapper/check-embed-file \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "u1",
    "pdf_doc_id": "d1",
    "investor_type": "Individual"
  }' | python3 -m json.tool
```

---

### `POST /mapper/run-all` — Full pipeline in one call

```bash
curl -s -X POST http://localhost:8000/mapper/run-all \
  -H "Content-Type: application/json" \
  -d '{
    "pdf_path": "./data/input/blank_form.pdf",
    "data_path": "./configs/form_keys.json",
    "user_id": "u1",
    "pdf_doc_id": "d1"
  }' | python3 -m json.tool
```

---

### With API key auth (when `MAPPER_API_KEY` is set)

```bash
curl -s -X POST http://localhost:8000/mapper/extract \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-mapper-api-key" \
  -d '{"pdf_path": "./blank_form.pdf", "user_id": "u1", "pdf_doc_id": "d1"}' \
  | python3 -m json.tool
```

---

### All endpoints summary

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Health check |
| `/mapper/extract` | POST | Extract form fields from PDF |
| `/mapper/map` | POST | LLM mapping of fields to schema |
| `/mapper/embed` | POST | Embed mapping metadata into PDF |
| `/mapper/fill` | POST | Fill embedded PDF with data |
| `/mapper/make-embed` | POST | Extract + Map + Embed (one call) |
| `/mapper/fill-pdf` | POST | Fill with profile data (chatbot/doc-upload integration) |
| `/mapper/check-embed-file` | POST | Check embed readiness |
| `/mapper/run-all` | POST | Full pipeline |

---

## 6. FastAPI — Mount in Existing App

```python
from fastapi import FastAPI
from entrypoints.fastapi_app import app as mapper_app

main_app = FastAPI()
main_app.mount("/mapper", mapper_app)
# Routes now at: POST /mapper/extract, POST /mapper/run-all, etc.
```

---

## 7. Cloud Entrypoints

### AWS Lambda

```python
from pdf_autofillr_mapper.entrypoints.aws_lambda import handler
# Deploy handler as your Lambda function handler
```

Required Lambda env vars:
```
OPENAI_API_KEY=sk-...
AWS_OUTPUT_BUCKET=my-mapper-output
AWS_CONFIG_BUCKET=my-mapper-config
AWS_REGION=us-east-1
MAPPER_API_KEY=your-secret     # optional auth
```

### Azure Functions

```python
from pdf_autofillr_mapper.entrypoints.azure_function import main
# Register main as your Azure Functions HTTP trigger
```

Required app settings:
```
OPENAI_API_KEY, AZURE_STORAGE_CONNECTION_STRING
```

### GCP Cloud Functions

```python
from pdf_autofillr_mapper.entrypoints.gcp_function import handler
```

Deploy:
```bash
gcloud functions deploy mapper \
  --runtime python311 \
  --trigger-http \
  --entry-point handler \
  --source .
```

---

## 8. From Source — Dev Mode

```bash
git clone https://github.com/yourorg/pdf-autofillr-mapper.git
cd pdf-autofillr-mapper

python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install with API server + dev deps
pip install -e ".[api,dev]"

# Copy sample configs
python -c "import pdf_autofillr_mapper; pdf_autofillr_mapper.copy_sample_configs('.')"

# Set up env
cp configs/.env.mapper.example .env
# Edit .env: set OPENAI_API_KEY=sk-your-actual-key
# Edit configs/mapper_config.ini: set paths

# Run API server with auto-reload
uvicorn entrypoints.fastapi_app:app --reload --port 8000

# Or use the CLI
pdf-mapper run-all \
  --pdf data/input/blank_form.pdf \
  --data configs/form_keys.json \
  --user-id u1 --pdf-doc-id d1
```

---

## 9. Run Tests

```bash
pip install "pdf-autofillr-mapper[dev]"
# or from source: pip install -e ".[dev]"

# Run all tests
pytest tests/ -v

# Run specific test files
pytest tests/test_extract.py -v
pytest tests/test_map.py -v
pytest tests/test_fill.py -v
pytest tests/test_pipeline.py -v
pytest tests/test_embed.py -v

# With coverage
pytest tests/ --cov=src/pdf_autofillr_mapper --cov-report=term-missing

# Stop on first failure
pytest tests/ -v -x
```

---

## 10. Docker

```bash
# Build
docker build -t pdf-mapper .

# Run — local storage
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=sk-your-key \
  --env-file .env \
  pdf-mapper

# Run — with config volume mounted
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=sk-your-key \
  -v /local/configs:/app/configs \
  -v /local/data:/app/data \
  pdf-mapper

# Run — AWS mode
docker run -p 8000:8000 \
  -e OPENAI_API_KEY=sk-your-key \
  -e AWS_OUTPUT_BUCKET=my-mapper-output \
  -e AWS_CONFIG_BUCKET=my-mapper-config \
  -e AWS_REGION=us-east-1 \
  pdf-mapper

curl http://localhost:8000/health
```

### docker-compose example

```yaml
version: "3.8"
services:
  mapper:
    build: .
    ports:
      - "8000:8000"
    environment:
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      MAPPER_API_KEY: ${MAPPER_API_KEY}
    volumes:
      - ./configs:/app/configs
      - ./data:/app/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

---

## 11. Configuration Reference

Configuration lives in two places: `.env` (secrets) and `configs/mapper_config.ini` (settings).

### `.env` — API keys and credentials

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | OpenAI key (for `gpt-4o` etc.) |
| `ANTHROPIC_API_KEY` | Anthropic key (for Claude models) |
| `AZURE_API_KEY` | Azure OpenAI key |
| `AZURE_API_BASE` | Azure OpenAI endpoint URL |
| `MAPPER_API_KEY` | When set, all API endpoints require `X-API-Key` header |
| `AWS_ACCESS_KEY_ID` | AWS credentials (or use IAM role) |
| `AWS_SECRET_ACCESS_KEY` | AWS credentials |
| `AWS_REGION_NAME` | AWS region (default: `us-east-1`) |

### `configs/mapper_config.ini` — Main configuration

```ini
[general]
source_type = local          # local | aws | azure | gcp

[mapping]
llm_model = gpt-4o           # any LiteLLM model string
use_second_mapper = false    # run a second LLM pass for verification

[local]
cache_registry_path = ./data/mapper/cache/hash_registry.json
output_base_path    = ./data/mapper/output

[aws]
output_bucket = my-mapper-output
config_bucket = my-mapper-config
region        = us-east-1

[rag]
enabled = false              # true = integrate with pdf-autofillr-rag
mode    = inprocess          # inprocess | http
api_url =                    # only when mode=http
api_key =                    # only when mode=http
```

### Server

| Variable | Default | Description |
|---|---|---|
| `PORT` | `8000` | API server port |
| `HOST` | `0.0.0.0` | API server host |
| `MAPPER_LOG_LEVEL` | `info` | Uvicorn log level |

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'fastapi'`**
```bash
pip install "pdf-autofillr-mapper[api]"
```

**`No API key found` / LLM errors**
```bash
export OPENAI_API_KEY=sk-your-actual-key
```

**`config_samples not found`**
```bash
pip install --force-reinstall pdf-autofillr-mapper
python -c "import pdf_autofillr_mapper; pdf_autofillr_mapper.copy_sample_configs('.')"
```

**Java utils not working (PDF embedding)**
The mapper uses Java JARs for PDF field embedding. Ensure Java 11+ is installed:
```bash
java -version
```

**Configs not found after pip install**
```bash
python -c "import pdf_autofillr_mapper; pdf_autofillr_mapper.copy_sample_configs('.')"
# Edit ./configs/mapper_config.ini with your paths
```