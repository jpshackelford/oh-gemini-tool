# Contributing to oh-gemini-tool

Thank you for your interest in contributing to oh-gemini-tool! This document provides guidelines and instructions for contributing.

## Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/jpshackelford/oh-gemini-tool.git
   cd oh-gemini-tool
   ```

2. **Install dependencies**
   ```bash
   # Install uv if you haven't already
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # Install the package with dev dependencies
   make dev
   # or
   uv pip install -e ".[dev,openhands]"
   ```

3. **Run tests to verify setup**
   ```bash
   make test
   ```

## Development Workflow

### Making Changes

1. **Create a new branch**
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/your-bug-fix
   ```

2. **Make your changes**
   - Write clean, well-documented code
   - Follow the existing code style
   - Add tests for new functionality
   - Update documentation as needed

3. **Run code quality checks**
   ```bash
   # Format code
   make format

   # Run linter
   make lint

   # Run tests
   make test

   # Run tests with coverage
   make test-cov

   # Or run all checks at once
   make all
   ```

4. **Commit your changes**
   ```bash
   git add .
   git commit -m "feat: add new feature"
   # or
   git commit -m "fix: resolve issue with X"
   ```

   We follow [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat:` for new features
   - `fix:` for bug fixes
   - `docs:` for documentation changes
   - `test:` for test changes
   - `refactor:` for code refactoring
   - `chore:` for maintenance tasks

5. **Push and create a pull request**
   ```bash
   git push origin your-branch-name
   ```

   Then create a pull request on GitHub.

### Automated PR Review

This repository uses **OpenHands** for automated code reviews. When you open a PR:

- The bot will automatically review your changes
- You'll receive **roasted** 🔥 feedback - direct, critical, and honest
- Expect no-nonsense reviews on code quality, best practices, and potential issues
- Reviews typically complete within a few minutes

**Trigger a review manually:**
- Add the `review-this` label to your PR
- Request `openhands-agent` as a reviewer
- Mark a draft PR as "Ready for review"

See [.github/OPENHANDS_REVIEW.md](.github/OPENHANDS_REVIEW.md) for more details.

## Code Quality Standards

### Testing

- Write tests for all new functionality
- Maintain or improve code coverage (minimum 80%)
- Tests should be clear and well-documented
- Use descriptive test names that explain what is being tested

**Do not mock `subprocess`.** The suite drives a small executable "fake agy" placed on
`PATH` (see `tests/conftest.py`), so tests exercise the real code path — binary lookup,
argv construction, execution, and parsing. Follow that pattern for anything that shells
out. Tests that need a real, authenticated `agy` belong behind the `agy_integration`
marker; tests that need a real LLM belong behind `agent_eval`.

### Code Style

- We use [Ruff](https://docs.astral.sh/ruff/) for linting and formatting
- Line length: 100 characters
- Follow PEP 8 guidelines
- Use type hints where appropriate

### Documentation

- Update docstrings for modified functions/classes
- Update README.md if adding new features
- Add examples for new functionality
- Keep documentation clear and concise

## Project Structure

```
oh-gemini-tool/
├── src/oh_gemini_tool/
│   ├── __init__.py        # Package exports (no SDK import)
│   ├── agy.py             # Dependency-free Antigravity CLI client
│   └── tool.py            # OpenHands SDK tool integration
├── tests/
│   ├── agent_eval/        # Opt-in end-to-end LLM evals
│   ├── conftest.py        # fake-agy fixture
│   ├── test_agy.py        # Client tests
│   └── test_tool.py       # Tool tests
├── examples/              # Usage examples
└── doc/                   # Additional documentation
```

## Running Tests

```bash
# Run all unit tests
make test

# Run tests with coverage
make test-cov

# Run specific test file
uv run pytest tests/test_agy.py -v

# Run specific test
uv run pytest tests/test_agy.py::TestRunAgy::test_successful_run -v

# Opt-in suites (excluded from the default run)
make test-agy                        # real, authenticated agy
uv run pytest tests -m agent_eval    # real LLM agent evals (needs LLM_API_KEY)
```

## Common Tasks

### Adding a New Action Parameter

1. Add the field to `GeminiDelegateAction` in `tool.py`
2. Thread it through `GeminiDelegateExecutor.execute` into `run_agy`
3. Add the corresponding argument to `build_command` in `agy.py`
4. Surface it in the observation if the agent needs it back
5. Write tests in `tests/test_agy.py` and `tests/test_tool.py`
6. Update the parameter table in README.md

### Adding a New Model Tier

1. Add it to `MODEL_TIERS` in `agy.py`
2. Add it to the `Literal` in `GeminiDelegateAction.model`
3. Update the action description and README

## Reporting Issues

When reporting issues, please include:

- A clear description of the problem
- Steps to reproduce
- Expected behavior
- Actual behavior
- Environment details (Python version, `agy --version`, OS)
- Minimal code example if applicable

## Questions?

Feel free to open an issue for questions or discussion about potential contributions.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
