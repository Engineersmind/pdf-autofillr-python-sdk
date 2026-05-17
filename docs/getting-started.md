# Getting Started

## 1. Install

```bash
# Everything
pip install "pdf-autofillr[all]"

# Mapper only (core engine)
pip install pdf-autofillr-mapper

# Chatbot + mapper
pip install "pdf-autofillr[chatbot]"

# Doc upload + mapper
pip install "pdf-autofillr[doc-upload]"

# Chatbot + RAG (self-learning)
pip install "pdf-autofillr[chatbot-rag]"

# Doc upload + RAG
pip install "pdf-autofillr[doc-upload-rag]"

# With cloud storage
pip install "pdf-autofillr[chatbot,s3]"     # AWS S3
pip install "pdf-autofillr[chatbot,azure]"  # Azure Blob
pip install "pdf-autofillr[chatbot,gcp]"    # Google Cloud
```

## 2. First-time setup

```bash
# Creates .env.example, configs/, data/ for your installed packages
pdf-autofillr setup

# Verify everything is configured
pdf-autofillr status
```

Then copy and fill in your LLM key:

```bash
cp .env.example .env
# Edit .env — set LLM_MODEL and API key
```

## 3. Run

### Mapper (standalone)

```bash
pdf-mapper embed --pdf path/to/blank_form.pdf          # once per template
pdf-mapper fill  --pdf path/to/blank_form.pdf --data user.json
pdf-mapper run-all --pdf path/to/blank_form.pdf --data user.json
pdf-mapper-server     # REST API → http://localhost:8000/docs
```

### Chatbot

```bash
chatbot-cli --pdf-path data/input/blank_form.pdf       # interactive session
chatbot-server        # REST API → http://localhost:8001/docs
```

### Doc Upload

```bash
doc-upload-cli --document investor.pdf --schema configs/form_keys.json
doc-upload-server     # REST API → http://localhost:8002/docs
```

### RAG

```bash
ragpdf-setup && ragpdf init-vectors                    # first time only
ragpdf predict --user u1 --session s1 --pdf form_id
ragpdf-server         # REST API → http://localhost:8003/docs
```

## 4. LLM configuration (.env)

```bash
# OpenAI (default)
LLM_MODEL=openai/gpt-4o-mini
OPENAI_API_KEY=sk-...

# Anthropic
LLM_MODEL=anthropic/claude-haiku-4-5
ANTHROPIC_API_KEY=sk-ant-...

# Free local — install Ollama from https://ollama.com
LLM_MODEL=ollama/llama3.1
OLLAMA_API_BASE=http://localhost:11434
# then: ollama pull llama3.1
```
