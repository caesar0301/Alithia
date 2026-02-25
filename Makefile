# Variables
PYTHON = python3
PYTHON_MODULES = alithia tests examples
COVERAGE_MODULES = alithia
TEST_DIR = tests
LINE_LENGTH = 120
VENV_DIR = .venv

# Colors for output
BLUE = \033[34m
GREEN = \033[32m
YELLOW = \033[33m
RED = \033[31m
RESET = \033[0m

# =============================================================================
# HELP
# =============================================================================

.PHONY: help
help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# =============================================================================
# SETUP COMMANDS
# =============================================================================

.PHONY: install setup check-env venv

venv: ## Create virtual environment using pyenv Python
	@echo "$(BLUE)🐍 Creating virtual environment...$(RESET)"
	@$(PYTHON) -m venv $(VENV_DIR)
	@echo "$(GREEN)✅ Virtual environment created at $(VENV_DIR)$(RESET)"
	@echo "$(YELLOW)💡 Activate with: source $(VENV_DIR)/bin/activate$(RESET)"

install: ## Install development dependencies
	@echo "$(BLUE)🔧 Installing development dependencies...$(RESET)"
	@pip install -e ".[default,dev]"

setup: venv install ## Setup development environment
	@echo "$(GREEN)✅ Development environment ready$(RESET)"

check-env: ## Check environment setup
	@echo "$(BLUE)🔍 Checking environment...$(RESET)"
	@echo "Python version: $$($(PYTHON) --version)"
	@echo "pyenv version: $$(pyenv --version 2>/dev/null || echo 'pyenv not found')"
	@echo "pip version: $$(pip --version)"
	@echo "Working directory: $$(pwd)"
	@echo "Python modules: $(PYTHON_MODULES)"

# =============================================================================
# AGENT COMMANDS
# =============================================================================

.PHONY: paperscout paperlens

paperscout: ## Run PaperScout agent (use CONFIG=path/to/config.json, FROM_DATE=YYYY-MM-DD, TO_DATE=YYYY-MM-DD)
	@echo "$(BLUE)📰 Running PaperScout agent...$(RESET)"
	@set -e; \
	CMD="python -m alithia.run paperscout_agent"; \
	if [ -n "$(CONFIG)" ]; then CMD="$$CMD --config $(CONFIG)"; fi; \
	if [ -n "$(FROM_DATE)" ]; then CMD="$$CMD --from-date $(FROM_DATE)"; fi; \
	if [ -n "$(TO_DATE)" ]; then CMD="$$CMD --to-date $(TO_DATE)"; fi; \
	eval $$CMD

paperlens: ## Run PaperLens agent (requires INPUT=path/to/topic.txt and DIRECTORY=path/to/papers)
	@echo "$(BLUE)🔍 Running PaperLens agent...$(RESET)"
	@if [ -z "$(INPUT)" ] || [ -z "$(DIRECTORY)" ]; then \
		echo "$(RED)❌ Error: INPUT and DIRECTORY are required$(RESET)"; \
		echo "Usage: make paperlens INPUT=path/to/topic.txt DIRECTORY=path/to/papers"; \
		echo "Optional: TOP_N=20 MODEL=all-mpnet-base-v2 VERBOSE=1"; \
		exit 1; \
	fi
	@set -e; \
	CMD="python -m alithia.run paperlens_agent -i $(INPUT) -d $(DIRECTORY)"; \
	if [ -n "$(TOP_N)" ]; then CMD="$$CMD -n $(TOP_N)"; fi; \
	if [ -n "$(MODEL)" ]; then CMD="$$CMD --model $(MODEL)"; fi; \
	if [ -n "$(VERBOSE)" ]; then CMD="$$CMD -v"; fi; \
	if [ -n "$(NO_RECURSIVE)" ]; then CMD="$$CMD --no-recursive"; fi; \
	if [ -n "$(FORCE_GPU)" ]; then CMD="$$CMD --force-gpu"; fi; \
	eval $$CMD

# =============================================================================
# TEST COMMANDS
# =============================================================================

.PHONY: test test-unit test-integration test-coverage test-watch

test: ## Run all tests.
	@echo "$(BLUE)🧪 Running all tests...$(RESET)"
	pytest $(TEST_DIR) -v

test-unit: ## Run unit tests only
	@echo "$(BLUE)🧪 Running unit tests...$(RESET)"
	pytest $(TEST_DIR) -v -m "not integration"

test-integration: ## Run integration tests only
	@echo "$(BLUE)🧪 Running integration tests...$(RESET)"
	pytest $(TEST_DIR) -v -m "integration"

test-coverage: ## Run tests with coverage
	@echo "$(BLUE)🧪 Running tests with coverage...$(RESET)"
	pytest $(TEST_DIR) --cov=$(COVERAGE_MODULES) --cov-report=html --cov-report=term-missing

test-watch: ## Run tests in watch mode
	@echo "$(BLUE)👀 Running tests in watch mode...$(RESET)"
	pytest-watch $(TEST_DIR) -- -v

# =============================================================================
# CODE QUALITY COMMANDS
# =============================================================================

.PHONY: format format-check lint lint-fix quality autofix

format: ## Format code (black, isort, autoflake)
	@echo "$(BLUE)🎨 Formatting code...$(RESET)"
	@python -m autoflake --in-place --recursive --remove-all-unused-imports --remove-unused-variables $(PYTHON_MODULES)
	@python -m isort $(PYTHON_MODULES) --line-length $(LINE_LENGTH)
	@python -m black $(PYTHON_MODULES) --line-length $(LINE_LENGTH)

format-check: ## Check if code is properly formatted
	@echo "$(BLUE)🔍 Checking code formatting...$(RESET)"
	@python -m black --check $(PYTHON_MODULES) || (echo "$(RED)❌ Code formatting check failed. Run 'make format' to fix.$(RESET)" && exit 1)
	@python -m isort --check-only $(PYTHON_MODULES) || (echo "$(RED)❌ Import sorting check failed. Run 'make format' to fix.$(RESET)" && exit 1)

lint: ## Lint code
	@echo "$(BLUE)🔍 Running linters...$(RESET)"
	@python -m flake8 --max-line-length=$(LINE_LENGTH) --extend-ignore=E203,W503 $(PYTHON_MODULES)

lint-fix: ## Auto-fix linting issues where possible
	@echo "$(BLUE)🔧 Auto-fixing linting issues...$(RESET)"
	@python -m autoflake --in-place --recursive --remove-all-unused-imports --remove-unused-variables $(PYTHON_MODULES)

quality: format-check lint ## Run all quality checks
	@echo "$(GREEN)🎉 All quality checks passed!$(RESET)"

autofix: lint-fix format ## Auto-fix all code quality issues

# =============================================================================
# BUILD COMMANDS
# =============================================================================

.PHONY: build build-wheel build-sdist package

build: ## Build package
	@echo "$(BLUE)🔨 Building package...$(RESET)"
	@python -m build

build-wheel: ## Build wheel
	@echo "$(BLUE)🔨 Building wheel...$(RESET)"
	@python -m build --wheel

build-sdist: ## Build source distribution
	@echo "$(BLUE)🔨 Building source distribution...$(RESET)"
	@python -m build --sdist

package: clean build ## Build and package for distribution

# =============================================================================
# CLEAN COMMANDS
# =============================================================================

.PHONY: clean clean-all

clean: ## Clean Python cache and build artifacts
	@echo "$(BLUE)🧹 Cleaning Python cache and build artifacts...$(RESET)"
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@find . -type f -name "*.pyd" -delete 2>/dev/null || true
	@find . -type f -name ".coverage" -delete 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "*.egg" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@rm -rf dist/ build/ 2>/dev/null || true

clean-all: clean ## Clean everything including dependencies
	@echo "$(GREEN)✅ Complete cleanup finished!$(RESET)"

# =============================================================================
# EXAMPLE COMMANDS
# =============================================================================

.PHONY: examples run-examples example-arxiv example-flashrank example-diagnose example-docling

examples: run-examples ## Run all examples (alias)

run-examples: ## Run all runnable examples
	@echo "$(BLUE)📚 Running examples...$(RESET)"
	@echo ""
	@echo "$(GREEN)▶ Running ArXiv Search Example...$(RESET)"
	@python examples/arxiv_search_example.py || true
	@echo ""
	@echo "$(GREEN)▶ Running FlashRank Demo...$(RESET)"
	@python examples/flashrank_demo.py || true
	@echo ""
	@echo "$(GREEN)▶ Running Yesterday Papers Diagnostic...$(RESET)"
	@python examples/diagnose_yesterday_papers.py || true
	@echo ""
	@echo "$(BLUE)💡 Note: docling_ocr_example.py requires a PDF file argument$(RESET)"
	@echo "   Run with: make example-docling PDF=path/to/paper.pdf"
	@echo ""
	@echo "$(GREEN)✅ All examples completed!$(RESET)"

# =============================================================================
# UTILITY COMMANDS
# =============================================================================

.PHONY: shell requirements version

shell: ## Activate development shell
	@echo "$(BLUE)🐚 Activating development shell...$(RESET)"
	@echo "$(YELLOW)💡 Run: source $(VENV_DIR)/bin/activate$(RESET)"

requirements: ## Generate requirements files
	@echo "$(BLUE)📋 Generating requirements files...$(RESET)"
	@pip freeze > requirements.txt

version: ## Show current version
	@echo "$(BLUE)Current version:$(RESET)"
	@echo "Cogent (pyproject.toml): $(shell grep '^version = ' pyproject.toml | cut -d'"' -f2)"

# =============================================================================
# DEVELOPMENT COMMANDS
# =============================================================================

.PHONY: dev dev-check full-check

dev-check: quality test-unit ## Quick development check (quality + unit tests)

full-check: format-check lint test build ## Full development check (all checks + all tests + build)

# =============================================================================
# DOCUMENTATION COMMANDS
# =============================================================================

.PHONY: docs docs-build docs-serve docs-clean

docs: ## Build documentation
	@echo "$(BLUE)📚 Building documentation...$(RESET)"
	@cd docs && make html
	@echo "$(GREEN)Documentation built: docs/_build/html/index.html$(RESET)"

docs-serve: docs ## Build and serve documentation locally
	@echo "$(GREEN)Serving documentation at http://localhost:8000$(RESET)"
	@cd docs/_build/html && python -m http.server 8000

docs-clean: ## Clean documentation build artifacts
	@rm -rf docs/_build/

# =============================================================================
# RELEASE COMMANDS
# =============================================================================

.PHONY: release publish publish-test check-publish-prereqs

release: clean build ## Build all release artifacts

publish: check-publish-prereqs ## Publish package to PyPI
	@echo "$(BLUE)📦 Publishing to PyPI...$(RESET)"
	@twine upload dist/*
	@echo "$(GREEN)✅ Package published to PyPI$(RESET)"

publish-test: check-publish-prereqs ## Publish package to TestPyPI
	@echo "$(BLUE)📦 Publishing to TestPyPI...$(RESET)"
	@twine upload --repository testpypi dist/*
	@echo "$(GREEN)✅ Package published to TestPyPI$(RESET)"

check-publish-prereqs: ## Check prerequisites for publishing
	@echo "$(BLUE)🔍 Checking publishing prerequisites...$(RESET)"
	@twine --version >/dev/null 2>&1 || (echo "$(RED)❌ twine not found. Install with: pip install twine$(RESET)" && exit 1)
	@if [ -z "$${TWINE_USERNAME}" ] && [ ! -f ~/.pypirc ]; then \
		echo "$(YELLOW)⚠️  PyPI credentials not found. Set TWINE_USERNAME/TWINE_PASSWORD or configure ~/.pypirc$(RESET)"; \
		echo "$(BLUE)💡 You can set credentials with:$(RESET)"; \
		echo "   export TWINE_USERNAME=__token__"; \
		echo "   export TWINE_PASSWORD=pypi-your_token_here"; \
		echo "   OR configure ~/.pypirc file"; \
		echo "$(BLUE)💡 Get tokens from: https://pypi.org/manage/account/token/$(RESET)"; \
	fi

test-auth: ## Test PyPI authentication
	@echo "$(BLUE)🔐 Testing PyPI authentication...$(RESET)"
	@if [ -n "$${TWINE_USERNAME}" ]; then \
		echo "$(GREEN)✅ TWINE_USERNAME is set$(RESET)"; \
	else \
		echo "$(YELLOW)⚠️  TWINE_USERNAME not set$(RESET)"; \
	fi
	@if [ -f ~/.pypirc ]; then \
		echo "$(GREEN)✅ ~/.pypirc file exists$(RESET)"; \
	else \
		echo "$(YELLOW)⚠️  ~/.pypirc file not found$(RESET)"; \
	fi

# =============================================================================
# CI/CD COMMANDS
# =============================================================================

.PHONY: ci ci-test ci-quality

ci: ci-quality ci-test ## Run CI pipeline (quality checks + tests)

ci-test: test-unit test-integration ## Run CI tests

ci-quality: format-check lint ## Run CI quality checks

# =============================================================================
# DEFAULT GOAL
# =============================================================================

.DEFAULT_GOAL := help 
