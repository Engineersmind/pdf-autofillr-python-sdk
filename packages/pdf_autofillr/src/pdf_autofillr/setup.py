# pdf_autofillr/entrypoints/setup.py
from __future__ import annotations

import importlib.resources
import json
import os
import shutil
from pathlib import Path

# ── Package detection ─────────────────────────────────────────────────────────


def _installed(pkg: str) -> bool:
    try:
        __import__(pkg)
        return True
    except ImportError:
        return False


def detect_combo() -> set[str]:
    combo = set()
    if _installed("chatbot"):
        combo.add("chatbot")
    if _installed("pdf_autofillr_doc_upload"):
        combo.add("doc_upload")
    if _installed("pdf_autofillr_mapper"):
        combo.add("mapper")
    if _installed("ragpdf"):
        combo.add("rag")
    return combo


def _config_source() -> Path | None:
    """Find the config_samples directory shipped with chatbot or doc_upload."""
    for pkg_name, _attr in [("chatbot", None), ("pdf_autofillr_doc_upload", None)]:
        try:
            mod = __import__(pkg_name)
            pkg_dir = Path(mod.__file__ or "").parent
            for candidate in ["config_samples", "configs"]:
                p = pkg_dir / candidate
                if p.exists():
                    return p
        except ImportError:
            pass
    return None


# ── Directory creation ────────────────────────────────────────────────────────


def _make_dirs(combo: set[str], dest: Path) -> list[str]:
    created = []
    dirs = ["data/input", "configs"]
    if "chatbot" in combo:
        dirs += ["data/chatbot"]
    if "doc_upload" in combo:
        dirs += ["data/doc_upload/jobs"]
    if "mapper" in combo:
        dirs += ["data/mapper/output", "data/mapper/cache"]
    if "rag" in combo:
        dirs += [
            "data/rag/vectors",
            "data/rag/vectors/source",
            "data/rag/predictions",
            "data/rag/metrics/time_series/global",
            "data/rag/pdf_hash_mapping",
        ]
    for d in dirs:
        p = dest / d
        p.mkdir(parents=True, exist_ok=True)
        created.append(str(p))
    for gk in ["data/input", "data/rag/predictions", "data/rag/metrics"]:
        gkp = dest / gk / ".gitkeep"
        if (dest / gk).exists() and not gkp.exists():
            gkp.touch()
    return created


# ── .env.example content per combo ───────────────────────────────────────────

_ENV_HEADER = """\
# ============================================================
# pdf-autofillr — .env.example
# Combination: {combo_label}
#
# 1. Copy this file:   cp .env.example .env
# 2. Fill in API key   (OPENAI_API_KEY or equivalent)
# 3. Set PDF path      ({pdf_var})
# 4. Run setup again to verify: pdf-autofillr status
# ============================================================

# ── LLM API Keys ─────────────────────────────────────────────
# Uncomment only the block for your provider
OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
# GROQ_API_KEY=gsk_...
# AZURE_API_KEY=
# AZURE_API_BASE=https://your-resource.openai.azure.com/
# AZURE_API_VERSION=2023-05-15
# AWS_ACCESS_KEY_ID=
# AWS_SECRET_ACCESS_KEY=
# AWS_REGION=us-east-1
# GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

# ── System ────────────────────────────────────────────────────
LITELLM_LOG=ERROR
PYTHONIOENCODING=utf-8
PYTHONUTF8=1

"""

