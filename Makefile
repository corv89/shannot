.PHONY: help docs docs-serve docs-clean ensure-venv sync sync-dev install install-dev pre-commit-install test test-unit test-integration test-coverage lint format type-check changelog

UV ?= uv
VENV ?= .venv
UV_SYNC_EXTRAS := dev
UV_RUN_EXTRAS := $(foreach extra,$(UV_SYNC_EXTRAS),--extra $(extra))
UV_RUN := $(UV) run --frozen $(UV_RUN_EXTRAS)

export UV_PROJECT_ENVIRONMENT ?= $(VENV)

help:
	@echo "Available commands:"
	@echo "  make docs          - Build documentation with MkDocs"
	@echo "  make docs-serve    - Start local documentation server"
	@echo "  make docs-clean    - Clean generated documentation"
	@echo "  make install       - Install package"
	@echo "  make install-dev   - Install package with dev dependencies"
	@echo "  make pre-commit-install - Install git hooks via pre-commit"
	@echo "  make test          - Run tests"
	@echo "  make lint          - Run ruff linter"
	@echo "  make format        - Format code with ruff"
	@echo "  make type-check    - Run type checker"
	@echo "  make changelog     - Update CHANGELOG.md from git history"

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
