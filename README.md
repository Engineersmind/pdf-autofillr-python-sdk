[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
<div align="center">

# pdf-autofillr

**AI-powered PDF form filling — extract, map, and fill any PDF form automatically.**

[![PyPI](https://img.shields.io/pypi/v/pdf-autofillr)](https://pypi.org/project/pdf-autofillr/)
[![Python](https://img.shields.io/pypi/pyversions/pdf-autofillr)](https://pypi.org/project/pdf-autofillr/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Tests](https://github.com/Engineersmind/pdf-autofillr/actions/workflows/tests.yml/badge.svg)](https://github.com/Engineersmind/pdf-autofillr/actions/workflows/tests.yml)

[**Quick Start**](#quick-start) · [**Packages**](#packages) · [**Docs**](docs/) · [**Plugins**](plugins/) · [**Benchmarks**](benchmarks/)

</div>

---

## Process Overview

```
Blank PDF form + your data
        │
        ▼
  pdf-mapper embed         ← once per template (extract fields → LLM map → bake metadata)
        │
        ▼
  Embedded PDF             ← cached and reusable
        │
   user data arrives via:
   ┌───────────────┬───────────────────┐
   │  chatbot      │  doc upload       │  (or direct API call)
   │  conversation │  any document     │
   └───────┬───────┴────────┬──────────┘
           │                │
           ▼                ▼
        pdf-mapper fill   ← writes values into form fields
           │
           ▼
        Filled PDF ✓
```

---

## Packages

| Package | PyPI | Version | Description |
|---------|------|---------|-------------|
| **pdf-autofillr** | umbrella | 1.1.4 | Install any combination via extras |
| **pdf-autofillr-mapper** | `pip install pdf-autofillr-mapper` | 1.0.10 | Core engine: extract · map · embed · fill |
| **pdf-autofillr-chatbot** | `pip install "pdf-autofillr[chatbot]"` | 0.3.0 | LLM conversation → PDF fill |
| **pdf-autofillr-doc-upload** | `pip install "pdf-autofillr[doc-upload]"` | 0.1.5 | Document extraction → PDF fill |
| **pdf-autofillr-rag** | `pip install "pdf-autofillr[rag]"` | 0.2.4 | Self-learning field prediction |

---

## Quick Start

### Install

```bash
pip install "pdf-autofillr[all]"          # everything
pip install pdf-autofillr-mapper           # mapper only
pip install "pdf-autofillr[chatbot]"      # chatbot + mapper
pip install "pdf-autofillr[doc-upload]"   # doc upload + mapper
pip install "pdf-autofillr[chatbot-rag]"  # chatbot + mapper + RAG
```

### First-time setup

```bash
pdf-autofillr setup    # creates .env.example, configs/, data/
pdf-autofillr status   # verify everything is configured
cp .env.example .env   # add your API key
```

### Configure LLM

```bash
# OpenAI (default)
LLM_MODEL=openai/gpt-4o-mini
OPENAI_API_KEY=sk-...

# Free local with Ollama
LLM_MODEL=ollama/llama3.1
# install: https://ollama.com — then: ollama pull llama3.1
```

### Run

```bash
# Mapper
pdf-mapper embed --pdf blank_form.pdf
pdf-mapper fill  --pdf blank_form.pdf --data user.json
pdf-mapper-server      # → http://localhost:8000/docs

# Chatbot
chatbot-cli --pdf-path data/input/blank_form.pdf
chatbot-server         # → http://localhost:8001/docs

# Doc Upload
doc-upload-cli --document investor.pdf --schema configs/form_keys.json
doc-upload-server      # → http://localhost:8002/docs

# RAG
ragpdf-setup && ragpdf init-vectors
ragpdf-server          # → http://localhost:8003/docs
```

---

## Architecture

```
chatbot ──┐
          ├──→ pdf-autofillr-mapper ──→ pdf-autofillr-rag (optional)
doc_upload┘              │
                         └──→ LLM (via LiteLLM — any provider)
                         └──→ Storage (local · S3 · Azure · GCS)
```

All packages support **in-process** or **HTTP** communication. See [docs/architecture/system-overview.md](docs/architecture/system-overview.md).

---

## Repository layout

```
pdf-autofillr/
│
├── packages/               ← The 5 PyPI packages (source of truth)
│   ├── mapper/             ← pdf-autofillr-mapper
│   ├── chatbot/            ← pdf-autofillr-chatbot
│   ├── doc_upload/         ← pdf-autofillr-doc-upload
│   ├── rag/                ← pdf-autofillr-rag
│   └── pdf_autofillr/      ← pdf-autofillr (umbrella)
│
├── plugins/                ← Extension framework
│   ├── core/               ← pdf-autofiller-core (shared interfaces)
│   ├── pdf_autofillr/      ← pdf-autofiller-plugins (plugin SDK)
│   ├── mapper/             ← mapper-specific plugin examples
│   ├── chatbot/            ← chatbot-specific plugin examples
│   ├── doc_upload/         ← doc_upload-specific plugin examples
│   └── rag/                ← rag-specific plugin examples
│
├── benchmarks/             ← LLM evaluation suite (all 4 packages)
├── deployment/             ← Docker for all 4 packages + cloud docs
├── docs/                   ← Guides and architecture
└── examples/               ← Working Python examples for all packages
```

---

## Development

```bash
git clone https://github.com/Engineersmind/pdf-autofillr.git
cd pdf-autofillr

cd packages/mapper          # or chatbot, rag, doc_upload
pip install -e ".[dev]"
cp .env.example .env
pytest tests/ -q
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide and release process.

---

## License

MIT — see [LICENSE](LICENSE).