_ENV_CHATBOT = """\
# ── CHATBOT ───────────────────────────────────────────────────
CHATBOT_LLM_MODEL=openai/gpt-4o-mini
CHATBOT_LLM_API_KEY=

chatbot_STORAGE=local
chatbot_DATA_PATH=./data/chatbot

# Cloud storage (only set when chatbot_STORAGE != local):
# chatbot_STORAGE=s3
# AWS_OUTPUT_BUCKET=my-chatbot-output
# AWS_CONFIG_BUCKET=my-chatbot-config
# chatbot_STORAGE=gcp
# GCP_OUTPUT_BUCKET=my-chatbot-output
# GCP_CONFIG_BUCKET=my-chatbot-config
# GCP_PROJECT_ID=my-project
# chatbot_STORAGE=azure
# AZURE_OUTPUT_CONTAINER=chatbot-output
# AZURE_CONFIG_CONTAINER=chatbot-config
# AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;...

chatbot_CONFIG_PATH=./configs

# none   = collect data only
# mapper = fill a PDF at end of conversation (requires mapper installed)
chatbot_PDF_FILLER=mapper
chatbot_PDF_PATH=./data/input/blank_form.pdf

chatbot_LOG_LEVEL=WARNING
chatbot_DEBUG_LOGGING=false

"""

_ENV_DOC_UPLOAD = """\
# ── DOC_UPLOAD ────────────────────────────────────────────────
# Supported document formats: pdf, docx, pptx, xlsx, csv, json, md, txt, html, xml
DOC_UPLOAD_LLM_MODEL=openai/gpt-4.1-mini
DOC_UPLOAD_LLM_API_KEY=

DOC_UPLOAD_STORAGE=local
DOC_UPLOAD_DATA_PATH=./data/doc_upload

# Cloud storage (only set when DOC_UPLOAD_STORAGE != local):
# DOC_UPLOAD_STORAGE=s3
# AWS_OUTPUT_BUCKET=my-doc-upload-output
# AWS_CONFIG_BUCKET=my-doc-upload-config
# DOC_UPLOAD_STORAGE=gcp
# GCP_OUTPUT_BUCKET=my-doc-upload-output
# GCP_CONFIG_BUCKET=my-doc-upload-config
# GCP_PROJECT_ID=my-project
# DOC_UPLOAD_STORAGE=azure
# AZURE_OUTPUT_CONTAINER=doc-upload-output
# AZURE_CONFIG_CONTAINER=doc-upload-config
# AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;...

DOC_UPLOAD_CONFIG_PATH=./configs

# none   = extract data only, return JSON
# mapper = extract + fill a blank PDF
DOC_UPLOAD_PDF_FILLER=mapper
DOC_UPLOAD_PDF_PATH=./data/input/blank_form.pdf

DOC_UPLOAD_TELEMETRY=off
# DOC_UPLOAD_TELEMETRY=local     -> writes metadata to ./telemetry/events.jsonl
# DOC_UPLOAD_TELEMETRY_PATH=./telemetry

DOC_UPLOAD_LOG_LEVEL=WARNING
DOC_UPLOAD_DEBUG_LOGGING=false

"""

_ENV_MAPPER = """\
# ── MAPPER ────────────────────────────────────────────────────
# Most mapper settings are in configs/mapper_config.ini (non-secret)
# Secrets only here.

# Mapper HTTP server auth (only needed when MAPPER_API_URL is set above)
MAPPER_API_KEY=

"""

_ENV_MAPPER_CONNECTION = """\
# ── MAPPER CONNECTION ─────────────────────────────────────────
# How chatbot/doc_upload connects to the mapper
# Empty = inprocess (mapper runs inside the same Python process — easiest)
# Set URL = HTTP mode (mapper running as a separate server)
MAPPER_API_URL=
MAPPER_API_KEY=

"""

