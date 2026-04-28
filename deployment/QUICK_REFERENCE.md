# Quick Reference

## Start all packages locally

```bash
cd packages/mapper    && pdf-mapper-server    # :8000
cd packages/chatbot   && chatbot-server       # :8001
cd packages/doc_upload && doc-upload-server   # :8002
cd packages/rag       && ragpdf-server        # :8003
```

## Health checks

```bash
curl http://localhost:8000/health   # mapper
curl http://localhost:8001/health   # chatbot
curl http://localhost:8002/health   # doc_upload
curl http://localhost:8003/health   # rag
```

## Docker

```bash
docker build -f deployment/docker/mapper/Dockerfile    -t pdf-autofillr-mapper .
docker build -f deployment/docker/chatbot/Dockerfile   -t pdf-autofillr-chatbot .
docker build -f deployment/docker/doc_upload/Dockerfile -t pdf-autofillr-doc-upload .
docker build -f deployment/docker/rag/Dockerfile       -t pdf-autofillr-rag .
```

## Release tags

```bash
git tag mapper-v1.0.8     && git push origin mapper-v1.0.8
git tag chatbot-v0.2.9    && git push origin chatbot-v0.2.9
git tag doc-upload-v0.1.5 && git push origin doc-upload-v0.1.5
git tag rag-v0.2.4        && git push origin rag-v0.2.4
git tag umbrella-v1.1.3   && git push origin umbrella-v1.1.3
```

## Docs

```
docs/getting-started.md         — install and run in 5 minutes
docs/guides/mapper.md           — mapper reference
docs/guides/chatbot.md          — chatbot reference
docs/guides/doc-upload.md       — doc upload reference
docs/guides/rag.md              — RAG reference
docs/guides/plugins.md          — plugin framework
docs/guides/deployment.md       — Docker and cloud
docs/architecture/system-overview.md — how packages connect
```
