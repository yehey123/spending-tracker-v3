# Spending Tracker

A personal finance web app with OCR-powered bank statement import. Upload PDF or image statements and let the app extract and categorize your transactions automatically. Includes a dashboard with spending charts and analytics.

## Features

- **Statement import** — upload PDF or image bank statements; parsed via Tesseract OCR, Claude, or OpenAI
- **Transaction management** — view, filter, and edit parsed transactions
- **Categories** — organize spending into custom categories
- **Analytics** — charts and breakdowns of spending over time
- **PWA + mobile** — installable as a PWA; Capacitor build targets iOS and Android

## Tech Stack

| Layer | Tech |
|---|---|
| Backend | Python 3.14, FastAPI, SQLAlchemy (async), Alembic |
| Database | PostgreSQL 16 |
| OCR | Tesseract, pdfplumber, OpenCV; optionally Claude or OpenAI |
| Frontend | Next.js 14, TypeScript, Tailwind CSS, TanStack Query, Recharts |
| Mobile | Capacitor (iOS / Android), PWA manifest |
| Infra | Docker, docker-compose, GitHub Actions |

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (for backend + database)
- [Node.js 20+](https://nodejs.org/) (for frontend)
- Python 3.14+ (only for local backend dev outside Docker)

---

## Setup

### 1. Clone the repo

```bash
git clone <repo-url>
cd spending-tracker
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and fill in the required values:

```env
# Required
DATABASE_URL=postgresql+asyncpg://user:password@db:5432/spending_tracker

# Optional — only needed if using AI-based OCR
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# OCR provider: tesseract (default) | claude | openai
OCR_PROVIDER=tesseract

# Upload directory (default is fine for Docker)
UPLOAD_DIR=/tmp/spending-tracker-uploads
```

### 3. Build and start backend + database

```bash
make build    # build Docker images
make migrate  # run database migrations
make up       # start services in background
```

Backend API is now at `http://localhost:8000`.  
Interactive API docs: `http://localhost:8000/docs`

### 4. Start the frontend

```bash
make frontend-dev
```

Frontend is now at `http://localhost:3000`.

---

## Available Make Commands

| Command | Description |
|---|---|
| `make build` | Build Docker images |
| `make up` | Start backend + database (detached) |
| `make migrate` | Apply Alembic database migrations |
| `make revision msg="..."` | Generate a new migration |
| `make test` | Run backend test suite |
| `make frontend-dev` | Start Next.js dev server |
| `make frontend-build` | Build frontend for production |

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | Yes | `postgresql+asyncpg://user:password@db:5432/spending_tracker` | PostgreSQL connection string |
| `OCR_PROVIDER` | No | `tesseract` | OCR engine: `tesseract`, `claude`, or `openai` |
| `ANTHROPIC_API_KEY` | Only if `OCR_PROVIDER=claude` | — | Anthropic API key |
| `OPENAI_API_KEY` | Only if `OCR_PROVIDER=openai` | — | OpenAI API key |
| `UPLOAD_DIR` | No | `/tmp/spending-tracker-uploads` | Where uploaded statements are stored |

---

## Project Structure

```
spending-tracker/
├── backend/
│   ├── src/
│   │   ├── api/routes/       # FastAPI route handlers
│   │   ├── core/             # Settings / config
│   │   ├── db/               # DB session + base
│   │   └── domain/           # ORM models + services
│   ├── alembic/              # DB migrations
│   ├── tests/
│   ├── Dockerfile
│   └── requirements/
├── frontend/
│   ├── src/
│   │   ├── app/              # Next.js app router pages
│   │   ├── components/       # UI components + charts
│   │   └── lib/              # API client + utilities
│   └── public/               # Icons, PWA manifest
├── docker-compose.yml
├── Makefile
└── .env                      # Local secrets (git-ignored)
```

---

## Running Tests

```bash
make test
```

Tests run against a live PostgreSQL instance spun up by docker-compose. CI (GitHub Actions) mirrors this setup exactly.

---

## Mobile (Capacitor)

The frontend can be built as a native iOS or Android app via Capacitor:

```bash
cd frontend
npm run build          # produces the static export
npx cap sync           # sync web assets to native projects
npx cap open ios       # open in Xcode
npx cap open android   # open in Android Studio
```

---

## License

MIT — see [LICENSE](LICENSE).
