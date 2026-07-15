# src/ragpdf/entrypoints/setup.py

"""
ragpdf-setup — run once after pip install.

    ragpdf-setup

Asks if you want the full editable module source code.
Always creates: .env, config.ini, data/rag/ with sample data.
"""

import json
import math
import os
import random
import secrets
import shutil

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def make_emb(seed: int, dim: int = 384) -> list:
    random.seed(seed)
    raw = [random.gauss(0, 1) for _ in range(dim)]
    norm = math.sqrt(sum(x * x for x in raw))
    return [round(x / norm, 6) for x in raw]


def _write_json(path: str, data, force: bool = False):
    if os.path.exists(path) and not force:
        print(f"  skip     {path}  (exists)")
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"  created  {path}")


def _write_text(path: str, content: str, force: bool = False, *, secret: bool = False) -> bool:
    if os.path.exists(path) and not force:
        print(f"  skip     {path}  (exists — not overwriting)")
        return False
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    if secret:
        # This file contains a generated secret (RAGPDF_API_KEY) — restrict
        # it to owner read/write only. Storing it in a plaintext config file
        # is unavoidable (the app reads it back at startup), but limiting
        # filesystem access to it is the standard, real mitigation.
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass  # best-effort; not all filesystems (e.g. some Windows setups) support this
    print(f"  created  {path}")
    return True


def _copy_module_source(dest: str = "./ragpdf"):
    """Copy installed ragpdf package source into ./ragpdf/ for editing."""
    import ragpdf as pkg

    src = os.path.dirname(pkg.__file__)

    if os.path.exists(dest):
        print(f"\n  ragpdf/ already exists at {dest} — skipping source copy.")
        print("  Use --force to overwrite.\n")
        return

    shutil.copytree(src, dest)
    print(f"\n  copied   ragpdf source -> {dest}/")
    print(f"  You can now edit {dest}/ directly.")
    print("  Add this to your .env:  RAGPDF_MODULE_PATH=./ragpdf\n")


# ──────────────────────────────────────────────────────────────────────────────
# Config file creators
# ──────────────────────────────────────────────────────────────────────────────


def _create_env(force: bool = False, api_key: str = "") -> bool:
    # NOTE on CodeQL "Clear-text storage of sensitive information": this
    # function necessarily writes RAGPDF_API_KEY into .env as plain text —
    # the running server reads it back at startup, so there is no way to
    # avoid storing it in a form the app itself can consume without an
    # external secrets manager, which is out of scope for a local dev
    # installer. The mitigation actually applied is restricting the file to
    # chmod 600 (see _write_text(secret=True) below) and never echoing the
    # full value to stdout (see the masked preview in main()). This finding
    # should be dismissed in GitHub's UI as "Won't fix" with this reasoning,
    # not treated as an outstanding code change.
    return _write_text(
        ".env",
        f"""\
# pdf-autofillr-rag — environment config
# Edit values below. Only fill sections relevant to your chosen backends.

# ── Storage ───────────────────────────────────────────────────
RAGPDF_STORAGE=local              # local | s3
RAGPDF_DATA_PATH=./data/rag

# S3 (only when RAGPDF_STORAGE=s3)
# RAGPDF_S3_BUCKET=your-bucket
# RAGPDF_S3_REGION=us-east-1
# RAGPDF_S3_PREFIX=ragpdf/

# ── Embedding Backend ─────────────────────────────────────────
RAGPDF_EMBEDDING_BACKEND=sentence_transformer   # sentence_transformer | openai | noop
RAGPDF_ST_MODEL=all-MiniLM-L6-v2

# OpenAI (only when RAGPDF_EMBEDDING_BACKEND=openai)
# OPENAI_API_KEY=sk-your-key
# RAGPDF_OPENAI_EMBEDDING_MODEL=text-embedding-3-small

# ── Vector Store ──────────────────────────────────────────────
RAGPDF_VECTOR_STORE=local         # local | s3 | pinecone | chroma | weaviate

# Pinecone (only when RAGPDF_VECTOR_STORE=pinecone)
# PINECONE_API_KEY=your-pinecone-key
# RAGPDF_PINECONE_INDEX=ragpdf-vectors
# RAGPDF_PINECONE_NAMESPACE=default

# ChromaDB (only when RAGPDF_VECTOR_STORE=chroma)
# RAGPDF_CHROMA_PATH=./chroma_data
# RAGPDF_CHROMA_COLLECTION=ragpdf_vectors

# Weaviate (only when RAGPDF_VECTOR_STORE=weaviate)
# RAGPDF_WEAVIATE_URL=http://localhost:8080
# RAGPDF_WEAVIATE_API_KEY=
# RAGPDF_WEAVIATE_CLASS=RagpdfVector

# ── LLM Corrector ─────────────────────────────────────────────
RAGPDF_CORRECTOR_BACKEND=noop     # noop | openai | anthropic

# OpenAI corrector (only when RAGPDF_CORRECTOR_BACKEND=openai)
# RAGPDF_OPENAI_MODEL=gpt-4-turbo-preview
# RAGPDF_OPENAI_TEMPERATURE=0.3
# RAGPDF_OPENAI_MAX_TOKENS=500

# Anthropic corrector (only when RAGPDF_CORRECTOR_BACKEND=anthropic)
# ANTHROPIC_API_KEY=sk-ant-your-key
# RAGPDF_ANTHROPIC_MODEL=claude-sonnet-4-20250514

# ── Prediction ────────────────────────────────────────────────
RAGPDF_PREDICTION_THRESHOLD=0.75
RAGPDF_TOP_K=5
RAGPDF_AMBIGUITY_THRESHOLD=0.10
RAGPDF_CONFIDENCE_DECAY_RATE=0.95
RAGPDF_CONFIDENCE_GROWTH_RATE=1.05
RAGPDF_MAX_CONFIDENCE=0.99
RAGPDF_MIN_CONFIDENCE=0.50

# ── Server ────────────────────────────────────────────────────
RAGPDF_API_KEY={api_key}
RAGPDF_SERVER_HOST=0.0.0.0
RAGPDF_SERVER_PORT=8000

# ── Debug ─────────────────────────────────────────────────────
RAGPDF_DEBUG=false
RAGPDF_LOG_LEVEL=INFO
""",
        force,
        secret=True,
    )


