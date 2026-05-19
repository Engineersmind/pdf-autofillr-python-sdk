# System Overview

## The 5 packages

```
pdf-autofillr (umbrella — install helper, zero runtime code)
│
├── pdf-autofillr-mapper     Core engine. All other packages depend on it.
│   ├── extract              Reads all form fields from a blank PDF (PyMuPDF)
│   ├── map                  LLM matches each field to your schema key
│   ├── embed                Bakes the mapping into PDF metadata (one-time per template)
│   └── fill                 Writes user values into the form fields
│
├── pdf-autofillr-chatbot    Collects user data through conversation, then calls mapper.fill
│
├── pdf-autofillr-doc-upload Extracts user data from uploaded documents, then calls mapper.fill
│
└── pdf-autofillr-rag        Self-learning field prediction — improves mapper accuracy over time
```

## Data flow

```
User input
│
├─ chatbot session ──────────────────┐
│                                    │
└─ document upload ──────────────────┤
                                     │ structured {field: value}
                                     ▼
                         pdf-autofillr-mapper
                         ┌──────────────────────┐
                         │ 1. extract (cached)  │
                         │ 2. map (LLM)         │◄── pdf-autofillr-rag (optional)
                         │ 3. embed (cached)    │
                         │ 4. fill              │
                         └──────────────────────┘
                                     │
                               Filled PDF ✓
```

## Connection modes

| Connection | Default | Alternative |
|-----------|---------|-------------|
| chatbot → mapper | in-process | HTTP via `MAPPER_API_URL` |
| doc_upload → mapper | in-process | HTTP via `MAPPER_API_URL` |
| mapper → RAG | disabled | enable: `RAG_ENABLED=true` |
| mapper → RAG (HTTP) | in-process | `RAG_MODE=http` + `RAG_API_URL` |

## Storage backends (all packages)

| Backend | Extra | Env var |
|---------|-------|---------|
| Local filesystem (default) | — | `STORAGE=local` |
| AWS S3 | `[s3]` or `[aws]` | `STORAGE=s3` |
| Azure Blob | `[azure]` | `STORAGE=azure` |
| Google Cloud Storage | `[gcp]` | `STORAGE=gcp` |

## Serverless entrypoints (all packages)

Each package ships entrypoints at `packages/<module>/src/<pkg>/entrypoints/`:

```
aws_lambda.py    → Lambda handler
azure_function.py → Azure Functions
gcp_function.py  → GCP Cloud Functions
fastapi_app.py   → FastAPI HTTP server
cli.py           → CLI tool
```
