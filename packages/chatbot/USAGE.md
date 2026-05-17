# pdf-autofillr-chatbot — Complete Usage Guide

> Conversational investor onboarding chatbot. Collects investor data through natural language and fills PDF subscription forms automatically.

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
pip install pdf-autofillr-chatbot

# With API server support
pip install "pdf-autofillr-chatbot[server]"

# With AWS S3 storage
pip install "pdf-autofillr-chatbot[s3]"

# Everything
pip install "pdf-autofillr-chatbot[all]"
```

### First-time setup (run once after install)

```bash
# 1. Copy sample config files into your working directory
python -c "import chatbot; chatbot.copy_sample_configs('.')"
# → Creates ./configs/ with all required JSON files

# 2. Create your .env file
# Download .env.example from the repo, or create manually:
cat > .env << 'EOF'
CHATBOT_LLM_MODEL=openai/gpt-4o-mini
OPENAI_API_KEY=sk-your-key-here

chatbot_STORAGE=local
chatbot_DATA_PATH=./data/chatbot
chatbot_CONFIG_PATH=./configs

chatbot_PDF_FILLER=none
chatbot_PDF_PATH=

chatbot_LOG_LEVEL=INFO
chatbot_DEBUG_LOGGING=false
EOF
```

### Run

```bash
chatbot-cli         # interactive terminal session
chatbot-server      # REST API on http://localhost:8001
```

---

## 2. Python Library Usage

### Minimal — data collection only

```python
from chatbot import chatbotClient, FormConfig
from chatbot.storage.local_storage import LocalStorage

client = chatbotClient(
    storage=LocalStorage("./data/chatbot", "./configs"),
    form_config=FormConfig.from_directory("./configs"),
    # api_key is optional — reads CHATBOT_LLM_API_KEY or OPENAI_API_KEY from env
)

# First turn: send empty string to get the greeting
response, complete, data = client.send_message(
    user_id="investor_123",
    session_id="session_abc",
    message="",
)
print(response)  # → "Hi! I am here to help you fill out your investment documents..."

# Continue the conversation
while not complete:
    user_input = input("You: ")
    response, complete, data = client.send_message("investor_123", "session_abc", user_input)
    print(f"Bot: {response}")

# data is a flat dict of all collected fields
print("Collected data:", data)
```

### With PDF filling (in-process mapper)

```python
from chatbot import chatbotClient, FormConfig
from chatbot.storage.local_storage import LocalStorage
from chatbot.pdf.mapper_filler import MapperPDFFiller

client = chatbotClient(
    storage=LocalStorage("./data/chatbot", "./configs"),
    form_config=FormConfig.from_directory("./configs"),
    pdf_filler=MapperPDFFiller(
        mapper_api_url="",           # empty = in-process (no separate server needed)
        mapper_api_key="",
        config_dir="./configs",
    ),
)

# Associate a blank PDF at session start
client.create_session(
    user_id="investor_123",
    session_id="session_abc",
    pdf_path="./data/input/blank_form.pdf",
)

response, complete, data = client.send_message("investor_123", "session_abc", "")
# ... conversation loop ...
```

### With PDF filling (mapper HTTP server mode)

```python
pdf_filler = MapperPDFFiller(
    mapper_api_url="http://localhost:8000",   # mapper server URL
    mapper_api_key="",
    config_dir="./configs",
)
```

### Session management

```python
# List all sessions for a user
sessions = client.list_sessions("investor_123")

# Get final data for a completed session
data = client.get_session_data("investor_123", "session_abc")

# Get fill report (stats on how many fields were filled)
report_text = client.get_fill_report_text("investor_123", "session_abc")
print(report_text)

# Delete a session
client.delete_session("investor_123", "session_abc")
```

### With S3 storage

```python
from chatbot.storage.s3_storage import S3Storage

client = chatbotClient(
    storage=S3Storage(
        output_bucket="my-chatbot-output",
        config_bucket="my-chatbot-config",
    ),
    form_config=FormConfig.from_directory("./configs"),
)
```

### Using a different LLM model

```python
import os
os.environ["CHATBOT_LLM_MODEL"] = "anthropic/claude-3-5-haiku-20241022"
os.environ["ANTHROPIC_API_KEY"] = "sk-ant-..."

