import os

from dotenv import load_dotenv

load_dotenv()

# ── Storage ──────────────────────────────────────────────────────────────────
# RAGPDF_STORAGE: where ALL prediction files, metrics, feedback go
#   local   -> ./data/rag (or RAGPDF_DATA_PATH)
#   s3      -> AWS S3 bucket
#   azure   -> Azure Blob Storage
#   gcs     -> Google Cloud Storage
RAGPDF_STORAGE = os.getenv("RAGPDF_STORAGE", "local")
RAGPDF_DATA_PATH = os.getenv("RAGPDF_DATA_PATH", "./data/rag")

# S3 storage
RAGPDF_S3_BUCKET = os.getenv("RAGPDF_S3_BUCKET", "")
RAGPDF_S3_REGION = os.getenv("RAGPDF_S3_REGION", "us-east-1")
RAGPDF_S3_PREFIX = os.getenv("RAGPDF_S3_PREFIX", "ragpdf/")

# Azure Blob storage
RAGPDF_AZURE_ACCOUNT = os.getenv("RAGPDF_AZURE_ACCOUNT", "")
RAGPDF_AZURE_CONTAINER = os.getenv("RAGPDF_AZURE_CONTAINER", "ragpdf")
RAGPDF_AZURE_CONN_STR = os.getenv("RAGPDF_AZURE_CONN_STR", "")

# GCS storage
RAGPDF_GCS_BUCKET = os.getenv("RAGPDF_GCS_BUCKET", "")
RAGPDF_GCS_PREFIX = os.getenv("RAGPDF_GCS_PREFIX", "ragpdf/")

# ── Embedding Backend ─────────────────────────────────────────────────────────
# RAGPDF_EMBEDDING_BACKEND: what generates vector embeddings for field context
#   sentence_transformer  -> local model, no API key (default, matches rag-lambda)
#   openai                -> OpenAI text-embedding-* models
#   litellm               -> any LiteLLM provider (Azure, Cohere, Bedrock, Ollama, etc.)
#   noop                  -> zero vectors, for unit tests only — DO NOT USE IN PROD
RAGPDF_EMBEDDING_BACKEND = os.getenv("RAGPDF_EMBEDDING_BACKEND", "sentence_transformer")
RAGPDF_ST_MODEL = os.getenv("RAGPDF_ST_MODEL", "all-MiniLM-L6-v2")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
RAGPDF_OPENAI_EMBEDDING_MODEL = os.getenv(
    "RAGPDF_OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"
)

# LiteLLM embedding — used when RAGPDF_EMBEDDING_BACKEND=litellm
# Model format: provider/model-name
#   openai/text-embedding-3-small       azure/my-deployment
#   cohere/embed-english-v3.0           ollama/nomic-embed-text
#   bedrock/amazon.titan-embed-text-v1  vertex_ai/textembedding-gecko
RAGPDF_LITELLM_EMBEDDING_MODEL = os.getenv(
    "RAGPDF_LITELLM_EMBEDDING_MODEL", "openai/text-embedding-3-small"
)

# ── Vector Store Backend ──────────────────────────────────────────────────────
# RAGPDF_VECTOR_STORE: where the vector database lives
#   local    -> flat JSON file on disk (matches rag-lambda default)
#   s3       -> flat JSON file in S3 (same logic, cloud persistence)
#   azure    -> flat JSON file in Azure Blob
#   gcs      -> flat JSON file in GCS
#   pinecone -> Pinecone managed vector DB
#   chroma   -> ChromaDB (local embedded or server)
#   weaviate -> Weaviate
RAGPDF_VECTOR_STORE = os.getenv("RAGPDF_VECTOR_STORE", "local")

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
RAGPDF_PINECONE_INDEX = os.getenv("RAGPDF_PINECONE_INDEX", "ragpdf-vectors")
RAGPDF_PINECONE_NAMESPACE = os.getenv("RAGPDF_PINECONE_NAMESPACE", "default")

RAGPDF_CHROMA_PATH = os.getenv("RAGPDF_CHROMA_PATH", "./chroma_data")
RAGPDF_CHROMA_COLLECTION = os.getenv("RAGPDF_CHROMA_COLLECTION", "ragpdf_vectors")

