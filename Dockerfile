# Slim image used by the API service. Does NOT include Playwright/Chromium
# (the scraper-cron service uses Dockerfile.scraper for that).
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential libpq5 curl \
 && rm -rf /var/lib/apt/lists/*

# Install Python deps without playwright (the API doesn't render JS).
COPY requirements.txt ./
RUN sed '/^playwright/d' requirements.txt > requirements.api.txt \
 && pip install -r requirements.api.txt

COPY job_scraper/ ./job_scraper/
COPY migrations/ ./migrations/
COPY alembic.ini ./
COPY *.py ./
COPY *_structured.xlsx ./
COPY docker/wait-for-db.sh /usr/local/bin/wait-for-db.sh
RUN chmod +x /usr/local/bin/wait-for-db.sh

EXPOSE 8000
ENV PYTHONPATH=/app \
    STORAGE_AUTO_CREATE=0

CMD ["bash", "-c", "wait-for-db.sh && python -m job_scraper migrate upgrade head && python -m job_scraper init-db && uvicorn job_scraper.api:app --host 0.0.0.0 --port 8000"]