_ENV_RAG = """\
# ── MAPPER -> RAG INTEGRATION ─────────────────────────────────
# RAG_ENABLED=true activates RAG. Mapper calls RAG after every mapping run.
# The vector DB ships with 137 real LP Subscription Agreement vectors and
# grows automatically as more forms are filled.
RAG_ENABLED=true
RAG_MODE=inprocess
RAG_API_URL=
RAG_API_KEY=

# ── RAG STORAGE ───────────────────────────────────────────────
RAGPDF_STORAGE=local
RAGPDF_DATA_PATH=./data/rag

# Cloud RAG storage (only set when RAGPDF_STORAGE != local):
# RAGPDF_STORAGE=s3
# RAGPDF_S3_BUCKET=my-rag-bucket
# RAGPDF_S3_REGION=us-east-1
# RAGPDF_S3_PREFIX=ragpdf/
# RAGPDF_STORAGE=azure
# RAGPDF_AZURE_ACCOUNT=mystorageaccount
# RAGPDF_AZURE_CONTAINER=ragpdf
# RAGPDF_AZURE_CONN_STR=DefaultEndpointsProtocol=https;...
# RAGPDF_STORAGE=gcs
# RAGPDF_GCS_BUCKET=my-rag-bucket
# RAGPDF_GCS_PREFIX=ragpdf/

# ── RAG EMBEDDINGS ────────────────────────────────────────────
# IMPORTANT: the bundled vector_database.json was built with OpenAI
# text-embedding-3-small (1536 dim). This MUST match — do not change
# to sentence_transformer without rebuilding the vector DB.
RAGPDF_EMBEDDING_BACKEND=openai
RAGPDF_OPENAI_EMBEDDING_MODEL=text-embedding-3-small
# RAGPDF_LITELLM_EMBEDDING_MODEL=openai/text-embedding-3-small

# ── RAG VECTOR STORE ──────────────────────────────────────────
RAGPDF_VECTOR_STORE=local
# PINECONE_API_KEY=pc-...
# RAGPDF_PINECONE_INDEX=ragpdf-vectors
# RAGPDF_PINECONE_NAMESPACE=default
# RAGPDF_CHROMA_PATH=./data/chroma
# RAGPDF_CHROMA_COLLECTION=ragpdf_vectors
# RAGPDF_WEAVIATE_URL=http://localhost:8080
# RAGPDF_WEAVIATE_API_KEY=
# RAGPDF_WEAVIATE_CLASS=RagpdfVector

# ── RAG LLM CORRECTOR ─────────────────────────────────────────
RAGPDF_CORRECTOR_BACKEND=noop
# RAGPDF_OPENAI_MODEL=gpt-4o-mini
# RAGPDF_OPENAI_TEMPERATURE=0.3
# RAGPDF_ANTHROPIC_MODEL=claude-3-5-haiku-20241022
# RAGPDF_LITELLM_CORRECTOR_MODEL=openai/gpt-4o-mini

# ── RAG PREDICTION TUNING ─────────────────────────────────────
RAGPDF_PREDICTION_THRESHOLD=0.75
RAGPDF_TOP_K=5
RAGPDF_AMBIGUITY_THRESHOLD=0.10
RAGPDF_CONFIDENCE_DECAY_RATE=0.95
RAGPDF_CONFIDENCE_GROWTH_RATE=1.05
RAGPDF_MAX_CONFIDENCE=0.99
RAGPDF_MIN_CONFIDENCE=0.50

# ── RAG SERVER (only when RAG_MODE=http) ──────────────────────
RAGPDF_API_KEY=dev-key
# RAGPDF_SERVER_HOST=0.0.0.0
# RAGPDF_SERVER_PORT=8000

RAGPDF_LOG_LEVEL=WARNING

"""


def build_env_example(combo: set[str]) -> str:
    has_chatbot = "chatbot" in combo
    has_doc = "doc_upload" in combo
    has_rag = "rag" in combo

    label = " + ".join(sorted(combo)) or "standalone"
    pdf_var = "chatbot_PDF_PATH" if has_chatbot else "DOC_UPLOAD_PDF_PATH"

    content = _ENV_HEADER.format(combo_label=label, pdf_var=pdf_var)

    if has_chatbot:
        content += _ENV_CHATBOT
    if has_doc:
        content += _ENV_DOC_UPLOAD
    if "mapper" in combo:
        if has_chatbot or has_doc:
            content += _ENV_MAPPER_CONNECTION
        else:
            content += _ENV_MAPPER
    if has_rag:
        content += _ENV_RAG

    return content


