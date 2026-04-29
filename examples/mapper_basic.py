"""
Mapper — Python library usage examples.

Requires: pip install pdf-autofillr-mapper
"""

import asyncio
import os
from pdf_autofillr_mapper import PDFPipeline, MapperConfig

# ─────────────────────────────────────────────────────────────────────────────
# Example 1 — Quickstart: load config from file, run full pipeline
# ─────────────────────────────────────────────────────────────────────────────
# Copy sample configs once after install:
#   python -c "import pdf_autofillr_mapper; pdf_autofillr_mapper.copy_sample_configs('.')"
# Then set your API key in .env or the environment, and run this script.

cfg = MapperConfig.from_directory("./configs")
cfg.validate()  # warns if no API key is found for either LLM phase

pipeline = PDFPipeline(mapper_config=cfg)
result = asyncio.run(pipeline.run_all(
    input_pdf_path="./data/input/blank_form.pdf",
    input_data_path="./configs/form_keys.json",
))
print("Filled PDF:", result["final_output"])


# ─────────────────────────────────────────────────────────────────────────────
# Example 2 — Programmatic config (no config file, no .env file)
# ─────────────────────────────────────────────────────────────────────────────

cfg2 = MapperConfig(
    llm_model="openai/gpt-4o",
    llm_api_key="sk-your-openai-key",        # Phase 1 — semantic mapping
    headers_llm_model="openai/gpt-4o",
    headers_llm_api_key="sk-your-openai-key", # Phase 2 — headers detection
)

# Or mix providers — use Anthropic for mapping, OpenAI for headers:
cfg_mixed = MapperConfig(
    llm_model="anthropic/claude-3-5-sonnet-20241022",
    llm_api_key="sk-ant-your-anthropic-key",
    headers_llm_model="openai/gpt-4o",
    headers_llm_api_key="sk-your-openai-key",
)


# ─────────────────────────────────────────────────────────────────────────────
# Example 3 — Load from environment variables (Lambda / Docker)
# ─────────────────────────────────────────────────────────────────────────────
# Set in .env or shell:
#   MAPPER_LLM_MODEL=openai/gpt-4o
#   MAPPER_LLM_API_KEY=sk-...           # universal override for Phase 1
#   MAPPER_HEADERS_LLM_MODEL=openai/gpt-4o
#   MAPPER_HEADERS_LLM_API_KEY=sk-...   # universal override for Phase 2 (blank = reuse above)
#
# Or provider-specific (litellm auto-routes by model name prefix):
#   OPENAI_API_KEY=sk-...
#   ANTHROPIC_API_KEY=sk-ant-...

cfg_env = MapperConfig.from_env()


# ─────────────────────────────────────────────────────────────────────────────
# Example 4 — Using different LLM providers
# ─────────────────────────────────────────────────────────────────────────────

# Anthropic Claude (both phases)
cfg_anthropic = MapperConfig(
    llm_model="anthropic/claude-3-5-sonnet-20241022",
    llm_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
    headers_llm_model="anthropic/claude-3-5-sonnet-20241022",
    # headers_llm_api_key blank → reuses MAPPER_LLM_API_KEY env var
)

# Groq (fast inference)
cfg_groq = MapperConfig(
    llm_model="groq/llama-3.3-70b-versatile",
    llm_api_key=os.getenv("GROQ_API_KEY", ""),
    headers_llm_model="groq/llama-3.3-70b-versatile",
)

# Local Ollama (no API key required)
cfg_ollama = MapperConfig(
    llm_model="ollama/llama3.2",
    headers_llm_model="ollama/llama3.2",
)

# Azure OpenAI
cfg_azure = MapperConfig(
    llm_model="azure/gpt-4o",
    llm_api_key=os.getenv("AZURE_API_KEY", ""),
    headers_llm_model="azure/gpt-4o",
)

# AWS Bedrock
cfg_bedrock = MapperConfig(
    llm_model="bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0",
    # Uses AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY from environment
    headers_llm_model="bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0",
)


# ─────────────────────────────────────────────────────────────────────────────
# Example 5 — Step-by-step pipeline (embed once, fill many times)
# ─────────────────────────────────────────────────────────────────────────────

cfg5 = MapperConfig.from_directory("./configs")
pipeline5 = PDFPipeline(mapper_config=cfg5)

# Step 1 — build an embedded template (run once per blank PDF form)
embed_result = asyncio.run(pipeline5.make_embed_file(
    pdf_path="./data/input/blank_form.pdf",
    user_id="example_user",
    pdf_doc_id="lp_sub_v1",
))
print("Embedded template:", embed_result.get("embedded_pdf_path"))

# Step 2 — fill with investor data (reuse the embedded template)
fill_result = asyncio.run(pipeline5.fill_pdf(
    pdf_path="./data/input/blank_form.pdf",
    user_id="example_user",
    pdf_doc_id="lp_sub_v1",
    user_data={
        "investor_name": "Jane Smith",
        "investor_type": "Individual",
        "commitment_amount": "500000",
        "email": "jane@example.com",
    },
))
print("Filled PDF:", fill_result.get("filled_pdf_path"))
