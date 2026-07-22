# src/ragpdf/utils/helpers.py
from datetime import datetime


def safe_for_log(value) -> str:
    """
    Replace characters that let user-controlled input forge fake log
    entries (CWE-117 / CodeQL py/log-injection) — a value like
    "alice\\n2026-01-01 00:00:00 CRITICAL fake admin login" would
    otherwise appear as a second, fabricated log line. Replaces
    newlines/carriage returns with a visible escape so the forged-line
    attempt is visible as data, not interpreted as a line break.

    Use this to wrap any user-controlled value (user_id, session_id,
    pdf_id, field_name, vector_id, key, etc.) immediately before it's
    interpolated into a logger.*() call.
    """
    return str(value).replace("\r\n", "\\r\\n").replace("\n", "\\n").replace("\r", "\\r")


def generate_submission_id(user_id, session_id, pdf_id, pdf_hash, storage):
    """
    Generate a submission ID with frequency tracking.
    Format: {user_id}_{session_id}_{pdf_id}_{frequency}_{unix_timestamp}
    Returns: (submission_id, frequency, is_duplicate)
    """
    frequency = get_pdf_frequency(pdf_hash, storage)
    is_duplicate = frequency > 1
    timestamp = int(datetime.utcnow().timestamp())
    submission_id = f"{user_id}_{session_id}_{pdf_id}_{frequency}_{timestamp}"
    return submission_id, frequency, is_duplicate


def get_pdf_frequency(pdf_hash, storage):
    """How many times has this PDF hash been submitted before?"""
    from ragpdf.utils.constants import PDF_HASH_MAPPING_KEY

    mapping = storage.load_json(PDF_HASH_MAPPING_KEY) or {}
    if pdf_hash not in mapping:
        return 1
    return mapping[pdf_hash].get("pdf_count", 0) + 1


def generate_vector_id(existing_vectors):
    """Generate next sequential vector ID (vec_001, vec_002, ...)."""
    if not existing_vectors:
        return "vec_001"
    ids = []
    for v in existing_vectors:
        try:
            ids.append(int(v["vector_id"].split("_")[1]))
        except (IndexError, ValueError):
            pass  # intentional
    next_id = max(ids) + 1 if ids else 1
    return f"vec_{next_id:03d}"


def calculate_avg(values):
    """Safe average."""
    return round(sum(values) / len(values), 6) if values else 0.0
