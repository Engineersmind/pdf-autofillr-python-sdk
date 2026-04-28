"""
Mapper — full pipeline in Python.

Requires: pip install pdf-autofillr-mapper
"""
from pdf_autofillr_mapper import MapperOrchestrator

orch = MapperOrchestrator.from_env()

# Step 1 — embed the template (run once per blank PDF form)
embed = orch.make_embed_file(
    pdf_path="data/input/blank_form.pdf",
    user_id="example_user",
    pdf_doc_id="lp_sub_v1",
)
print(f"Embedded: {embed.embedded_pdf_path}")

# Step 2 — fill with user data
fill = orch.fill_pdf(
    pdf_path="data/input/blank_form.pdf",
    user_id="example_user",
    pdf_doc_id="lp_sub_v1",
    user_data={
        "investor_name": "Jane Smith",
        "investor_type": "Individual",
        "commitment_amount": "500000",
        "email": "jane@example.com",
    },
)
print(f"Filled PDF: {fill.filled_pdf_path}")
