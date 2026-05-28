# tests/integration/test_full_pipeline.py
"""
Integration test — requires numpy and scikit-learn but NO external API keys.
Uses NoOpCorrectorBackend and a simple cosine-similarity predictor with dummy embeddings.
"""

import pytest

from ragpdf import LocalStorage, RAGPDFClient
from ragpdf.correctors.noop_corrector import NoOpCorrectorBackend
from ragpdf.embeddings.base import EmbeddingBackend
from ragpdf.vector_stores.local_vector_store import LocalVectorStore


class DummyEmbeddingBackend(EmbeddingBackend):
    """Deterministic embeddings for testing — no model download."""

    def embed(self, text):
        h = hash(text) % 1000
        emb = [0.0] * 384
        emb[h % 384] = 1.0
        return emb

    def embed_batch(self, texts):
        return [self.embed(t) for t in texts]


@pytest.fixture
def client(tmp_path):
    storage = LocalStorage(str(tmp_path))
    vector_store = LocalVectorStore(str(tmp_path))
    return RAGPDFClient(
        storage=storage,
        vector_store=vector_store,
        embedding_backend=DummyEmbeddingBackend(),
        corrector=NoOpCorrectorBackend(),
    )


FIELDS = [
    {
        "field_id": "f1",
        "field_name": "Investor Name",
        "context": "full legal name",
        "section_context": "Identity",
        "headers": ["Section 1"],
    },
    {
        "field_id": "f2",
        "field_name": "Email",
        "context": "email address",
        "section_context": "Contact",
        "headers": ["Section 2"],
    },
]

PDF_CAT = {
    "category": "Private Markets",
    "sub_category": "PE",
    "document_type": "LP Sub Agreement",
}


@pytest.mark.integration
def test_empty_vector_store_returns_no_predictions(client):
    result = client.get_predictions("u1", "s1", "p1", FIELDS, "hash001", PDF_CAT)
    assert "submission_id" in result
    assert result["summary"]["total_fields"] == 2
    assert result["summary"]["predicted_fields"] == 0


@pytest.mark.integration
def test_predict_after_seeding(tmp_path):
    # Seed the vector store first, THEN build the client so it loads the seeded data
    emb = DummyEmbeddingBackend()
    store = LocalVectorStore(str(tmp_path))
    for field in FIELDS:
        text = emb.create_text_from_field(field)
        embedding = emb.embed(text)
        store.add_vector(
            field_name=f"predicted_{field['field_id']}",
            context=field["context"],
            section_context=field["section_context"],
            headers=field["headers"],
            embedding=embedding,
        )
    store.save()

    # Build client AFTER seeding so LocalVectorStore loads the persisted vectors
    storage = LocalStorage(str(tmp_path))
    vector_store = LocalVectorStore(str(tmp_path))
    seeded_client = RAGPDFClient(
        storage=storage,
        vector_store=vector_store,
        embedding_backend=emb,
        corrector=NoOpCorrectorBackend(),
    )

    result = seeded_client.get_predictions("u1", "s1", "p1", FIELDS, "hash001", PDF_CAT)
    assert result["summary"]["predicted_fields"] > 0


@pytest.mark.integration
def test_full_pipeline(client, tmp_path):
    # Step 1: predict
    client.get_predictions("u1", "s1", "p1", FIELDS, "hash001", PDF_CAT)

    # Step 2: save filled PDF
    llm_preds = {
        "predictions": {
            "f1": {"predicted_field_name": "investor_full_name", "confidence": 0.88},
            "f2": {"predicted_field_name": "investor_email", "confidence": 0.91},
        }
    }
    final_preds = {
        "final_predictions": {
            "f1": {
                "selected_field_name": "investor_full_name",
                "selected_from": "llm",
                "llm_confidence": 0.88,
            },
            "f2": {
                "selected_field_name": "investor_email",
                "selected_from": "llm",
                "llm_confidence": 0.91,
            },
        }
    }
    result = client.save_filled_pdf("u1", "s1", "p1", llm_preds, final_preds)
    assert "metrics_summary" in result

    # Step 3: metrics
    m = client.get_metrics("pdf", user_id="u1", session_id="s1", pdf_id="p1")
    assert m is not None

    # Step 4: feedback
    fb = client.submit_feedback(
        "u1",
        "s1",
        "p1",
        [
            {
                "error_type": "wrong_field_name",
                "field_name": "investor_full_name",
                "feedback": "Should be full_legal_name",
                "field_type": "text",
            }
        ],
    )
    assert "errors_processed" in fb

    # Step 5: system info
    info = client.get_system_info()
    assert "summary" in info
