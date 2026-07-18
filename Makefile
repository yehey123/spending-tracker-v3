.PHONY: build up down dev logs test migrate revision frontend-dev shell-db shell-backend

check-docker:
	@echo "Checking Docker status..."
	@if ! docker info >/dev/null 2>&1; then \
		echo "Docker is not running. Launching Docker Desktop..."; \
		open -a Docker; \
		echo "Waiting for Docker to initialize..."; \
		until docker info >/dev/null 2>&1; do \
			printf "."; \
			sleep 2; \
		done; \
		echo "\nDocker is ready!"; \
	else \
		echo "Docker is already running."; \
	fi

build: check-docker
	docker compose build

up: check-docker
	docker compose up -d

dev: check-docker
	docker compose up

down:
	docker compose down

logs:
	docker compose logs -f

test: check-docker
	docker compose run --rm \
		-e DATABASE_URL=postgresql+asyncpg://user:password@db:5432/spending_tracker \
		backend pytest tests/ \
		--ignore=tests/services/test_storage_gcs.py \
		--ignore=tests/services/test_storage_s3.py -v

migrate:
	docker compose run --rm backend alembic upgrade head

revision:
	docker compose run --rm backend alembic revision --autogenerate -m "$(msg)"

frontend-dev:
	cd frontend && npm run dev

shell-db:
	docker compose exec db psql -U user spending_tracker

shell-backend:
	docker compose exec backend bash
