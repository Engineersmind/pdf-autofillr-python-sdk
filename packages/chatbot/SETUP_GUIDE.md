# chatbot Module — Setup Guide

Complete configuration reference before running the API server or CLI.

---

## Minimum Setup (Local, Data-Only)

Five steps to get running locally with no PDF filling:

```bash
# 1. Copy env template
cd modules/chatbot
cp .env.example .env

# 2. Add your OpenAI key
echo "OPENAI_API_KEY=sk-your-key-here" >> .env

# 3. Install dependencies
pip install -r requirements.txt
pip install -r requirements-api.txt

# 4. Start server
python api_server.py

# 5. Test it
curl http://localhost:8001/health
```

---

## Required Environment Variables

### Core (always required)

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | OpenAI API key — used for GPT-4o-mini extraction |

### Storage

| Variable | Default | Description |
|---|---|---|
| `chatbot_STORAGE` | `local` | `local` or `s3` |
| `chatbot_DATA_PATH` | `./data/chatbot` | Root directory for session data (local mode) |
| `chatbot_CONFIG_PATH` | `./config_samples` | Path to form config JSON files |

### AWS S3 (only when `chatbot_STORAGE=s3`)

| Variable | Description |
|---|---|
| `AWS_OUTPUT_BUCKET` | S3 bucket for session/output data |
| `AWS_CONFIG_BUCKET` | S3 bucket for form config JSON files |
| `AWS_REGION` | AWS region (default: `us-east-1`) |
| `AWS_ACCESS_KEY_ID` | AWS credentials — or use IAM role / `AWS_PROFILE` |
| `AWS_SECRET_ACCESS_KEY` | AWS credentials |

### PDF Filler

| Variable | Default | Description |
|---|---|---|
| `chatbot_PDF_FILLER` | `none` | `none` \| `mapper` \| `managed` |
| `chatbot_PDF_PATH` | _(empty)_ | Path to blank PDF — required when filler != none |

#### Mapper mode (`chatbot_PDF_FILLER=mapper`)

| Variable | Default | Description |
|---|---|---|
| `MAPPER_API_URL` | `http://localhost:8000` | Base URL of the mapper API server |
| `MAPPER_URL_PREFIX` | `/mapper` | Route prefix. Use `/mapper` for `api_server.py`, empty for `fastapi_app.py` |
| `MAPPER_API_KEY` | _(empty)_ | API key for mapper server (if auth enabled) |

#### Managed mode (`chatbot_PDF_FILLER=managed`)

Requires the private `chatbot-managed` package.

| Variable | Description |
|---|---|
| `AUTH0_DOMAIN` | Auth0 tenant domain |
| `AUTH0_CLIENT_ID` | Auth0 M2M client ID |
| `AUTH0_CLIENT_SECRET` | Auth0 M2M client secret |
| `AUTH0_AUDIENCE` | Auth0 API audience |
| `FILL_PDF_LAMBDA_URL` | URL of the PDF filling Lambda |
| `PDF_API_KEY` | API key for the Lambda |

---

## Form Config Files

The chatbot needs a set of JSON config files describing the form fields.
`config_samples/` contains a full working example for an investment subscription agreement.

| File | Description |
|---|---|
| `form_keys.json` | All fields in the form (nested JSON structure) |
| `meta_form_keys.json` | Field metadata (type, label per field) |
| `mandatory.json` | Flat dict of mandatory field keys |
| `field_questions.json` | Custom question text per field |
| `form_keys_label.json` | Human-readable labels per flat key |
| `global_investor_type_keys/form_keys_{type}.json` | Per-investor-type field subsets |

Point to your own config files with:
```bash
chatbot_CONFIG_PATH=/path/to/your/configs
```

---

## Environment Configurations

### Local Development (default)

```bash
# .env
OPENAI_API_KEY=sk-your-key-here
chatbot_STORAGE=local
chatbot_DATA_PATH=./data/chatbot
chatbot_CONFIG_PATH=./config_samples
chatbot_PDF_FILLER=none
```

### Local + Mapper PDF Filling