# Or groq:
os.environ["CHATBOT_LLM_MODEL"] = "groq/llama-3.1-8b-instant"
os.environ["GROQ_API_KEY"] = "gsk_..."

# Or local ollama (no key needed):
os.environ["CHATBOT_LLM_MODEL"] = "ollama/llama3.1"
```

Supported model prefixes (via LiteLLM): `openai/`, `anthropic/`, `groq/`, `gemini/`, `azure/`, `bedrock/`, `vertex_ai/`, `ollama/`

---

## 3. CLI Usage

```bash
# Interactive session (default)
chatbot-cli

# With a PDF to fill
chatbot-cli --pdf-path ./data/input/blank_form.pdf

# Save collected data to a JSON file
chatbot-cli --output ./filled_data.json

# Print fill statistics report at the end
chatbot-cli --report

# Tag the session with specific IDs
chatbot-cli --user-id investor_123 --session-id session_abc

# Single message (non-interactive, for scripting)
chatbot-cli --message "My name is John Smith" --user-id u1 --session-id s1

# All options together
chatbot-cli \
  --user-id investor_123 \
  --session-id session_abc \
  --pdf-path ./blank_form.pdf \
  --output ./filled_data.json \
  --report \
  --log-level INFO
```

### CLI flags

| Flag | Default | Description |
|---|---|---|
| `--user-id` | `cli_user` | User identifier |
| `--session-id` | _(auto UUID)_ | Session identifier |
| `--message` | _(interactive)_ | Send a single message and exit |
| `--pdf-path` | _(from .env)_ | Path to blank PDF |
| `--output` | _(none)_ | Save filled data to JSON file |
| `--report` | off | Print fill statistics at end |
| `--log-level` | `WARNING` | Logging level for terminal |

---

## 4. API Server

### Start the server

```bash
# Via installed command
chatbot-server

# Or via Python directly
python -m chatbot.entrypoints.server

# Or via uvicorn (dev mode with auto-reload)
uvicorn chatbot.entrypoints.fastapi_app:app --reload --port 8001

# Custom port
PORT=9000 chatbot-server

# Production (multi-worker)
uvicorn chatbot.entrypoints.fastapi_app:app --host 0.0.0.0 --port 8001 --workers 4
```

Server starts at: **http://localhost:8001**
Interactive API docs: **http://localhost:8001/docs**

### Mount into your existing FastAPI app

```python
from fastapi import FastAPI
from chatbot.entrypoints.fastapi_app import app as chatbot_app

main_app = FastAPI()
main_app.mount("/onboarding", chatbot_app)
# chatbot routes now live at /onboarding/chat, /onboarding/session/..., etc.
```

---

## 5. API Endpoint Reference & Testing

### `GET /health` — Health check

```bash
curl http://localhost:8001/health
```

```json
{
  "status": "ok",
  "version": "0.3.0",
  "storage": "local",
  "pdf_filler": "none"
}
```

---

### `POST /chatbot/chat` — Send a message

```bash
# Turn 1: empty message to get the greeting
curl -s -X POST http://localhost:8001/chatbot/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id":"u1","session_id":"s1","message":""}' \
  | python3 -m json.tool

# Turn 2: respond to the bot
curl -s -X POST http://localhost:8001/chatbot/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id":"u1","session_id":"s1","message":"My name is Alice Johnson"}' \
  | python3 -m json.tool

# With a PDF (first turn only)
curl -s -X POST http://localhost:8001/chatbot/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id":"u1",
    "session_id":"s1",
    "message":"",
    "pdf_path":"./data/input/blank_form.pdf"
  }' | python3 -m json.tool
