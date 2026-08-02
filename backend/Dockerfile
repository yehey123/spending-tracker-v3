# syntax=docker/dockerfile:1
FROM python:3.14-slim

ARG TARGET_ENV=production

RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements/base.txt requirements/dev.txt ./requirements/
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements/base.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    [ "$TARGET_ENV" = "development" ] && pip install -r requirements/dev.txt || true

COPY . .

ENV PYTHONPATH=/app/src

CMD ["sh", "-c", "alembic upgrade head && python -m src.domain.services.category_seeder && uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 1"]
