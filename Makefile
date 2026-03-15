.PHONY: install dev test lint migrate build run clean

# ── Setup ──────────────────────────────────────────────────────────────────────
install:
	pip install -e ".[dev]"

# ── Development ────────────────────────────────────────────────────────────────
dev:
	uvicorn app.main:app --reload --port 8000

# ── Testing ────────────────────────────────────────────────────────────────────
test:
	pytest tests/ -v

test-unit:
	pytest tests/unit/ -v

test-integration:
	pytest tests/integration/ -v

# ── Database migrations ────────────────────────────────────────────────────────
migrate:
	alembic upgrade head

migrate-down:
	alembic downgrade -1

migration:
	@read -p "Migration name: " name; alembic revision --autogenerate -m "$$name"

# ── Docker ─────────────────────────────────────────────────────────────────────
build:
	docker build -t tydline-core .

run:
	docker compose up

run-detached:
	docker compose up -d

stop:
	docker compose down

# ── Background worker ──────────────────────────────────────────────────────────
tracker:
	python -m app.workers.tracker

# ── Cleanup ────────────────────────────────────────────────────────────────────
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	find . -type f -name "*.pyc" -delete 2>/dev/null; true
	rm -rf .pytest_cache htmlcov .coverage
