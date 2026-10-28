# --- build the frontend ---
FROM node:20-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- backend + built frontend in one image ---
FROM python:3.12-slim
WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# bake the model into the image so cold starts don't download it
ENV FASTEMBED_CACHE_PATH=/app/.cache/fastembed
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('sentence-transformers/all-MiniLM-L6-v2')"

COPY backend/resumatch ./resumatch
COPY --from=web /web/dist ./static

ENV STATIC_DIR=/app/static \
    PORT=7860
EXPOSE 7860

RUN useradd -m app && chown -R app /app
USER app

CMD ["sh", "-c", "uvicorn resumatch.api:app --host 0.0.0.0 --port ${PORT}"]