def _create_config_ini(force: bool = False, api_key: str = "") -> bool:
    # See the identical note in _create_env() above — same accepted,
    # necessary cleartext storage, same chmod 600 mitigation.
    return _write_text(
        "config.ini",
        f"""\
[storage]
backend     = local
data_path   = ./data/rag
s3_bucket   =
s3_region   = us-east-1
s3_prefix   = ragpdf/

[embeddings]
backend      = sentence_transformer
st_model     = all-MiniLM-L6-v2
openai_model = text-embedding-3-small

[vector_store]
backend              = local
pinecone_index       = ragpdf-vectors
pinecone_namespace   = default
chroma_path          = ./chroma_data
chroma_collection    = ragpdf_vectors
weaviate_url         = http://localhost:8080

[corrector]
backend         = noop
openai_model    = gpt-4-turbo-preview
anthropic_model = claude-sonnet-4-20250514

[prediction]
threshold            = 0.75
top_k                = 5
ambiguity_threshold  = 0.10
confidence_decay     = 0.95
confidence_growth    = 1.05
max_confidence       = 0.99
min_confidence       = 0.50

[server]
api_key = {api_key}
host    = 0.0.0.0
port    = 8000
""",
        force,
        secret=True,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Sample data
# ──────────────────────────────────────────────────────────────────────────────


def _create_ragpdf_data(base: str = "./data/rag", force: bool = False):

    # ── Directory skeleton ────────────────────────────────────
    for d in [
        f"{base}/input/fields",
        f"{base}/vectors",
        f"{base}/pdf_hash_mapping",
        f"{base}/predictions",
        f"{base}/metrics/time_series/global",
    ]:
        os.makedirs(d, exist_ok=True)

    for f in [f"{base}/predictions/.gitkeep", f"{base}/metrics/.gitkeep"]:
        if not os.path.exists(f):
            open(f, "w").close()

    # ── input/fields/lp_subscription_fields.json ─────────────
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

    # ── input/pdf_category.json ───────────────────────────────
    _write_json(
        f"{base}/input/pdf_category.json",
        {
            "category": "Private Markets",
            "sub_category": "Private Equity",
            "document_type": "LP Subscription Agreement",
        },
        force,
    )

    # ── input/sample_errors.json ──────────────────────────────
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

    # ── vectors/vector_database.json ──────────────────────────
    #
    # Columns: vid, fname, ctx, sctx, hdrs,
    #          seed, pos, neg, usage, stab, hist, src
    vec_defs = [
        (
            "vec_001",
            "investor_full_legal_name",
            "Full legal name of the investor as it appears on government-issued ID",
            "Investor Identity",
            ["Section 1", "Personal Information"],
            1,
            14,
            0,
            18,
            1.0,
            [0.75, 0.7875, 0.8268, 0.8682, 0.9116],
            "rag",
        ),
        (
            "vec_002",
            "investor_email_address",
            "Email address for all fund correspondence and notices",
            "Contact Details",
            ["Section 2", "Contact"],
            2,
            8,
            0,
            10,
            1.0,
            [0.75, 0.7875, 0.8268],
            "rag",
        ),
        (
            "vec_003",
            "tax_identification_number",
            "Social Security Number or Employer Identification Number for tax reporting",
            "Tax Information",
            ["Section 3", "Tax Details"],
            3,
            4,
            2,
            9,
            0.6667,
            [0.75, 0.7125, 0.6769],
            "rag",
        ),
        (
            "vec_004",
            "commitment_amount_usd",
            "Total capital commitment amount in US dollars",
            "Investment Details",
            ["Section 4", "Subscription Amount"],
            4,
            10,
            0,
            12,
            1.0,
            [0.75, 0.7875, 0.8268, 0.8682],
            "rag",
        ),
        (
            "vec_005",
            "investor_type",
            "Type of investor entity - individual, trust, corporation, partnership",
            "Investor Classification",
            ["Section 1", "Entity Type"],
            5,
            18,
            0,
            22,
            1.0,
            [0.75, 0.7875, 0.8268, 0.8682, 0.9116, 0.9572],
            "rag",
        ),
        (
            "vec_006",
            "residential_address_line1",
            "Street address line 1 of principal place of residence or business",
            "Address",
            ["Section 2", "Address Details"],
            6,
            7,
            0,
            9,
            1.0,
            [0.75, 0.7875, 0.8268],
            "llm",
        ),
        (
            "vec_007",
            "date_of_birth",
            "Date of birth of the individual investor",
            "Personal Information",
            ["Section 1", "KYC Details"],
            7,
            5,
            1,
            8,
            0.8333,
            [0.75, 0.7875],
            "rag",
        ),
        (
            "vec_008",
            "accredited_investor_status",
            "Confirmation of accredited investor status under SEC Rule 501",
            "Investor Qualification",
            ["Section 5", "Accreditation"],
            8,
            12,
            0,
            14,
            1.0,
            [0.75, 0.7875, 0.8268, 0.8682, 0.9116],
            "rag",
        ),
        (
            "vec_009",
            "bank_account_number",
            "Bank account number for capital call wire transfers",
            "Banking Details",
            ["Section 6", "Wire Instructions"],
            9,
            6,
            0,
            8,
            1.0,
            [0.75, 0.7875, 0.8268],
            "llm",
        ),
        (
            "vec_010",
            "signature_date",
            "Date on which the subscription agreement is signed by the investor",
            "Execution",
            ["Signature Page"],
            10,
            9,
            0,
            11,
            1.0,
            [0.75, 0.7875, 0.8268, 0.8682],
            "rag",
        ),
        (
            "vec_011",
            "country_of_citizenship",
            "Country of citizenship or incorporation for FATCA/CRS compliance",
            "Regulatory Compliance",
            ["Section 7", "FATCA / CRS"],
            11,
            8,
            0,
            10,
            1.0,
            [0.75, 0.7875, 0.8268, 0.8682],
            "rag",
        ),
        (
            "vec_012",
            "beneficial_owner_name",
            "Name of the ultimate beneficial owner of the investing entity",
            "AML / KYC",
            ["Section 8", "AML Compliance"],
            12,
            5,
            0,
            7,
            1.0,
            [0.75, 0.7875, 0.8268],
            "llm",
        ),
    ]

    vectors = []
    for vid, fname, ctx, sctx, hdrs, seed, pos, neg, usage, stab, hist, src in vec_defs:
        vectors.append(
            {
                "vector_id": vid,
                "field_name": fname,
                "context": ctx,
                "section_context": sctx,
                "headers": hdrs,
                "embedding": make_emb(seed),
                "confidence_history": hist,
                "positive_count": pos,
                "negative_count": neg,
                "usage_count": usage,
                "stability_score": stab,
                "avg_confidence": round(sum(hist) / len(hist), 4),
                "error_history": (
                    [
                        {
                            "timestamp": "2026-02-14T10:00:00Z",
                            "pdf_hash": "ddeeff445566",
                            "error_type": "wrong_field_name",
                            "user_feedback": "Corrected by user",
                            "corrected_to": "ssn_or_ein",
                            "original_confidence": 0.75,
                        }
                    ]
                    if neg > 0
                    else []
                ),
                "created_at": "2026-01-10T08:00:00Z",
                "last_updated": "2026-03-01T14:22:00Z",
                "last_used": "2026-03-15T09:11:00Z",
                "pdf_hash": "aabbcc112233",
                "submission_id": "user_01_session_01_pdf_001_1_1736496000",
                "category": "Private Markets",
                "sub_category": "Private Equity",
                "document_type": "LP Subscription Agreement",
                "prediction_source": src,
            }
        )

    _write_json(
        f"{base}/vectors/vector_database.json",
        {
            "metadata": {
                "total_count": len(vectors),
                "last_updated": "2026-03-15T09:11:00Z",
            },
            "vectors": vectors,
        },
        force,
    )

    # ── pdf_hash_mapping/mapping.json ─────────────────────────
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
            },
            "ddeeff445566": {
                "pdf_hash": "ddeeff445566",
                "pdf_id": "pdf_002",
                "category": "Private Markets",
                "sub_category": "Private Credit",
                "document_type": "Side Letter Agreement",
                "pdf_count": 1,
                "total_submissions": 1,
                "submissions": [
                    {
                        "submission_id": "user_03_session_02_pdf_002_1_1737964800",
                        "user_id": "user_03",
                        "session_id": "session_02",
                        "pdf_id": "pdf_002",
                        "frequency": 1,
                        "timestamp": "2026-01-27T10:00:00Z",
                        "total_fields": 8,
                        "accuracy_llm": 0.875,
                        "accuracy_rag": 0.75,
                        "accuracy_ensemble": 0.875,
                        "errors_reported": 1,
                    },
                ],
                "aggregated_stats": {
                    "avg_accuracy_llm": 0.875,
                    "avg_accuracy_rag": 0.75,
                    "avg_accuracy_ensemble": 0.875,
                    "avg_coverage_llm": 0.875,
                    "avg_coverage_rag": 0.75,
                    "total_errors": 1,
                    "consistency_score": 0.8125,
                    "improvement_trend": "new",
                },
                "first_seen": "2026-01-27T10:00:00Z",
                "last_seen": "2026-01-27T10:00:00Z",
            },
        },
        force,
    )

    # ── metrics/time_series/global/time_series.json ───────────
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
                {
                    "timestamp": "2026-01-27T10:00:00Z",
                    "submission_id": "user_03_session_02_pdf_002_1_1737964800",
                    "user_id": "user_03",
                    "session_id": "session_02",
                    "pdf_id": "pdf_002",
                    "metrics": {
                        "total_fields": 8,
                        "predicted_llm": 7,
                        "predicted_rag": 6,
                        "predicted_ensemble": 7,
                        "coverage_llm": 0.875,
                        "coverage_rag": 0.75,
                        "coverage_ensemble": 0.875,
                        "accuracy_llm": 0.875,
                        "accuracy_rag": 0.75,
                        "accuracy_ensemble": 0.875,
                        "avg_conf_llm": 0.862,
                        "avg_conf_rag": 0.841,
                        "avg_conf_ensemble": 0.854,
                        "agreement_rate": 0.857,
                        "conflict_rate": 0.143,
                        "rag_recovery": 0.0,
                        "llm_recovery": 0.125,
                        "errors_llm": 1,
                        "errors_rag": 2,
                        "errors_ensemble": 1,
                    },
                },
                {
                    "timestamp": "2026-02-04T12:00:00Z",
                    "submission_id": "user_02_session_03_pdf_001_2_1738694400",
                    "user_id": "user_02",
                    "session_id": "session_03",
                    "pdf_id": "pdf_001",
                    "metrics": {
                        "total_fields": 12,
                        "predicted_llm": 11,
                        "predicted_rag": 11,
                        "predicted_ensemble": 11,
                        "coverage_llm": 0.9167,
                        "coverage_rag": 0.9167,
                        "coverage_ensemble": 0.9167,
                        "accuracy_llm": 0.9167,
                        "accuracy_rag": 0.9167,
                        "accuracy_ensemble": 0.9167,
                        "avg_conf_llm": 0.903,
                        "avg_conf_rag": 0.897,
                        "avg_conf_ensemble": 0.9,
                        "agreement_rate": 1.0,
                        "conflict_rate": 0.0,
                        "rag_recovery": 0.0,
                        "llm_recovery": 0.0,
                        "errors_llm": 1,
                        "errors_rag": 1,
                        "errors_ensemble": 1,
                    },
                },
                {
                    "timestamp": "2026-03-05T09:00:00Z",
                    "submission_id": "user_01_session_05_pdf_001_3_1741132800",
                    "user_id": "user_01",
                    "session_id": "session_05",
                    "pdf_id": "pdf_001",
                    "metrics": {
                        "total_fields": 12,
                        "predicted_llm": 12,
                        "predicted_rag": 12,
                        "predicted_ensemble": 12,
                        "coverage_llm": 1.0,
                        "coverage_rag": 1.0,
                        "coverage_ensemble": 1.0,
                        "accuracy_llm": 1.0,
                        "accuracy_rag": 1.0,
                        "accuracy_ensemble": 1.0,
                        "avg_conf_llm": 0.924,
                        "avg_conf_rag": 0.918,
                        "avg_conf_ensemble": 0.921,
                        "agreement_rate": 1.0,
                        "conflict_rate": 0.0,
                        "rag_recovery": 0.0,
                        "llm_recovery": 0.0,
                        "errors_llm": 0,
                        "errors_rag": 0,
                        "errors_ensemble": 0,
                    },
                },
            ],
            "metadata": {
                "total_entries": 4,
                "first_entry": "2026-01-10T08:00:00Z",
                "last_entry": "2026-03-05T09:00:00Z",
            },
        },
        force,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────