```bash
# .env — chatbot module
OPENAI_API_KEY=sk-your-key-here
chatbot_PDF_FILLER=mapper
chatbot_PDF_PATH=./data/input/blank_subscription.pdf
MAPPER_API_URL=http://localhost:8000
MAPPER_URL_PREFIX=/mapper

# Start mapper first (separate terminal):
#   cd ../mapper && python api_server.py
```

### AWS Production

```bash
# .env
OPENAI_API_KEY=sk-your-key-here
chatbot_STORAGE=s3
AWS_OUTPUT_BUCKET=my-chatbot-output-bucket
AWS_CONFIG_BUCKET=my-chatbot-config-bucket
AWS_REGION=us-east-1
# Credentials via IAM role on EC2/ECS (no keys needed)

chatbot_PDF_FILLER=mapper
chatbot_PDF_PATH=s3://my-pdf-bucket/blank_form.pdf
MAPPER_API_URL=http://mapper-service.internal:8000
MAPPER_URL_PREFIX=/mapper
```

### Docker

```bash
docker build -t chatbot-module .

# Local
docker run -p 8001:8001 \
  -e OPENAI_API_KEY=sk-... \
  chatbot-module

# With mapper
docker run -p 8001:8001 \
  -e OPENAI_API_KEY=sk-... \
  -e chatbot_PDF_FILLER=mapper \
  -e chatbot_PDF_PATH=/data/blank.pdf \
  -e MAPPER_API_URL=http://mapper:8000 \
  -v /local/pdfs:/data \
  chatbot-module
```

---

## Telemetry (opt-in)

Telemetry is **disabled by default**. Field values are never sent — only counts, latencies, and state transitions.

```bash
chatbot_TELEMETRY=true
chatbot_TELEMETRY_MODE=local         # local | self_hosted | managed
chatbot_TELEMETRY_ENDPOINT=http://localhost:9000/events
chatbot_SDK_API_KEY=chatbot_tel_...
```

---

## Rate Limiting (opt-in)

Rate limiting is **disabled by default**.

```bash
chatbot_RATE_LIMIT_ENABLED=true
chatbot_RATE_LIMIT_STORAGE=local      # local | redis
REDIS_URL=redis://localhost:6379
```

Default limits (configurable in code via `RateLimitConfig`):
- 100 messages per session
- 5 sessions per user per day
- 20 LLM calls per session

---

## Troubleshooting

### `EnvironmentError: OPENAI_API_KEY is not set`
```bash
export OPENAI_API_KEY=sk-your-actual-key
# or add to .env
```

### `ModuleNotFoundError: No module named 'fastapi'`
```bash
pip install -r requirements-api.txt
```

### `ModuleNotFoundError: No module named 'chatbot'`
```bash
# Run from modules/chatbot/ root, or set PYTHONPATH:
export PYTHONPATH=/path/to/modules/chatbot
```

### `ImportError: pdf-autofiller-sdk is required`
```bash
# Install mapper SDK from the rv1 repo:
pip install -e ../../modules/mapper/sdks/python/
# or if published:
pip install -r requirements-mapper.txt
```

### Mapper API returns 404 on `/mapper/fill`
Check `MAPPER_URL_PREFIX`:
- Use `MAPPER_URL_PREFIX=/mapper` when using `modules/mapper/api_server.py`
- Use `MAPPER_URL_PREFIX=` (empty) when using `modules/mapper/entrypoints/fastapi_app.py`

### Server starts on wrong port
```bash
PORT=8001 python api_server.py
# or set PORT= in .env
```

---

## File Checklist

Before running:

- [ ] `.env` exists with `OPENAI_API_KEY` set
- [ ] `chatbot_CONFIG_PATH` points to a directory with `form_keys.json`, `mandatory.json`, etc.
- [ ] `requirements.txt` and `requirements-api.txt` installed
- [ ] If `chatbot_PDF_FILLER=mapper`: mapper module is running and `MAPPER_API_URL` is set
- [ ] If `chatbot_STORAGE=s3`: AWS credentials and bucket names configured

**Do NOT commit `.env` to git.**

---

## Summary

**Minimum for local testing:**

```bash
cp .env.example .env
# Add: OPENAI_API_KEY=sk-...
pip install -r requirements.txt requirements-api.txt
python api_server.py
curl http://localhost:8001/health
```
