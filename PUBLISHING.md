# Publishing Guide for oh-gemini-tool

This guide explains how to publish `oh-gemini-tool` to PyPI (Python Package Index).

## Overview

This repository uses **Release Please** for automated releases based on conventional
commits. You have two options:

1. **Automated Publishing with Release Please (Recommended)** - Fully automated releases
2. **Manual Publishing** - Using API tokens and local commands

## Option 1: Automated Publishing with Release Please (Recommended)

This is the **easiest and most secure** method. Your repository is configured to use
Release Please!

### How It Works

Release Please automates the entire release process:

1. **You commit** using conventional commit messages (see below)
2. **Release Please creates** a "Release PR" that:
   - Automatically bumps the version in `pyproject.toml`
   - Generates/updates `CHANGELOG.md` from your commits
   - Creates a release when you merge the PR
3. **GitHub Actions publishes** your package to PyPI automatically
4. **Creates a GitHub Release** with distribution files

**No manual version updates. No manual changelog. No manual tagging. It's all
automated!** ✨

### One-Time Setup on PyPI

You need to configure Trusted Publishing on PyPI **before your first release**:

1. **Create a PyPI account** (if you don't have one):
   - Go to https://pypi.org/account/register/
   - Verify your email address

2. **Register your project name** (reserve it):
   - Go to https://pypi.org/manage/account/publishing/
   - Click "Add a new pending publisher"
   - Fill in:
     - **PyPI Project Name**: `oh-gemini-tool`
     - **Owner**: `jpshackelford`
     - **Repository name**: `oh-gemini-tool`
     - **Workflow name**: `release.yml`
     - **Environment name**: `pypi`
   - Click "Add"

   This reserves the name and allows GitHub Actions to publish without API tokens!

### Conventional Commits

Release Please uses your commit messages to determine version bumps. Use these prefixes:

#### Breaking Changes (Major version bump)
```bash
git commit -m "feat!: redesign tool API

BREAKING CHANGE: removed the legacy delegate() method"
```
Bumps: `0.1.0` → `1.0.0` (or `0.1.0` → `0.2.0` before 1.0)

#### New Features (Minor version bump)
```bash
git commit -m "feat: add sandbox mode support"
```
Bumps: `0.1.0` → `0.2.0`

#### Bug Fixes (Patch version bump)
```bash
git commit -m "fix: thread conversation id on resumed runs"
```
Bumps: `0.1.0` → `0.1.1`

#### Other Useful Types
```bash
git commit -m "docs: update README with new examples"
git commit -m "refactor: simplify envelope parsing"
git commit -m "perf: avoid replaying the session for unrelated work"
git commit -m "test: add tests for timeout handling"
git commit -m "chore: update dependencies"
git commit -m "ci: add Python 3.13 to test matrix"
```
These types appear in the changelog but don't trigger a release by themselves.

### Publishing Workflow

Once the one-time PyPI setup is complete:

```bash
# 1. Make your changes
git add .
git commit -m "feat: add new feature"
git push origin main

# 2. Release Please automatically creates/updates a "Release PR"
# - Check PRs: https://github.com/jpshackelford/oh-gemini-tool/pulls
# - Review the version bump and changelog

# 3. Merge the Release PR
# - This triggers the actual release!
# - GitHub Actions will build and publish to PyPI
# - A GitHub Release is created automatically

# 4. Done! Your package is live on PyPI
```

**Watch the progress**:
- Release PR: https://github.com/jpshackelford/oh-gemini-tool/pulls
- GitHub Actions: https://github.com/jpshackelford/oh-gemini-tool/actions
- Releases: https://github.com/jpshackelford/oh-gemini-tool/releases

### Versioning

Release Please follows [Semantic Versioning](https://semver.org/) automatically:

- `fix:` commits → Patch bump (`0.1.0` → `0.1.1`)
- `feat:` commits → Minor bump (`0.1.0` → `0.2.0`)
- `feat!:` or `BREAKING CHANGE:` → Major bump (`0.1.0` → `1.0.0`)

Multiple commits are batched into a single release PR!

## Option 2: Manual Publishing

If you prefer manual control or want to test locally:

### One-Time Setup

1. **Install uv** (if not already installed):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Create PyPI account**:
   - Go to https://pypi.org/account/register/
   - Verify your email

3. **Create API token**:
   - Go to https://pypi.org/manage/account/token/
   - Click "Add API token"
   - Name: `oh-gemini-tool`
   - Scope: Select "Entire account" for first publish, then "Project: oh-gemini-tool"
     for subsequent releases
   - Copy the token (starts with `pypi-...`)

4. **Configure uv with your token**:
   ```bash
   # Store in keyring (secure)
   uv publish --username __token__ --password pypi-your-token-here --dry-run

   # Or export as environment variable
   export UV_PUBLISH_TOKEN=pypi-your-token-here
   ```

### Publishing Steps

Manual publishing is useful for testing or if you need to bypass the automated workflow:

```bash
# 1. Ensure all tests pass
make all

# 2. Build the package
make build

# 3. Test on TestPyPI first (optional but recommended)
make publish-test

# Test installation from TestPyPI:
# pip install -i https://test.pypi.org/simple/ oh-gemini-tool

# 4. Publish to production PyPI
make publish
```

**Note**: Manual publishing doesn't update version numbers or changelogs. Consider using
Release Please for the full workflow.

## Testing Your Package

After publishing, test the installation:

```bash
# Create a fresh virtual environment
python -m venv test-env
source test-env/bin/activate  # On Windows: test-env\Scripts\activate

# Install from PyPI
pip install oh-gemini-tool

# The core client needs no extra dependencies
python -c "from oh_gemini_tool import run_agy; print('Success!')"

# The agent tool needs the [openhands] extra
pip install "oh-gemini-tool[openhands]"
python -c "from oh_gemini_tool.tool import GeminiDelegateTool; print('Tool ready!')"
```

## Pre-Release Checklist

Before merging a Release PR:

- [ ] All tests pass: `make all`
- [ ] Review the auto-generated CHANGELOG.md
- [ ] Verify the version bump is correct
- [ ] All commits use conventional commit format
- [ ] Code formatted: `make format`

**Note**: Version and changelog are automatically updated by Release Please!

## Troubleshooting

### "The name 'oh-gemini-tool' is already taken"

If someone else registered this name, you'll need to:
1. Choose a different name (e.g., `jpshackelford-gemini-tool`)
2. Update `name` in `pyproject.toml`
3. Update the package name in `.github/workflows/release.yml`

### "403 Forbidden" when publishing

For automated publishing:
- Ensure you completed the Trusted Publishing setup on PyPI
- Verify the workflow name and environment name match exactly

For manual publishing:
- Check your API token is valid
- Ensure the token has the right scope (entire account or project-specific)

### Package not showing up on PyPI

- It can take a few minutes for PyPI to index new packages
- Check for errors in the GitHub Actions workflow logs
- Verify the package built successfully in the "Build" job

### No Release PR is being created

If Release Please isn't creating a release PR:

- Ensure you're using conventional commit messages (`feat:`, `fix:`, etc.)
- Check the Release Please workflow ran:
  https://github.com/jpshackelford/oh-gemini-tool/actions
- The PR might already exist - check open PRs
- Make sure commits are on the `main` branch

### Release PR exists but version didn't bump

- Check your commit message format matches conventional commits
- Only `feat:`, `fix:`, and breaking changes trigger releases
- Commits like `docs:`, `chore:`, `test:` are included but don't bump version alone

## Resources

- [Release Please Documentation](https://github.com/googleapis/release-please)
- [Conventional Commits Specification](https://www.conventionalcommits.org/)
- [PyPI Trusted Publishing Guide](https://docs.pypi.org/trusted-publishers/)
- [Python Packaging User Guide](https://packaging.python.org/)
- [Semantic Versioning](https://semver.org/)
- [uv Documentation](https://docs.astral.sh/uv/)

## Quick Reference

### Using Release Please (Recommended)

```bash
# Make changes with conventional commits
git commit -m "feat: add new feature"
git commit -m "fix: correct bug"
git push origin main

# Check for Release PR
# https://github.com/jpshackelford/oh-gemini-tool/pulls

# Merge the Release PR → automatic release!
```

### Conventional Commit Quick Reference

```bash
feat:     # New feature (minor bump)
fix:      # Bug fix (patch bump)
feat!:    # Breaking change (major bump)
docs:     # Documentation changes
refactor: # Code refactoring
perf:     # Performance improvements
test:     # Test changes
chore:    # Maintenance tasks
ci:       # CI/CD changes
```

### Manual Commands (Testing/Development)

```bash
# Show current version
make version

# Build distribution packages locally
make build

# Publish to TestPyPI
make publish-test

# Publish to production PyPI (bypasses Release Please)
make publish
```
