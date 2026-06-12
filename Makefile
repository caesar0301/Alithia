# Makefile for alithia-agent
# Common commands for development and usage

.PHONY: help install sync run daemon status test lint lint-fix format clean build publish

# Network-safe defaults for constrained regions/networks.
# Override when needed, e.g.:
#   make build UV_INDEX_URL=https://pypi.org/simple UV_HTTP_TIMEOUT=180
UV_INDEX_URL ?= https://pypi.tuna.tsinghua.edu.cn/simple
UV_HTTP_TIMEOUT ?= 120

# Default target
help:
	@echo "Alithia-Agent Commands"
	@echo "======================"
	@echo ""
	@echo "Setup:"
	@echo "  make install    Install dependencies with uv"
	@echo "  make sync       Sync dependencies"
	@echo ""
	@echo "Usage:"
	@echo "  make run        Run agent with default prompt"
	@echo "  make run-prompt PROMPT='...'  Run with custom prompt"
	@echo "  make paperscout Run paperscout subagent"
	@echo "  make paperlens  Run paperlens subagent"
	@echo "  make daemon     Start background daemon process"
	@echo "  make status     Show daemon/scheduler status"
	@echo ""
	@echo "Development:"
	@echo "  make test       Run tests"
	@echo "  make lint       Run ruff linter"
	@echo "  make lint-fix   Auto-fix lint issues with ruff"
	@echo "  make format     Run ruff formatter"
	@echo "  make check      Run lint + format check"
	@echo ""
	@echo "Release:"
	@echo "  make build      Build sdist/wheel into dist/"
	@echo "  make publish    Upload dist/* to PyPI (needs TWINE_PASSWORD)"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean      Clean cache and temp files"
	@echo ""

# Setup commands
install:
	uv sync

sync:
	uv sync

# Run commands
run:
	uv run alithia-agent "Find new papers about AI and machine learning"

run-prompt:
	uv run alithia-agent "$(PROMPT)"

paperscout:
	uv run alithia-agent --subagent paperscout "Check for new papers"

paperlens:
	uv run alithia-agent --subagent paperlens "Analyze papers"

# Daemon commands
daemon:
	uv run alithia-agent daemon

daemon-stop:
	@if [ -f ~/.alithia/daemon.pid ]; then \
		kill $(cat ~/.alithia/daemon.pid) 2>/dev/null || echo "Daemon not running"; \
		rm -f ~/.alithia/daemon.pid; \
	else \
		echo "No PID file found"; \
	fi

status:
	uv run alithia-agent status

status-json:
	uv run alithia-agent status --output json

# Development commands
test:
	uv run pytest tests/ -v

test-coverage:
	uv run pytest tests/ -v --cov=alithia_agent --cov-report=term-missing

lint:
	uv run ruff check .

lint-fix:
	uv run ruff check . --fix

format:
	uv run ruff format .

format-check:
	uv run ruff format --check alithia_agent/

check: lint format-check

typecheck:
	uv run mypy alithia_agent/

# Release commands
build:
	UV_HTTP_TIMEOUT=$(UV_HTTP_TIMEOUT) \
		uv run --index-url $(UV_INDEX_URL) --with build python -m build

publish:
	@TOKEN="$(PYPI_TOKEN)"; \
	if [ -z "$$TOKEN" ]; then TOKEN="$(TWINE_PASSWORD)"; fi; \
	if [ -z "$$TOKEN" ]; then \
		echo "PyPI token required. Set PYPI_TOKEN (preferred) or TWINE_PASSWORD."; \
		echo "Example: make publish PYPI_TOKEN=pypi-xxxx"; \
		exit 1; \
	fi; \
	TWINE_USERNAME=$${TWINE_USERNAME:-__token__} \
	TWINE_PASSWORD="$$TOKEN" \
	UV_HTTP_TIMEOUT=$(UV_HTTP_TIMEOUT) \
	uv run --index-url $(UV_INDEX_URL) --with twine python -m twine upload dist/*

# Maintenance commands
clean:
	rm -rf .ruff_cache/ .pytest_cache/ .mypy_cache/
	rm -rf *.egg-info __pycache__ alithia_agent/__pycache__
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .venv/lib/python*/site-packages/*.pyc

clean-logs:
	rm -rf ~/.alithia/logs/*.log

clean-db:
	rm -rf ~/.alithia/data/alithia.db

# Quick aliases
p: paperscout
l: paperlens
d: daemon
s: status