# ── mapper_config.ini content ─────────────────────────────────────────────────


def build_mapper_ini(combo: set[str]) -> str:
    has_rag = "rag" in combo
    rag_section = (
        """
[rag]
# Set enabled=true AND RAG_ENABLED=true in .env to activate RAG
enabled = true
mode = inprocess
api_url =
api_key =
"""
        if has_rag
        else """
[rag]
# RAG is not in your installed combination.
# To add: pip install "pdf-autofillr[chatbot,rag]" and re-run pdf-autofillr setup
enabled = false
"""
    )
    return f"""\
# pdf-autofillr-mapper configuration
# Non-secret settings only. API keys go in .env.
# Combination: {" + ".join(sorted(combo))}

[general]
source_type = local
pdf_cache_enabled = true

[headers]
headers_llm_model = gpt-4o
headers_llm_provider = openai
headers_openai_model_id = gpt-4o
headers_claude_model_id = claude-3-5-sonnet-20241022
headers_temperature = 0.0
headers_max_tokens = 8192
headers_chunk_size = 5
headers_max_workers = 3

[mapping]
llm_model = gpt-4o
llm_temperature = 0.0
llm_max_tokens = 4096
llm_timeout = 120
llm_max_retries = 3
confidence_threshold = 0.7
chunking_strategy = page
chunking_chunk_size = 9
chunking_overlap = 1
include_description = 1
use_second_mapper = false

[local]
output_base_path = ./data/mapper/output
cache_registry_path = ./data/mapper/cache/hash_registry.json
temp_local_dir = /tmp

[aws]
output_base_path = s3://YOUR_BUCKET/mapper/output
cache_registry_path = s3://YOUR_BUCKET/mapper/cache/hash_registry.json
temp_local_dir = /tmp

[azure]
output_base_path = azure://YOUR_CONTAINER/mapper/output
cache_registry_path = azure://YOUR_CONTAINER/mapper/cache/hash_registry.json
temp_local_dir = /tmp

[gcp]
output_base_path = gs://YOUR_BUCKET/mapper/output
cache_registry_path = gs://YOUR_BUCKET/mapper/cache/hash_registry.json
temp_local_dir = /tmp

[notifications]
teams_notifications_enabled = false
teams_webhook_url =
{rag_section}"""


# ── README_QUICKSTART.md ──────────────────────────────────────────────────────


