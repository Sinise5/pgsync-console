# ==========================================
# App image — code only (patch sudah di base)
# ==========================================
FROM pgsync-laporan:base

LABEL description="PGSync Laporan — app image (code only)"
LABEL maintainer="QTI Research"

WORKDIR /app

COPY . .

RUN mkdir -p /tmp

CMD ["python3", "scripts/sync_laporan_batch.py", "--help"]
