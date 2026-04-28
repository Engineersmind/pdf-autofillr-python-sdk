# pdf-autofillr-doc-upload

Upload any document — LLM extracts field values and fills the blank PDF.

**Supported formats:** PDF · DOCX · PPTX · XLSX · CSV · JSON · TXT · MD · HTML · XML

## Install

```bash
pip install "pdf-autofillr[doc-upload]"                  # + mapper
pip install "pdf-autofillr[doc-upload-rag]"              # + mapper + RAG
pip install "pdf-autofillr[doc-upload,s3]"               # + mapper + S3
```

## CLI

```bash
doc-upload-cli \
  --document investor.pdf \
  --schema configs/form_keys.json \
  --pdf-path data/input/blank_form.pdf
doc-upload-server     # REST API → http://localhost:8002/docs
```

## Key env vars

```bash
DOC_UPLOAD_LLM_MODEL=openai/gpt-4o-mini
OPENAI_API_KEY=sk-...
DOC_UPLOAD_PDF_FILLER=mapper
DOC_UPLOAD_PDF_PATH=./data/input/blank_form.pdf
DOC_UPLOAD_STORAGE=local
```

## Source layout

```
packages/doc_upload/src/pdf_autofillr_doc_upload/
├── client.py        DocUploadClient — main entry point
├── extraction/      Document reader + LLM extractor
├── pdf/             Filling + mapper integration
├── storage/         Local, S3, GCS, Azure
├── config/          DocUploadSettings
└── entrypoints/     CLI · FastAPI · Lambda · Azure · GCP
```
