# Mapper Module - Deployment Guide

## Overview

The mapper module is designed to be **platform-agnostic** and can be deployed to multiple environments:

- **Local Development**: Run on your machine with local filesystem
- **AWS**: Lambda + API Gateway + S3
- **Azure**: Functions + Blob Storage + API Management
- **GCP**: Cloud Functions + Cloud Storage + API Gateway
- **Docker**: Containerized deployment (self-hosted or cloud)

## Architecture Decision

The mapper module follows a **source-based configuration** approach:

```
config.ini → [general] source_type = {local|aws|azure|gcp}
              ↓
         Loads appropriate client
              ↓
         Uses provider-specific paths
```

This means:
- ✅ **One codebase** for all platforms
- ✅ **Configuration-driven** deployment
- ✅ **Optional cloud dependencies** (install only what you need)
- ✅ **Extensible** to new platforms

---

## Deployment Targets

### 1. **Local Development** (Already Working)
**Use Case**: Development, testing, small-scale processing

**Setup**:
```bash
# Install base dependencies
pip install -e .

# Configure
cp config.ini.example config.ini
# Edit config.ini → set source_type = local

# Run API server
python -m uvicorn src.orchestrator:app --reload
```

**Pros**: Fast iteration, easy debugging
**Cons**: Not scalable, no cloud storage

---

### 2. **AWS Deployment**
**Use Case**: Serverless, auto-scaling, S3 storage

**Components**:
- Lambda function (mapper processing)
- API Gateway (REST endpoints)
- S3 buckets (input/output/cache)
- IAM roles (permissions)

**Setup**:
```bash
# Install AWS dependencies
pip install -e ".[aws]"

# Deploy
cd ../../deployment/aws/mapper
./deploy.sh
```

**Configuration**:
```ini
[general]
source_type = aws

[aws]
cache_registry_path = s3://my-bucket/cache/hash_registry.json
output_base_path = s3://my-bucket/pdf-autofiller
```

**See**: [`deployment/aws/mapper/README.md`](../../../deployment/aws/mapper/README.md)

---

### 3. **Azure Deployment**
**Use Case**: Enterprise integration, Azure ecosystem

**Components**:
- Azure Functions (mapper processing)
- Blob Storage (input/output/cache)
- API Management (REST endpoints)
- Managed Identity (authentication)

**Setup**:
```bash
# Install Azure dependencies
pip install -e ".[azure]"

# Deploy
cd ../../deployment/azure/mapper
./deploy.sh
```

**Configuration**:
```ini
[general]
source_type = azure

[azure]
cache_registry_path = azure://my-container/cache/hash_registry.json
output_base_path = azure://my-container/pdf-autofiller
```

**See**: [`deployment/azure/mapper/README.md`](../../../deployment/azure/mapper/README.md)

---

### 4. **GCP Deployment**
**Use Case**: Google Cloud ecosystem, Cloud Run

**Components**:
- Cloud Functions (mapper processing)
- Cloud Storage (input/output/cache)
- API Gateway (REST endpoints)
- Service Account (authentication)

**Setup**:
```bash
# Install GCP dependencies
pip install -e ".[gcp]"

# Deploy
cd ../../deployment/gcp/mapper
./deploy.sh
```

**Configuration**:
```ini
[general]
source_type = gcp

[gcp]
cache_registry_path = gs://my-bucket/cache/hash_registry.json
output_base_path = gs://my-bucket/pdf-autofiller
```

**See**: [`deployment/gcp/mapper/README.md`](../../../deployment/gcp/mapper/README.md)

---

### 5. **Docker Deployment**
**Use Case**: Self-hosted, Kubernetes, cloud-agnostic

**Components**:
- Docker container (FastAPI app)
- Volume mounts (local storage) OR cloud storage
- Environment variables (configuration)

**Setup**:
```bash
# Build image
cd ../../deployment/docker/mapper
docker build -t pdf-mapper:latest .

# Run container
docker run -p 8000:8000 \
  -v /path/to/config.ini:/app/config.ini \
  -v /path/to/data:/data \
  -e SOURCE_TYPE=local \
  pdf-mapper:latest
```

**See**: [`deployment/docker/mapper/README.md`](../../../deployment/docker/mapper/README.md)

---

## Comparison Matrix

