# Deployment

See [`deployment/`](../../deployment/) for full docs. Quick reference:

## Docker

```bash
docker build -f deployment/docker/mapper/Dockerfile    -t pdf-autofillr-mapper .
docker build -f deployment/docker/chatbot/Dockerfile   -t pdf-autofillr-chatbot .
docker build -f deployment/docker/doc_upload/Dockerfile -t pdf-autofillr-doc-upload .
docker build -f deployment/docker/rag/Dockerfile       -t pdf-autofillr-rag .
```

## Serverless entrypoints

Each package: `packages/<module>/src/<pkg>/entrypoints/`
- `aws_lambda.py` — Lambda
- `azure_function.py` — Azure Functions
- `gcp_function.py` — GCP Cloud Functions

## Environment variables

All packages read from `.env`. Key ones:

| Variable | Description |
|----------|-------------|
| `LLM_MODEL` | LiteLLM model string |
| `OPENAI_API_KEY` | OpenAI |
| `ANTHROPIC_API_KEY` | Anthropic |
| `STORAGE` | `local` · `s3` · `azure` · `gcp` |
| `MAPPER_API_URL` | Set if mapper runs as separate service |
| `RAG_ENABLED` | `true` to enable RAG |
