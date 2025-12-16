.PHONY: help test lint format check install clean

help:  ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:  ## Install package with dev dependencies
	pip install -e ".[dev]"

test:  ## Run tests with pytest
	pytest

test-cov:  ## Run tests with coverage report
	pytest --cov=envseal --cov-report=term-missing --cov-report=html

lint:  ## Run linting (ruff check)
	ruff check envseal/ tests/

lint-fix:  ## Auto-fix linting issues
	ruff check --fix envseal/ tests/

format:  ## Format code with ruff
	ruff format envseal/ tests/

format-check:  ## Check if code is formatted
	ruff format --check envseal/ tests/

type-check:  ## Run type checking with mypy
	mypy envseal/

check:  ## Run all checks (lint + format + type + test)
	@echo "==> Running ruff lint..."
	ruff check envseal/ tests/
	@echo "\n==> Checking format..."
	ruff format --check envseal/ tests/
	@echo "\n==> Running mypy..."
	mypy envseal/ || true
	@echo "\n==> Running tests..."
	pytest

ci:  ## Run CI checks (stricter - fails on any error)
	ruff check envseal/ tests/
	ruff format --check envseal/ tests/
	pytest

clean:  ## Clean up generated files
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	rm -rf htmlcov/
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

.DEFAULT_GOAL := help
