# LLM Providers

All packages use [LiteLLM](https://docs.litellm.ai/docs/providers). Set `LLM_MODEL` in `.env`.

```bash
# OpenAI
LLM_MODEL=openai/gpt-4o-mini
OPENAI_API_KEY=sk-...

# Anthropic
LLM_MODEL=anthropic/claude-haiku-4-5
ANTHROPIC_API_KEY=sk-ant-...

# AWS Bedrock (IAM — no API key)
LLM_MODEL=bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0

# Azure OpenAI
LLM_MODEL=azure/gpt-4o
AZURE_API_KEY=...
AZURE_API_BASE=https://your-resource.openai.azure.com/
AZURE_API_VERSION=2024-02-01

# Google Gemini
LLM_MODEL=gemini/gemini-1.5-flash
GEMINI_API_KEY=...

# Local via Ollama — free, no API key
LLM_MODEL=ollama/llama3.1
OLLAMA_API_BASE=http://localhost:11434
# Install: https://ollama.com — then: ollama pull llama3.1
```

See [benchmarks/](../../benchmarks/) for model accuracy and cost comparisons.