```

**Request body:**

| Field | Type | Required | Description |
|---|---|---|---|
| `user_id` | string | ✅ | Unique investor identifier |
| `session_id` | string | ✅ | Unique session identifier |
| `message` | string | — | User's message. Send `""` on first turn to get the greeting |
| `pdf_path` | string | — | Path to blank PDF. Only needed on first turn |

**Response:**

```json
{
  "user_id": "u1",
  "session_id": "s1",
  "response": "Hi! I am here to help you fill out your investment documents...",
  "session_complete": false,
  "filled_data": null
}
```

When `session_complete` is `true`, `filled_data` contains all collected fields:

```json
{
  "session_complete": true,
  "filled_data": {
    "full_name": "Alice Johnson",
    "email": "alice@example.com",
    "address_registered.address_registered_country_id": "USA"
  }
}
```

---

### `GET /chatbot/session/{user_id}/{session_id}` — Get completed session data

```bash
curl http://localhost:8001/chatbot/session/u1/s1 | python3 -m json.tool
```

Returns `404` if session doesn't exist or hasn't completed yet.

---

### `GET /chatbot/session/{user_id}/{session_id}/fill-report` — Fill statistics

```bash
# JSON format (default)
curl "http://localhost:8001/chatbot/session/u1/s1/fill-report" | python3 -m json.tool

# Human-readable text
curl "http://localhost:8001/chatbot/session/u1/s1/fill-report?format=text" | python3 -m json.tool
```

---

### `DELETE /chatbot/session/{user_id}/{session_id}` — Delete session

```bash
curl -X DELETE http://localhost:8001/chatbot/session/u1/s1
```

---

### Full conversation via curl (copy-paste script)

```bash
BASE="http://localhost:8001"
USER="investor_123"
SESSION="session_$(date +%s)"

echo "=== Turn 1: Greeting ==="
curl -s -X POST $BASE/chatbot/chat \
  -H "Content-Type: application/json" \
  -d "{\"user_id\":\"$USER\",\"session_id\":\"$SESSION\",\"message\":\"\"}" \
  | python3 -m json.tool

echo "=== Turn 2: Investor type ==="
curl -s -X POST $BASE/chatbot/chat \
  -H "Content-Type: application/json" \
  -d "{\"user_id\":\"$USER\",\"session_id\":\"$SESSION\",\"message\":\"Individual\"}" \
  | python3 -m json.tool

echo "=== Turn 3: Name ==="
curl -s -X POST $BASE/chatbot/chat \
  -H "Content-Type: application/json" \
  -d "{\"user_id\":\"$USER\",\"session_id\":\"$SESSION\",\"message\":\"My name is Alice Johnson\"}" \
  | python3 -m json.tool
```

### Full conversation via Python (httpx)

```python
import httpx

BASE = "http://localhost:8001"
USER = "investor_123"
SESSION = "session_abc"

def send(message: str) -> dict:
    r = httpx.post(f"{BASE}/chatbot/chat", json={
        "user_id": USER,
        "session_id": SESSION,
        "message": message,
    })
    r.raise_for_status()
    return r.json()

data = send("")
print(f"Bot: {data['response']}")

while not data["session_complete"]:
    msg = input("You: ")
    data = send(msg)
    print(f"Bot: {data['response']}")

print("\nSession complete!")
print("Filled data:", data["filled_data"])

# Fetch fill report
r = httpx.get(f"{BASE}/chatbot/session/{USER}/{SESSION}/fill-report?format=text")
print(r.json()["report"])
```

---

## 6. FastAPI — Mount in Existing App

### Option A — Use the pre-built app (bare routes: `/chat`, `/session/...`)

```python
from fastapi import FastAPI
from chatbot.entrypoints.fastapi_app import app as chatbot_app

main_app = FastAPI()
main_app.mount("/onboarding", chatbot_app)
# Routes: POST /onboarding/chat, GET /onboarding/session/{uid}/{sid}, etc.
```

### Option B — Use `api_server.py` routes (prefixed: `/chatbot/chat`, `/chatbot/session/...`)

After `pip install "pdf-autofillr-chatbot[server]"`, the `api_server.py` file (included in the package) has all routes under `/chatbot/` prefix.

```bash
# Run it directly
uvicorn chatbot.entrypoints.fastapi_app:app --port 8001

