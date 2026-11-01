# ==========================================
# PGSync Admin Backend - Self-contained build
# Context: pgsync-admin/backend/
# ==========================================
FROM python:3.12-slim

WORKDIR /app

# Install system deps (libpq for psycopg v3)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy source
COPY pyproject.toml ./

# Install Python deps (uv)
RUN pip install --no-cache-dir uv && \
    uv venv /app/.venv && \
    uv sync --no-dev --no-install-project

# Copy application after dependencies so source edits reuse the dependency layer.
COPY backend/ ./backend/
COPY scripts/ ./backend/scripts/

# Create data dir
RUN mkdir -p /data

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:3505/health')"

EXPOSE 3505

CMD ["/bin/bash", "-c", "source /app/.venv/bin/activate && python -m backend.main"]
