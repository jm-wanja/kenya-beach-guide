.PHONY: help setup dev-backend dev-frontend docker-up docker-down test ingest train lint clean

help: ## Show this help message
	@echo "Kenya Beach Guide"
	@echo "================="
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
setup: ## Create Python venv and install all dependencies
	@echo "→ Creating Python virtual environment..."
	cd backend && python3 -m venv .venv && \
		. .venv/bin/activate && \
		pip install --upgrade pip && \
		pip install -r requirements.txt
	@echo "→ Installing frontend dependencies..."
	cd frontend && npm install
	@echo "✓ Setup complete."

# ---------------------------------------------------------------------------
# Development
# ---------------------------------------------------------------------------
dev-backend: ## Start FastAPI dev server (port 8200)
	cd backend && . .venv/bin/activate && \
		uvicorn main:app --reload --host 0.0.0.0 --port 8200

dev-frontend: ## Start Vite dev server (port 5174)
	cd frontend && npm run dev

# ---------------------------------------------------------------------------
# Docker
# ---------------------------------------------------------------------------
docker-up: ## Start all services with Docker Compose
	docker compose up --build -d

docker-down: ## Stop all Docker services
	docker compose down

docker-logs: ## Tail Docker logs
	docker compose logs -f

# ---------------------------------------------------------------------------
# Data & ML
# ---------------------------------------------------------------------------
ingest: ## Fetch historical tide data (backfill 365 days)
	cd backend && . .venv/bin/activate && \
		python -m src.data.ingestion --backfill-days 365

ingest-weather: ## Fetch weather/marine forecasts for all beaches
	cd backend && . .venv/bin/activate && \
		python -m src.data.ingestion --weather

train: ## Train ML forecast and anomaly detection models
	cd backend && . .venv/bin/activate && \
		python -m src.models.train_forecast && \
		python -m src.models.train_anomaly

# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------
test: test-backend ## Run all tests

test-backend: ## Run backend unit tests
	cd backend && . .venv/bin/activate && \
		python -m pytest tests/ -v --tb=short

test-coverage: ## Run tests with coverage report
	cd backend && . .venv/bin/activate && \
		python -m pytest tests/ -v --cov=src --cov-report=html --cov-report=term

# ---------------------------------------------------------------------------
# Quality
# ---------------------------------------------------------------------------
lint: ## Lint backend code
	cd backend && . .venv/bin/activate && \
		ruff check src/ tests/ main.py

format: ## Format backend code
	cd backend && . .venv/bin/activate && \
		ruff format src/ tests/ main.py

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------
clean: ## Remove generated files
	rm -rf backend/.venv backend/__pycache__ backend/src/__pycache__
	rm -rf backend/*.db backend/htmlcov
	rm -rf frontend/node_modules frontend/dist
	rm -rf models/*.joblib models/*.json
