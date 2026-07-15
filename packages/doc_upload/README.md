# pdf-autofillr-doc-upload

Extract structured data from any document format using an LLM, then optionally fill a blank PDF via the mapper module.

## Supported document formats

| Format | Extension |
|--------|-----------|
| PDF | `.pdf` |
| Word | `.docx` |
| PowerPoint | `.pptx` |
| Excel | `.xlsx`, `.xls` |
| CSV | `.csv` |
| JSON | `.json` |
| Markdown | `.md`, `.markdown` |
| Plain text | `.txt` |
| HTML | `.html`, `.htm` |
| XML | `.xml` |

## Supported LLM providers (via LiteLLM)

Any model LiteLLM supports — OpenAI, Anthropic, Groq, Ollama, AWS Bedrock, Azure OpenAI, Google Vertex AI, and more.

---

## Installation

```bash
# Step 1 — create venv
python -m venv venv
.\venv\Scripts\activate   # Windows
# source venv/bin/activate  # Linux/Mac

# Step 2 — install litellm (pinned)
pip install "litellm==1.59.12" --no-cache-dir

# Step 3 — install mapper (from sibling modules3/mapper/)
pip install -e ../mapper --no-cache-dir --no-deps
pip install PyMuPDF tiktoken pydantic pydantic-settings python-dotenv tenacity requests aiohttp httpx numpy tqdm python-json-logger --no-cache-dir

# Step 4 — install extractor
pip install -e . --no-cache-dir --no-deps
pip install python-docx python-pptx openpyxl --no-cache-dir

# Verify
python -c "import pdf_autofillr_doc_upload; print('extractor ok')"
python -c "import pdf_autofillr_mapper; print('mapper ok')"
```

---

## Setup

### 1. Copy sample configs
```bash
python -c "import pdf_autofillr_doc_upload; pdf_autofillr_doc_upload.copy_sample_configs('.')"
```

### 2. Create `.env`
```bash
cp .env.example .env
# Edit .env — set DOC_UPLOAD_LLM_MODEL and DOC_UPLOAD_LLM_API_KEY at minimum
```

Minimal `.env`:
```env
DOC_UPLOAD_LLM_MODEL=openai/gpt-4.1-mini
DOC_UPLOAD_LLM_API_KEY=sk-...
DOC_UPLOAD_STORAGE=local
DOC_UPLOAD_DATA_PATH=./extractor_data
DOC_UPLOAD_CONFIG_PATH=./configs
# Required to run the FastAPI server — see "FastAPI server" below.
AUTH_TOKEN=change-me-to-a-long-random-secret
```

---

## Running

### Interactive local runner
```bash
python -m entrypoints.local
```

### Non-interactive (single document)
```bash
python -m entrypoints.local --document investor.pdf --schema configs/form_keys.json --output output/filled.json
```

### CLI
```bash
doc-upload-cli --document investor.pdf --schema configs/form_keys.json --output filled.json --report
```

### FastAPI server
```bash
doc-upload-server
# or
uvicorn entrypoints.fastapi_app:app --reload --port 8001
```

**Authentication is required.** Set `AUTH_TOKEN` to a strong secret before
starting the server — every request must send it as the `X-API-Key` header,
or the server responds with a config error. (For local-only experimentation
you can instead set `DOC_UPLOAD_ALLOW_INSECURE_NO_AUTH=true`, but never do
this in a deployment reachable by anyone else.)

Then POST to `http://localhost:8001/extract`:
```json
{
  "document_path": "/path/to/investor_profile.pdf",
  "schema_path": "configs/form_keys.json"
}
```
with header `X-API-Key: <your AUTH_TOKEN>`.

`document_path` and `schema_path` must resolve inside `DOC_UPLOAD_DATA_PATH`,
`DOC_UPLOAD_CONFIG_PATH`, or a directory listed in
`DOC_UPLOAD_ALLOWED_DOCUMENT_ROOTS` (comma-separated). Paths outside those
directories — including via `..` traversal or symlinks — are rejected with
HTTP 400. If your documents live somewhere else (e.g. an uploads folder),
add that folder to `DOC_UPLOAD_ALLOWED_DOCUMENT_ROOTS` rather than removing
the restriction.

