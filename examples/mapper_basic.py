"""
Mapper — unified Python library client.

Combines:
  - PDFPipeline  (full config control, async, step-by-step or all-in-one)
  - MapperOrchestrator  (simple env-based setup, sync API)

Requires: pip install pdf-autofillr-mapper

First-time setup:
    python -c "import pdf_autofillr_mapper; pdf_autofillr_mapper.copy_sample_configs('.')"
"""

import asyncio
import os
from pdf_autofillr_mapper import PDFPipeline, MapperConfig, MapperOrchestrator

PDF_PATH   = "./data/input/blank_form.pdf"
USER_ID    = "example_user"
PDF_DOC_ID = "lp_sub_v1"
USER_DATA  = {
    "investor_name":    "Jane Smith",
    "investor_type":    "Individual",
    "commitment_amount": "500000",
    "email":            "jane@example.com",
}

# ─────────────────────────────────────────────────────────────────────────────
# APPROACH A — MapperOrchestrator (simple, env-based, sync)
# Use when: you just need embed + fill with minimal setup.
# ─────────────────────────────────────────────────────────────────────────────

orch = MapperOrchestrator.from_env()

# Step A1 — Embed the blank PDF template (run once per form)
embed = orch.make_embed_file(
    pdf_path=PDF_PATH,
    user_id=USER_ID,
    pdf_doc_id=PDF_DOC_ID,
)
print(f"Embedded: {embed.embedded_pdf_path}")

# Step A2 — Fill with investor data
fill = orch.fill_pdf(
    pdf_path=PDF_PATH,
    user_id=USER_ID,
    pdf_doc_id=PDF_DOC_ID,
    user_data=USER_DATA,
)
print(f"Filled PDF (orchestrator): {fill.filled_pdf_path}")


# ─────────────────────────────────────────────────────────────────────────────
# APPROACH B — PDFPipeline (full config control, async)
# Use when: you need custom LLM providers, mixed models, or a full pipeline run.
# ─────────────────────────────────────────────────────────────────────────────

# ── Config options (pick one) ──────────────────────────────────────────────

# B1. Load from ./configs directory + .env file (recommended for most projects)
cfg = MapperConfig.from_directory("./configs")
cfg.validate()  # warns if no API key is found for either LLM phase

# B2. Load purely from environment variables (Lambda / Docker)
# Set: MAPPER_LLM_MODEL, MAPPER_LLM_API_KEY, MAPPER_HEADERS_LLM_MODEL, etc.
# Or provider-specific: OPENAI_API_KEY, ANTHROPIC_API_KEY (litellm auto-routes)

# cfg = MapperConfig.from_env()

# B3. Programmatic — hardcode model + key (no config files needed)
# cfg = MapperConfig(
#     llm_model="openai/gpt-4o",
#     llm_api_key="sk-your-openai-key",         # Phase 1 — semantic mapping
#     headers_llm_model="openai/gpt-4o",
#     headers_llm_api_key="sk-your-openai-key",  # Phase 2 — headers detection
# )

# B4. Mix providers — Anthropic for mapping, OpenAI for headers
# cfg = MapperConfig(
#     llm_model="anthropic/claude-3-5-sonnet-20241022",
#     llm_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
#     headers_llm_model="openai/gpt-4o",
#     headers_llm_api_key=os.getenv("OPENAI_API_KEY", ""),
# )

# Other supported providers:
#   Groq:    llm_model="groq/llama-3.3-70b-versatile",  llm_api_key=os.getenv("GROQ_API_KEY")
#   Ollama:  llm_model="ollama/llama3.2"                (no API key required)
#   Azure:   llm_model="azure/gpt-4o",                  llm_api_key=os.getenv("AZURE_API_KEY")
#   Bedrock: llm_model="bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0"
#            (uses AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY from environment)

# ── Pipeline usage ─────────────────────────────────────────────────────────

pipeline = PDFPipeline(mapper_config=cfg)

# Option 1 — Run the full pipeline in one call (extract → map → embed → fill)
result = asyncio.run(pipeline.run_all(
    input_pdf_path=PDF_PATH,
    input_data_path="./configs/form_keys.json",
))
print(f"Filled PDF (full run): {result['final_output']}")

# Option 2 — Step-by-step: embed once, fill many times
embed_result = asyncio.run(pipeline.make_embed_file(
    pdf_path=PDF_PATH,
    user_id=USER_ID,
    pdf_doc_id=PDF_DOC_ID,
))
print(f"Embedded template: {embed_result.get('embedded_pdf_path')}")

fill_result = asyncio.run(pipeline.fill_pdf(
    pdf_path=PDF_PATH,
    user_id=USER_ID,
    pdf_doc_id=PDF_DOC_ID,
    user_data=USER_DATA,
))
print(f"Filled PDF (pipeline): {fill_result.get('filled_pdf_path')}")