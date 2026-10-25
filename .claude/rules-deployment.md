# Deployment Rules — Spending Tracker SaaS

Derived from the 2026-07-29 blueprint audit (E10–E16).

---

## RULE-DEPLOY-01: Container memory limits required

Every service in docker-compose must specify memory limits. On a 2 GB Hetzner CX22 VPS, an OOM from one service kills the entire stack without limits.

**Mandatory limits per service**:
```yaml
services:
  backend:
    mem_limit: 256m
  frontend:
    mem_limit: 512m
  caddy:
    mem_limit: 64m
```

Tesseract OCR jobs spike to ~150 MB peak; if run in the backend process, the 256m limit accommodates it. If extracted to a worker, give the worker its own 256m limit.

---

## RULE-DEPLOY-02: Log rotation on all services

Docker's default JSON logging has no rotation. Add to every service in docker-compose:

```yaml
logging:
  driver: json-file
  options:
    max-size: "10m"
    max-file: "3"
```

On a 20 GB VPS disk with active logging, unrotated logs can fill the disk within days.

---

## RULE-DEPLOY-03: Docker healthchecks required for backend

The backend service must declare a healthcheck so Docker and the compose orchestrator can detect failed starts before routing traffic:

```yaml
backend:
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
    interval: 30s
    timeout: 5s
    retries: 3
    start_period: 15s
```

The `/health` endpoint already exists (see `api/routes/health.py`). Without a healthcheck, `depends_on` conditions cannot use `condition: service_healthy`.

---

## RULE-DEPLOY-04: SSH known_hosts pinning in CI

The GitHub Actions SSH deploy workflow must pin the Hetzner VPS host fingerprint to prevent MITM on the deploy step.

**Setup** (one-time, run from a trusted machine):
```bash
ssh-keyscan -H <VPS_IP> >> .ssh/known_hosts
```

Store the known_hosts content in a GitHub Actions secret (`VPS_KNOWN_HOSTS`) and use it in the workflow:
```yaml
- uses: webfactory/ssh-agent@v0.9.0
  with:
    ssh-private-key: ${{ secrets.DEPLOY_KEY }}
- run: |
    mkdir -p ~/.ssh
    echo "${{ secrets.VPS_KNOWN_HOSTS }}" >> ~/.ssh/known_hosts
    chmod 600 ~/.ssh/known_hosts
```

Never use `StrictHostKeyChecking no` in CI — this negates the entire point of SSH host verification.

---

## RULE-DEPLOY-05: Supabase keepalive cron

Supabase free tier pauses projects after 7 days of inactivity. A paused project adds 10–30s cold-start latency on the next request.

**Mitigation**: add a lightweight keepalive ping to the GitHub Actions schedule or as a Hetzner cron (via `spending-tracker-deploy/`):

```bash
# Cron: every 5 days at 02:00
0 2 */5 * * curl -sf "https://<project>.supabase.co/rest/v1/health" \
  -H "apikey: $SUPABASE_ANON_KEY" > /dev/null
```

Alternatively, use Upstash QStash (free tier, 500 msg/day) for a managed ping.

---

## RULE-DEPLOY-05b: Supabase connection — use direct connection, not pooler

Supabase's free-tier PgBouncer runs in **transaction mode**, which is incompatible with asyncpg's prepared statements. Connecting via the pooler URL (port 6543) will cause `prepared statement already exists` errors under concurrent load.

**Fix**: use the direct connection URL (port 5432) in `DATABASE_URL`:
```
postgresql+asyncpg://postgres:[password]@db.[ref].supabase.co:5432/postgres?sslmode=require
```

If the 60-connection free-tier limit becomes a constraint, either:
1. Disable prepared statement caching: `asyncpg.create_pool(..., statement_cache_size=0)`, then use the pooler port.
2. Upgrade to Supabase Pro for session-mode pooling support.

Also note: **Supabase free tier takes weekly backups only (RPO = 7 days).** If this is unacceptable for production, upgrade or add a pg_dump cron to the VPS.

---

## RULE-DEPLOY-06: Workers pinned to 1 while in-process cache is active

The backend Dockerfile CMD must use `--workers 1` as long as E16's in-process TTL cache is active. Multiple workers = each process has its own private cache = invalidation from one worker does not propagate to others = stale data served and silent correctness failures.

**Upgrade path**: when horizontal scaling is needed, replace `backend/src/core/cache.py` with a Redis-backed implementation using the same `get / set / clear` interface. No route changes needed.

```dockerfile
CMD ["sh", "-c", "alembic upgrade head && uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 1"]
```

If E10's compose override already sets `--workers 1`, the Dockerfile must also set it as the default so non-override builds don't silently use 2 workers.
