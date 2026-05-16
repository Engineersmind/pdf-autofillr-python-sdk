# PDF Mapper Module

The core PDF field extraction, mapping, embedding, and filling engine.

## 🚀 Quick Start

### 1. Configure the Module

**IMPORTANT: You must configure before running!**

```bash
# Copy configuration templates
cp .env.example .env
cp config.ini.example config.ini

# Edit .env - Add your API keys
nano .env

# Edit config.ini - Set your storage paths
nano config.ini
```

See **[SETUP_GUIDE.md](SETUP_GUIDE.md)** for detailed configuration instructions.

### 2. Install Dependencies

```bash
# Core dependencies
pip install -r requirements.txt

# For API server
pip install -r requirements-api.txt
```

### 3. Run API Server

```bash
python api_server.py
```

Server will be available at: **http://localhost:8000**

Interactive docs at: **http://localhost:8000/docs**

---

## 📁 File Structure

```
modules/mapper/
├── .env.example            ← Copy to .env (add your API keys)
├── config.ini.example      ← Copy to config.ini (configure paths)
├── config.ini              ← Active configuration (DO NOT COMMIT)
├── .env                    ← Active environment (DO NOT COMMIT)
├── SETUP_GUIDE.md          ← Detailed setup instructions
├── API_SERVER.md           ← API server documentation
├── api_server.py           ← FastAPI server (run this!)
├── requirements.txt        ← Python dependencies
├── requirements-api.txt    ← API server dependencies
├── setup.py                ← Package setup
└── src/                    ← Core source code
    ├── orchestrator.py     ← Main orchestration logic
    ├── extractors/         ← PDF field extraction
    ├── mappers/            ← Field mapping (LLM)
    ├── embedders/          ← Metadata embedding
    ├── fillers/            ← PDF filling
    ├── chunkers/           ← Document chunking
    ├── groupers/           ← Field grouping
    ├── headers/            ← Header detection
    ├── validators/         ← Field validation
    └── core/               ← Configuration & logging
```

---

## 🎯 What This Module Does

1. **Extract** - Extracts form fields from PDF files
2. **Map** - Maps extracted fields to your data schema using LLM
3. **Embed** - Embeds mapping metadata into PDF for reuse
4. **Fill** - Fills embedded PDFs with actual data

### Operations

| Operation | Input | Output | Use Case |
|-----------|-------|--------|----------|
| **extract** | PDF file | Field list JSON | Discover what fields exist |
| **map** | Extracted fields | Mapping JSON | Create field-to-schema mapping |
| **embed** | PDF + mapping | Embedded PDF | Prepare PDF for filling |
| **fill** | Embedded PDF + data | Filled PDF | Generate completed forms |
| **make-embed** | PDF file | Embedded PDF | One-step: extract+map+embed |
| **run-all** | PDF + data | Filled PDF | Complete pipeline |

---

## 🔧 Configuration Overview

### Required Configuration

**In `.env`:**
```bash
# Choose one
CLOUD_PROVIDER=local          # For local development
# CLOUD_PROVIDER=aws          # For AWS deployment
# CLOUD_PROVIDER=azure        # For Azure deployment

# Add your LLM API key
OPENAI_API_KEY=sk-your-key-here
```

**In `config.ini`:**
```ini
[general]
source_type = local

[mapping]
llm_model = gpt-4o
use_second_mapper = false

[local]
cache_registry_path = /path/to/cache/hash_registry.json
output_base_path = /path/to/output
```

See **[SETUP_GUIDE.md](SETUP_GUIDE.md)** for complete details.

---

## 🌐 Running as API Server

```bash
# Start server
python api_server.py

# In another terminal, test it
curl http://localhost:8000/health
```

**Available endpoints:**
- `GET /` - API info
- `GET /health` - Health check
- `POST /mapper/extract` - Extract fields
- `POST /mapper/map` - Map fields
- `POST /mapper/embed` - Embed metadata
- `POST /mapper/fill` - Fill PDF
- `POST /mapper/make-embed` - Extract+Map+Embed
- `POST /mapper/fill-pdf` - Fill embedded PDF
- `POST /mapper/check-embed-file` - Check if PDF has embeddings
- `POST /mapper/run-all` - Complete pipeline

