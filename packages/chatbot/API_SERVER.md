# chatbot API Server

Complete reference for the `api_server.py` FastAPI server.

Base URL: `http://localhost:8001`  
Interactive docs: `http://localhost:8001/docs`

---

## Quick Start

```bash
python api_server.py
curl http://localhost:8001/health
```

---

## Endpoints

### `GET /`
API info and endpoint map.

**Response:**
```json
{
  "name": "chatbot Onboarding API",
  "version": "0.3.0",
  "status": "running",
  "endpoints": { ... }
}
```

---

### `GET /health`
Health check. Returns current storage mode and PDF filler mode.

**Response:**
```json
{
  "status": "ok",
  "version": "0.3.0",
  "storage": "local",
  "pdf_filler": "none"
}
```

---

### `POST /chatbot/chat`
Send one message in a conversation session.

**Request body:**
```json
{
  "user_id": "investor_123",
  "session_id": "session_abc",
  "message": "",
  "pdf_path": "/path/to/blank_form.pdf"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `user_id` | string | ✅ | Unique investor identifier |
| `session_id` | string | ✅ | Unique session identifier |
| `message` | string | — | User's message. Send empty string `""` on first turn to get the greeting |
| `pdf_path` | string | — | Path to blank PDF. Overrides `chatbot_PDF_PATH` env var. Only needed once at session start |

**Response:**
```json
{
  "user_id": "investor_123",
  "session_id": "session_abc",
  "response": "Hi! I am here to help you fill out your investment documents. Have you used this service before?",
  "session_complete": false,
  "filled_data": null
}
```

When `session_complete` is `true`, `filled_data` contains the collected investor data as a flat dict:
```json
{
  "session_complete": true,
  "filled_data": {
    "full_name": "Alice Johnson",
    "email": "alice@alicecapital.com",
    "address_registered.address_registered_country_id": "USA",
    ...
  }
}
```

**Error responses:**
- `400` — missing user_id or session_id
- `429` — rate limit exceeded
- `500` — internal error

---

### `GET /chatbot/session/{user_id}/{session_id}`
Return the final filled data dict for a **completed** session.

**Response:**
```json
{
  "user_id": "investor_123",
  "session_id": "session_abc",
  "data": {
    "full_name": "Alice Johnson",
    "email": "alice@alicecapital.com",
    ...
  }
}
```

Returns `404` if session doesn't exist or is not yet complete.

---

### `GET /chatbot/session/{user_id}/{session_id}/fill-report`
Return fill statistics for a completed session.

**Query params:**
- `format=json` (default) — full report dict
- `format=text` — human-readable text summary

**Response (format=json):**
```json
{
  "user_id": "investor_123",
  "session_id": "session_abc",
  "report": {
    "summary": {
      "investor_type": "Individual",
      "total_fields_in_config": 45,
      "total_fields_filled": 38,
      "mandatory_filled": 18,
      "mandatory_total": 18,
      "optional_filled": 20,
      "optional_total": 27,
      "fill_rate_pct": 84.4,
      "mandatory_fill_rate_pct": 100.0
    },
    "unfilled_optional": ["wiring_details.bank_name", ...]
  }
}
```

**Response (format=text):**
```json
{
  "report": "Fill Report — Individual\n========================\nMandatory: 18/18 (100%)\nOptional: 20/27 (74%)\n..."
}
```

Returns `404` if session not complete.

---

### `DELETE /chatbot/session/{user_id}/{session_id}`
Delete all data for a session (session state, conversation log, outputs).

**Response:**
```json
{
  "deleted": true,
  "user_id": "investor_123",
  "session_id": "session_abc"
}
```

---

## Example: Full Conversation via curl

```bash
BASE="http://localhost:8001"
USER="investor_123"
SESSION="session_$(date +%s)"

# Turn 1: greeting
curl -s -X POST $BASE/chatbot/chat \
  -H "Content-Type: application/json" \
  -d "{\"user_id\": \"$USER\", \"session_id\": \"$SESSION\", \"message\": \"\"}" \
  | python3 -m json.tool

# Turn 2: select investor type
curl -s -X POST $BASE/chatbot/chat \
  -H "Content-Type: application/json" \
  -d "{\"user_id\": \"$USER\", \"session_id\": \"$SESSION\", \"message\": \"1\"}" \
  | python3 -m json.tool

# ... continue conversation ...

# Get final data once complete
curl -s $BASE/chatbot/session/$USER/$SESSION | python3 -m json.tool

# Get fill report
curl -s "$BASE/chatbot/session/$USER/$SESSION/fill-report?format=text" | python3 -m json.tool
```

---

## Example: Python Client

```python
import httpx

BASE = "http://localhost:8001"
USER = "investor_123"
SESSION = "session_abc"

def send(message: str) -> dict:
    resp = httpx.post(f"{BASE}/chatbot/chat", json={
        "user_id": USER,
        "session_id": SESSION,
        "message": message,
    })
    resp.raise_for_status()
    return resp.json()

# Start conversation
data = send("")
print(data["response"])

while not data["session_complete"]:
    msg = input("You: ")
    data = send(msg)
    print(f"Bot: {data['response']}")

print("Session complete!")
print(data["filled_data"])
```

---

## Running Options

```bash
# Default (port 8001)
python api_server.py

# Custom port
PORT=9000 python api_server.py

# With uvicorn directly (auto-reload for development)
uvicorn api_server:app --reload --port 8001

# Production (multiple workers)
uvicorn api_server:app --host 0.0.0.0 --port 8001 --workers 4

# Docker
docker run -p 8001:8001 --env-file .env chatbot-module
```

---

## Route Prefix Notes

`api_server.py` uses `/chatbot/` prefix for all endpoints (e.g. `POST /chatbot/chat`).

If you need bare routes (e.g. `POST /chat`), use `entrypoints/fastapi_app.py` instead:
```bash
uvicorn entrypoints.fastapi_app:app --port 8001
```
