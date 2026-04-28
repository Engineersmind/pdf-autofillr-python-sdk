# src/ragpdf/utils/helpers.py
from datetime import datetime


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
            pass
    next_id = max(ids) + 1 if ids else 1
    return f"vec_{next_id:03d}"


def calculate_avg(values):
    """Safe average."""
    return round(sum(values) / len(values), 6) if values else 0.0
