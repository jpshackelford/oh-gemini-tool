.PHONY: help install dev lint format test test-cov test-agy clean all check build publish-test publish version

# Default target
help:
	@echo "oh-gemini-tool - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install    Install in editable mode"
	@echo "  make dev        Install with development dependencies"
	@echo ""
	@echo "Code Quality:"
	@echo "  make lint       Run ruff linter"
	@echo "  make format     Format code with ruff"
	@echo "  make check      Run all checks (lint)"
	@echo ""
	@echo "Testing:"
	@echo "  make test       Run tests"
	@echo "  make test-cov   Run tests with coverage report"
	@echo "  make test-agy   Run tests that exercise the real agy binary"
	@echo ""
	@echo "Building & Publishing:"
	@echo "  make build          Build distribution packages"
	@echo "  make publish-test   Publish to TestPyPI (for testing)"
	@echo "  make publish        Publish to PyPI (production)"
	@echo "  make version        Show current version"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean      Remove build artifacts and caches"
	@echo "  make all        Run all checks and tests"

# Install in editable mode
install:
	uv pip install -e .

# Install development dependencies
dev:
	uv pip install -e ".[dev,openhands]"

# Run linter (matches CI checks)
lint:
	uv run ruff check src tests
	uv run ruff format --check src tests

# Format code (auto-fix)
format:
	uv run ruff format src tests
	uv run ruff check --fix src tests

# Run all code quality checks
check: lint

# Run tests
test:
	uv run pytest tests -v

# Run tests with coverage
test-cov:
	uv run pytest tests -v \
		--cov=oh_gemini_tool \
		--cov-report=term-missing \
		--cov-report=html \
		--cov-fail-under=80

# Run the opt-in suite that shells out to a real, authenticated agy binary
test-agy:
	uv run pytest tests -v -m agy_integration --no-cov

# Clean build artifacts
clean:
	rm -rf __pycache__ .pytest_cache .ruff_cache htmlcov .coverage coverage.xml
	rm -rf build dist *.egg-info
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Run all checks and tests
all: check test

# Show current version
version:
	@grep "^version" pyproject.toml | sed 's/version = "\(.*\)"/\1/'

# Build distribution packages
build: clean
	@echo "Building distribution packages..."
	uv build
	@echo ""
	@echo "Build complete! Packages created in dist/"
	@ls -lh dist/

# Publish to TestPyPI (for testing before production release)
publish-test: build
	@echo "Publishing to TestPyPI..."
	@echo "You'll need a TestPyPI API token: https://test.pypi.org/manage/account/token/"
	uv publish --publish-url https://test.pypi.org/legacy/

# Publish to PyPI (production)
publish: build
	@echo "⚠️  WARNING: This will publish to production PyPI!"
	@echo "Make sure you've:"
	@echo "  1. Updated the version in pyproject.toml"
	@echo "  2. Run 'make all' to verify all tests pass"
	@echo "  3. Committed and pushed all changes"
	@echo ""
	@read -p "Continue? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		echo "Publishing to PyPI..."; \
		uv publish; \
	else \
		echo "Cancelled."; \
	fi
