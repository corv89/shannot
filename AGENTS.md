# Repository Guidelines

## Project Structure & Module Organization
- `shannot/` contains the Python package; `cli.py` exposes the `shannot` entry point while `sandbox.py` and `executors/` orchestrate bubblewrap.
- `profiles/` provides reference sandbox configurations for agents; copy and tailor these instead of editing in place.
- `docs/` and `mkdocs.yml` drive published documentation; generated output lands in `site/` and should only change during doc releases.
- `tests/` groups unit and integration suites with shared fixtures in `tests/conftest.py`.

## Build, Test, and Development Commands
- `make install` hydrates `.venv/` with runtime dependencies via `uv sync --frozen`; use this to match the lockfile exactly.
- `make install-dev` expands the environment with the `dev` and `all` extras and installs pre-commit hooks so tooling stays consistent.
- `make test` exercises the full suite inside the managed environment.
- `make test-unit` skips `@pytest.mark.integration` cases for quicker local iteration.
- `make test-integration` runs only integration scenarios that require Linux + bubblewrap.
- `make test-coverage` reports coverage via `pytest --cov=shannot --cov-report=term`.
- `make lint`/`make format` delegate to `ruff check .` and `ruff format .` inside the UV managed environment.
- `make type-check` runs `basedpyright` with the same extras; no manual virtualenv activation is required for any target.
- `make docs` compiles MkDocs output; `make docs-serve` hosts it at `http://127.0.0.1:8000` for live previews.

## Coding Style & Naming Conventions
- Target Python 3.10+, four-space indents, and a 100-character line cap enforced by Ruff.
- Prefer double quotes for strings and exhaustively annotate functions; unresolved types surface as `basedpyright` warnings.
- Modules and fixtures use `snake_case`; CLI surface names remain lowercase with hyphens (see `pyproject.toml` entry points).

## Testing Guidelines
- Store tests under `tests/` with files named `test_*.py` and functions `test_*`.
- Mark Linux-only or bubblewrap-dependent cases with `@pytest.mark.linux_only` and `@pytest.mark.requires_bwrap`; add `@pytest.mark.integration` for end-to-end scenarios.
- Report coverage using `pytest --cov=shannot --cov-report=term` and mirror the existing fixture patterns instead of reimplementing sandbox setup.

## Commit & Pull Request Guidelines
- Use short, imperative commit subjects mirroring the current history (e.g., `Add GitHub Actions workflow for MkDocs documentation`).
- Squash WIP commits before review and reference related issues in the body when applicable.
- PRs should outline motivation, highlight risky changes, list validation commands, and note any skipped checks (for example, integration tests on macOS hosts).
- Attach CLI logs or screenshots for documentation or UX changes so reviewers can verify agent-facing behavior.
