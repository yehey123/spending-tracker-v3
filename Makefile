.PHONY: build up test migrate revision frontend-dev frontend-build

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
	docker-compose build

up: check-docker
	docker-compose up -d

test:
	docker-compose run --rm backend pytest

migrate:
	docker-compose run --rm backend alembic upgrade head

revision:
	docker-compose run --rm backend alembic revision --autogenerate -m "$(msg)"

frontend-dev:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build
