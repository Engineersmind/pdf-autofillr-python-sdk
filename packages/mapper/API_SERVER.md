# FastAPI Server Setup

## Quick Start

### 1. Install Dependencies

```bash
cd modules/mapper
pip install -r requirements.txt
pip install -r requirements-api.txt
```

### 2. Configure

Make sure `config.ini` is set up (already done in your case).

### 3. Run the Server

```bash
cd modules/mapper
python api_server.py
```

**Or with uvicorn directly:**
```bash
cd modules/mapper
uvicorn api_server:app --reload --port 8000
```

### 4. Verify It's Running

```bash
curl http://localhost:8000/health
```

**Output:**
```json
{"status": "healthy"}
```

---

## Test with SDK

Once the server is running:

### Install SDK
```bash
cd sdks/python
pip install -e .
```

### Use CLI
```bash
# Extract
pdf-autofiller --api-url http://localhost:8000 extract /path/to/input.pdf

# Make embed file (recommended)
pdf-autofiller --api-url http://localhost:8000 make-embed /path/to/input.pdf --use-rag

# Complete example
pdf-autofiller \
  --api-url http://localhost:8000 \
  make-embed \
  /Users/raghava/Documents/EMC/pdf-autofillr/data/modules/mapper_sample/input/small_4page.pdf \
  --use-rag
```

### Use Python SDK
```python
from pdf_autofiller import PDFMapperClient

client = PDFMapperClient(
    api_key="optional",
    base_url="http://localhost:8000"
)

result = client.mapper.extract("/path/to/input.pdf")
print(result)
```

---

## API Documentation

Once server is running, visit:
- **Interactive API docs**: http://localhost:8000/docs
- **Alternative docs**: http://localhost:8000/redoc

---

## Available Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | API info |
| `/health` | GET | Health check |
| `/mapper/extract` | POST | Extract fields from PDF |
| `/mapper/map` | POST | Map fields to schema |
| `/mapper/embed` | POST | Embed metadata into PDF |
| `/mapper/fill` | POST | Fill PDF with data |
| `/mapper/make-embed-file` | POST | Extract + Map + Embed (recommended) |
| `/mapper/fill-pdf` | POST | Fill embedded PDF |
| `/mapper/check-embed-file` | POST | Check if PDF has embedded data |
| `/mapper/run-all` | POST | Complete pipeline |

---

## Example Requests

### Using curl

```bash
# Extract
curl -X POST http://localhost:8000/mapper/extract \
  -H "Content-Type: application/json" \
  -d '{
    "pdf_path": "/path/to/input.pdf",
    "user_id": 1,
    "pdf_doc_id": 100
  }'

# Make embed file
curl -X POST http://localhost:8000/mapper/make-embed-file \
  -H "Content-Type: application/json" \
  -d '{
    "pdf_path": "/path/to/input.pdf",
    "user_id": 1,
    "pdf_doc_id": 100,
    "use_second_mapper": true
  }'
```

---

## Configuration

The API server uses your existing `config.ini`:
- Cache settings
- RAG API URL (if configured)
- Storage paths
- All other mapper configurations

---

## Troubleshooting

### Port already in use
```bash
# Use different port
uvicorn api_server:app --reload --port 8001
```

### Import errors
```bash
# Make sure you're in modules/mapper directory
cd modules/mapper
python api_server.py
```

### Config not found
```bash
# Make sure config.ini exists
ls -la config.ini
```

---

## Production Deployment

For production, use a proper ASGI server:

```bash
# Install production dependencies
pip install gunicorn

# Run with Gunicorn
gunicorn api_server:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000
```

---

## Next Steps

1. ✅ Start the API server
2. ✅ Install SDK: `cd sdks/python && pip install -e .`
3. ✅ Test with CLI: `pdf-autofiller --api-url http://localhost:8000 extract input.pdf`
4. ✅ Check API docs: http://localhost:8000/docs

🎉 **Your mapper module is now an API!**
