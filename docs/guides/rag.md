# pdf-autofillr-rag

Self-learning field prediction. Ships with 137 LP Subscription Agreement vectors.

## Install

```bash
pip install "pdf-autofillr[rag]"                         # OpenAI embeddings
pip install "pdf-autofillr-rag[transformers]"            # local Sentence Transformers
pip install "pdf-autofillr-rag[pinecone]"               # Pinecone vector store
pip install "pdf-autofillr-rag[chroma]"                 # ChromaDB
pip install "pdf-autofillr-rag[weaviate]"               # Weaviate
```

## CLI

```bash
ragpdf-setup           # first-time bootstrap
ragpdf init-vectors    # build vector_database.json
ragpdf predict --user u1 --session s1 --pdf form_id
ragpdf feedback --user u1 --session s1 --pdf form_id --errors errors.json
ragpdf metrics --type global
ragpdf system-info
ragpdf-server          # REST API → http://localhost:8003/docs
```

## Key env vars

```bash
OPENAI_API_KEY=sk-...
RAG_VECTOR_STORE=local     # local | s3 | azure | gcs | pinecone | chroma | weaviate
RAG_CORRECTOR=openai       # openai | anthropic | litellm | noop
RAG_STORAGE=local
```

## Source layout

```
packages/rag/src/ragpdf/
├── client.py           RAGPDFClient — main entry point
├── pipeline/           Prediction, processing, feedback pipelines
├── embeddings/         OpenAI, SentenceTransformer, LiteLLM, noop
├── vector_stores/      Local, S3, Azure, GCS, Pinecone, ChromaDB, Weaviate
├── correctors/         OpenAI, Anthropic, LiteLLM, noop
├── services/           Analytics, metrics, time-series, case classifier
├── storage/            Data persistence
└── entrypoints/        CLI · FastAPI · Lambda · Azure · GCP
```