RAGPDF_WEAVIATE_URL = os.getenv("RAGPDF_WEAVIATE_URL", "http://localhost:8080")
RAGPDF_WEAVIATE_API_KEY = os.getenv("RAGPDF_WEAVIATE_API_KEY", "")
RAGPDF_WEAVIATE_CLASS = os.getenv("RAGPDF_WEAVIATE_CLASS", "RagpdfVector")

# ── LLM Corrector Backend ─────────────────────────────────────────────────────
# RAGPDF_CORRECTOR_BACKEND: LLM used during feedback (API 4) to generate
#   corrected snake_case field names from user error reports
#   noop       -> no LLM call, cleans field name to snake_case (safe default)
#   openai     -> GPT-4 (matches rag-lambda default)
#   anthropic  -> Claude
#   litellm    -> any LiteLLM provider
RAGPDF_CORRECTOR_BACKEND = os.getenv("RAGPDF_CORRECTOR_BACKEND", "noop")
RAGPDF_OPENAI_MODEL = os.getenv("RAGPDF_OPENAI_MODEL", "gpt-4-turbo-preview")
RAGPDF_OPENAI_TEMPERATURE = float(os.getenv("RAGPDF_OPENAI_TEMPERATURE", "0.3"))
RAGPDF_OPENAI_MAX_TOKENS = int(os.getenv("RAGPDF_OPENAI_MAX_TOKENS", "500"))
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
RAGPDF_ANTHROPIC_MODEL = os.getenv("RAGPDF_ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

# LiteLLM corrector — used when RAGPDF_CORRECTOR_BACKEND=litellm
# Model format: provider/model-name
#   openai/gpt-4o-mini             anthropic/claude-3-haiku-20240307
#   groq/llama-3.1-8b-instant      bedrock/anthropic.claude-3-haiku...
#   azure/my-gpt4-deployment       ollama/llama3.1
RAGPDF_LITELLM_CORRECTOR_MODEL = os.getenv(
    "RAGPDF_LITELLM_CORRECTOR_MODEL", "openai/gpt-4o-mini"
)
RAGPDF_LITELLM_CORRECTOR_TEMP = float(os.getenv("RAGPDF_LITELLM_CORRECTOR_TEMP", "0.3"))
RAGPDF_LITELLM_CORRECTOR_TOKENS = int(
    os.getenv("RAGPDF_LITELLM_CORRECTOR_TOKENS", "500")
)

# ── Prediction Thresholds (matches rag-lambda settings.py exactly) ────────────
PREDICTION_THRESHOLD = float(os.getenv("RAGPDF_PREDICTION_THRESHOLD", "0.75"))
TOP_K = int(os.getenv("RAGPDF_TOP_K", "5"))
AMBIGUITY_THRESHOLD = float(os.getenv("RAGPDF_AMBIGUITY_THRESHOLD", "0.10"))
CONFIDENCE_DECAY_RATE = float(os.getenv("RAGPDF_CONFIDENCE_DECAY_RATE", "0.95"))
CONFIDENCE_GROWTH_RATE = float(os.getenv("RAGPDF_CONFIDENCE_GROWTH_RATE", "1.05"))
MAX_CONFIDENCE = float(os.getenv("RAGPDF_MAX_CONFIDENCE", "0.99"))
MIN_CONFIDENCE = float(os.getenv("RAGPDF_MIN_CONFIDENCE", "0.50"))

# ── Server ─────────────────────────────────────────────────────────────────────
RAGPDF_API_KEY = os.getenv("RAGPDF_API_KEY", "dev-key")
RAGPDF_SERVER_HOST = os.getenv("RAGPDF_SERVER_HOST", "0.0.0.0")
RAGPDF_SERVER_PORT = int(os.getenv("RAGPDF_SERVER_PORT", "8000"))
RAGPDF_SERVER_MODE = os.getenv("RAGPDF_SERVER_MODE", "false").lower() == "true"

# ── Debug ──────────────────────────────────────────────────────────────────────
RAGPDF_DEBUG = os.getenv("RAGPDF_DEBUG", "false").lower() == "true"
RAGPDF_LOG_LEVEL = os.getenv("RAGPDF_LOG_LEVEL", "INFO")
