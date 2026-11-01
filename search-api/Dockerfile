FROM python:3.12-slim

LABEL description="Laporan Search API — FastAPI service for OpenSearch full-text search"
LABEL maintainer="QTI Research"

# Install uv via curl (more reliable than COPY --from=ghcr.io)
RUN pip install uv && \
    uv --version

WORKDIR /app

# Install project dependencies
COPY pyproject.toml ./
RUN uv sync --no-dev

# Copy application code
COPY main.py ./

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health')"

# Expose port (internal container)
EXPOSE 8080

# Run
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
