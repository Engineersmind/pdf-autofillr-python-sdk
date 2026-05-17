# Mapper Module - Universal Dockerfile
# Supports all cloud platforms (AWS, Azure, GCP, Local)
# Configure at runtime via SOURCE_TYPE environment variable

FROM python:3.11-slim AS base

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Create non-root user for security
RUN useradd -m -u 1000 mapper && chown -R mapper:mapper /app

# ============================================
# DEPENDENCIES LAYER (cached)
# ============================================

# Copy requirements first (for layer caching)
COPY requirements-full.txt .

# Install Python dependencies as root (pip needs write access)
RUN pip install --no-cache-dir -r requirements-full.txt

# ============================================
# APPLICATION LAYER
# ============================================

# Switch to non-root user
USER mapper

# Copy application source
COPY --chown=mapper:mapper src/ ./src/
COPY --chown=mapper:mapper adapter_src/ ./adapter_src/
COPY --chown=mapper:mapper api_server.py .
COPY --chown=mapper:mapper config.ini.example ./config.ini

# Set Python path
ENV PYTHONPATH=/app/src:/app:/app/adapter_src
ENV PATH=/home/mapper/.local/bin:$PATH

# ============================================
# RUNTIME CONFIGURATION
# ============================================

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default environment variables (override at runtime)
ENV SOURCE_TYPE=local \
    LOG_LEVEL=INFO \
    PORT=8000 \
    PYTHONUNBUFFERED=1

# Run FastAPI server
CMD ["python", "-m", "uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"]