def main():
    import argparse

    parser = argparse.ArgumentParser(
        prog="ragpdf-setup",
        description="Setup pdf-autofillr-rag in your project directory.",
    )
    parser.add_argument(
        "--path", default="./data/rag", help="Data folder path (default: ./data/rag)"
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    parser.add_argument(
        "--edit", action="store_true", help="Skip prompt, always copy module source"
    )
    parser.add_argument(
        "--no-edit", action="store_true", help="Skip prompt, never copy module source"
    )
    args = parser.parse_args()

    print("""
╔══════════════════════════════════════════════════════╗
║          pdf-autofillr-rag  —  Setup                 ║
╚══════════════════════════════════════════════════════╝
""")

    # ── Ask about source code ─────────────────────────────────
    if args.edit:
        copy_source = True
    elif args.no_edit:
        copy_source = False
    else:
        print("Do you want the full module source code copied to ./ragpdf/")
        print("so you can edit backends, pipelines, and services directly?")
        print()
        answer = input("Copy source for editing? [y/N]: ").strip().lower()
        copy_source = answer in ("y", "yes")

    print()

    # Generate a unique secret for this install rather than shipping a known
    # default — every prior installer wrote the same "dev-key" for everyone.
    generated_api_key = secrets.token_urlsafe(32)

    # ── Always: .env, config.ini, data/rag/ ──────────────────
    env_written = _create_env(force=args.force, api_key=generated_api_key)
    config_ini_written = _create_config_ini(force=args.force, api_key=generated_api_key)
    _create_ragpdf_data(base=args.path, force=args.force)

    # ── Optional: copy module source ──────────────────────────
    if copy_source:
        _copy_module_source(dest="./ragpdf")

    # Never echo the full secret to stdout — terminal scrollback, CI logs,
    # and screen recordings can all leak it. Show a masked preview only;
    # the real value is in .env (chmod 600) for the user to open directly.
    # codeql[py/clear-text-logging-sensitive-data] -- this derives a masked
    # preview (first/last 4 chars only) specifically so the full secret is
    # never in the printed output; CodeQL's taint tracking still flags any
    # value derived from generated_api_key regardless of masking. Reviewed:
    # the full key is never logged, only this truncated preview.
    _masked_key = generated_api_key[:4] + "…" + generated_api_key[-4:]

    if env_written or config_ini_written:
        _key_line = (
            f"  A unique RAGPDF_API_KEY was generated for you in "
            f"{'.env' if env_written else ''}"
            f"{' and ' if env_written and config_ini_written else ''}"
            f"{'config.ini' if config_ini_written else ''} ({_masked_key}).\n"
            "  Open .env to see the full value — send it as the X-API-Key\n"
            "  header on every request. Keep it secret — anyone with it can\n"
            "  call this server."
        )
    else:
        # Neither file was written (both already existed and --force wasn't
        # passed) — the generated key above was never persisted anywhere.
        _key_line = (
            "  .env and config.ini already exist and were left untouched, so\n"
            "  the newly generated key below was NOT saved. Whatever\n"
            "  RAGPDF_API_KEY is already in your .env is what's active — this\n"
            f"  freshly generated one ({_masked_key}) was discarded. Re-run with\n"
            "  --force if you want to replace it."
        )

    # ── Done ──────────────────────────────────────────────────
    print(f"""
{'='*54}
Setup complete.

{_key_line}

  1. Edit .env with your API keys / backends
  2. ragpdf system-info       ← verify setup
  3. ragpdf-server            ← start API server
     -> Swagger: http://localhost:8000/docs
{'  4. Edit ./ragpdf/ to customise backends' if copy_source else ''}
{'='*54}
""")


if __name__ == "__main__":
    main()
