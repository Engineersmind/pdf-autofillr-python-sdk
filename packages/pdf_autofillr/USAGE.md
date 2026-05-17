# pdf-autofillr — Complete Usage Guide

> The umbrella package for the PDF form-filling ecosystem. Install any combination of chatbot, doc-upload, mapper, and RAG modules with a single `pip install`.

---

## Table of Contents

1. [What Is This Package?](#1-what-is-this-package)
2. [Install — Choose Your Combination](#2-install--choose-your-combination)
3. [After Install — Setup & Status](#3-after-install--setup--status)
4. [How the Modules Connect](#4-how-the-modules-connect)
5. [Starting Each Module](#5-starting-each-module)
6. [Cloud Storage Add-ons](#6-cloud-storage-add-ons)
7. [RAG Vector Store Add-ons](#7-rag-vector-store-add-ons)
8. [Individual Package Docs](#8-individual-package-docs)

---

## 1. What Is This Package?

`pdf-autofillr` is a meta-package — it installs and wires together the right combination of modules for your use case. You do not write code against this package directly; it installs the actual SDKs.

| Module | PyPI Package | What it does |
|---|---|---|
| **chatbot** | `pdf-autofillr-chatbot` | Conversational form filling — user types answers |
| **doc-upload** | `pdf-autofillr-doc-upload` | Extract data from an uploaded document, fill PDF |
| **mapper** | `pdf-autofillr-mapper` | Core PDF engine — extract, map, embed, fill |
| **rag** | `pdf-autofillr-rag` | Self-learning RAG predictions, gets smarter over time |

---

## 2. Install — Choose Your Combination

### Single modules

```bash
pip install pdf-autofillr[chatbot]       # chatbot + mapper + FastAPI server
pip install pdf-autofillr[doc-upload]    # doc-upload + mapper + FastAPI server
pip install pdf-autofillr[mapper]        # mapper alone + FastAPI server
pip install pdf-autofillr[rag]           # RAG alone (with OpenAI embeddings)
```

### Common combinations

```bash
# Chatbot + mapper + self-learning RAG
pip install "pdf-autofillr[chatbot,rag]"

# Doc upload + mapper + self-learning RAG
pip install "pdf-autofillr[doc-upload,rag]"

# Both chatbot AND doc-upload input methods + mapper
pip install "pdf-autofillr[chatbot,doc-upload]"

# Full stack: everything
pip install "pdf-autofillr[all]"
```

### Install individual packages directly (no meta-package)

```bash
pip install pdf-autofillr-chatbot
pip install pdf-autofillr-doc-upload
pip install pdf-autofillr-mapper
pip install pdf-autofillr-rag
```

---

## 3. After Install — Setup & Status

```bash
# Write .env.example, configs/, data/ structure for your installed combination
pdf-autofillr setup

# Check what is installed and configured correctly
pdf-autofillr status
```

Then:

```bash
# Copy the generated .env.example to .env and fill in your API key
cp .env.example .env
# Edit .env: set OPENAI_API_KEY=sk-your-key-here

# Drop your blank PDF form into the input directory
# (path shown by pdf-autofillr setup)
cp /path/to/your/blank_form.pdf data/input/blank_form.pdf
```

---

## 4. How the Modules Connect

```
User types answers
      ↓
  CHATBOT ──────────────────────────────────────────────────────┐
                                                                 ↓
User uploads document (PDF/DOCX/XLSX/CSV/...)               MAPPER  ──→ fills blank_form.pdf
      ↓                                                          ↑
  DOC-UPLOAD ───────────────────────────────────────────────────┘
                                                                 ↕
                                              RAG ← learns from every run,
                                                    predicts field mappings next time
```

### Chatbot → Mapper connection

```bash
# In-process (default, no separate server needed)
MAPPER_API_URL=                    # leave empty

# HTTP (mapper running as separate server on port 8000)
MAPPER_API_URL=http://localhost:8000
```

### Doc-upload → Mapper connection

```bash
# Same env vars as chatbot
MAPPER_API_URL=                    # empty = in-process
MAPPER_API_URL=http://localhost:8000  # or HTTP
```

### Mapper → RAG connection

```bash
# In mapper's .env:
RAG_ENABLED=true
RAG_MODE=inprocess                 # or: http

# In mapper's mapper_config.ini:
[rag]
enabled = true
mode = inprocess
```

---

## 5. Starting Each Module

```bash
# Start chatbot API server (port 8001)
chatbot-server
# or
pdf-autofillr chatbot

# Start doc-upload API server (port 8001)
doc-upload-server
# or
pdf-autofillr doc-upload

# Start mapper API server (port 8000)
pdf-mapper-server
# or
pdf-autofillr mapper

# Start RAG API server (port 8000)
ragpdf-server
# or
pdf-autofillr rag
```

### Running chatbot + mapper together (typical setup)

```bash
# Terminal 1 — start mapper
pdf-mapper-server
# Server at http://localhost:8000

# Terminal 2 — start chatbot (connected to mapper via HTTP)
MAPPER_API_URL=http://localhost:8000 chatbot-server
# Server at http://localhost:8001
```

### Or run both with mapper in-process (simpler, one terminal)

```bash
# Set MAPPER_API_URL= (empty) and start chatbot
chatbot_PDF_FILLER=mapper MAPPER_API_URL= chatbot-server
# Mapper runs inside the chatbot process — no separate terminal needed
```

### Quick health checks after starting

```bash
curl http://localhost:8001/health    # chatbot / doc-upload
curl http://localhost:8000/health    # mapper / rag
```

---

## 6. Cloud Storage Add-ons

```bash
# AWS S3
pip install "pdf-autofillr[chatbot,s3]"
pip install "pdf-autofillr[all,s3]"

# Google Cloud Storage
pip install "pdf-autofillr[chatbot,gcp]"
pip install "pdf-autofillr[all,gcp]"

# Azure Blob Storage
pip install "pdf-autofillr[chatbot,azure]"
pip install "pdf-autofillr[all,azure]"
```

---

## 7. RAG Vector Store Add-ons

```bash
# Pinecone (managed vector DB)
pip install "pdf-autofillr[chatbot,rag,rag-pinecone]"

# ChromaDB (local embedded, no server needed)
pip install "pdf-autofillr[chatbot,rag,rag-chroma]"

# Weaviate (self-hosted or cloud)
pip install "pdf-autofillr[chatbot,rag,rag-weaviate]"
```

---

## 8. Individual Package Docs

Each module has its own complete USAGE.md with full API reference, CLI, Docker, tests, and config:

| Module | USAGE file | PyPI page |
|---|---|---|
| chatbot | `chatbot/USAGE.md` | `pypi.org/project/pdf-autofillr-chatbot` |
| doc-upload | `doc_upload/USAGE.md` | `pypi.org/project/pdf-autofillr-doc-upload` |
| mapper | `mapper/USAGE.md` | `pypi.org/project/pdf-autofillr-mapper` |
| rag | `rag/USAGE.md` | `pypi.org/project/pdf-autofillr-rag` |
