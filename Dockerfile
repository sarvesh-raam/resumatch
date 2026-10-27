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

# CPU-only torch keeps the image ~1.5 GB smaller than the default CUDA wheel
RUN pip install --no-cache-dir torch==2.11.0 --index-url https://download.pytorch.org/whl/cpu
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# bake the model into the image so cold starts don't download it
ENV HF_HOME=/app/.cache/huggingface
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

COPY backend/resumatch ./resumatch
COPY --from=web /web/dist ./static

ENV STATIC_DIR=/app/static \
    PORT=7860
EXPOSE 7860

RUN useradd -m app && chown -R app /app
USER app

CMD ["sh", "-c", "uvicorn resumatch.api:app --host 0.0.0.0 --port ${PORT}"]
