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

# System deps for psycopg and general use
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl && \
    rm -rf /var/lib/apt/lists/*

# Install Python package
COPY pyproject.toml README.md ./
COPY alithia/ alithia/
RUN pip install --no-cache-dir -e ".[all]"

# Pre-download the sentence-transformer model used by PaperScout reranker
# so it's available offline at runtime (HuggingFace may be unreachable)
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('avsolatorio/GIST-small-Embedding-v0', cache_folder='/tmp/alithia_models')"

# Copy built frontend into the location the backend expects
COPY --from=frontend-build /app/dashboard-frontend/dist ./dashboard-frontend/dist

# Default config path — mount or set at runtime
ENV ALITHIA_CONFIG_PATH=/app/alithia_config.json

EXPOSE 8080

CMD ["python", "-m", "alithia.run", "dashboard", "--host", "0.0.0.0", "--port", "8080"]