See **[API_SERVER.md](API_SERVER.md)** for API documentation.

---

## 📦 Using as Python Module

```python
from src.orchestrator import run_extraction, run_mapping, run_embedding, run_filling

# Extract fields
extracted = run_extraction(pdf_path, user_id, pdf_doc_id)

# Map fields
mapped = run_mapping(user_id, pdf_doc_id)

# Embed metadata
embedded = run_embedding(pdf_path, user_id, pdf_doc_id)

# Fill PDF
filled = run_filling(embedded_pdf_path, user_id, pdf_doc_id, input_data)
```

---

## 🧪 Testing

```bash
# Run all tests
pytest

# Run specific test
pytest tests/test_extract.py

# With coverage
pytest --cov=src
```

---

## 🐳 Deployment Options

### Local Development
```bash
python api_server.py
```

### Docker
```bash
docker build -t pdf-mapper .
docker run -p 8000:8000 --env-file .env pdf-mapper
```

### AWS Lambda
See `deployment/aws/` for Lambda deployment scripts.

### Azure Functions
See `deployment/azure/` for Azure deployment scripts.

### GCP Cloud Functions
See `deployment/gcp/` for GCP deployment scripts.

---

## 🔗 Integration with SDK

Once the API server is running, install the SDK:

```bash
cd ../../sdks/python
pip install -e .

# Use CLI
pdf-autofiller --api-url http://localhost:8000 extract input.pdf

# Or Python
from pdf_autofiller import PDFMapperClient
client = PDFMapperClient("http://localhost:8000")
result = client.extract("input.pdf", 1, 100)
```

---

## 📚 Documentation

- **[SETUP_GUIDE.md](SETUP_GUIDE.md)** - Configuration setup
- **[API_SERVER.md](API_SERVER.md)** - API documentation
- **[INSTALLATION_GUIDE.md](INSTALLATION_GUIDE.md)** - Installation details
- **[../../docs/](../../docs/)** - Complete project documentation

---

## 🔍 Troubleshooting

### Module 'boto3' not found
```ini
# In config.ini, set:
[general]
rag_api_url = 
# Leave empty to disable RAG
```

### API key errors
```bash
# Make sure .env has your key:
OPENAI_API_KEY=sk-your-actual-key-here
```

### Import errors
```bash
# Install dependencies:
pip install -r requirements.txt
```

### Server won't start
```bash
# Install API dependencies:
pip install -r requirements-api.txt
```

---

## ⚙️ Environment Variables

Key environment variables (set in `.env`):

| Variable | Required | Description |
|----------|----------|-------------|
| `CLOUD_PROVIDER` | ✅ | `local`, `aws`, `azure`, or `gcp` |
| `OPENAI_API_KEY` | ✅ | OpenAI API key |
| `ANTHROPIC_API_KEY` | 🔷 | Claude/Anthropic key (if using Claude) |
| `AWS_ACCESS_KEY_ID` | 🔷 | AWS credentials (if using AWS) |
| `AWS_SECRET_ACCESS_KEY` | 🔷 | AWS credentials (if using AWS) |
| `AZURE_STORAGE_CONNECTION_STRING` | 🔷 | Azure credentials (if using Azure) |

---

## 📝 License

See [LICENSE](../../LICENSE) file in project root.

---

## 🤝 Contributing

See [CONTRIBUTING.md](../../CONTRIBUTING.md) for guidelines.

---

## Quick Command Reference

```bash
# Setup
cp .env.example .env
cp config.ini.example config.ini
pip install -r requirements.txt requirements-api.txt

# Run server
python api_server.py

# Test
curl http://localhost:8000/health
pytest

# Install SDK (for client usage)
cd ../../sdks/python && pip install -e .
```