# Or use the chatbot-server command
chatbot-server
```

---

## 7. Cloud Entrypoints

### AWS Lambda

```python
# lambda_function.py
from chatbot.entrypoints.aws_lambda import handler
# Deploy handler as your Lambda function — it's a drop-in handler
```

```bash
# Deploy with SAM or serverless
pip install "pdf-autofillr-chatbot[s3]"
# Set env vars in Lambda: CHATBOT_LLM_API_KEY, chatbot_STORAGE=s3, AWS_OUTPUT_BUCKET, etc.
```

### Azure Functions

```python
from chatbot.entrypoints.azure_function import main
# Register main as your Azure Function HTTP trigger
```

### GCP Cloud Functions

```python
from chatbot.entrypoints.gcp_function import chatbot_function
# Register chatbot_function as your GCP HTTP function
```

---

## 8. From Source — Dev Mode

```bash
# Clone repo and enter the chatbot module
git clone https://github.com/yourorg/pdf-autofillr-chatbot.git
cd pdf-autofillr-chatbot

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install in editable mode with all dev dependencies
# IMPORTANT: use pyproject.toml, NOT requirements.txt (requirements.txt has stale deps)
pip install -e ".[server,dev]"

# Copy sample configs
python -c "import chatbot; chatbot.copy_sample_configs('.')"

# Set up .env
cp .env.example .env
# Edit .env: set OPENAI_API_KEY=sk-your-actual-key

# Run the API server with auto-reload
uvicorn api_server:app --reload --port 8001

# Or run the CLI
chatbot-cli
```

> **Note:** When installing from source, always use `pip install -e ".[server,dev]"` from `pyproject.toml`. The `requirements.txt` file has a known stale dep (`langchain-openai`) — the code uses `litellm` which is correctly listed in `pyproject.toml`.

---

## 9. Run Tests

```bash
# Install dev dependencies first
pip install "pdf-autofillr-chatbot[dev]"
# or from source: pip install -e ".[dev]"

# Run all unit tests (fast, no network, no API calls)
pytest tests/unit/ -v

# Run integration tests (uses TestClient, no real server needed)
pytest tests/integration/ -v

# Run everything
pytest -v

# With coverage report
pytest tests/unit/ --cov=src/chatbot --cov-report=term-missing

# Run a specific test file
pytest tests/unit/test_engine.py -v
pytest tests/unit/test_extraction.py -v
pytest tests/unit/test_session.py -v

# Run only fast unit tests (marked)
pytest -m unit -v

# Run with verbose output and stop on first failure
pytest tests/unit/ -v -x
```

---

## 10. Docker

### Build

```bash
docker build -t chatbot-module .
```

### Run — local storage, data-only (no PDF filling)

```bash
docker run -p 8001:8001 \
  -e OPENAI_API_KEY=sk-your-key \
  chatbot-module
```

### Run — from .env file

```bash
docker run -p 8001:8001 --env-file .env chatbot-module
```

### Run — with mapper PDF filling

```bash
docker run -p 8001:8001 \
  -e OPENAI_API_KEY=sk-your-key \
  -e chatbot_PDF_FILLER=mapper \
  -e chatbot_PDF_PATH=/data/blank_form.pdf \
  -e MAPPER_API_URL=http://mapper-service:8000 \
  -v /local/path/to/pdfs:/data \
  chatbot-module
```

### Run — with S3 storage

```bash
docker run -p 8001:8001 \
  -e OPENAI_API_KEY=sk-your-key \
  -e chatbot_STORAGE=s3 \
  -e AWS_OUTPUT_BUCKET=my-chatbot-output \
  -e AWS_CONFIG_BUCKET=my-chatbot-config \
  -e AWS_REGION=us-east-1 \
  chatbot-module
```

### Health check

```bash
curl http://localhost:8001/health
```

### docker-compose example

```yaml
version: "3.8"
services:
  chatbot:
    image: chatbot-module
    build: .
    ports:
      - "8001:8001"
    environment:
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      chatbot_STORAGE: local
      chatbot_DATA_PATH: /data/chatbot
      chatbot_PDF_FILLER: none
      chatbot_LOG_LEVEL: INFO
    volumes:
      - ./data:/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

---

## 11. Configuration Reference

All config is via environment variables or `.env` file.

