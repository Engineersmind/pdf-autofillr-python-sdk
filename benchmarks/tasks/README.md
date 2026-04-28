# Benchmark Tasks

One task file per package. All functions raise `NotImplementedError` — signatures define the contract.

## mapper_tasks.py — pdf-autofillr-mapper

| Task | Input | Key metrics |
|------|-------|-------------|
| `field_extraction` | PDF | Precision · Recall · F1 |
| `field_mapping` | PDF + schema keys + model | Exact accuracy · Fuzzy accuracy · Confidence |
| `form_filling` | Embedded PDF + user data | Fill accuracy % |

## chatbot_tasks.py — pdf-autofillr-chatbot

| Task | Input | Key metrics |
|------|-------|-------------|
| `conversation_extraction` | Transcript + form keys + model | Extraction accuracy · Field coverage · Turns |
| `session_completion` | Sessions dir | Completion rate · Avg turns |

## doc_upload_tasks.py — pdf-autofillr-doc-upload

| Task | Input | Key metrics |
|------|-------|-------------|
| `document_extraction` | Document + schema keys + model | Extraction accuracy per format |
| `end_to_end_fill` | Document + blank PDF + model | Extraction + fill accuracy |

## rag_tasks.py — pdf-autofillr-rag

| Task | Input | Key metrics |
|------|-------|-------------|
| `field_prediction` | Fields + vector store + model | Accuracy · Top-3 · MRR |
| `feedback_loop` | Fields + corrections | Accuracy before/after · Improvement |
| `vector_retrieval` | Query fields + relevant map | Precision · Recall · F1 |

## Running

```bash
python benchmarks/run_benchmark.py --module mapper --task field_mapping --model gpt-4o-mini --dataset financial
python benchmarks/run_benchmark.py --module rag    --task field_prediction --model claude-3-5-haiku
python benchmarks/run_benchmark.py --module chatbot --task conversation_extraction --model gpt-4o-mini
```
