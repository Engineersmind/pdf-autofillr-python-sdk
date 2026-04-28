# Mapper Module - Docker Setup

## 📦 What's Included

This directory contains everything needed to build and deploy the Mapper module as a Docker container:

```
modules/mapper/
├── Dockerfile              ← Universal Docker image (all clouds)
├── requirements-full.txt   ← Consolidated dependencies (AWS+Azure+GCP)
├── .dockerignore          ← Optimize build
├── docker-build.sh        ← Build script
├── docker-test.sh         ← Test script
└── src/                   ← Application code
```

## 🎯 Strategy

### **One Image, All Clouds**

This Dockerfile creates a **universal image** that includes:
- ✅ All core dependencies (PyMuPDF, OpenAI, etc.)
- ✅ AWS SDK (boto3)
- ✅ Azure SDK (azure-storage-blob)
- ✅ Google Cloud SDK (google-cloud-storage)
- ✅ FastAPI server

**Size**: ~750MB total
**Benefit**: Deploy anywhere without rebuilding!

## 🚀 Quick Start

### 1. Build Image

```bash
cd /Users/raghava/Documents/EMC/pdf-autofillr/modules/mapper

# Build with script
./docker-build.sh

# Or build manually
docker build -t pdf-mapper:latest .
```

### 2. Test Image

```bash
# Automated test
export OPENAI_API_KEY=sk-your-key-here
./docker-test.sh

# Or test manually
docker run -p 8000:8000 \
  -e SOURCE_TYPE=local \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  pdf-mapper:latest
```

### 3. Verify

```bash
# Health check
curl http://localhost:8000/health

# API docs
open http://localhost:8000/docs
```

## 🔧 Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SOURCE_TYPE` | Yes | `local` | Storage backend: `local`, `aws`, `azure`, `gcp` |
| `OPENAI_API_KEY` | Yes | - | OpenAI API key |
| `LOG_LEVEL` | No | `INFO` | Logging level |
| `PORT` | No | `8000` | API server port |

### Cloud-Specific Variables

**AWS**:
```bash
docker run \
  -e SOURCE_TYPE=aws \
  -e AWS_REGION=us-east-1 \
  -e AWS_ACCESS_KEY_ID=... \
  -e AWS_SECRET_ACCESS_KEY=... \
  -e OPENAI_API_KEY=... \
  pdf-mapper:latest
```

**Azure**:
```bash
docker run \
  -e SOURCE_TYPE=azure \
  -e AZURE_STORAGE_CONNECTION_STRING=... \
  -e OPENAI_API_KEY=... \
  pdf-mapper:latest
```

**GCP**:
```bash
docker run \
  -e SOURCE_TYPE=gcp \
  -e GOOGLE_CLOUD_PROJECT=my-project \
  -v /path/to/key.json:/app/key.json \
  -e GOOGLE_APPLICATION_CREDENTIALS=/app/key.json \
  -e OPENAI_API_KEY=... \
  pdf-mapper:latest
```

## 📊 Image Details

### Size Breakdown

```
Base (python:3.11-slim):    150MB
Core dependencies:          400MB
Cloud SDKs:
  - boto3 (AWS):             50MB
  - azure-storage-blob:      80MB
  - google-cloud-storage:    70MB
Application code:            10MB
─────────────────────────────────
Total:                      ~750MB
```

### What's Included

- ✅ PyMuPDF (PDF processing)
- ✅ OpenAI/Anthropic clients
- ✅ FastAPI + Uvicorn
- ✅ All cloud SDKs (AWS, Azure, GCP)
- ✅ Mapper module code
- ✅ API server

## 🧪 Testing

### Local Testing

```bash
# 1. Build
./docker-build.sh

# 2. Run
docker run -d -p 8000:8000 \
  -e SOURCE_TYPE=local \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  -v $(pwd)/../../data:/data \
  --name mapper-test \
  pdf-mapper:latest

# 3. Test endpoints
curl http://localhost:8000/health
curl http://localhost:8000/docs

# 4. View logs
docker logs -f mapper-test

# 5. Cleanup
docker stop mapper-test && docker rm mapper-test
```

### Automated Testing

```bash
export OPENAI_API_KEY=sk-...
./docker-test.sh
```

## 🚢 Deployment

### AWS Lambda

```bash
# Build image
./docker-build.sh

# Deploy to AWS
cd ../../deployment/aws/mapper
./deploy.sh
```

**See**: [`deployment/aws/mapper/README.md`](../../deployment/aws/mapper/README.md)

### Azure Functions

```bash
# Build image
./docker-build.sh

# Deploy to Azure
cd ../../deployment/azure/mapper
./deploy.sh
```

**See**: [`deployment/azure/mapper/README.md`](../../deployment/azure/mapper/README.md)

### GCP Cloud Run

```bash
# Build image
./docker-build.sh

# Deploy to GCP
cd ../../deployment/gcp/mapper
./deploy.sh
```

**See**: [`deployment/gcp/mapper/README.md`](../../deployment/gcp/mapper/README.md)

## 🔍 Troubleshooting

### Build Issues

**Error**: `requirements-full.txt not found`
```bash
# Make sure you're in the mapper directory
cd modules/mapper
./docker-build.sh
```

**Error**: `Dockerfile not found`
```bash
# Check file exists
ls -la Dockerfile
```

### Runtime Issues

**Container exits immediately**:
```bash
# Check logs
docker logs <container-id>

# Run interactively
docker run -it --entrypoint bash pdf-mapper:latest
```

**Health check failing**:
```bash
# Check if server is starting
docker logs <container-id>

# Test manually inside container
docker exec -it <container-id> curl http://localhost:8000/health
```

**Import errors**:
```bash
# Verify Python path
docker run --rm pdf-mapper:latest python -c "import sys; print('\n'.join(sys.path))"

# Test imports
docker run --rm pdf-mapper:latest python -c "import src; print('OK')"
```

## 📚 Related Documentation

- [Module README](README.md) - Mapper module overview
- [Deployment Plan](../../deployment/DEPLOYMENT_PLAN.md) - Overall deployment strategy
- [Docker Strategy](../../deployment/DOCKER_STRATEGY.md) - Module-based Docker approach
- [AWS Deployment](../../deployment/aws/mapper/README.md) - AWS-specific deployment

## 💡 Tips

### Development

```bash
# Mount code for live reload
docker run -p 8000:8000 \
  -v $(pwd)/src:/app/src \
  -v $(pwd)/api_server.py:/app/api_server.py \
  -e SOURCE_TYPE=local \
  -e OPENAI_API_KEY=$OPENAI_API_KEY \
  pdf-mapper:latest \
  uvicorn api_server:app --reload --host 0.0.0.0
```

### Debugging

```bash
# Shell into container
docker run -it --entrypoint bash pdf-mapper:latest

# Run with verbose logging
docker run -e LOG_LEVEL=DEBUG pdf-mapper:latest
```

### Optimization

```bash
# Multi-stage build (smaller image)
# Already implemented in Dockerfile

# Prune unused images
docker image prune -a

# Check image layers
docker history pdf-mapper:latest
```

## 🎯 Summary

✅ **DO**:
- Use `docker-build.sh` to build
- Use `docker-test.sh` to test
- Set `SOURCE_TYPE` at runtime
- Include all cloud SDKs (one image)

❌ **DON'T**:
- Build separate images per cloud
- Hardcode cloud credentials in image
- Skip testing before deployment

🎁 **Benefits**:
- Deploy anywhere (AWS/Azure/GCP)
- Test locally with any source
- Single image to maintain
- ~750MB (reasonable size)
