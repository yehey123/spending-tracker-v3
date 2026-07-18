# Project Rules

## Docker pip caching

- Always start Dockerfiles with `# syntax=docker/dockerfile:1` (enables BuildKit).
- Use `--mount=type=cache,target=/root/.cache/pip` on every pip install step — never `--no-cache-dir`.
- Install production dependencies first (`requirements/base.txt`), then dev/test additions (`requirements/dev.txt`) in a separate layer gated by `ARG TARGET_ENV`.
- Build dev image: `docker build --build-arg TARGET_ENV=development ...`
- Build prod image: `docker build ...` (default `TARGET_ENV=production` skips dev packages)
- New packages: add to `base.txt` if needed in production, `dev.txt` if test/lint/dev only.
