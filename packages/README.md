# PDF-AutoFillr — SDK

> Pip-installable Python packages for the PDF-AutoFillr ecosystem. Developers can install any combination and integrate form-filling into their own applications.

---

## Packages

```
SDK/
├── pdf_autofillr/      → Umbrella package (pdf-autofillr on PyPI)
├── chatbot/            → pdf-autofillr-chatbot
├── doc_upload/         → pdf-autofillr-doc-upload
├── mapper/             → pdf-autofillr-mapper
└── rag/                → pdf-autofillr-rag
```

---

## Install combinations

```bash
# Everything
pip install "pdf-autofillr[all]"

# Chatbot + mapper
pip install "pdf-autofillr[chatbot]"

# Doc upload + mapper
pip install "pdf-autofillr[doc-upload]"

# Chatbot + mapper + RAG
pip install "pdf-autofillr[chatbot,rag]"

# Doc upload + mapper + RAG
pip install "pdf-autofillr[doc-upload,rag]"
```

---

## First-time setup (after install)

```bash
# Creates .env.example, configs/, data/ for your installed combination
pdf-autofillr setup

# Verify everything is configured correctly
pdf-autofillr status
```

---

## Package details

### pdf_autofillr (umbrella)

The top-level package. Detects which sub-packages are installed and runs the setup wizard that creates the correct folder structure, `.env.example`, and `mapper_config.ini` for your combination.

```
pdf_autofillr/src/pdf_autofillr/
├── cli.py       → pdf-autofillr setup / status commands
├── setup.py     → Folder + config generation logic
└── status.py    → Installation and config verification
```

---

### chatbot

Conversational PDF form-filling. An LLM-powered bot collects investor data through natural dialogue and fills a blank PDF form at the end of the session.

```
chatbot/src/chatbot/
├── client.py             → chatbotClient — main SDK interface
├── core/                 → Conversation engine, router, session, states
├── extraction/           → LLM-based field extraction from conversation
├── handlers/             → Per-state handlers (investor type, data collection, ...)
├── pdf/                  → PDF filling interface and mapper integration
├── storage/              → Local, S3, GCS, Azure storage backends
├── config/               → Settings, form config
└── entrypoints/          → CLI, FastAPI, Lambda, Azure, GCP handlers
```

**CLI:**
```bash
chatbot-cli --pdf-path data/input/blank_form.pdf --report
chatbot-server
```

**Key env vars:**
```
CHATBOT_LLM_MODEL=openai/gpt-4o-mini
chatbot_PDF_FILLER=mapper
chatbot_PDF_PATH=./data/input/blank_form.pdf
chatbot_STORAGE=local
```

---

### doc_upload

Batch document extraction and PDF filling. Upload any document — the LLM extracts form field values and fills the blank PDF.

**Supported formats:** PDF, DOCX, PPTX, XLSX, CSV, JSON, TXT, MD, HTML, XML

```
doc_upload/src/pdf_autofillr_doc_upload/
├── client.py          → DocUploadClient — main SDK interface
├── extraction/        → Document reader, LLM extractor, LLM client
├── pdf/               → PDF filling interface and mapper integration
├── storage/           → Local, S3, GCS, Azure storage backends
├── config/            → DocUploadSettings
└── entrypoints/       → CLI, FastAPI, Lambda, Azure, GCP handlers
```

**CLI:**
```bash
doc-upload-cli --document investor.pdf --schema configs/form_keys.json --report
doc-upload-server
```

**Key env vars:**
```
DOC_UPLOAD_LLM_MODEL=openai/gpt-4.1-mini
DOC_UPLOAD_PDF_FILLER=mapper
DOC_UPLOAD_PDF_PATH=./data/input/blank_form.pdf
DOC_UPLOAD_STORAGE=local
```

---

### mapper

The core PDF engine. Extracts fields from a blank PDF, maps them to your schema via LLM, builds an embed template, and fills it with data. Used by both chatbot and doc_upload — can also run standalone.

```
mapper/src/pdf_autofillr_mapper/
├── orchestrator.py       → Main pipeline orchestrator
├── inprocess_filler.py   → Direct in-process PDF filling
├── extractors/           → PyMuPDF-based field extraction
├── mappers/              → Semantic LLM mapping
├── embedders/            → Embed file builder
├── fillers/              → PDF form filling
├── chunkers/             → Page and sliding-window chunking
├── clients/              → LLM clients (OpenAI, Claude, unified)
├── java_utils/           → Java tools for form field operations
└── entrypoints/          → CLI, FastAPI server, Lambda, Azure, GCP
```

**CLI:**
```bash
pdf-mapper extract --pdf data/input/blank_form.pdf
pdf-mapper map     --pdf data/input/blank_form.pdf
pdf-mapper embed   --pdf data/input/blank_form.pdf
pdf-mapper fill    --pdf data/input/blank_form.pdf --data data.json
pdf-mapper run-all --pdf data/input/blank_form.pdf --data data.json
pdf-mapper-server
```

**Config:** `configs/mapper_config.ini` — LLM model, chunking strategy, storage backend, RAG toggle.

---

### rag

Self-learning RAG prediction engine. Predicts canonical form field names by comparing new fields against a vector store that grows with every form fill.

Ships with **137 real LP Subscription Agreement vectors** (OpenAI `text-embedding-3-small`, 1536-dim).

```
rag/src/ragpdf/
├── client.py              → RAGPDFClient — main SDK interface
├── pipeline/              → Prediction, processing, feedback pipelines
├── embeddings/            → OpenAI, Sentence Transformer, LiteLLM, noop backends
├── vector_stores/         → Local JSON, S3, Azure, GCS, Pinecone, ChromaDB, Weaviate
├── correctors/            → OpenAI, Anthropic, LiteLLM, noop correctors
├── services/              → Analytics, case classifier, metrics, time series
├── storage/               → Data storage backends
└── entrypoints/           → CLI, FastAPI server, Lambda, Azure, GCP handlers
```

**CLI:**
```bash
ragpdf init-vectors                          # embed vectors, build vector_database.json
ragpdf predict --user u1 --session s1 ...    # run prediction
ragpdf feedback --user u1 --errors ...       # submit corrections
ragpdf metrics --type global                 # view performance metrics
ragpdf system-info                           # vector count, users, PDFs
ragpdf-server                                # start HTTP server
ragpdf-setup                                 # one-time bootstrap
```

**Vector stores:** local · S3 · Azure · GCS · Pinecone · ChromaDB · Weaviate

**Embedding backends:** OpenAI (default, matches bundled vectors) · Sentence Transformers · LiteLLM

---

## Module connection map

```
chatbot ──┐
          ├──→ mapper ──→ RAG (optional, RAG_ENABLED=true)
doc_upload┘        │
                   └──→ LLM providers (via LiteLLM)
                   └──→ Storage (local / S3 / Azure / GCS)
```

- **chatbot → mapper:** inprocess (default) or HTTP via `MAPPER_API_URL`
- **doc_upload → mapper:** inprocess (default) or HTTP via `MAPPER_API_URL`
- **mapper → RAG:** inprocess (default) or HTTP via `RAG_MODE=http` + `RAG_API_URL`

---

## Testing

Each package has its own test suite:

```bash
# chatbot
cd chatbot && python -m pytest tests/

# doc_upload
cd doc_upload && python run_all_tests.py

# mapper
cd mapper && python -m pytest tests/

# rag
cd rag && python run_all_tests.py
```

---

## Publishing to PyPI

See `pdf_autofillr/pypi.txt` for publishing instructions and version management.

---

*For Lambda deployment see the `dev` and `prod` branches. For documentation see the `docs` branch.*
