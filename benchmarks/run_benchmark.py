"""
pdf-autofillr Benchmark Runner

Usage:
    python benchmarks/run_benchmark.py
    python benchmarks/run_benchmark.py --module mapper --task field_mapping
    python benchmarks/run_benchmark.py --module mapper --model gpt-4o-mini --dataset financial
    python benchmarks/run_benchmark.py --module rag --task field_prediction --model claude-3-5-haiku
"""

import argparse

MODULES  = ["mapper", "chatbot", "doc_upload", "rag"]
DATASETS = ["financial", "medical", "legal", "government", "hr", "insurance"]
MODELS   = ["gpt-4o", "gpt-4o-mini", "claude-3-5-sonnet", "claude-3-5-haiku", "llama3.1", "mistral"]

MODULE_TASKS = {
    "mapper":     ["field_extraction", "field_mapping", "form_filling"],
    "chatbot":    ["conversation_extraction", "session_completion"],
    "doc_upload": ["document_extraction", "end_to_end_fill"],
    "rag":        ["field_prediction", "feedback_loop", "vector_retrieval"],
}


def parse_args():
    parser = argparse.ArgumentParser(description="Run pdf-autofillr benchmarks")
    parser.add_argument("--module",  choices=MODULES,  default=None, help="Package to benchmark (default: all)")
    parser.add_argument("--task",    default=None, help="Task name (default: all for module)")
    parser.add_argument("--model",   choices=MODELS,   default=None, help="Model (default: all)")
    parser.add_argument("--dataset", choices=DATASETS, default=None, help="Dataset category (default: all)")
    parser.add_argument("--output",  default="benchmarks/results", help="Output directory")
    return parser.parse_args()


def run(module: str, task: str, model: str, dataset: str, output_dir: str):
    """Run one module × task × model × dataset combination."""
    raise NotImplementedError(f"Not yet implemented: {module}/{task}/{model}/{dataset}")


def main():
    args = parse_args()

    modules = [args.module] if args.module else MODULES
    models  = [args.model]  if args.model  else MODELS

    for module in modules:
        tasks    = [args.task]    if args.task    else MODULE_TASKS[module]
        datasets = [args.dataset] if args.dataset else (
            DATASETS if module in ("mapper", "doc_upload") else ["general"]
        )
        for task in tasks:
            for model in models:
                for dataset in datasets:
                    label = f"{module}/{task}/{model}/{dataset}"
                    print(f"Running: {label} ...")
                    try:
                        run(module, task, model, dataset, args.output)
                        print(f"  ✓ done")
                    except NotImplementedError as e:
                        print(f"  – skipped ({e})")


if __name__ == "__main__":
    main()
