# pdf-autofillr-mapper

Core PDF processing engine. All other packages depend on it.

## Install

```bash
pip install pdf-autofillr-mapper                          # core
pip install "pdf-autofillr-mapper[api]"                  # + FastAPI server
pip install "pdf-autofillr-mapper[aws]"                  # + S3
pip install "pdf-autofillr-mapper[all]"                  # + API + all cloud
```

## CLI

```bash
pdf-mapper extract --pdf blank_form.pdf                   # inspect fields
pdf-mapper embed   --pdf blank_form.pdf                   # build template
pdf-mapper fill    --pdf blank_form.pdf --data data.json  # fill
pdf-mapper run-all --pdf blank_form.pdf --data data.json  # full pipeline
pdf-mapper-server                                         # REST API :8000
```

## Python

```python
from pdf_autofillr_mapper import MapperOrchestrator

orch = MapperOrchestrator.from_env()
result = orch.run_all(
    pdf_path="blank_form.pdf",
    user_data={"investor_name": "Jane Smith", "amount": "500000"},
    user_id="user_001",
    pdf_doc_id="lp_sub_v1",
)
print(result.filled_pdf_path)
```

## Key env vars

```bash
MAPPER_LLM_MODEL=openai/gpt-4o-mini
OPENAI_API_KEY=sk-...
MAPPER_STORAGE=local          # local | s3 | azure | gcp
MAPPER_DATA_PATH=./data
RAG_ENABLED=false             # true to enable RAG pass
```

## Source layout

```
packages/mapper/src/pdf_autofillr_mapper/
├── orchestrator.py     Main pipeline
├── inprocess_filler.py Direct fill (no HTTP)
├── extractors/         PyMuPDF field extraction
├── mappers/            Semantic LLM mapping
├── embedders/          Embed metadata into PDF
├── fillers/            Write values into form fields
├── chunkers/           Page / sliding-window chunking
├── clients/            LLM clients (OpenAI, Claude, LiteLLM)
├── java_utils/         Java tools for complex form operations
└── entrypoints/        CLI · FastAPI · Lambda · Azure · GCP
```