### LLM

| Variable | Default | Description |
|---|---|---|
| `CHATBOT_LLM_MODEL` | `openai/gpt-4o-mini` | LiteLLM model string |
| `CHATBOT_LLM_API_KEY` | — | Universal API key override |
| `OPENAI_API_KEY` | — | OpenAI key (auto-detected for `openai/` models) |
| `ANTHROPIC_API_KEY` | — | Anthropic key (auto-detected for `anthropic/` models) |
| `GROQ_API_KEY` | — | Groq key (auto-detected for `groq/` models) |
| `AZURE_API_KEY` | — | Azure key (also set `AZURE_API_BASE`) |
| `GEMINI_API_KEY` | — | Google Gemini key |

### Storage

| Variable | Default | Description |
|---|---|---|
| `chatbot_STORAGE` | `local` | `local`, `s3`, `gcp`, or `azure` |
| `chatbot_DATA_PATH` | `./data/chatbot` | Local session data directory |
| `chatbot_CONFIG_PATH` | `./configs` | Form config JSON files directory |

### PDF Filling

| Variable | Default | Description |
|---|---|---|
| `chatbot_PDF_FILLER` | `none` | `none`, `mapper`, or `custom` |
| `chatbot_PDF_PATH` | — | Path to blank PDF (required when filler != none) |
| `MAPPER_API_URL` | — | Mapper server URL. Leave empty for in-process mode |
| `MAPPER_API_KEY` | — | Mapper API key (if auth enabled) |

### Server & Logging

| Variable | Default | Description |
|---|---|---|
| `PORT` | `8001` | API server port |
| `HOST` | `0.0.0.0` | API server host |
| `chatbot_LOG_LEVEL` | `INFO` | Log level |
| `chatbot_DEBUG_LOGGING` | `false` | Enable verbose debug logs |

### AWS S3 (`chatbot_STORAGE=s3`)

| Variable | Description |
|---|---|
| `AWS_OUTPUT_BUCKET` | S3 bucket for session data |
| `AWS_CONFIG_BUCKET` | S3 bucket for config JSON files |
| `AWS_REGION` | AWS region (default: `us-east-1`) |
| `AWS_ACCESS_KEY_ID` | AWS credentials (or use IAM role) |
| `AWS_SECRET_ACCESS_KEY` | AWS credentials |

### GCP (`chatbot_STORAGE=gcp`)

| Variable | Description |
|---|---|
| `GCP_OUTPUT_BUCKET` | GCS bucket for session data |
| `GCP_CONFIG_BUCKET` | GCS bucket for config JSON files |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to service account JSON |

### Azure (`chatbot_STORAGE=azure`)

| Variable | Description |
|---|---|
| `AZURE_STORAGE_CONNECTION_STRING` | Azure Storage connection string |
| `AZURE_OUTPUT_CONTAINER` | Container for session data |
| `AZURE_CONFIG_CONTAINER` | Container for config files |

---

## Troubleshooting

**`EnvironmentError: No API key found for model 'openai/gpt-4o-mini'`**
```bash
export OPENAI_API_KEY=sk-your-actual-key
# or add to .env
```

**`ModuleNotFoundError: No module named 'fastapi'`**
```bash
pip install "pdf-autofillr-chatbot[server]"
```

**`ModuleNotFoundError: No module named 'chatbot'`**
```bash
# You're running from source without installing. Either:
pip install -e ".[server]"
# or set PYTHONPATH:
export PYTHONPATH=/path/to/chatbot/src
```

**`ModuleNotFoundError: No module named 'litellm'`**
```bash
# requirements.txt has a known stale entry. Install directly:
pip install litellm
# Or better: always install via pyproject.toml:
pip install "pdf-autofillr-chatbot"
```

**`chatbot_PDF_FILLER is set but chatbot_PDF_PATH is missing`**
```bash
# Add to .env:
chatbot_PDF_PATH=./data/input/blank_form.pdf
```

**Configs not found after pip install**
```bash
# Run the copy helper once:
python -c "import chatbot; chatbot.copy_sample_configs('.')"
# Configs are now in ./configs/
```