.PHONY: install sync build test coverage lint format clean help

install:
	@echo "Installing dependencies..."
	uv sync --package pgsync-admin-backend

build:
	@echo "Building project..."
	uv sync --package pgsync-admin-backend --extra dev

dev:
	@echo "Running development server..."
	uv run python backend/main.py

init-db:
	@echo "Initializing database..."
	uv run python -m backend.db.init_db

test:
	@echo "Running all tests..."
	uv run --package pgsync-admin-backend --extra dev pytest tests/ -v

test-unit:
	@echo "Running unit tests..."
	uv run --package pgsync-admin-backend --extra dev pytest tests/unit/ -v

test-integration:
	@echo "Running integration tests..."
	uv run --package pgsync-admin-backend --extra dev pytest tests/integration/ -v

coverage:
	@echo "Running tests with coverage..."
	uv run --package pgsync-admin-backend --extra dev pytest tests/ --cov=backend --cov-report=html --cov-report=term
	@echo "Coverage report: htmlcov/index.html"

lint:
	@echo "Running linters..."
	uv run --package pgsync-admin-backend --extra dev ruff check backend/ tests/

lint-fix:
	@echo "Auto-fixing linting issues..."
	uv run --package pgsync-admin-backend --extra dev ruff check backend/ tests/ --fix

format:
	@echo "Formatting code..."
	uv run --package pgsync-admin-backend --extra dev black backend/ tests/

type-check:
	@echo "Type checking..."
	uv run --package pgsync-admin-backend --extra dev mypy backend/

check: lint type-check
	@echo "All checks passed!"

clean:
	@echo "Cleaning build artifacts..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name htmlcov -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name .coverage -delete 2>/dev/null || true

help:
	@echo "PGSync Admin Backend - Available commands:"
	@echo ""
	@echo "  make install       Install dependencies"
	@echo "  make dev           Run development server on localhost:3505"
	@echo "  make init-db       Initialize SQLite database"
	@echo "  make test          Run all tests"
	@echo "  make test-unit     Run unit tests only"
	@echo "  make test-integration Run integration tests only"
	@echo "  make coverage      Run tests with coverage report"
	@echo "  make lint          Check code style"
	@echo "  make lint-fix      Auto-fix linting issues"
	@echo "  make format        Format code with black"
	@echo "  make type-check    Type checking with mypy"
	@echo "  make check         Run all checks (lint + type)"
	@echo "  make clean         Clean build artifacts"
	@echo "  make help          Show this help message"
