.PHONY: help docs docs-serve docs-clean ensure-venv sync sync-dev install install-dev pre-commit-install test test-unit test-integration test-coverage lint format type-check clean build build-binary changelog

UV ?= uv
VENV ?= .venv
UV_SYNC_EXTRAS := dev
UV_RUN_EXTRAS := $(foreach extra,$(UV_SYNC_EXTRAS),--extra $(extra))
UV_RUN := $(UV) run --frozen $(UV_RUN_EXTRAS)

export UV_PROJECT_ENVIRONMENT ?= $(VENV)

help:
	@echo "Shannot Development Commands"
	@echo ""
	@echo "Environment Setup:"
	@echo "  make install           - Install package with frozen dependencies"
	@echo "  make install-dev       - Install with dev dependencies + pre-commit hooks"
	@echo "  make pre-commit-install - Install pre-commit git hooks only"
	@echo ""
	@echo "Testing:"
	@echo "  make test              - Run all tests (unit + integration)"
	@echo "  make test-unit         - Run unit tests only (skip integration)"
	@echo "  make test-integration  - Run integration tests only (require PyPy sandbox)"
	@echo "  make test-coverage     - Run tests with coverage reporting"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint              - Run ruff linter"
	@echo "  make format            - Format code with ruff"
	@echo "  make type-check        - Run basedpyright type checker"
	@echo ""
	@echo "Documentation:"
	@echo "  make docs              - Build MkDocs documentation (output to site/)"
	@echo "  make docs-serve        - Serve documentation at http://127.0.0.1:8000"
	@echo "  make docs-clean        - Clean generated documentation"
	@echo ""
	@echo "Building & Distribution:"
	@echo "  make clean             - Remove build artifacts, __pycache__, *.pyc"
	@echo "  make build             - Build distribution packages (wheel + sdist)"
	@echo "  make build-binary      - Build standalone Nuitka binary (Linux recommended)"
	@echo ""
	@echo "Release Management:"
	@echo "  make changelog         - Update CHANGELOG.md from git history (requires git-cliff)"
	@echo ""
	@echo "Low-level targets:"
	@echo "  make ensure-venv       - Create .venv if it doesn't exist"
	@echo "  make sync              - Sync dependencies (runtime only)"
	@echo "  make sync-dev          - Sync dependencies (with dev extras)"

ensure-venv:
	@$(UV) venv --allow-existing $(VENV)

sync: ensure-venv
	$(UV) sync --frozen

sync-dev: ensure-venv
	$(UV) sync --frozen $(UV_RUN_EXTRAS)

install: sync

install-dev: sync-dev pre-commit-install

pre-commit-install:
	@$(UV_RUN) pre-commit install --install-hooks

docs: sync-dev
	@echo "Building documentation with MkDocs..."
	@$(UV_RUN) mkdocs build
	@echo "Documentation built in site/"
	@echo "Open site/index.html in your browser to view"

docs-serve: sync-dev
	@echo "Starting documentation server on http://127.0.0.1:8000"
	@$(UV_RUN) mkdocs serve

docs-clean:
	@echo "Cleaning generated documentation..."
	@rm -rf site .mkdocs_cache
	@echo "Documentation cleaned"

test: sync-dev
	@$(UV_RUN) pytest

test-unit: sync-dev
	@$(UV_RUN) pytest -v -m "not integration"

test-integration: sync-dev
	@$(UV_RUN) pytest -v -m "integration"

test-coverage: sync-dev
	@$(UV_RUN) pytest --cov=shannot --cov-report=term

lint: sync-dev
	@$(UV_RUN) ruff check .

format: sync-dev
	@$(UV_RUN) ruff format .

type-check: sync-dev
	@$(UV_RUN) basedpyright

clean:
	@echo "Cleaning build artifacts..."
	@rm -rf dist/ build/ *.egg-info
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete
	@echo "Cleaned"

build: sync-dev
	@echo "Building distribution packages..."
	@$(UV_RUN) python -m build
	@echo "Built packages in dist/"

build-binary:
	@echo "Building standalone binary with Nuitka..."
	@python build_binary.py
	@echo "Binary in dist/"

changelog:
	@echo "Updating CHANGELOG.md from git history..."
	@if ! command -v git-cliff &> /dev/null; then \
		echo "Error: git-cliff is not installed"; \
		echo "Install it with: brew install git-cliff (macOS) or visit https://github.com/orhun/git-cliff"; \
		exit 1; \
	fi
	@git-cliff --config cliff.toml -o CHANGELOG.md
	@echo "✅ CHANGELOG.md updated successfully"
	@echo "Remember to commit the updated CHANGELOG.md"
