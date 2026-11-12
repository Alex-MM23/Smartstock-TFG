# SmartStock AI - Development Makefile

.PHONY: help dev dev-backend dev-frontend test test-backend test-frontend lint build docker-build docker-up docker-down clean

# Default target
help:
	@echo "SmartStock AI - Development Commands"
	@echo ""
	@echo "Development:"
	@echo "  make dev           - Start both backend and frontend in development mode"
	@echo "  make dev-backend   - Start only backend (FastAPI with reload)"
	@echo "  make dev-frontend  - Start only frontend (Angular dev server)"
	@echo ""
	@echo "Testing:"
	@echo "  make test          - Run all tests (backend + frontend)"
	@echo "  make test-backend  - Run backend tests only"
	@echo "  make test-frontend - Run frontend tests only"
	@echo ""
	@echo "Linting:"
	@echo "  make lint          - Run linters (ruff + prettier)"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build  - Build all Docker images"
	@echo "  make docker-up     - Start all services with docker-compose"
	@echo "  make docker-down   - Stop all services"
	@echo "  make docker-logs   - View logs from all services"
	@echo ""
	@echo "Database:"
	@echo "  make db-init       - Initialize database (create tables, views, admin user)"
	@echo "  make db-ingest     - Ingest sample data (2 years simulated)"
	@echo "  make db-train      - Train ML model"
	@echo "  make db-reset      - Reset database (drop all, recreate, ingest, train)"
	@echo ""
	@echo "Production:"
	@echo "  make prod-build    - Build production Docker images"
	@echo "  make prod-up       - Start production stack"
	@echo "  make prod-down     - Stop production stack"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean         - Clean build artifacts and caches"

# Development
dev:
	docker-compose up -d db && \
	sleep 5 && \
	cd Back && python -m src.data.migrations && \
	cd .. && \
	docker-compose up api frontend

dev-backend:
	cd Back && uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	cd front-app && npm start

# Testing
test: test-backend test-frontend

test-backend:
	cd Back && pytest tests/ -v

test-frontend:
	cd front-app && npm test -- --run

# Linting
lint:
	cd Back && ruff check .
	cd front-app && npx prettier --check src/

# Docker
docker-build:
	docker-compose build

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

# Database
db-init:
	cd Back && python -m src.data.migrations

db-ingest:
	cd Back && python -m src.data.ingest --dias 730

db-train:
	cd Back && python -m src.models.train

db-reset:
	docker-compose down -v
	docker-compose up -d db
	sleep 10
	cd Back && python -m src.data.migrations && python -m src.data.ingest --dias 730 --reset && python -m src.models.train

# Production
prod-build:
	docker-compose -f docker-compose.prod.yml build

prod-up:
	docker-compose -f docker-compose.prod.yml up -d

prod-down:
	docker-compose -f docker-compose.prod.yml down

# Clean
clean:
	rm -rf Back/__pycache__ Back/src/__pycache__ Back/src/*/__pycache__
	rm -rf Back/.pytest_cache Back/artifacts
	rm -rf front-app/node_modules front-app/dist
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true