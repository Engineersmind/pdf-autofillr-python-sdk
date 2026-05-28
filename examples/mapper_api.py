"""
PDF Mapper — unified REST API client.

Combines:
  - JSON-based REST flow  (extract → map → make-embed-file → fill-pdf)
  - File-upload shorthand (embed + fill in fewer calls)

Start the server first:
    pdf-mapper-server               # default port 8000
    PORT=8000 pdf-mapper-server

Requires: pip install httpx
"""

import json

import httpx

BASE = "http://localhost:8000"
HEADERS: dict[str, str] = (
    {}
)  # add {"X-API-Key": "your-key"} if MAPPER_API_KEY is set on the server

PDF_PATH = "data/input/blank_form.pdf"
USER_ID = 1
PDF_DOC_ID = 101
SESSION_ID = "session_001"
ENV = "Local_user"

# ─────────────────────────────────────────────────────────────────────────────
# Health check
# ─────────────────────────────────────────────────────────────────────────────
resp = httpx.get(f"{BASE}/health", headers=HEADERS)
resp.raise_for_status()
print("Health:", resp.json())
# → {"status": "healthy", "service": "pdf-mapper"}


# ─────────────────────────────────────────────────────────────────────────────
# APPROACH A — JSON REST flow (full pipeline)
# Use when: the PDF is already on the server's filesystem.
# ─────────────────────────────────────────────────────────────────────────────

# Step 1 — Extract: pull raw fields from the blank PDF
resp = httpx.post(
    f"{BASE}/extract",
    headers=HEADERS,
    json={
        "pdf_path": PDF_PATH,
        "session_id": SESSION_ID,
    },
)
resp.raise_for_status()
print("Extract:", json.dumps(resp.json(), indent=2))

# Step 2 — Map: LLM maps raw fields to your target schema
resp = httpx.post(
    f"{BASE}/map",
    headers=HEADERS,
    json={
        "pdf_path": PDF_PATH,
        "session_id": SESSION_ID,
        "mapper_type": "ensemble",  # semantic | headers | rag | ensemble
    },
    timeout=120,
)
resp.raise_for_status()
print("Map:", json.dumps(resp.json(), indent=2))

# Step 3 — Make embed file: extract + map + embed in one call
# Run once per blank PDF template — the result is reused for every fill.
resp = httpx.post(
    f"{BASE}/make-embed-file",
    headers=HEADERS,
    json={
        "user_id": USER_ID,
        "pdf_doc_id": PDF_DOC_ID,
        "session_id": SESSION_ID,
        "env": ENV,
        "investor_type": "Individual",
        "use_second_mapper": False,
    },
    timeout=180,
)
resp.raise_for_status()
print("Make embed file:", resp.json())

# Step 4 — Fill: inject investor data into the embedded PDF
resp = httpx.post(
    f"{BASE}/fill-pdf",
    headers=HEADERS,
    json={
        "user_id": USER_ID,
        "pdf_doc_id": PDF_DOC_ID,
        "session_id": SESSION_ID,
        "env": ENV,
    },
    timeout=60,
)
resp.raise_for_status()
print("Fill (JSON flow):", resp.json())


# ─────────────────────────────────────────────────────────────────────────────
# APPROACH B — File-upload shorthand (embed + fill)
# Use when: the PDF lives on the client and must be streamed to the server.
# ─────────────────────────────────────────────────────────────────────────────

# Step B1 — Embed: upload the blank PDF and register it server-side
with open(PDF_PATH, "rb") as f:
    resp = httpx.post(
        f"{BASE}/embed",
        headers=HEADERS,
        files={"pdf": f},
        data={
            "user_id": str(USER_ID),
            "pdf_doc_id": str(PDF_DOC_ID),
        },
    )
resp.raise_for_status()
print("Embed (upload flow):", resp.json())

# Step B2 — Fill: upload the same blank PDF + supply investor data as JSON
with open(PDF_PATH, "rb") as f:
    resp = httpx.post(
        f"{BASE}/fill",
        headers=HEADERS,
        files={"pdf": f},
        data={
            "user_id": str(USER_ID),
            "pdf_doc_id": str(PDF_DOC_ID),
            "user_data": json.dumps(
                {
                    "investor_name": "Jane Smith",
                    "commitment_amount": "500000",
                }
            ),
        },
        timeout=60,
    )
resp.raise_for_status()
print("Fill (upload flow):", resp.json())


# ─────────────────────────────────────────────────────────────────────────────
# Utility — Check embed status (was this PDF already embedded?)
# ─────────────────────────────────────────────────────────────────────────────
resp = httpx.post(
    f"{BASE}/check-embed-file",
    headers=HEADERS,
    json={
        "user_id": USER_ID,
        "pdf_doc_id": PDF_DOC_ID,
        "session_id": SESSION_ID,
        "env": ENV,
    },
)
resp.raise_for_status()
print("Embed status:", resp.json())