def build_quickstart(combo: set[str]) -> str:
    label = " + ".join(sorted(combo)) or "standalone"
    has_chatbot = "chatbot" in combo
    has_doc = "doc_upload" in combo
    has_rag = "rag" in combo

    folder_lines = [
        "```",
        "data/",
        "├── input/",
        "│   └── blank_form.pdf   <- PUT YOUR BLANK PDF HERE",
    ]
    if has_chatbot:
        folder_lines += [
            "├── chatbot/",
            "│   └── {user_id}/sessions/{session_id}/",
            "│       ├── final_output_flat.json   <- all collected fields",
            "│       ├── fill_report.json          <- which fields were filled",
            "│       └── filled.pdf                <- the filled PDF",
        ]
    if has_doc:
        folder_lines += [
            "├── doc_upload/",
            "│   └── jobs/{job_id}/",
            "│       ├── output_flat.json   <- extracted fields",
            "│       └── filled.pdf         <- the filled PDF",
        ]
    if "mapper" in combo:
        folder_lines += [
            "├── mapper/",
            "│   ├── output/{user_id}/pdfs/{pdf_id}/",
            "│   │   ├── blank_form_extracted.json",
            "│   │   ├── blank_form_mapped.json",
            "│   │   └── blank_form_filled.pdf",
            "│   └── cache/hash_registry.json",
        ]
    if has_rag:
        folder_lines += [
            "└── rag/",
            "    ├── vectors/vector_database.json   <- grows automatically",
            "    ├── predictions/{user_id}/{session_id}/{pdf_id}/",
            "    └── metrics/time_series/",
        ]
    folder_lines.append("```")

    next_steps = []
    if has_chatbot:
        next_steps.append(
            "- **Start chatbot:** `chatbot-server` or `python api_server.py` in chatbot/"
        )
    if has_doc:
        next_steps.append(
            "- **Start doc_upload:** `doc-upload-server` or `python entrypoints/fastapi_app.py` in doc_upload/"
        )
    if "mapper" in combo and not has_chatbot and not has_doc:
        next_steps.append(
            "- **Start mapper:** `pdf-mapper-server` or `python api_server.py` in mapper/"
        )
    if has_rag:
        next_steps.append("- **Start RAG server (HTTP mode):** `ragpdf-server` in rag/")

    return f"""\
# pdf-autofillr Quickstart
**Combination:** {label}

## 1. Configure
```bash
cp .env.example .env
# Edit .env:
#   Set your API key (OPENAI_API_KEY or equivalent)
#   Set the path to your blank PDF form
```

## 2. Drop your blank PDF
```
data/input/blank_form.pdf
```
This is the empty PDF form that will be filled with investor data.

## 3. Folder structure
{chr(10).join(folder_lines)}

## 4. Start
{chr(10).join(next_steps)}

## Key files
| File | Purpose |
|------|---------|
| `.env` | All secrets and runtime config |
| `configs/form_keys.json` | Your field schema — defines all fillable fields |
| `configs/mapper_config.ini` | Mapper LLM model, chunking, storage, RAG toggle |
| `data/input/blank_form.pdf` | The blank PDF to fill |

## Connections
{'- chatbot -> mapper: inprocess by default (set MAPPER_API_URL to use HTTP mode)' if has_chatbot else ''}
{'- doc_upload -> mapper: inprocess by default (set MAPPER_API_URL to use HTTP mode)' if has_doc else ''}
{'- mapper -> rag: set RAG_ENABLED=true in .env and [rag] enabled=true in mapper_config.ini' if has_rag else ''}

## Docs
- chatbot/README.md
- doc_upload/README.md
- mapper/README.md
- rag/README.md
"""


# ── RAG data helpers ──────────────────────────────────────────────────────────


def _write_json(path: str, data, force: bool = False):
    if os.path.exists(path) and not force:
        print(f"  skip     {path}  (exists)")
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"  created  {path}")


def _load_bundled_vector_db() -> dict:
    """
    Load the real vector_database.json bundled with the ragpdf package.

    137 vectors, 1536-dim OpenAI text-embedding-3-small embeddings.
    These are real semantic embeddings — cosine similarity works from day one.
    Falls back to empty DB if the ragpdf package is not installed yet.
    """
    # Try via ragpdf package data (preferred)
    try:
        pkg_files = importlib.resources.files("ragpdf")
        db_file = pkg_files / "data" / "vector_database.json"
        with db_file.open("r", encoding="utf-8") as f:
            data = json.load(f)
        n = len(data.get("vectors", []))
        print(
            f"  loaded   bundled vector_database.json  ({n} vectors, 1536-dim OpenAI)"
        )
        return data
    except Exception:
        pass

    # Fallback: __file__ path (editable installs)
    try:
        import ragpdf as pkg_mod

        pkg_dir = os.path.dirname(pkg_mod.__file__)
        db_path = os.path.join(pkg_dir, "data", "vector_database.json")
        if os.path.exists(db_path):
            with open(db_path, encoding="utf-8") as f:
                data = json.load(f)
            n = len(data.get("vectors", []))
            print(
                f"  loaded   bundled vector_database.json  ({n} vectors, 1536-dim OpenAI)"
            )
            return data
    except Exception:
        pass

    print(
        "  warning  ragpdf bundled vector_database.json not found — starting with empty vector DB"
    )
    print("           Predictions accumulate automatically after the first form fill.")
    return {"metadata": {"total_count": 0, "last_updated": ""}, "vectors": []}


