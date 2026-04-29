"""
Mapper — call via REST API.

Start the server first:
    pdf-mapper-server               # default port 8000
    PORT=8000 pdf-mapper-server

Requires: pip install httpx
"""

import json
import httpx

BASE = "http://localhost:8000"
HEADERS = {}  # add {"X-API-Key": "your-key"} if MAPPER_API_KEY is set on the server

# ─────────────────────────────────────────────────────────────────────────────
# Health check
# ─────────────────────────────────────────────────────────────────────────────
print(httpx.get(f"{BASE}/health").json())
# → {"status": "healthy", "service": "pdf-mapper"}


# ─────────────────────────────────────────────────────────────────────────────
# Step 1 — Extract: get raw fields from a PDF
# ─────────────────────────────────────────────────────────────────────────────
r = httpx.post(f"{BASE}/extract", headers=HEADERS, json={
    "pdf_path": "data/input/blank_form.pdf",
    "session_id": "session_001",
})
r.raise_for_status()
print("Extract:", json.dumps(r.json(), indent=2))


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — Map: LLM maps raw fields to your target schema
# ─────────────────────────────────────────────────────────────────────────────
r = httpx.post(f"{BASE}/map", headers=HEADERS, json={
    "pdf_path": "data/input/blank_form.pdf",
    "session_id": "session_001",
    "mapper_type": "ensemble",   # semantic | headers | rag | ensemble
}, timeout=120)
r.raise_for_status()
print("Map:", json.dumps(r.json(), indent=2))


# ─────────────────────────────────────────────────────────────────────────────
# Step 3 — Make embed file: extract + map + embed in one call
# (run once per blank PDF template — result is reused for all fills)
# ─────────────────────────────────────────────────────────────────────────────
r = httpx.post(f"{BASE}/make-embed-file", headers=HEADERS, json={
    "user_id": 1,
    "pdf_doc_id": 101,
    "session_id": "session_001",
    "env": "Local_user",
    "investor_type": "Individual",
    "use_second_mapper": False,
}, timeout=180)
r.raise_for_status()
print("Make embed file:", r.json())


# ─────────────────────────────────────────────────────────────────────────────
# Step 4 — Fill: inject investor data into the embedded PDF
# ─────────────────────────────────────────────────────────────────────────────
r = httpx.post(f"{BASE}/fill-pdf", headers=HEADERS, json={
    "user_id": 1,
    "pdf_doc_id": 101,
    "session_id": "session_001",
    "env": "Local_user",
}, timeout=60)
r.raise_for_status()
print("Fill:", r.json())


# ─────────────────────────────────────────────────────────────────────────────
# Utility — Check embed file (was a PDF already embedded?)
# ─────────────────────────────────────────────────────────────────────────────
r = httpx.post(f"{BASE}/check-embed-file", headers=HEADERS, json={
    "user_id": 1,
    "pdf_doc_id": 101,
    "session_id": "session_001",
    "env": "Local_user",
})
r.raise_for_status()
print("Embed status:", r.json())
