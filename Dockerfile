# ---- Stage 1: Build the frontend ----
FROM registry.cn-hangzhou.aliyuncs.com/lacogito/node:24-alpine3.21 AS frontend-build

WORKDIR /app/dashboard-frontend
COPY dashboard-frontend/package.json dashboard-frontend/package-lock.json* ./
RUN npm ci
COPY dashboard-frontend/ ./
RUN npm run build

# ---- Stage 2: Python backend ----
FROM registry.cn-hangzhou.aliyuncs.com/lacogito/python:3.11-bookworm AS backend

WORKDIR /app

# Use aliyun apt mirror for faster downloads in China
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources

# System deps for psycopg and general use
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl && \
    rm -rf /var/lib/apt/lists/*

# Set model cache dir so the downloaded model lands in a known location
ENV SENTENCE_TRANSFORMERS_HOME=/app/models

# Copy pyproject.toml first for dependency caching
COPY pyproject.toml README.md ./

# Install dependencies and download model (cached layer if pyproject.toml unchanged).
# Create minimal package structure so pip can resolve the local package, then remove it.
# HF_HUB_OFFLINE must NOT be set here — the model is downloaded at build time.
RUN mkdir -p alithia && touch alithia/__init__.py && \
    pip install --no-cache-dir ".[all]" && \
    python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('avsolatorio/GIST-small-Embedding-v0')" && \
    rm -rf alithia

# Disable HuggingFace network access at runtime — model is already baked into the image
ENV HF_HUB_OFFLINE=1
# Use local model cost map — githubusercontent.com may be unreachable in production
ENV LITELLM_LOCAL_MODEL_COST_MAP=true

# Copy source and install the package without re-resolving deps (already satisfied above).
# --no-deps skips the dependency resolver, making this layer near-instant on source changes.
COPY alithia/ alithia/
RUN pip install --no-cache-dir --no-deps .

# Copy built frontend into the location the backend expects
COPY --from=frontend-build /app/dashboard-frontend/dist ./dashboard-frontend/dist

# Default config path — mount or set at runtime
ENV ALITHIA_CONFIG_PATH=/app/alithia_config.json

EXPOSE 8080

CMD ["python", "-m", "alithia.run", "dashboard", "--host", "0.0.0.0", "--port", "8080"]
