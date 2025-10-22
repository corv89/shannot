.PHONY: help docs docs-serve docs-clean install install-dev test lint format type-check

help:
	@echo "Available commands:"
	@echo "  make docs          - Generate API documentation with pdoc3"
	@echo "  make docs-serve    - Start local documentation server"
	@echo "  make docs-clean    - Clean generated documentation"
	@echo "  make install       - Install package"
	@echo "  make install-dev   - Install package with dev dependencies"
	@echo "  make test          - Run tests"
	@echo "  make lint          - Run ruff linter"
	@echo "  make format        - Format code with ruff"
	@echo "  make type-check    - Run type checker"

docs:
	@echo "Generating API documentation..."
	@mkdir -p docs/api
	@pdoc --html --output-dir docs/api --config show_source_code=True --config latex_math=True --force shannot
	@if [ -d docs/api/shannot ]; then \
		mv docs/api/shannot/* docs/api/ && rmdir docs/api/shannot; \
	fi
	@echo "Documentation generated in docs/api/"
	@echo "Open docs/api/index.html in your browser to view"

docs-serve:
	@echo "Starting documentation server on http://localhost:8080"
	@pdoc --http localhost:8080 shannot

docs-clean:
	@echo "Cleaning generated documentation..."
	@rm -rf docs/api docs/html docs/_build
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
