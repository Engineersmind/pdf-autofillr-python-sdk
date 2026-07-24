# pdf-autofillr-mapper — Complete Usage Guide

> PDF field extraction, semantic mapping, embedding and filling engine. The core engine used by the chatbot and doc-upload modules.

---

## Table of Contents

1. [PyPI Install — Quick Start (for Users)](#1-pypi-install--quick-start-for-users)
2. [Python Library Usage](#2-python-library-usage)
3. [LLM Credentials](#3-llm-credentials)
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
# (see Section 3 — LLM Credentials for all providers and two-phase key setup)

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

## 3. LLM Credentials

The mapper uses two LLM phases internally. Each can use a different model and provider.

| Phase | Purpose | Model setting | Key env var |
|---|---|---|---|
| Phase 1 — Mapping | Semantic field mapping | `[mapping] llm_model` | `MAPPER_LLM_API_KEY` |
| Phase 2 — Headers | Section header detection | `[headers] headers_llm_model` | `MAPPER_HEADERS_LLM_API_KEY` |

### Option A — Universal key overrides (simplest)

```bash
# .env or shell
MAPPER_LLM_API_KEY=sk-your-key           # Phase 1
MAPPER_HEADERS_LLM_API_KEY=sk-your-key  # Phase 2 — leave blank to reuse above
```

### Option B — Provider-specific keys (litellm auto-routes by model name prefix)

```bash
OPENAI_API_KEY=sk-...               # model prefix: openai/ or gpt-
ANTHROPIC_API_KEY=sk-ant-...        # model prefix: anthropic/ or claude-
GROQ_API_KEY=gsk_...                # model prefix: groq/
GEMINI_API_KEY=...                  # model prefix: gemini/
AZURE_API_KEY=...                   # model prefix: azure/
AZURE_API_BASE=https://...          # required alongside AZURE_API_KEY
AWS_ACCESS_KEY_ID=...               # model prefix: bedrock/
AWS_SECRET_ACCESS_KEY=...
# Ollama — no key needed             # model prefix: ollama/
```

### Programmatic config (two phases, different providers)

```python
from pdf_autofillr_mapper import MapperConfig

# Same provider for both phases
cfg = MapperConfig(
    llm_model="openai/gpt-4o",
    llm_api_key="sk-...",
    headers_llm_model="openai/gpt-4o",
    headers_llm_api_key="sk-...",
)

# Different providers — Anthropic for mapping, OpenAI for headers
cfg = MapperConfig(
    llm_model="anthropic/claude-3-5-sonnet-20241022",
    llm_api_key="sk-ant-...",
    headers_llm_model="openai/gpt-4o",
    headers_llm_api_key="sk-...",
)

# Groq (fast, cheap)
cfg = MapperConfig(
    llm_model="groq/llama-3.3-70b-versatile",
    llm_api_key="gsk_...",
    headers_llm_model="groq/llama-3.3-70b-versatile",
)

# Local Ollama — no API key
cfg = MapperConfig(
    llm_model="ollama/llama3.2",
    headers_llm_model="ollama/llama3.2",
)
```

### Validate credentials at startup

```python
cfg = MapperConfig.from_directory("./configs")
cfg.validate()  # prints a warning if no key is found for either phase
```

---

## 4. CLI Usage

```bash
# Extract raw form fields from a PDF (no LLM)
pdf-mapper extract blank_form.pdf
pdf-mapper extract blank_form.pdf -o fields.json

# Map fields to your target schema via LLM — requires the input JSON data
# you're mapping fields against
pdf-mapper map blank_form.pdf --input-json investor_data.json
pdf-mapper map blank_form.pdf --input-json investor_data.json -o mapped.json

# Create an embedded template (extract + map + embed in one step)
# Run once per blank PDF template — result is reused for all fills
pdf-mapper make-embed-file blank_form.pdf -o embedded_form.pdf

# Check if a PDF already has embedded metadata
pdf-mapper check-embed-file blank_form.pdf

# Fill with data from a JSON file
pdf-mapper fill blank_form.pdf -d investor_data.json -o filled_form.pdf

# Full pipeline — extract → map → embed → fill (also needs --input-json)
pdf-mapper run-all blank_form.pdf --input-json investor_data.json -o final_form.pdf

# Control log verbosity
pdf-mapper --log-level DEBUG run-all blank_form.pdf --input-json investor_data.json -o final_form.pdf

# View help
pdf-mapper --help
pdf-mapper run-all --help
```

### CLI subcommands

| Command | Description |
|---|---|
| `extract <pdf>` | Extract raw PDF form fields (no LLM) |
| `map <pdf> --input-json <data.json>` | Map fields to target schema via LLM |
| `make-embed-file <pdf> -o <out>` | Extract + Map + Embed in one step |
| `check-embed-file <pdf>` | Check whether PDF has embedded metadata |
| `fill <pdf> -d <data.json> -o <out>` | Fill form with data from JSON file |
| `run-all <pdf> --input-json <data.json> -o <out>` | Full pipeline: extract → map → embed → fill |

### Common flags

| Flag | Description |
|---|---|
| `-o / --output` | Output file path |
| `-d / --data-file` | JSON file with field data (for `fill`) |
| `--input-json` | Path to input JSON data to map fields against (for `map`, `run-all`) |
| `--mapper-type` | Accepted for compatibility; not currently wired to a mapping-strategy switch — mapping behavior comes from `mapping.ini`/`mapping_config` |
| `--session-id` | Session ID for tracking/caching |
| `--log-level` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |

---

## 4. API Server

### Start the server

```bash
# Via installed command (default port 8000)
pdf-mapper-server

# Via Python directly
python -m pdf_autofillr_mapper.entrypoints.server

# Via uvicorn (dev mode with auto-reload)
uvicorn pdf_autofillr_mapper.entrypoints.fastapi_app:app --reload --port 8000

# Custom port
PORT=9000 pdf-mapper-server

# Production (multi-worker)
uvicorn pdf_autofillr_mapper.entrypoints.fastapi_app:app --host 0.0.0.0 --port 8000 --workers 4
```

Server starts at: **http://localhost:8000**
Interactive API docs: **http://localhost:8000/docs**

### Authentication

If `MAPPER_API_KEY` is set in the environment, every request must include:

```
X-API-Key: your-api-key
```

Leave `MAPPER_API_KEY` blank to disable authentication (development).

Server starts at: **http://localhost:8000**
Interactive API docs: **http://localhost:8000/docs**

---

## 5. API Endpoint Reference & Testing

### `GET /health` — Health check

```bash
curl http://localhost:8000/health
```

```json
{"status": "ok", "version": "1.0.11"}
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

## 7. FastAPI — Mount in Existing App

```python
from fastapi import FastAPI
from pdf_autofillr_mapper.entrypoints.fastapi_app import app as mapper_app

main_app = FastAPI()
main_app.mount("/mapper", mapper_app)
# Routes now at: POST /mapper/extract, POST /mapper/fill-pdf, etc.
```

---

## 8. Cloud Entrypoints

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

## 9. From Source — Dev Mode

```bash
git clone https://github.com/yourorg/pdf-autofillr-mapper.git
cd pdf-autofillr-mapper

python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install with API server + dev deps
pip install -e ".[server,dev]"

# Copy sample configs
python -c "import pdf_autofillr_mapper; pdf_autofillr_mapper.copy_sample_configs('.')"

# Set up env
cp configs/.env.mapper.example .env
# Edit .env: set OPENAI_API_KEY=sk-your-actual-key
# Edit configs/mapper_config.ini: set paths

# Run API server with auto-reload
uvicorn pdf_autofillr_mapper.entrypoints.fastapi_app:app --reload --port 8000

# Or use the CLI
pdf-mapper run-all blank_form.pdf -o filled_form.pdf
```

---

## 10. Run Tests

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

## 11. Docker

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

## 12. Configuration Reference

Configuration lives in two places: `.env` (secrets) and `configs/mapper_config.ini` (settings).

### `.env` — API keys and credentials

**LLM — Phase 1 (Mapping)**

| Variable | Description |
|---|---|
| `MAPPER_LLM_API_KEY` | Universal key for Phase 1 (overrides provider-specific keys) |
| `MAPPER_LLM_MODEL` | LiteLLM model string for semantic mapping (default: `gpt-4o`) |

**LLM — Phase 2 (Headers)**

| Variable | Description |
|---|---|
| `MAPPER_HEADERS_LLM_API_KEY` | Universal key for Phase 2 (blank = reuse `MAPPER_LLM_API_KEY`) |
| `MAPPER_HEADERS_LLM_MODEL` | LiteLLM model string for header detection (default: `gpt-4o`) |

**Provider-specific keys (auto-detected by litellm)**

| Variable | Provider | Model prefix |
|---|---|---|
| `OPENAI_API_KEY` | OpenAI | `openai/`, `gpt-`, `o1`, `o3` |
| `ANTHROPIC_API_KEY` | Anthropic | `anthropic/`, `claude-` |
| `GROQ_API_KEY` | Groq | `groq/` |
| `GEMINI_API_KEY` | Google Gemini | `gemini/` |
| `AZURE_API_KEY` + `AZURE_API_BASE` | Azure OpenAI | `azure/` |
| `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` | AWS Bedrock | `bedrock/` |
| _(none)_ | Ollama (local) | `ollama/` |

**Server & storage**

| Variable | Description |
|---|---|
| `MAPPER_API_KEY` | When set, all API endpoints require `X-API-Key` header |
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

**`UserWarning: No API key found for mapping model 'gpt-4o'`**
```bash
# Option A — universal override
export MAPPER_LLM_API_KEY=sk-your-key

# Option B — provider-specific
export OPENAI_API_KEY=sk-your-key
```

**`UserWarning: No API key found for headers model 'gpt-4o'`**
```bash
# Leave MAPPER_HEADERS_LLM_API_KEY blank to reuse MAPPER_LLM_API_KEY
# Or set it explicitly:
export MAPPER_HEADERS_LLM_API_KEY=sk-your-key
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