---

## Storage backends

| Value | Description |
|-------|-------------|
| `local` | Local filesystem (default, for dev) |
| `s3` | AWS S3 |
| `gcp` | Google Cloud Storage |
| `azure` | Azure Blob Storage |

Set `DOC_UPLOAD_STORAGE=s3` and the matching bucket env vars.

---

## PDF Filling (mapper integration)

Set `DOC_UPLOAD_PDF_FILLER=mapper` and the Lambda URL:

```env
DOC_UPLOAD_PDF_FILLER=mapper
DOC_UPLOAD_FILL_PDF_LAMBDA_URL=https://xyz.lambda-url.us-east-1.on.aws
DOC_UPLOAD_PDF_API_KEY=my-api-key
```

The client runs extraction and embed-file preparation **in parallel**, then calls `fill_pdf` once both complete — identical to the Lambda `main.py` pipeline.

---

## Telemetry

| Value | Description |
|-------|-------------|
| `off` | Disabled (default, zero overhead) |
| `local` | Append events to `./extractor_telemetry/events.jsonl` |
| `managed` | (stub) HTTP POST to `DOC_UPLOAD_TELEMETRY_ENDPOINT` |

Field values are **never** included in telemetry. Only metadata (counts, latencies, file extensions) is logged. Job IDs are one-way SHA-256 hashed.

---

## Entrypoints

| File | Use case |
|------|----------|
| `entrypoints/local.py` | Interactive development REPL |
| `entrypoints/cli.py` | `doc-upload-cli` command |
| `entrypoints/server.py` | `doc-upload-server` (uvicorn) |
| `entrypoints/fastapi_app.py` | FastAPI app (mount or standalone) |
| `entrypoints/aws_lambda.py` | AWS Lambda handler |
| `entrypoints/gcp_function.py` | GCP Cloud Functions handler |
| `entrypoints/azure_function.py` | Azure Functions handler |

---

## Programmatic API

```python
from pdf_autofillr_doc_upload import DocUploadClient

client = DocUploadClient()

# Extract only
result = client.run(
    document_path="investor_profile.pdf",
    schema_path="configs/form_keys.json",
    output_path="output/filled.json",
)

print(result["output_flat"])   # flat dot-notation dict
print(result["output_nested"]) # nested dict matching schema

# Extract + fill PDF
result = client.run(
    document_path="investor_profile.pdf",
    schema_path="configs/form_keys.json",
    user_id="42",
    pdf_doc_id="99",
    session_id="sess_abc",
    investor_type="Individual",
)
```

---

## Module structure

```
extractor/
├── pyproject.toml
├── .env.example
├── README.md
├── config_samples/
│   └── form_keys.json
├── entrypoints/
│   ├── local.py             ← interactive REPL
│   ├── cli.py               ← doc-upload-cli
│   ├── server.py            ← doc-upload-server
│   ├── fastapi_app.py       ← FastAPI app
│   ├── aws_lambda.py        ← AWS Lambda
│   ├── gcp_function.py      ← GCP Cloud Functions
│   └── azure_function.py    ← Azure Functions
└── src/pdf_autofillr_doc_upload/
    ├── __init__.py
    ├── client.py            ← DocUploadClient (main API)
    ├── config/
    │   └── settings.py      ← all env var config
    ├── storage/
    │   ├── base.py          ← abstract interface
    │   ├── local_storage.py
    │   ├── s3_storage.py
    │   ├── gcp_storage.py
    │   ├── azure_storage.py
    │   └── factory.py
    ├── extraction/
    │   ├── document_reader.py  ← PDF/DOCX/PPTX/XLSX/CSV/JSON/MD/HTML/XML
    │   ├── llm_client.py       ← LiteLLM wrapper
    │   └── extractor.py        ← full pipeline
    ├── pdf/
    │   ├── interface.py
    │   ├── api_handler.py      ← HTTP client for Lambda
    │   └── mapper_filler.py    ← mapper integration
    ├── logging/
    │   └── logger.py           ← ExecutionLogger
    ├── telemetry/
    │   ├── collector.py
    │   └── config.py
    └── managed/
        └── __init__.py         ← stub for future managed service
```
