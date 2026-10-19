# OpenHands Antigravity (Gemini) Delegate Tool

[![CI](https://github.com/jpshackelford/oh-gemini-tool/actions/workflows/ci.yml/badge.svg)](https://github.com/jpshackelford/oh-gemini-tool/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/oh-gemini-tool)](https://pypi.org/project/oh-gemini-tool/)
[![Python versions](https://img.shields.io/pypi/pyversions/oh-gemini-tool)](https://pypi.org/project/oh-gemini-tool/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

An [OpenHands](https://github.com/All-Hands-AI/OpenHands) tool that delegates work to the
**Google Antigravity CLI** (`agy`). The agent loop stays small and cheap; `agy` does the
heavy lifting — in the conversation workspace, on your Antigravity subscription.

## Why this exists

OpenHands supports Gemini through ACP today, but not for personal subscriptions:

- **`gemini-cli` over ACP** works for Enterprise and for billed API keys. Google retired
  consumer-tier OAuth on 2026-06-18, so a personal subscription cannot use it.
- **Antigravity as a built-in ACP provider** is deferred upstream. Google ships a
  first-party ACP server that works on a personal subscription, but it is distributed as
  a platform binary rather than an npm package, which the provider install mechanism does
  not yet support.

`agy` itself, however, is already installed, already authenticated, and runs on the
subscription. It just has no `--acp` mode. This tool drives it headlessly instead.

> **This tool is a workaround, not the ideal integration.** ACP is the better answer —
> it keeps OpenHands as the primary agent and exposes streaming, typed tool calls, and
> permission gating. **A first-party Antigravity ACP server exists and already works with
> the SDK's `acp_command` escape hatch on a personal subscription.**
>
> See **[`doc/gemini-acp-path.md`](doc/gemini-acp-path.md)** — it covers what ACP is, how
> OpenHands supports other vendors' harnesses today, how to use Gemini with an Enterprise
> account, a step-by-step tutorial for a personal subscription, why first-class support is
> not there yet, and a factual list of what the integration does and does not do.

> **Scope note.** This is a personal/experimental integration. It drives Google's own
> CLI with your own credentials. Google's own terms govern that use — including whether
> it is permitted and whether the Antigravity binary may be redistributed. Those terms
> are Google's to change and we do not interpret them here; read them at
> <https://antigravity.google/terms> before relying on this. See
> [`doc/gemini-acp-path.md` §5.5](doc/gemini-acp-path.md) for the licensing and
> distribution facts we can state.

## Requirements

- **Google Antigravity**, installed and authenticated as the account you want to use.
  Verify with `agy models` (or any `agy -p "..."` call).
- **Python 3.12+** for the OpenHands tool integration. The core client
  (`oh_gemini_tool.agy`) is standard-library only and runs on older Pythons.

## Installation

The core client has no runtime dependencies:

```bash
pip install oh-gemini-tool          # or: uv pip install oh-gemini-tool
```

To use it as an OpenHands agent tool, install the `openhands` extra. It pulls in
`openhands-sdk`, which requires **Python 3.12+**:

```bash
pip install "oh-gemini-tool[openhands]"
```

## Usage as an OpenHands agent tool

The tool lives in `oh_gemini_tool.tool`; importing that module registers it under the
name `gemini_delegate`.

```python
from openhands.sdk import Agent
from oh_gemini_tool.tool import GeminiDelegateTool

agent = Agent(
    tools=[GeminiDelegateTool],
    # ... other configuration
)
```

Pair it with a small loop model and let it offload the expensive work:

```python
from openhands.sdk import LLM, Agent, Conversation, Tool
from oh_gemini_tool.tool import GeminiDelegateTool

loop_llm = LLM(model="gpt-5.5", api_key=...)          # cheap orchestrator
agent = Agent(llm=loop_llm, tools=[Tool(name=GeminiDelegateTool.name)])

conversation = Conversation(agent=agent, workspace=".")
conversation.send_message(
    "Delegate to Antigravity: add type hints to every function in src/ and run the tests."
)
conversation.run()
```

On a **remote agent-server**, reference the tool by its module qualname so the server
imports and registers it on conversation creation:

```python
"tools": [{"name": "gemini_delegate"}],
"tool_module_qualnames": {"gemini_delegate": "oh_gemini_tool.tool"},
```

## The `gemini_delegate` action

| Parameter | Type | Default | Description |
|---|---|---|---|
| `task` | string | required | Self-contained instruction for Antigravity. It runs autonomously and cannot ask questions mid-task, so state the goal, the files, and the definition of done. |
| `model` | `flash_lite` \| `flash` \| `pro` \| null | account default | Antigravity model tier. |
| `reuse_session` | bool | `true` | Continue the previous Antigravity conversation so it keeps context. Set `false` for unrelated work (also faster — resuming replays the session). |
| `timeout_seconds` | int | `900` | Hard wall-clock limit. |

The observation reports the response, `status`, Antigravity `conversation_id`,
`num_turns`, `duration_seconds`, and token `usage`.

## Sessions

`agy` supports resuming a conversation, and this tool threads it for you:

| Invocation | Behaviour |
|---|---|
| `agy -p ...` (no flag) | **New** conversation every call — no memory of prior calls |
| `agy -p ... --conversation <id>` | **Resumes** that conversation |

By default, one OpenHands conversation maps to one Antigravity session: the executor
captures the `conversation_id` from each result and passes it on the next call.

- **Never use bare `-c` / `--continue`.** It resumes whichever conversation *any* `agy`
  process touched last, so unrelated delegations can leak context into each other.
  Always resume by explicit id — which is what this tool does.
- **Resuming is slower and costs more input tokens**, because the prior session is
  replayed. Measured on trivial prompts: fresh ~3.5 s vs resume ~43 s, with input
  tokens growing from ~12k to ~14k+. Use `reuse_session=false` for unrelated work.
- **Still one-shot per call.** Even resumed, each call is a complete turn — you cannot
  pause mid-task to answer a question. This is continuity *across* delegations, not
  interactive steering *within* one.
- **Don't share one session across parallel delegations.** Serialize them, or give each
  branch `reuse_session=false`, or their turns will interleave into one context.
- The session pointer is **in-memory**. Antigravity persists conversations on disk, but
  a restarted agent-server starts a fresh session.

## Standalone usage (no agent)

`run_agy` drives the CLI directly and needs no SDK:

```python
from oh_gemini_tool.agy import run_agy

result = run_agy(
    "Create a file named demo.txt containing HELLO. Then reply DONE.",
    working_dir=".",
)
if result.ok:
    print(result.status, result.usage)
    print(result.response)

# Resume the same conversation on the next call:
follow_up = run_agy(
    "What file did you just create?",
    working_dir=".",
    conversation_id=result.conversation_id,
)
```

`build_command` and `parse_result` are exposed separately if you want to construct or
inspect calls yourself.

## How it works

```
OpenHands agent loop (small/cheap model)
        │  gemini_delegate(task=...)
        ▼
GeminiDelegateExecutor ──► agy -p "<task>" --output-format json [--conversation <id>]
        │                         │
        │                         └── runs on your Antigravity subscription,
        │                             edits files in the workspace directly
        ▼
GeminiDelegateObservation  ◄── JSON envelope: status, response, usage, conversation_id
```

See [`doc/gemini-tool.md`](doc/gemini-tool.md) for the design write-up, including the
trade-offs of this approach.

See [`doc/gemini-acp-path.md`](doc/gemini-acp-path.md) for **the better integration**:
what ACP support OpenHands has today, its limitations for personal subscriptions, the
first-party Antigravity ACP server (which already works via `acp_command`), and the
specific issues and PRs blocking a built-in provider — with dates.

## Development

```bash
git clone https://github.com/jpshackelford/oh-gemini-tool.git
cd oh-gemini-tool

make dev        # install with dev + openhands extras
make lint       # ruff check + format check
make test       # unit tests
make test-cov   # unit tests with coverage (fails under 80%)
make all        # lint + test
```

Opt-in suites (excluded from the default run):

```bash
make test-agy                     # drives a real, authenticated agy
uv run pytest tests -m agent_eval # real LLM agent evals (needs LLM_API_KEY)
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md).

This project uses [Conventional Commits](https://www.conventionalcommits.org/) and
[Release Please](https://github.com/googleapis/release-please) for automated releases:

```bash
feat: add new feature       # minor version bump
fix: correct bug            # patch version bump
docs: update documentation
refactor: improve code
chore: update dependencies
```

### Automated Code Review

This repository uses [OpenHands](https://github.com/All-Hands-AI/OpenHands) for automated
PR reviews. Reviews are **roasted** style 🔥 — expect critical, no-nonsense feedback. See
[.github/OPENHANDS_REVIEW.md](.github/OPENHANDS_REVIEW.md) for details.
