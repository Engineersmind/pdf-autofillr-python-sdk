# Docker Strategy

## One image per package

```
deployment/docker/
├── mapper/       Dockerfile · docker-compose.yml · .env.example · build.sh · test.sh
├── chatbot/      Dockerfile · docker-compose.yml · .env.example
├── doc_upload/   Dockerfile · docker-compose.yml · .env.example
└── rag/          Dockerfile · docker-compose.yml · .env.example
```

All images install from PyPI (`pip install "pdf-autofillr-<pkg>[server]"`) and support all cloud providers via env vars — no rebuild needed.

## Build context

Use the **repo root** as Docker build context:

```bash
docker build -f deployment/docker/mapper/Dockerfile -t pdf-autofillr-mapper:latest .
```

## Switch cloud at runtime

```bash
docker run -e SOURCE_TYPE=aws   -e AWS_REGION=us-east-1 ... pdf-autofillr-mapper:latest
docker run -e SOURCE_TYPE=azure -e AZURE_STORAGE_CONNECTION_STRING=... pdf-autofillr-mapper:latest
docker run -e SOURCE_TYPE=gcp   -e GOOGLE_CLOUD_PROJECT=... pdf-autofillr-mapper:latest
docker run -e SOURCE_TYPE=local ... pdf-autofillr-mapper:latest
```

## Connect packages via HTTP

```bash
docker run -p 8000:8000 pdf-autofillr-mapper:latest
docker run -p 8001:8000 -e MAPPER_API_URL=http://host.docker.internal:8000 pdf-autofillr-chatbot:latest
docker run -p 8002:8000 -e MAPPER_API_URL=http://host.docker.internal:8000 pdf-autofillr-doc-upload:latest
docker run -p 8003:8000 pdf-autofillr-rag:latest
```
