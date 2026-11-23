# syntax=docker/dockerfile:1
FROM python:3.14-slim AS builder

ARG TARGET_ENV=production

RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH

WORKDIR /app
COPY requirements/ ./requirements/
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements/base.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    if [ "$TARGET_ENV" = "development" ]; then pip install -r requirements/dev.txt; fi

FROM python:3.14-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH

WORKDIR /app
COPY . .

ENV PYTHONPATH=/app/src

CMD ["sh", "-c", "alembic upgrade head && uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 1"]
