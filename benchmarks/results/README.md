# Benchmark Results

Results from `python benchmarks/run_benchmark.py` are saved here as JSON files.

## File naming

```
results/<module>/<model>_<dataset>_<task>_<YYYY-MM-DD>.json
```

Examples:
```
results/mapper/gpt-4o-mini_financial_field_mapping_2026-04-01.json
results/chatbot/claude-3-5-haiku_general_conversation_extraction_2026-04-01.json
results/rag/gpt-4o_general_field_prediction_2026-04-01.json
results/doc_upload/gpt-4o-mini_financial_document_extraction_2026-04-01.json
```

## Leaderboard — Mapper: Field Mapping Accuracy (%)

| Model | Financial | Medical | Legal | Government | HR | Insurance | Avg |
|-------|-----------|---------|-------|------------|----|-----------|-----|
| gpt-4o | — | — | — | — | — | — | — |
| gpt-4o-mini | — | — | — | — | — | — | — |
| claude-3-5-sonnet | — | — | — | — | — | — | — |
| claude-3-5-haiku | — | — | — | — | — | — | — |
| llama3.1 (local) | — | — | — | — | — | — | — |
| mistral (local) | — | — | — | — | — | — | — |

## Leaderboard — Chatbot: Session Completion Rate (%)

| Model | Completion Rate | Avg Turns | Field Coverage |
|-------|----------------|-----------|----------------|
| gpt-4o | — | — | — |
| gpt-4o-mini | — | — | — |
| claude-3-5-haiku | — | — | — |

## Leaderboard — RAG: Field Prediction Accuracy (%)

| Model | Accuracy | Top-3 Accuracy | MRR |
|-------|----------|----------------|-----|
| gpt-4o | — | — | — |
| gpt-4o-mini | — | — | — |
| claude-3-5-haiku | — | — | — |

## Leaderboard — Doc Upload: Extraction Accuracy (%) by Format

| Model | PDF | DOCX | XLSX | CSV | JSON | Avg |
|-------|-----|------|------|-----|------|-----|
| gpt-4o-mini | — | — | — | — | — | — |
| claude-3-5-haiku | — | — | — | — | — | — |

## Leaderboard — Performance (all modules)

| Model | Avg Latency (ms) | Avg Cost ($/PDF) | Notes |
|-------|-----------------|-----------------|-------|
| gpt-4o | — | — | Highest accuracy |
| gpt-4o-mini | — | — | Best cost/accuracy |
| claude-3-5-sonnet | — | — | |
| claude-3-5-haiku | — | — | Fastest Anthropic |
| llama3.1 (local) | — | $0 | Free, no API key |
| mistral (local) | — | $0 | Free, no API key |