def _create_ragpdf_data(combo: set[str], dest: Path, force: bool = False):
    """Create data/rag/ directory structure with real sample vectors."""
    if "rag" not in combo:
        return

    base = str(dest / "data" / "rag")

    # Folder skeleton already created by _make_dirs — just write files
    _write_json(
        f"{base}/input/fields/lp_subscription_fields.json",
        [
            {
                "field_id": "f001",
                "field_name": "Investor Name",
                "context": "Full legal name of the investor as it appears on government-issued identification",
                "section_context": "Investor Identity",
                "headers": ["Section 1", "Personal Information"],
            },
            {
                "field_id": "f002",
                "field_name": "Email",
                "context": "Email address for all fund correspondence and legal notices",
                "section_context": "Contact Details",
                "headers": ["Section 2", "Contact"],
            },
            {
                "field_id": "f003",
                "field_name": "Tax ID / SSN / EIN",
                "context": "Social Security Number or Employer Identification Number for tax reporting purposes",
                "section_context": "Tax Information",
                "headers": ["Section 3", "Tax Details"],
            },
            {
                "field_id": "f004",
                "field_name": "Commitment Amount",
                "context": "Total capital commitment amount in United States dollars",
                "section_context": "Investment Details",
                "headers": ["Section 4", "Subscription Amount"],
            },
            {
                "field_id": "f005",
                "field_name": "Investor Type",
                "context": "Type of investor entity: individual, trust, corporation, limited partnership, or other",
                "section_context": "Investor Classification",
                "headers": ["Section 1", "Entity Type"],
            },
            {
                "field_id": "f006",
                "field_name": "Address Line 1",
                "context": "Street address line 1 of principal place of residence or business",
                "section_context": "Address",
                "headers": ["Section 2", "Address Details"],
            },
            {
                "field_id": "f007",
                "field_name": "Date of Birth / Incorporation",
                "context": "Date of birth for individuals or date of incorporation for entities",
                "section_context": "Personal Information",
                "headers": ["Section 1", "KYC Details"],
            },
            {
                "field_id": "f008",
                "field_name": "Accredited Investor",
                "context": "Confirmation of accredited investor status under SEC Rule 501 of Regulation D",
                "section_context": "Investor Qualification",
                "headers": ["Section 5", "Accreditation"],
            },
            {
                "field_id": "f009",
                "field_name": "Bank Account Number",
                "context": "Bank account number for capital call wire transfers and distributions",
                "section_context": "Banking Details",
                "headers": ["Section 6", "Wire Instructions"],
            },
            {
                "field_id": "f010",
                "field_name": "Signature Date",
                "context": "Date on which the subscription agreement is executed and signed by the investor",
                "section_context": "Execution",
                "headers": ["Signature Page"],
            },
            {
                "field_id": "f011",
                "field_name": "Country of Citizenship",
                "context": "Country of citizenship for individuals or country of incorporation, required for FATCA and CRS",
                "section_context": "Regulatory Compliance",
                "headers": ["Section 7", "FATCA / CRS"],
            },
            {
                "field_id": "f012",
                "field_name": "Beneficial Owner",
                "context": "Name of the ultimate beneficial owner who owns or controls 25 percent or more of the investing entity",
                "section_context": "AML / KYC",
                "headers": ["Section 8", "AML Compliance"],
            },
        ],
        force,
    )

    _write_json(
        f"{base}/input/pdf_category.json",
        {
            "category": "Private Markets",
            "sub_category": "Private Equity",
            "document_type": "LP Subscription Agreement",
        },
        force,
    )

    _write_json(
        f"{base}/input/sample_errors.json",
        [
            {
                "error_type": "wrong_field_name",
                "field_name": "tax_identification_number",
                "field_type": "text",
                "value": "123-45-6789",
                "feedback": "This field is the combined SSN/EIN field, not just tax ID",
                "page_number": 3,
                "corners": [[120, 340], [480, 340], [480, 360], [120, 360]],
            }
        ],
        force,
    )

    # ── vectors/vector_database.json ─────────────────────────────────────────
    # Load the real 137-vector DB bundled with ragpdf (1536-dim OpenAI embeddings).
    # Replaces the old make_emb() random Gaussian noise approach which produced
    # vectors that never matched anything at prediction time.
    vector_db = _load_bundled_vector_db()
    _write_json(f"{base}/vectors/vector_database.json", vector_db, force)

    _write_json(
        f"{base}/pdf_hash_mapping/mapping.json",
        {
            "aabbcc112233": {
                "pdf_hash": "aabbcc112233",
                "pdf_id": "pdf_001",
                "category": "Private Markets",
                "sub_category": "Private Equity",
                "document_type": "LP Subscription Agreement",
                "pdf_count": 3,
                "total_submissions": 3,
                "submissions": [
                    {
                        "submission_id": "user_01_session_01_pdf_001_1_1736496000",
                        "user_id": "user_01",
                        "session_id": "session_01",
                        "pdf_id": "pdf_001",
                        "frequency": 1,
                        "timestamp": "2026-01-10T08:00:00Z",
                        "total_fields": 12,
                        "accuracy_llm": 1.0,
                        "accuracy_rag": 1.0,
                        "accuracy_ensemble": 1.0,
                        "errors_reported": 0,
                    },
                    {
                        "submission_id": "user_02_session_03_pdf_001_2_1738694400",
                        "user_id": "user_02",
                        "session_id": "session_03",
                        "pdf_id": "pdf_001",
                        "frequency": 2,
                        "timestamp": "2026-02-04T12:00:00Z",
                        "total_fields": 12,
                        "accuracy_llm": 0.9167,
                        "accuracy_rag": 0.9167,
                        "accuracy_ensemble": 0.9167,
                        "errors_reported": 1,
                    },
                    {
                        "submission_id": "user_01_session_05_pdf_001_3_1741132800",
                        "user_id": "user_01",
                        "session_id": "session_05",
                        "pdf_id": "pdf_001",
                        "frequency": 3,
                        "timestamp": "2026-03-05T09:00:00Z",
                        "total_fields": 12,
                        "accuracy_llm": 1.0,
                        "accuracy_rag": 1.0,
                        "accuracy_ensemble": 1.0,
                        "errors_reported": 0,
                    },
                ],
                "aggregated_stats": {
                    "avg_accuracy_llm": 0.9722,
                    "avg_accuracy_rag": 0.9722,
                    "avg_accuracy_ensemble": 0.9722,
                    "avg_coverage_llm": 0.9167,
                    "avg_coverage_rag": 0.9167,
                    "total_errors": 1,
                    "consistency_score": 0.9444,
                    "improvement_trend": "stable",
                },
                "first_seen": "2026-01-10T08:00:00Z",
                "last_seen": "2026-03-05T09:00:00Z",
            }
        },
        force,
    )

    _write_json(
        f"{base}/metrics/time_series/global/time_series.json",
        {
            "level": "global",
            "identifier": "global",
            "entries": [
                {
                    "timestamp": "2026-01-10T08:00:00Z",
                    "submission_id": "user_01_session_01_pdf_001_1_1736496000",
                    "user_id": "user_01",
                    "session_id": "session_01",
                    "pdf_id": "pdf_001",
                    "metrics": {
                        "total_fields": 12,
                        "predicted_llm": 11,
                        "predicted_rag": 10,
                        "predicted_ensemble": 11,
                        "coverage_llm": 0.9167,
                        "coverage_rag": 0.8333,
                        "coverage_ensemble": 0.9167,
                        "accuracy_llm": 1.0,
                        "accuracy_rag": 1.0,
                        "accuracy_ensemble": 1.0,
                        "avg_conf_llm": 0.891,
                        "avg_conf_rag": 0.876,
                        "avg_conf_ensemble": 0.884,
                        "agreement_rate": 0.909,
                        "conflict_rate": 0.091,
                        "rag_recovery": 0.0,
                        "llm_recovery": 0.1,
                        "errors_llm": 0,
                        "errors_rag": 0,
                        "errors_ensemble": 0,
                    },
                },
            ],
            "metadata": {
                "total_entries": 1,
                "first_entry": "2026-01-10T08:00:00Z",
                "last_entry": "2026-01-10T08:00:00Z",
            },
        },
        force,
    )

    # ── vectors/source/vector_source.json ─────────────────────────────────────
    # Copy the bundled field definitions (no embeddings) into the source/ folder.
    # This is what `ragpdf init-vectors` reads to generate embeddings and build
    # vector_database.json. Never overwritten once present — user may customise it.
    source_dir = os.path.join(base, "vectors", "source")
    os.makedirs(source_dir, exist_ok=True)
    dest_source = os.path.join(source_dir, "vector_source.json")
    if not os.path.exists(dest_source) or force:
        try:
            pkg_file = (
                importlib.resources.files("ragpdf") / "data" / "vector_source.json"
            )
            with importlib.resources.as_file(pkg_file) as p:
                shutil.copy(str(p), dest_source)
            print(f"  created  {dest_source}")
        except Exception as e:
            print(f"  warning  could not copy vector_source.json: {e}")
            print(
                "           Run: ragpdf init-vectors --source /path/to/vector_source.json"
            )


