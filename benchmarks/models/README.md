# Benchmark Models

Each YAML card describes one model used in benchmarks.

```
name:           short identifier used in --model flag and result filenames
provider:       openai | anthropic | local
litellm_model:  full LiteLLM model string (set as LLM_MODEL in .env)
context_window: max tokens
pricing:
  input_per_1m_tokens:  USD per 1M input tokens
  output_per_1m_tokens: USD per 1M output tokens
env_key:        environment variable that holds the API key
local:          true if runs locally (no API key, no cost)
notes:          when to use this model
```

## Adding a model

1. Create `benchmarks/models/<name>.yaml` following the schema above.
2. Add the model name to `MODELS` in `benchmarks/run_benchmark.py`.
3. Add pricing to `MODEL_PRICING` in `benchmarks/metrics/mapper_metrics.py`.
