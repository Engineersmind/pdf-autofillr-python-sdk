# chatbot Module

Conversational investor onboarding chatbot — collects investor data through natural language and fills PDF subscription forms.

## 🚀 Quick Start

### 1. Configure

```bash
cd modules/chatbot
cp .env.example .env
nano .env          # add OPENAI_API_KEY at minimum
```

See **[SETUP_GUIDE.md](SETUP_GUIDE.md)** for full configuration.

### 2. Install Dependencies

```bash
pip install -r requirements.txt
pip install -r requirements-api.txt
```

### 3. Run

```bash
# API server (recommended)
python api_server.py

# Interactive CLI
python -m entrypoints.local

# Or interactively via CLI tool
python -m entrypoints.cli
```

Server: **http://localhost:8001**  
API Docs: **http://localhost:8001/docs**

---

## 📁 Structure

```
modules/chatbot/
├── .env.example              ← Copy to .env — add your API keys
├── api_server.py             ← FastAPI server (run this!)
├── requirements.txt          ← Core dependencies
├── requirements-api.txt      ← FastAPI + uvicorn
├── requirements-mapper.txt   ← PDF mapper connector (optional)
├── requirements-s3.txt       ← AWS S3 storage (optional)
├── requirements-full.txt     ← Everything (used by Docker)
├── pyproject.toml            ← Package metadata
├── Dockerfile                ← Container build
├── SETUP_GUIDE.md            ← Detailed setup
├── API_SERVER.md             ← API endpoint reference
├── entrypoints/
│   ├── local.py              ← Interactive CLI / Python-callable
│   ├── cli.py                ← Command-line interface
│   ├── fastapi_app.py        ← Bare FastAPI app (no /chatbot prefix)
│   └── aws_lambda.py         ← AWS Lambda handler
├── src/chatbot/              ← Core SDK source
│   ├── client.py             ← chatbotClient — main entry point
│   ├── config/               ← Settings, FormConfig
│   ├── core/                 ← Engine, router, session, states (13-state machine)
│   ├── extraction/           ← LLM extractor, fallback, prompt builder
│   ├── handlers/             ← One handler per conversation state
│   ├── limits/               ← Rate limiter
│   ├── logging/              ← Debug logger
│   ├── managed/              ← Stub for private managed PDF service
│   ├── pdf/                  ← PDFFillerInterface, MapperPDFFiller, workflow
│   ├── storage/              ← LocalStorage, S3Storage, StorageBackend
│   ├── telemetry/            ← Opt-in telemetry collector
│   ├── utils/                ← Field utils, address utils, intent detection
│   └── validation/           ← Field + phone validators
├── config_samples/           ← Form config JSON files (10 investor types)
├── tests/
│   ├── conftest.py           ← Shared fixtures
│   ├── unit/                 ← Fast, no I/O tests
│   └── integration/          ← Full-stack tests (TestClient)
└── data/
    ├── input/                ← Place blank PDFs here
    ├── output/               ← Filled PDFs and session data written here
    └── cache/                ← Optional: session cache
```

---

## 🎯 What This Module Does

A 13-state conversation engine that:

1. **Greets** the investor and checks for existing saved data
2. **Asks** the investor to select their type (Individual, Corporation, LLC, Trust, etc.)
3. **Collects** all mandatory fields through natural conversation using GPT-4o-mini extraction
4. **Validates** fields (email, phone format, boolean checks)
5. **Handles** address copy (mailing = registered), boolean groups, sequential fill for stubborn fields
6. **Fills** the blank PDF via the mapper module (optional)
7. **Completes** the session and saves structured JSON output

### Conversation states

| State | Description |
|---|---|
| `INIT` | Greeting, check for existing profile |
| `UPDATE_EXISTING_PROMPT` | Offer to pre-fill from previous session |
| `INVESTOR_TYPE_SELECT` | Choose from 10 investor types |
| `DATA_COLLECTION` | Main loop — LLM extraction per turn |
| `MISSING_FIELDS_PROMPT` | Re-ask skipped mandatory fields |
| `BOOLEAN_GROUP_SELECT` | Handle yes/no checkbox groups |
| `SEQUENTIAL_FILL` | One field at a time for stubborn fields |
| `MAILING_ADDRESS_CHECK` | Is mailing same as registered? |
| `CONTINUE_PROMPT` | Mid-session checkpoint |
| `OPTIONAL_FIELDS_PROMPT` | Offer non-mandatory fields |
| `ANOTHER_INFO_PROMPT` | Any corrections before submit? |
| `CONFIRM_AND_SUBMIT` | Final confirmation |
| `COMPLETE` | Session done, outputs saved |

---

## 🔌 PDF Filling

Three modes controlled by `chatbot_PDF_FILLER` env var:

| Mode | Description |
|---|---|
| `none` (default) | Data-only — no PDF filling |
| `mapper` | Connect to the **mapper module** (`modules/mapper/`) via its API |
| `managed` | Private Auth0+Lambda service (requires `chatbot-managed` package) |

For `mapper` mode, start the mapper API server first:
```bash
cd ../mapper
python api_server.py     # runs on port 8000

# Then in modules/chatbot:
chatbot_PDF_FILLER=mapper
MAPPER_API_URL=http://localhost:8000
MAPPER_URL_PREFIX=/mapper
```

---

## 🌐 API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | API info |
| `/health` | GET | Health check |
| `/chatbot/chat` | POST | Send a message |
| `/chatbot/session/{user_id}/{session_id}` | GET | Get completed session data |
| `/chatbot/session/{user_id}/{session_id}/fill-report` | GET | Fill statistics report |
| `/chatbot/session/{user_id}/{session_id}` | DELETE | Delete session |

See **[API_SERVER.md](API_SERVER.md)** for full request/response schemas.

---

## 📦 Using as a Python Library

```python
from src.chatbot import chatbotClient, LocalStorage, FormConfig

client = chatbotClient(
    openai_api_key="sk-...",
    storage=LocalStorage("./chatbot_data", "./config_samples"),
    form_config=FormConfig.from_directory("./config_samples"),
    pdf_filler=None,
)

# Send messages
response, complete, data = client.send_message(
    user_id="investor_123",
    session_id="session_abc",
    message="",
)
print(response)   # → "Hi! I am here to help you fill out..."
```

---

## 🧪 Testing

```bash
# Run all tests
pytest

# Unit tests only (fast, no network)
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v

# With coverage
pytest --cov=src/chatbot --cov-report=term-missing

# A specific test
pytest tests/unit/test_rate_limiter.py -v
```

---

## 🐳 Docker

```bash
docker build -t chatbot-module .
docker run -p 8001:8001 --env-file .env chatbot-module
```

---

## 🔗 Integration with mapper module

```
rv1 repo/
├── modules/
│   ├── mapper/          ← PDF extraction + mapping + filling engine
│   │   └── api_server.py  runs on :8000
│   └── chatbot/         ← This module
│       └── api_server.py  runs on :8001
│           └── MAPPER_API_URL=http://localhost:8000
```

---

## 📚 Documentation

- **[SETUP_GUIDE.md](SETUP_GUIDE.md)** — Configuration reference
- **[API_SERVER.md](API_SERVER.md)** — API endpoint documentation
- **[config_samples/README.md](config_samples/README.md)** — Form config format

---

## Quick Command Reference

```bash
# Setup
cp .env.example .env && nano .env
pip install -r requirements.txt requirements-api.txt

# Run
python api_server.py

# Test
curl http://localhost:8001/health
pytest tests/unit/

# Interactive CLI
python -m entrypoints.local
```
