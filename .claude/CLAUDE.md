# Project Rules

## Docker pip caching

- Always start Dockerfiles with `# syntax=docker/dockerfile:1` (enables BuildKit).
- Use `--mount=type=cache,target=/root/.cache/pip` on every pip install step — never `--no-cache-dir`.
- Install production dependencies first (`requirements/base.txt`), then dev/test additions (`requirements/dev.txt`) in a separate layer gated by `ARG TARGET_ENV`.
- Build dev image: `docker build --build-arg TARGET_ENV=development ...`
- Build prod image: `docker build ...` (default `TARGET_ENV=production` skips dev packages)
- New packages: add to `base.txt` if needed in production, `dev.txt` if test/lint/dev only.

## Docker rebuild required on every code change

Backend and frontend have **no source volume mounts** — code is baked into the image at build time. Every code change requires:

```bash
docker compose build <service> && docker compose up -d <service>
```

Run tests inside the dev image (not the running production container):
```bash
docker compose run --rm -e TARGET_ENV=development backend sh -c "pip install -r requirements/dev.txt -q && python -m pytest tests/ -q"
```

Apply migrations after rebuilding backend:
```bash
docker compose exec backend alembic upgrade head
```

Without a rebuild, the running container will not see any file edits. This applies to both `backend` and `frontend` services.
