# syntax=docker/dockerfile:1.7
# --- builder ---
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

RUN pip install --no-cache-dir uv==0.5.*

WORKDIR /app
COPY pyproject.toml ./
RUN uv sync --no-dev --no-install-project
COPY . .
RUN uv sync --no-dev

# --- runtime ---
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# ADR 0004 slice 1: local OCR for scanned PDFs. Tesseract is the ONLY system
# binary in the parse child — added deliberately to keep OCR local (no cloud
# egress). `-eng` is the English language pack pytesseract shells out to.
# pypdfium2 (the rasterizer) needs no system package — its wheel bundles PDFium.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 neo
# ADR 0002: original-file storage root, owned by neo so a fresh named volume
# mounted here inherits neo ownership — a root-owned mountpoint would deny the
# non-root process on first write. Path matches settings.document_storage_root.
RUN mkdir -p /var/neo/documents && chown -R neo:neo /var/neo
WORKDIR /app

COPY --from=builder --chown=neo:neo /app /app
USER neo

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=15s CMD \
    python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
