.PHONY: build up down test-backend test-frontend lint ci

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

test-backend:
	docker compose run --rm api pytest -q

test-frontend:
	docker compose run --rm web npm test

lint:
	docker compose run --rm api ruff check .
	docker compose run --rm web npm run lint

ci: build lint test-backend test-frontend
