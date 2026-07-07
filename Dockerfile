# Stage 1 — build React frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend
# Chiave API statica iniettata nel bundle a build-time (Vite la legge da
# import.meta.env.VITE_*). Passare con: docker build --build-arg VITE_APP_API_KEY=...
ARG VITE_APP_API_KEY
ENV VITE_APP_API_KEY=${VITE_APP_API_KEY}
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2 — Python backend + built frontend
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist
RUN mkdir -p /app/logs
EXPOSE 8000
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
