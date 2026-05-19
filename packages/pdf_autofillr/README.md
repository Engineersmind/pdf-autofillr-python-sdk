# pdf-autofillr

PDF form-filling ecosystem — chatbot, doc-upload, mapper, and RAG — install any combination.

## Install

```bash
# Full stack (everything)
pip install pdf-autofillr[all]

# Chatbot + mapper (conversational form filling)
pip install pdf-autofillr[chatbot]

# Doc upload + mapper (extract from document → fill PDF)
pip install pdf-autofillr[doc-upload]

# Chatbot + mapper + RAG (self-learning predictions)
pip install pdf-autofillr[chatbot,rag]

# Doc upload + mapper + RAG
pip install pdf-autofillr[doc-upload,rag]

# Chatbot + doc_upload + mapper (both input methods)
pip install pdf-autofillr[chatbot,doc-upload]

# Individual modules standalone
pip install pdf-autofillr-chatbot
pip install pdf-autofillr-doc-upload
pip install pdf-autofillr-mapper
pip install pdf-autofillr-rag
```

## After install

```bash
# Write .env.example, configs/, data/ for your installed combination:
pdf-autofillr setup

# Check that everything is configured correctly:
pdf-autofillr status
```

## Configure

```bash
cp .env.example .env
# Edit .env:
#   Set your API key  → OPENAI_API_KEY=sk-...
#   Set your PDF path → chatbot_PDF_PATH=./data/input/blank_form.pdf
```

Drop your blank (empty) PDF form into `data/input/blank_form.pdf`.

## Start

```bash
pdf-autofillr chatbot       # start chatbot server (port 8001)
pdf-autofillr doc-upload    # start doc_upload server (port 8001)
pdf-autofillr mapper        # start mapper server (port 8000)
pdf-autofillr rag           # start RAG server (port 8000)
```

## How the modules connect

```
User types → CHATBOT ──→ collects fields ──→ MAPPER ──→ fills blank_form.pdf
                                                ↕
User uploads doc → DOC_UPLOAD → extracts fields → MAPPER → fills blank_form.pdf
                                                ↕
                                             RAG ← learns from each run, predicts next time
```

- **chatbot → mapper**: `MAPPER_API_URL` empty = inprocess (default). Set URL = HTTP server.
- **doc_upload → mapper**: same pattern, `MAPPER_API_URL`.
- **mapper → rag**: set `RAG_ENABLED=true` in `.env` + `[rag] enabled=true` in `mapper_config.ini`.

## Cloud storage

Add cloud extras when needed:

```bash
pip install "pdf-autofillr[chatbot,s3]"    # chatbot with S3 storage
pip install "pdf-autofillr[all,gcp]"       # full stack with GCP
pip install "pdf-autofillr[all,azure]"     # full stack with Azure
```

## RAG vector store

```bash
pip install "pdf-autofillr[chatbot,rag,rag-pinecone]"  # Pinecone
pip install "pdf-autofillr[chatbot,rag,rag-chroma]"    # ChromaDB
```

## Module docs

- `chatbot/README.md`
- `doc_upload/README.md`
- `mapper/README.md`
- `rag/README.md`
