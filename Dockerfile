# Production image for Google Cloud Run (or any container host).
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir uv

WORKDIR /app

# Rely on .dockerignore to omit .venv, tests, local secrets, etc.
COPY . /app

RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:${PATH}"

RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 8080

ENTRYPOINT ["/app/docker-entrypoint.sh"]
