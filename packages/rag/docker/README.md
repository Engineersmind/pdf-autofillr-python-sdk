# Docker

All Docker files live here. Build context is always the **project root** (one level up).

## Files

| File | Purpose |
|---|---|
| `Dockerfile` | FastAPI server — production entrypoint (multi-stage, slim runtime) |
| `Dockerfile.test` | Test runner — unit + integration tests, no API keys needed |
| `Dockerfile.lambda` | AWS Lambda container image |
| `docker-compose.yml` | Local dev orchestration (server, tests, optional Chroma/Weaviate) |

`.dockerignore` lives at the **project root** — Docker requires it there.

---

## Quick start (from the project root)

```bash
# Start the FastAPI server
docker compose -f docker/docker-compose.yml up server

# Run all unit tests
docker compose -f docker/docker-compose.yml run --rm test

# Run only unit tests
docker compose -f docker/docker-compose.yml run --rm test pytest tests/unit/ -v

# Run only integration tests
docker compose -f docker/docker-compose.yml run --rm test pytest tests/integration/ -v -m integration

# Run with coverage report
docker compose -f docker/docker-compose.yml run --rm test pytest tests/ --cov=ragpdf --cov-report=html

# Server + ChromaDB vector store
docker compose -f docker/docker-compose.yml --profile chroma up

# Server + Weaviate vector store
docker compose -f docker/docker-compose.yml --profile weaviate up
```

---

## Building images manually (from the project root)

```bash
# Production server
docker build -f docker/Dockerfile -t ragpdf-server .

# Test runner
docker build -f docker/Dockerfile.test -t ragpdf-test .

# Lambda
docker build -f docker/Dockerfile.lambda -t ragpdf-lambda .
```

---

## Lambda deployment

After building `ragpdf-lambda`:

```bash
# Tag and push to ECR
aws ecr get-login-password | docker login --username AWS --password-stdin <account>.dkr.ecr.<region>.amazonaws.com
docker tag ragpdf-lambda <account>.dkr.ecr.<region>.amazonaws.com/ragpdf-lambda:latest
docker push <account>.dkr.ecr.<region>.amazonaws.com/ragpdf-lambda:latest
```

Set the Lambda handler to: `ragpdf.entrypoints.aws_lambda.lambda_handler`

Required Lambda env vars:
```
RAGPDF_STORAGE=s3
RAGPDF_VECTOR_STORE=s3
RAGPDF_S3_BUCKET=your-bucket
RAGPDF_API_KEY=your-secret
RAGPDF_CORRECTOR_BACKEND=noop   # or openai / anthropic
```