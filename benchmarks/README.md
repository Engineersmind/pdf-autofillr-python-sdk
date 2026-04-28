# pdf-autofillr Benchmarks

Standardised evaluation suite for all five packages across real-world PDF form categories.

## Quick start

```bash
# Run mapper benchmarks — all models, financial dataset
python benchmarks/run_benchmark.py --module mapper --dataset financial

# Run RAG benchmarks — specific model
python benchmarks/run_benchmark.py --module rag --model gpt-4o-mini

# Run chatbot benchmarks
python benchmarks/run_benchmark.py --module chatbot --model claude-3-5-haiku

# Run doc_upload benchmarks — all formats
python benchmarks/run_benchmark.py --module doc_upload

# Run everything
python benchmarks/run_benchmark.py
```

## Structure

```
benchmarks/
├── run_benchmark.py        Entry point — dispatches all module × task × model × dataset combos
├── tasks/                  Task definitions (one file per package)
│   ├── mapper_tasks.py     field_extraction · field_mapping · form_filling
│   ├── chatbot_tasks.py    conversation_extraction · session_completion
│   ├── doc_upload_tasks.py document_extraction · end_to_end_fill
│   └── rag_tasks.py        field_prediction · feedback_loop · vector_retrieval
├── metrics/                Scoring functions (one file per package)
│   ├── mapper_metrics.py   precision/recall/F1 · mapping accuracy · fill accuracy · cost
│   ├── chatbot_metrics.py  extraction accuracy · session completion · turns · coverage
│   ├── doc_upload_metrics.py per-format accuracy · fill accuracy
│   └── rag_metrics.py      prediction accuracy · top-k · MRR · feedback improvement
├── models/                 Model config cards (YAML)
├── datasets/               PDF categories (add PDFs + ground truth here)
│   ├── financial/
│   ├── medical/
│   ├── legal/
│   ├── government/
│   ├── hr/
│   └── insurance/
└── results/                Benchmark run outputs + leaderboards
```

## Adding a dataset PDF

1. Drop the PDF into `datasets/<category>/pdfs/`
2. Add its schema keys JSON to `datasets/<category>/schema_keys/`
3. Add expected mappings to `datasets/<category>/ground_truth/`
4. Run: `python benchmarks/run_benchmark.py --module mapper --dataset <category>`