| Feature | Local | AWS | Azure | GCP | Docker |
|---------|-------|-----|-------|-----|--------|
| **Scalability** | ❌ Low | ✅ Auto | ✅ Auto | ✅ Auto | ⚠️ Manual |
| **Cost** | ✅ Free | ⚠️ Pay-per-use | ⚠️ Pay-per-use | ⚠️ Pay-per-use | ⚠️ Infrastructure |
| **Setup Complexity** | ✅ Simple | ⚠️ Moderate | ⚠️ Moderate | ⚠️ Moderate | ✅ Simple |
| **Storage** | Local FS | S3 | Blob | Cloud Storage | Any |
| **Auth** | None | IAM | Managed Identity | Service Account | Custom |
| **Cold Start** | ❌ N/A | ⚠️ Yes | ⚠️ Yes | ⚠️ Yes | ❌ No |
| **Best For** | Dev/Testing | Production | Enterprise | ML/Data | Self-hosted |

---

## Deployment Checklist

### Before Deploying:

- [ ] **Test locally first**
  ```bash
  source_type = local
  pytest tests/
  ```

- [ ] **Configure environment variables**
  - LLM API keys (OpenAI, Anthropic, etc.)
  - Cloud credentials (AWS, Azure, GCP)
  - Webhook URLs (Teams notifications)

- [ ] **Update config.ini for target platform**
  ```ini
  source_type = {aws|azure|gcp|local}
  ```

- [ ] **Install platform-specific dependencies**
  ```bash
  pip install -e ".[aws]"  # or azure, gcp
  ```

- [ ] **Test API endpoints**
  ```bash
  curl -X POST http://localhost:8000/health
  ```

### After Deploying:

- [ ] **Verify deployment**
  - Check API Gateway/Function URL
  - Test health endpoint
  - Test mapping endpoint with sample PDF

- [ ] **Monitor logs**
  - AWS CloudWatch
  - Azure Application Insights
  - GCP Cloud Logging

- [ ] **Set up alerts**
  - Error rate > 5%
  - Response time > 30s
  - Failed LLM calls

---

## Environment Variables

Each deployment needs these environment variables:

### Required:
```bash
# LLM API Keys (at least one)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Or for AWS Bedrock/Azure OpenAI/GCP Vertex
AWS_REGION=us-east-1
AZURE_OPENAI_ENDPOINT=https://...
GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
```

### Optional:
```bash
# Notifications
TEAMS_WEBHOOK_URL=https://...

# Performance
LLM_TIMEOUT=300
MAX_CONCURRENT_OPERATIONS=5
```

### Cloud-Specific:

**AWS**:
```bash
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_DEFAULT_REGION=us-east-1
```

**Azure**:
```bash
AZURE_STORAGE_CONNECTION_STRING=...
# OR managed identity (no env vars needed)
```

**GCP**:
```bash
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
GOOGLE_CLOUD_PROJECT=my-project
```

---

## Troubleshooting

### Issue: "Module not found" errors
**Solution**: Install platform dependencies
```bash
pip install -e ".[aws]"  # or azure, gcp
```

### Issue: "Access denied" to storage
**Solution**: Check IAM/permissions
- AWS: Lambda execution role needs S3 permissions
- Azure: Function App needs Storage Blob Data Contributor
- GCP: Service account needs Storage Admin

### Issue: LLM timeouts
**Solution**: Increase timeout in config.ini
```ini
[performance]
llm_timeout = 600  # increase from 300
```

### Issue: Cold starts too slow
**Solution**: 
- AWS: Use provisioned concurrency
- Azure: Use Premium plan
- GCP: Use min instances
- Docker: Keep container warm with health checks

---

## Next Steps

1. **Choose your deployment target** (recommend starting with local → Docker → cloud)
2. **Follow platform-specific guide** in `deployment/{platform}/mapper/README.md`
3. **Test with sample PDFs** from `data/modules/mapper_sample/`
4. **Set up monitoring and alerts**
5. **Configure CI/CD pipeline** (optional)

---

## Related Documentation

- [Setup Guide](SETUP_GUIDE.md) - Initial configuration
- [Module README](README.md) - Module overview
- [API Reference](../../docs/api-reference/mapper-api.md) - API endpoints
- [Architecture](../../docs/architecture/system-overview.md) - System design

---

## Support

For deployment issues:
1. Check troubleshooting section above
2. Review platform-specific README
3. Check logs in cloud console
4. Open issue on GitHub