# ── Main ──────────────────────────────────────────────────────────────────────


def run_setup(dest_str: str = ".") -> None:
    dest = Path(dest_str).resolve()
    combo = detect_combo()

    if not combo:
        print("No pdf-autofillr modules detected.")
        print("Install one first, e.g.: pip install pdf-autofillr[chatbot]")
        return

    label = " + ".join(sorted(combo))
    print(f"\n📦 Detected modules: {label}\n")

    created_dirs = _make_dirs(combo, dest)
    print(f"✅ Folders: {len(created_dirs)} directories created/verified")

    config_src = _config_source()
    configs_dst = dest / "configs"
    configs_dst.mkdir(parents=True, exist_ok=True)

    if config_src and config_src.exists():
        shutil.copytree(str(config_src), str(configs_dst), dirs_exist_ok=True)
        print(f"✅ Configs copied to {configs_dst}")
    else:
        print(
            "⚠  Could not find config_samples — install chatbot or doc_upload to get them"
        )

    if "mapper" in combo:
        ini_path = configs_dst / "mapper_config.ini"
        ini_path.write_text(build_mapper_ini(combo))
        print(f"✅ mapper_config.ini written: {ini_path}")

    env_path = dest / ".env.example"
    env_path.write_text(build_env_example(combo), encoding="utf-8")
    print(f"✅ .env.example written: {env_path}")

    qs_path = dest / "README_QUICKSTART.md"
    qs_path.write_text(build_quickstart(combo), encoding="utf-8")
    print(f"✅ README_QUICKSTART.md written: {qs_path}")

    # Write RAG data files (uses bundled real vector DB, not random noise)
    if "rag" in combo:
        _create_ragpdf_data(combo, dest, force=False)
        print("✅ RAG data initialised: data/rag/")

    has_env = (dest / ".env").exists()
    has_pdf = (dest / "data" / "input" / "blank_form.pdf").exists()

    print(f"""
{'='*60}
Setup complete for: {label}

Next steps:
{'  ✅ .env already exists' if has_env else '  1. cp .env.example .env'}
{'  ✅ blank_form.pdf found' if has_pdf else '  2. Drop your blank PDF into: data/input/blank_form.pdf'}
  3. Edit .env -> set your API key (OPENAI_API_KEY)
  4. pdf-autofillr status   <- verify everything is ready
{'='*60}
""")
