# syntax=docker/dockerfile:1
# Flatten sandbox for scripts/email_import/fetch.py — built and run by fetch.py, never by hand.
# Runtime flags (set by fetch.py): --network none --read-only --cap-drop ALL
#   --security-opt no-new-privileges --memory 512m --pids-limit 64 --cpus 1
FROM python:3.12-slim
RUN --mount=type=cache,target=/root/.cache/pip pip install pymupdf==1.28.2
COPY flatten.py /app/flatten.py
USER 65534:65534
ENTRYPOINT ["python", "/app/flatten.py"]
