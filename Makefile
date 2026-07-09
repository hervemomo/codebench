.PHONY: build up down test-backend test-frontend lint check-org-scoping ci

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

check-org-scoping:
	bash scripts/check_org_scoping.sh

ci: build lint check-org-scoping test-backend test-frontend
