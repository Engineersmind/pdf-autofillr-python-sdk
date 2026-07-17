# ── Stage 1: builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# Copy only what's needed to install the package
# Context is the project root (passed via docker-compose or -f flag)
COPY pyproject.toml .
COPY src/ src/

# Install the package with all extras into a prefix dir (keeps image clean)
RUN pip install --upgrade pip \
 && pip install --prefix=/install ".[transformers,server]"


# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

LABEL org.opencontainers.image.title="ragpdf-sdk"
LABEL org.opencontainers.image.description="Self-learning RAG field prediction server"
LABEL org.opencontainers.image.version="0.1.1"

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy source (entrypoints need the package on sys.path)
COPY src/ src/
COPY .env.example .env.example
# Note: build context must be the project root, not the docker/ folder

# Data volume — ragpdf_data lives here so it can be mounted at runtime
RUN mkdir -p /data/ragpdf_data /data/chroma_data
VOLUME ["/data"]

# All config via env vars (see .env.example).
# RAGPDF_API_KEY is intentionally NOT set here — bake a real secret into an
# image and it ships to everyone who pulls it. Provide it at runtime instead,
# e.g. `docker run -e RAGPDF_API_KEY=... ...` or via your orchestrator's
# secrets mechanism. The server refuses to start serving requests without it.
ENV RAGPDF_DATA_PATH=/data/ragpdf_data \
    RAGPDF_CHROMA_PATH=/data/chroma_data \
    RAGPDF_STORAGE=local \
    RAGPDF_VECTOR_STORE=local \
    RAGPDF_EMBEDDING_BACKEND=sentence_transformer \
    RAGPDF_ST_MODEL=all-MiniLM-L6-v2 \
    RAGPDF_CORRECTOR_BACKEND=noop \
    RAGPDF_SERVER_HOST=0.0.0.0 \
    RAGPDF_SERVER_PORT=8000 \
    RAGPDF_LOG_LEVEL=INFO \
    PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -sf http://localhost:8000/health || exit 1

# ragpdf-server is the console script from pyproject.toml
CMD ["ragpdf-server"]