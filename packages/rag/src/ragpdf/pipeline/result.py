# ragpdf/pipeline/result.py
from dataclasses import dataclass, field
from typing import Optional, Any


@dataclass
class FieldPrediction:
    """Single field prediction from RAG."""
    field_id: str
    matched: bool
    confidence: float
    field_name: Optional[str] = None          # None if not matched
    vector_id: Optional[str] = None
    vector_confidence: Optional[float] = None  # stored confidence in that vector
    positive_count: int = 0
    negative_count: int = 0
    usage_count: int = 0
    stability_score: float = 1.0
    top_k: list[dict] = field(default_factory=list)
    similarity_margin: float = 0.0
    best_candidate: Optional[str] = None      # top result even if below threshold


@dataclass
class PredictionResult:
    """Full result of API 1 — get_predictions."""
    user_id: str
    session_id: str
    pdf_id: str
    submission_id: str
    pdf_hash: str
    frequency: int
    is_duplicate: bool
    predictions: dict[str, Optional[FieldPrediction]]  # field_id -> prediction or None
    summary: dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""


@dataclass
class ProcessingResult:
    """Full result of API 2 — save_filled_pdf (inner processing pipeline)."""
    user_id: str
    session_id: str
    pdf_id: str
    submission_id: str
    success: bool
    case_classification: Optional[dict] = None
    metrics: Optional[dict] = None
    vector_update_summary: Optional[dict] = None
    error: Optional[str] = None


@dataclass
class FeedbackResult:
    """Full result of API 4 — submit_feedback."""
    user_id: str
    session_id: str
    pdf_id: str
    submission_id: str
    errors_processed: int
    vectors_updated: int
    corrections_generated: int
    corrected_mappings: list[dict] = field(default_factory=list)
    updated_accuracy: Optional[dict] = None
    error: Optional[str] = None


@dataclass
class MetricsResult:
    """Wrapper around analytics query results."""
    metric_type: str
    data: dict[str, Any]
