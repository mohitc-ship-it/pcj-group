# ── Stage 1: Build React frontend ────────────────────────────────────────────
FROM node:20-slim AS frontend-builder
WORKDIR /build
COPY frontend/PCJ-frontend/package*.json ./
RUN npm ci
COPY frontend/PCJ-frontend/ ./
RUN npm run build

# ── Stage 2: Python + WeasyPrint + FastAPI ────────────────────────────────────
FROM python:3.11-slim

# WeasyPrint system dependencies (pango, cairo, gdk-pixbuf)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi8 \
    libglib2.0-0 \
    libharfbuzz0b \
    libfribidi0 \
    shared-mime-info \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps first (cached layer)
COPY swanky_women/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Backend source
COPY swanky_women/ ./

# React build output
COPY --from=frontend-builder /build/dist ./dist/

# Writable runtime directories
RUN mkdir -p assets data

EXPOSE 8000

CMD ["uvicorn", "editor_api:app", "--host", "0.0.0.0", "--port", "8000"]
