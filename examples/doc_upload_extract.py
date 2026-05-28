"""
Doc Upload — extract from document and fill PDF.

Requires: pip install "pdf-autofillr[doc-upload]"
"""

from pdf_autofillr_doc_upload import DocUploadClient

client = DocUploadClient.from_env()

result = client.process(
    document_path="investor_data.pdf",  # or .docx, .xlsx, .csv, .json …
    pdf_path="data/input/blank_form.pdf",
    schema_keys_path="configs/form_keys.json",
    user_id="user_001",
    pdf_doc_id="lp_sub_v1",
)

print(f"Extracted fields: {result.extracted_fields}")
print(f"Filled PDF: {result.filled_pdf_path}")
print(f"Confidence: {result.avg_confidence:.2f}")
