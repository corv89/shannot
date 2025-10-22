.PHONY: help docs docs-serve docs-clean install install-dev test lint format type-check

help:
	@echo "Available commands:"
	@echo "  make docs          - Build documentation with MkDocs"
	@echo "  make docs-serve    - Start local documentation server"
	@echo "  make docs-clean    - Clean generated documentation"
	@echo "  make install       - Install package"
	@echo "  make install-dev   - Install package with dev dependencies"
	@echo "  make test          - Run tests"
	@echo "  make lint          - Run ruff linter"
	@echo "  make format        - Format code with ruff"
	@echo "  make type-check    - Run type checker"

docs:
	@echo "Building documentation with MkDocs..."
	@mkdocs build
	@echo "Documentation built in site/"
	@echo "Open site/index.html in your browser to view"

docs-serve:
	@echo "Starting documentation server on http://127.0.0.1:8000"
	@mkdocs serve

docs-clean:
	@echo "Cleaning generated documentation..."
	@rm -rf site .mkdocs_cache
	@echo "Documentation cleaned"

install:
	uv pip install -e .

install-dev:
	uv pip install -e ".[dev,all]"

test:
	pytest

lint:
	ruff check .

format:
	ruff format .

type-check:
	basedpyright
