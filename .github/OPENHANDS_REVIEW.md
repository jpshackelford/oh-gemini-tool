# OpenHands Automated PR Review

This repository uses [OpenHands](https://github.com/All-Hands-AI/OpenHands) for automated pull request reviews.

## How It Works

The OpenHands bot automatically reviews pull requests when:

1. **A new PR is opened** (non-draft)
2. **A draft PR is marked as ready for review**
3. **The `review-this` label is added** to any PR
4. **OpenHands is requested as a reviewer** (`openhands-agent` or `all-hands-bot`)

## Review Triggers

### Automatic Review
New non-draft PRs are automatically reviewed when opened.

### Manual Trigger Options

**Option 1: Add the label**
```bash
gh pr edit <PR_NUMBER> --add-label "review-this"
```

**Option 2: Request OpenHands as reviewer**
```bash
gh pr edit <PR_NUMBER> --add-reviewer openhands-agent
```

**Option 3: Mark draft as ready**
If you have a draft PR, marking it as "Ready for review" will trigger the review.

### Re-trigger a Review

To re-run the review after making changes:

1. Remove and re-add the `review-this` label:
   ```bash
   gh pr edit <PR_NUMBER> --remove-label "review-this"
   gh pr edit <PR_NUMBER> --add-label "review-this"
   ```

2. Or close and re-request the reviewer.

## Review Style

The bot provides **roasted** feedback 🔥 - critical and direct - focusing on:
- Code quality and best practices
- Potential bugs or issues
- What's wrong and how to fix it
- Documentation completeness
- Test coverage

Expect honest, no-nonsense reviews that get straight to the point.

## Configuration

### LLM Model
Currently using: `litellm_proxy/claude-sonnet-4-5-20250929` via the OpenHands LLM proxy.

To use a different model, edit `.github/workflows/pr-review-by-openhands.yml`:
```yaml
with:
  llm-model: openai/gpt-4  # or any supported model
  review-style: roasted # or constructive, concise, detailed
```

### Review Styles
- `roasted` - Critical, direct feedback 🔥 (default)
- `constructive` - Balanced, helpful feedback
- `concise` - Brief, to-the-point reviews
- `detailed` - Comprehensive, thorough reviews

### Required Secrets

The workflow needs one repository secret:

- `LLM_API_KEY` — key for the OpenHands LLM proxy (`llm-proxy.app.all-hands.dev`)

Add it under Settings → Secrets and variables → Actions.

### Custom LLM Endpoint

To use a custom LLM endpoint or proxy, update the workflow:

```yaml
with:
  llm-model: litellm_proxy/your-model
  llm-base-url: https://your-llm-proxy.com
  llm-api-key: ${{ secrets.LLM_API_KEY }}
```

## Limitations

- Only reviews PRs from the same repository (not forks, for security)
- Skips draft PRs unless explicitly triggered
- One review per PR event (use concurrency control)

## Disabling Reviews

To temporarily disable automated reviews:

1. **For a specific PR**: Keep it as a draft until ready
2. **For the repository**: Disable the workflow in Settings → Actions

## Learn More

- [OpenHands Documentation](https://docs.openhands.dev)
- [PR Review Plugin](https://github.com/OpenHands/extensions/tree/main/plugins/pr-review)
- [OpenHands on GitHub](https://github.com/All-Hands-AI/OpenHands)
