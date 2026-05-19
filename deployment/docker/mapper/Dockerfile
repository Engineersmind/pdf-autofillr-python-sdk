# pdf-autofillr-mapper — Docker image
# Supports AWS / Azure / GCP / local via env vars at runtime.

FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y curl openjdk-17-jre-headless && rm -rf /var/lib/apt/lists/*
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

RUN pip install --no-cache-dir --user "pdf-autofillr-mapper[api,aws,azure,gcp]"

ENV PATH=/home/appuser/.local/bin:$PATH
ENV SOURCE_TYPE=local
ENV LOG_LEVEL=INFO
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["pdf-mapper-server"]
