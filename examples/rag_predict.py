"""
RAG — predict field mappings and submit feedback.

Requires: pip install "pdf-autofillr-rag[openai]"
"""
from ragpdf import RAGPDFClient

client = RAGPDFClient.from_env()

# Predict canonical keys for raw PDF field names
result = client.predict(
    user_id="user_001",
    session_id="session_abc",
    pdf_id="lp_form_q2",
    fields=["investor_full_name", "commitment_usd", "entity_type"],
)

for field, pred in result.predictions.items():
    print(f"  {field:30} → {pred.canonical_key} ({pred.confidence:.2f})")

# Submit corrections — improves future predictions
client.submit_feedback(
    user_id="user_001",
    session_id="session_abc",
    pdf_id="lp_form_q2",
    errors={"commitment_usd": "investment_amount"},
)
print("Feedback submitted — vector store updated")