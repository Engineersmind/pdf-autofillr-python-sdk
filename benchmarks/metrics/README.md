# Benchmark Metrics

One metrics file per package. All functions raise `NotImplementedError` until implemented — the signatures and docstrings define the contract.

| File | Package | Tasks covered |
|------|---------|---------------|
| `mapper_metrics.py` | pdf-autofillr-mapper | field_extraction · field_mapping · form_filling · performance |
| `chatbot_metrics.py` | pdf-autofillr-chatbot | extraction_accuracy · session_completion · turns · field_coverage |
| `doc_upload_metrics.py` | pdf-autofillr-doc-upload | extraction_accuracy (per format) · fill_accuracy · format_coverage |
| `rag_metrics.py` | pdf-autofillr-rag | prediction_accuracy · top-k · MRR · feedback_improvement · retrieval_precision |

## Shared: performance

`mapper_metrics.py` contains `estimate_cost()` and `MODEL_PRICING` which are shared across all modules — import from there.

## Adding results

After running benchmarks, save JSON to `results/<module>/<model>_<dataset>_<task>_<date>.json`.
