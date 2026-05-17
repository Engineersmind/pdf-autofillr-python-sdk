# pdf-autofillr-rag — Docker image

FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

RUN pip install --no-cache-dir --user "pdf-autofillr-rag[server]"

ENV PATH=/home/appuser/.local/bin:$PATH
ENV LOG_LEVEL=INFO
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["ragpdf-server"]
