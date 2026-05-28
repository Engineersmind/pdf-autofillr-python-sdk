# src/ragpdf/client.py
"""
RAGPDFClient — single public entry point for the ragpdf-sdk.

All six APIs are exposed as typed Python methods.
Every component (storage, embeddings, vector store, corrector) is pluggable.
"""

import logging

from ragpdf.correctors.base import FieldCorrectorBackend
from ragpdf.embeddings.base import EmbeddingBackend
from ragpdf.models.predictor import FieldPredictor
from ragpdf.pipeline.feedback_pipeline import FeedbackPipeline
from ragpdf.pipeline.prediction_pipeline import PredictionPipeline
from ragpdf.pipeline.processing_pipeline import ProcessingPipeline
from ragpdf.services.analytics_service import AnalyticsService
from ragpdf.storage.base import StorageBackend
from ragpdf.vector_stores.base import VectorStoreBackend

logger = logging.getLogger(__name__)


class RAGPDFClient:
    """
    Self-learning RAG field prediction client.

    Quick start (all local, no cloud deps):
        from ragpdf import RAGPDFClient

        client = RAGPDFClient.from_env()   # reads .env

    Full explicit setup:
        from ragpdf import (
            RAGPDFClient,
            LocalStorage,
            LocalVectorStore,
            SentenceTransformerBackend,
            OpenAICorrectorBackend,
        )

        client = RAGPDFClient(
            storage=LocalStorage("./data"),
            vector_store=LocalVectorStore("./data"),
            embedding_backend=SentenceTransformerBackend("all-MiniLM-L6-v2"),
            corrector=OpenAICorrectorBackend(api_key="sk-..."),
        )
    """

    def __init__(
        self,
        storage: StorageBackend,
        vector_store: VectorStoreBackend,
        embedding_backend: EmbeddingBackend,
        corrector: FieldCorrectorBackend | None = None,
    ):
        self._storage = storage
        self._vector_store = vector_store
        self._embedding = embedding_backend

        from ragpdf.correctors.noop_corrector import NoOpCorrectorBackend

        self._corrector = corrector or NoOpCorrectorBackend()

        predictor = FieldPredictor(embedding_backend, vector_store)
        self._prediction = PredictionPipeline(predictor, storage)
        self._processing = ProcessingPipeline(storage, vector_store, embedding_backend)
        self._feedback = FeedbackPipeline(storage, vector_store, self._corrector)
        self._analytics = AnalyticsService(storage)

    @classmethod
    def from_env(cls) -> "RAGPDFClient":
        """Create client from environment variables / .env file."""
        from ragpdf.correctors.factory import CorrectorFactory
        from ragpdf.embeddings.factory import EmbeddingFactory
        from ragpdf.storage.factory import StorageFactory
        from ragpdf.vector_stores.factory import VectorStoreFactory

        return cls(
            storage=StorageFactory.create(),
            vector_store=VectorStoreFactory.create(),
            embedding_backend=EmbeddingFactory.create(),
            corrector=CorrectorFactory.create(),
        )

    # ── API 1: Get RAG Predictions ────────────────────────────────────────────
    def get_predictions(
        self,
        user_id: str,
        session_id: str,
        pdf_id: str,
        fields: list,
        pdf_hash: str,
        pdf_category: dict,
    ) -> dict:
        """
        Generate RAG predictions for a list of PDF form fields.

        Args:
            user_id      : Unique user identifier
            session_id   : Unique session identifier
            pdf_id       : Unique PDF identifier
            fields       : List of field dicts. Each field:
                           {
                               "field_id":        "f001",
                               "field_name":      "Name Box",       # optional, improves accuracy
                               "context":         "Full legal name of investor",
                               "section_context": "Investor Identity",
                               "headers":         ["Section 1", "Personal Details"]
                           }
            pdf_hash     : MD5/SHA of the PDF file (used for dedup + frequency tracking)
            pdf_category : {"category": "...", "sub_category": "...", "document_type": "..."}

        Returns dict with submission_id, frequency, is_duplicate, and prediction summary.
        RAG predictions are saved to storage automatically.
        """
        return self._prediction.run(
            user_id, session_id, pdf_id, fields, pdf_hash, pdf_category
        )

    # ── API 2: Save Filled PDF + Run Processing Pipeline ─────────────────────
    def save_filled_pdf(
        self,
        user_id: str,
        session_id: str,
        pdf_id: str,
        llm_predictions: dict,
        final_predictions: dict,
        filled_pdf_location: str | None = None,
    ) -> dict:
        """
        Store the filled PDF and run the full processing pipeline:
        case classification -> metrics -> vector updates -> time series.

        Args:
            llm_predictions   : {"predictions": {"field_id": {"predicted_field_name": ..., "confidence": ...}}}
            final_predictions : {"final_predictions": {"field_id": {"selected_field_name": ...,
                                                                      "selected_from": "rag"|"llm",
                                                                      "rag_confidence": ...,
                                                                      "llm_confidence": ...}}}

        Returns processing summary.
        """
        return self._processing.run(
            user_id, session_id, pdf_id, llm_predictions, final_predictions
        )

    # ── API 4: User Feedback ──────────────────────────────────────────────────
    def submit_feedback(
        self,
        user_id: str,
        session_id: str,
        pdf_id: str,
        errors: list,
        timestamp: str | None = None,
    ) -> dict:
        """
        Submit user error feedback. Each error triggers:
        - LLM-generated correction (via corrector backend)
        - Negative confidence update on responsible vector
        - Embedding regeneration enriched with the correction
        - Metric recalculation + time series update

        Args:
            errors: List of error dicts:
                    {
                        "error_type":  "wrong_field_name",
                        "field_name":  "investor_name",      # what was filled
                        "field_type":  "text",
                        "value":       "wrong value",
                        "feedback":    "Should be full_legal_name",
                        "page_number": 1,
                        "corners":     [[x,y], ...]          # bounding box
                    }
        """
        sub_info = self._storage.load_json(
            f"predictions/{user_id}/{session_id}/{pdf_id}/metadata/submission_info.json"
        )
        submission_id = (
            sub_info.get("submission_id", "unknown") if sub_info else "unknown"
        )
        return self._feedback.run(
            user_id, session_id, pdf_id, submission_id, errors, timestamp
        )

    # ── API 5: Get Metrics ────────────────────────────────────────────────────
    def get_metrics(self, metric_type: str, **kwargs) -> dict:
        """
        Retrieve metrics. metric_type options:

            "pdf"         -> user_id, session_id, pdf_id
            "category"    -> category
            "subcategory" -> category, subcategory
            "doctype"     -> category, subcategory, doctype
            "global"      -> (no params) — full LLM vs RAG comparison + time series
            "compare"     -> pdfs=[{user_id, session_id, pdf_id}, ...]
            "pdf_hash"    -> pdf_hash — all submissions for this PDF hash

        Example:
            client.get_metrics("global")
            client.get_metrics("pdf", user_id="u1", session_id="s1", pdf_id="p1")
            client.get_metrics("category", category="Private Markets")
        """
        return self._analytics.get_metrics({"metric_type": metric_type, **kwargs})

    # ── API 6: Get System Info ────────────────────────────────────────────────
    def get_system_info(self) -> dict:
        """
        Returns a full system overview:
        total PDFs, users, sessions, categories, vectors, error counts.
        """
        return self._analytics.get_metrics({"metric_type": "system_info"})

    # ── API 7: Get Error Analytics ────────────────────────────────────────────
    def get_error_analytics(
        self,
        date_from: str | None = None,
        date_to: str | None = None,
        category: str | None = None,
        subcategory: str | None = None,
        doctype: str | None = None,
    ) -> dict:
        """
        Filtered error analytics with breakdowns by category, date, error type, case type.

        All filters are optional — combine freely.

        Example:
            client.get_error_analytics(
                date_from="2026-01-01T00:00:00Z",
                category="Private Markets"
            )
        """
        return self._analytics.get_error_analytics(
            {
                "date_from": date_from,
                "date_to": date_to,
                "category": category,
                "subcategory": subcategory,
                "doctype": doctype,
            }
        )
