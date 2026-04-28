# Deployment Plan

Each package has its own FastAPI server and serverless entrypoints (Lambda · Azure · GCP).

## Package ports (local dev)

| Package | Port | Start command |
|---------|------|---------------|
| mapper | 8000 | `pdf-mapper-server` |
| chatbot | 8001 | `chatbot-server` |
| doc_upload | 8002 | `doc-upload-server` |
| rag | 8003 | `ragpdf-server` |

## Local development

```bash
cd packages/mapper    && pip install -e ".[dev,api]"    && pdf-mapper-server
cd packages/chatbot   && pip install -e ".[dev,server]" && chatbot-server
cd packages/doc_upload && pip install -e ".[dev,server]" && doc-upload-server
cd packages/rag       && pip install -e ".[dev,server]" && ragpdf-server
```

## Docker

```bash
# Build mapper (includes Java)
docker build -f deployment/docker/mapper/Dockerfile -t pdf-autofillr-mapper:latest .

# Build others
docker build -f deployment/docker/chatbot/Dockerfile    -t pdf-autofillr-chatbot:latest .
docker build -f deployment/docker/doc_upload/Dockerfile -t pdf-autofillr-doc-upload:latest .
docker build -f deployment/docker/rag/Dockerfile        -t pdf-autofillr-rag:latest .

# Run with docker-compose
cd deployment/docker/mapper    && docker-compose up
cd deployment/docker/chatbot   && docker-compose up
cd deployment/docker/doc_upload && docker-compose up
cd deployment/docker/rag       && docker-compose up
```

## AWS Lambda

Each package ships `packages/<module>/src/<pkg>/entrypoints/aws_lambda.py`.
Deploy as a Lambda container image — set `DEPLOY_MODE=lambda`.

## Azure Functions

`packages/<module>/src/<pkg>/entrypoints/azure_function.py`. Set `DEPLOY_MODE=azure`.

## GCP Cloud Functions

`packages/<module>/src/<pkg>/entrypoints/gcp_function.py`. Set `DEPLOY_MODE=gcp`.

## Storage

All packages: set `STORAGE=s3` (or `azure`, `gcp`, `local`) and matching credentials in `.env`.

## Run tests before deploying

```bash
cd packages/mapper    && pytest tests/ -q
cd packages/chatbot   && pytest tests/ -q
cd packages/doc_upload && python run_all_tests.py
cd packages/rag       && python run_all_tests.py
```
