# chatbot Module — Dockerfile
# Supports local, AWS S3, and mapper PDF filler via runtime env vars.
#
# Build:
#   docker build -t chatbot-module .
#
# Run (local storage, no PDF filling):
#   docker run -p 8001:8001 --env-file .env chatbot-module
#
# Run (S3 storage + mapper PDF filler):
#   docker run -p 8001:8001 \
#     -e chatbot_STORAGE=s3 \
#     -e AWS_OUTPUT_BUCKET=my-bucket \
#     -e AWS_CONFIG_BUCKET=my-config-bucket \
#     -e chatbot_PDF_FILLER=mapper \
#     -e MAPPER_API_URL=http://mapper-service:8000 \
#     -e OPENAI_API_KEY=sk-... \
#     chatbot-module

FROM python:3.11-slim AS base

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Non-root user
RUN useradd -m -u 1000 chatbot && chown -R chatbot:chatbot /app

# ── Dependencies layer (cached) ───────────────────────────────────────
COPY requirements-full.txt .
RUN pip install --no-cache-dir -r requirements-full.txt

# ── Application layer ────────────────────────────────────────────────
USER chatbot

COPY --chown=chatbot:chatbot src/ ./src/
COPY --chown=chatbot:chatbot api_server.py .
COPY --chown=chatbot:chatbot config_samples/ ./config_samples/
COPY --chown=chatbot:chatbot entrypoints/ ./entrypoints/

# Default config_samples as config path
ENV chatbot_CONFIG_PATH=/app/config_samples

ENV PYTHONPATH=/app:/app/src
ENV PATH=/home/chatbot/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

ENV PORT=8001 \
    chatbot_LOG_LEVEL=INFO \
    chatbot_STORAGE=local \
    chatbot_PDF_FILLER=none

CMD ["python", "-m", "uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8001"]
