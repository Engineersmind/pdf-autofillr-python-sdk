# Mapper Module Setup Guide

**Before running the API server or using the SDK, you MUST configure the mapper module.**

## Quick Start (Local Development)

### 1. Copy Environment Variables Template

```bash
cd modules/mapper
cp .env.example .env
```

### 2. Edit `.env` - Set Your API Keys

Open `.env` and configure at minimum:

```bash
# ============================================
# REQUIRED: Choose cloud provider or local
# ============================================
CLOUD_PROVIDER=local

# ============================================
# REQUIRED: LLM API Key (choose one)
# ============================================
# For OpenAI (most common)
OPENAI_API_KEY=sk-your-actual-key-here

# OR for Claude/Anthropic
ANTHROPIC_API_KEY=sk-ant-your-actual-key-here

# OR for AWS Bedrock (already configured if using AWS)
# Uses AWS credentials below

# OR for Azure OpenAI
AZURE_OPENAI_API_KEY=your-azure-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/

# ============================================
# OPTIONAL: For RAG (second mapper)
# ============================================
RAG_API_URL=https://your-rag-api-url.com
# Leave empty to disable RAG
```

### 3. Edit `config.ini` - Configure Storage

Open `config.ini` and set:

```ini
[general]
# For local development
source_type = local

[mapping]
# Choose your LLM model
llm_model = gpt-4o
# or: claude-3-5-sonnet-20241022
# or: bedrock/anthropic.claude-3-5-sonnet-20241022-v2:0

# Use RAG second mapper?
use_second_mapper = false
# Set to true if you have RAG API configured

[local]
# Update these paths to your actual local directories
cache_registry_path = /path/to/your/cache/hash_registry.json
output_base_path = /path/to/your/output
local_input_pdf = /path/to/test/input.pdf
local_input_json = /path/to/test/input.json
```

### 4. Verify Configuration

```bash
# Check if config files exist
ls -la .env config.ini

# Test configuration
python -c "from src.core.config import GlobalConfig; print(GlobalConfig())"
```

### 5. Install Dependencies

```bash
# Install required packages
pip install -r requirements.txt

# For API server (if running FastAPI)
pip install -r requirements-api.txt
```

### 6. Start API Server

```bash
python api_server.py
```

You should see:
```
INFO:     Started server process [12345]
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### 7. Test Server

Open another terminal:

```bash
# Health check
curl http://localhost:8000/health

# Or open in browser
open http://localhost:8000/docs
```

---

## Configuration for Different Environments

### Local Development (Recommended for Testing)

```bash
# .env
CLOUD_PROVIDER=local
OPENAI_API_KEY=sk-your-key-here
```

```ini
# config.ini
[general]
source_type = local

[local]
output_base_path = /Users/yourname/pdf-autofiller/output
cache_registry_path = /Users/yourname/pdf-autofiller/cache/hash_registry.json
```

### AWS Deployment

```bash
# .env
CLOUD_PROVIDER=aws
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
AWS_S3_BUCKET=your-pdf-bucket
OPENAI_API_KEY=sk-your-key-here
```

```ini
# config.ini
[general]
source_type = aws

[aws]
cache_registry_path = s3://your-bucket/pdf-autofiller/cache/hash_registry.json
output_base_path = s3://your-bucket/pdf-autofiller
```

### Azure Deployment

```bash
# .env
CLOUD_PROVIDER=azure
AZURE_STORAGE_CONNECTION_STRING=your-connection-string
AZURE_STORAGE_ACCOUNT_NAME=your-storage-account
AZURE_OPENAI_API_KEY=your-azure-key
```

```ini
# config.ini
[general]
source_type = azure

[azure]
cache_registry_path = azure://your-container/pdf-autofiller/cache/hash_registry.json
output_base_path = azure://your-container/pdf-autofiller
```

---

## Required vs Optional Configuration

### ✅ REQUIRED

1. **LLM API Key** (in `.env`)
   - `OPENAI_API_KEY` OR
   - `ANTHROPIC_API_KEY` OR
   - AWS credentials (if using Bedrock) OR
   - Azure credentials (if using Azure OpenAI)

2. **Cloud Provider** (in `.env`)
   - `CLOUD_PROVIDER=local` (for local testing)
   - `CLOUD_PROVIDER=aws` (for AWS)
   - `CLOUD_PROVIDER=azure` (for Azure)
   - `CLOUD_PROVIDER=gcp` (for GCP)

3. **Storage Configuration** (in `config.ini`)
   - `source_type` must match `CLOUD_PROVIDER`
   - Paths for cache and output
   - LLM model selection

### 🔷 OPTIONAL

1. **RAG API** (in `.env` and `config.ini`)
   - Only needed if using second mapper
   - Set `use_second_mapper = false` to disable

2. **Teams Notifications** (in `.env` and `config.ini`)
   - For operational alerts
   - Disabled by default

3. **Advanced Settings** (in `config.ini`)
   - Temperature, max tokens, chunking strategy
   - Have sensible defaults

---

## Troubleshooting

### "Module 'boto3' not found"

**Problem:** RAG API URL is set but boto3 not installed.

**Solution:** Either:
```ini
# config.ini
[general]
rag_api_url = 
# Leave empty to disable RAG
```

Or install boto3:
```bash
pip install boto3
```

### "OpenAI API key not found"

**Problem:** Missing API key in `.env`

**Solution:**
```bash
# Add to .env
OPENAI_API_KEY=sk-your-actual-key-here
```

### "Storage path not found"

**Problem:** Paths in `config.ini` don't exist

**Solution:** Create the directories:
```bash
mkdir -p /path/to/your/output
mkdir -p /path/to/your/cache
```

### Server won't start

**Problem:** Missing dependencies

**Solution:**
```bash
pip install -r requirements.txt
pip install -r requirements-api.txt
```

---

## Next Steps

Once the mapper module is configured and running:

1. **Test with curl:**
   ```bash
   curl http://localhost:8000/health
   ```

2. **Install SDK:**
   ```bash
   cd ../../sdks/python
   pip install -e .
   ```

3. **Configure SDK:**
   ```bash
   cd sdks/python
   cp .env.example .env
   # Edit .env to set API_URL=http://localhost:8000
   ```

4. **Use SDK:**
   ```bash
   pdf-autofiller --help
   ```

---

## File Checklist

Before running the server, make sure these files are configured:

- [ ] `modules/mapper/.env` - Environment variables with API keys
- [ ] `modules/mapper/config.ini` - Storage paths and LLM settings
- [ ] `modules/mapper/requirements.txt` - Dependencies installed
- [ ] `modules/mapper/api_server.py` - Server file exists

**DO NOT commit `.env` to git!** (Already in `.gitignore`)

---

## Summary

**Minimum config for local testing:**

1. Copy `.env.example` → `.env`
2. Add your OpenAI API key to `.env`
3. Set `CLOUD_PROVIDER=local` in `.env`
4. Update local paths in `config.ini` [local] section
5. Run `python api_server.py`

That's it! 🚀
