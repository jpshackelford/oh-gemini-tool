# Antigravity Delegate Tool

## 1. Introduction

This document describes the design of `oh-gemini-tool`: an OpenHands tool that delegates
work to the Google Antigravity CLI (`agy`). It exists so an OpenHands agent can use a
Google Antigravity subscription for heavy work, without an API key and without waiting
for first-class ACP support.

### 1.1 Problem Statement

Two OpenHands paths reach Gemini, and neither fits a personal subscription:

- **`gemini-cli` over ACP.** Works, but Google retired consumer-tier OAuth for individual
  accounts on 2026-06-18. A personal account must therefore use a billed API key, which
  means paying for the subscription *and* for API usage.
- **Antigravity as a built-in ACP provider.** Deferred upstream. The first-party ACP
  server is a ~650 MiB download (~1.9 GiB unpacked) with no npm fallback, which does not
  fit the ACP startup budget.

Meanwhile `agy` is already installed, already authenticated, and runs on the
subscription. It simply has no `--acp` mode.

### 1.2 Proposed Solution

Rather than wait for ACP support, drive `agy`'s existing headless interface. `agy -p
"<task>" --output-format json` runs autonomously, edits files in the working directory,
and returns a structured envelope. Wrapping that in a tool gives the agent a way to
offload expensive work to the subscription.

## 2. Developer Experience

### 2.1 Tool Invocation

```python
from openhands.sdk import Agent, Tool
from oh_gemini_tool.tool import GeminiDelegateTool

agent = Agent(llm=loop_llm, tools=[Tool(name=GeminiDelegateTool.name)])
```

The agent then calls `gemini_delegate(task=..., model=..., reuse_session=...)`.

### 2.2 Standalone Invocation

`run_agy` exposes the same capability without the SDK:

```python
from oh_gemini_tool.agy import run_agy

result = run_agy("Refactor src/ to use dataclasses.", working_dir=".")
print(result.status, result.usage)
```

## 3. Architecture

```
OpenHands agent loop (small/cheap model)
        │  gemini_delegate(task=...)
        ▼
GeminiDelegateExecutor ──► agy -p "<task>" --output-format json [--conversation <id>]
        │                         │
        │                         └── runs on the Antigravity subscription,
        │                             edits files in the workspace directly
        ▼
GeminiDelegateObservation  ◄── JSON envelope: status, response, usage, conversation_id
```

The split is deliberate:

- `oh_gemini_tool.agy` — standard library only. Command construction, execution, and
  envelope parsing. Importable and testable without the SDK.
- `oh_gemini_tool.tool` — the OpenHands integration. Action, observation, executor, and
  tool definition. Imports the SDK lazily via the `[openhands]` extra.

### 3.1 Failure Model

`run_agy` never raises for a failed *run*. Missing binary, non-zero exit, timeout,
unparseable output, and an `error` field in the envelope all become `AgyResult(ok=False)`
with a reason. The executor turns those into error observations. Only a missing binary
raises (`AgyNotFoundError`), and the executor catches it — so a misconfigured environment
produces a readable tool error rather than a crashed conversation.

### 3.2 Session Continuity

`agy` supports resuming a conversation, and the tool threads it:

| Invocation | Behaviour |
|---|---|
| `agy -p ...` (no flag) | New conversation every call — no memory of prior calls |
| `agy -p ... --conversation <id>` | Resumes that conversation |

The executor captures `conversation_id` from each envelope and passes it on the next
call, so one OpenHands conversation maps to one Antigravity session by default.

Bare `-c` / `--continue` is deliberately **never** used: it resumes whichever
conversation *any* `agy` process touched last, which would leak context between
unrelated delegations.

Measured behaviour on trivial prompts:

| | Fresh | Resume |
|---|---|---|
| Duration | ~3.5 s | ~43 s |
| Input tokens | ~12k | ~14k+ |

Resuming replays the session, so it is slower and costs more input tokens. That is why
`reuse_session=false` exists for unrelated work.

## 4. Trade-offs

### 4.1 What this approach gives up

- **No streaming.** `agy -p` returns one final envelope; intermediate steps are invisible
  to the agent loop.
- **No interactive steering.** Each call is a complete turn. The agent cannot pause
  mid-task to answer a clarifying question.
- **No tool-approval prompt.** Non-interactive runs cannot answer permission prompts, so
  the tool passes `--dangerously-skip-permissions` (or `--sandbox`). The OpenHands
  security analyzer still gates the *call* to the tool, but not what `agy` does inside.
- **A second, opaque agent.** Work happens under Antigravity's own model and context. The
  loop's history and `agy`'s history are separate; only the response text crosses over.

### 4.2 Why not wrap the ACP server

The ACP server is the better *integration* — streaming, tool calls, session state, and
OpenHands as the primary agent. It is currently blocked upstream from being a built-in
provider, not from working at all:

1. `acp_server="custom"` with an explicit `acp_command` — the SDK supports this today,
   and it **works with Google's first-party Antigravity ACP server on a personal
   subscription**. This is the recommended path if you want the proper integration now.
2. Wait for the upstream provider work to land a first-class entry.

For a personal workflow, a small tool beats a large sidecar. For a product, the ACP
route is the right shape.

See **[`gemini-acp-path.md`](gemini-acp-path.md)** for the full picture: what OpenHands
supports today, the bugs blocking the built-in provider, the artifact-size measurements,
and the specific issues and PRs to support.

## 5. Terms and Eligibility

This tool drives Google's own CLI with the user's own credentials, which is closer to
intended Antigravity use than scraping the API. The boundary Google drew is that API and
external-application usage is billed separately from subscription quota; programmatic
automation of a local CLI sits in a grey zone. Check it against your intended use before
shipping it to others.

## 6. Testing Strategy

- **Unit tests** (`tests/test_agy.py`, `tests/test_tool.py`) run against a *real
  subprocess*: a small executable "fake agy" is placed on `PATH`. This exercises the
  actual code path — `shutil.which`, argv construction, execution, parsing — without
  mocking `subprocess` and without needing Antigravity installed.
- **`agy_integration`** (`make test-agy`) drives a real, authenticated `agy`. Skipped
  automatically when the binary is absent.
- **`agent_eval`** (`pytest -m agent_eval`) runs a real LLM agent equipped only with the
  tool, to catch regressions in whether a model can actually translate instructions into
  correct tool calls.
