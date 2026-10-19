# The ACP path for Gemini (and why it is the better integration)

This document is the longer companion to the [README](../README.md). The README
describes `oh-gemini-tool`, the tool this repository ships. This document explains why
that tool is a **workaround**, what the **proper** integration looks like, what
OpenHands supports today, and what is blocking the better solution — with links to the
specific issues and PRs, and dates.

If you are evaluating whether OpenHands can use a personal Google Antigravity or Gemini
subscription, read this first.

**Last verified: 2026-10-19** against `openhands-sdk` 1.49.6 and Antigravity ACP server
1.4.1. Version-sensitive claims are dated inline; re-check them before relying on them.

---

## 1. Why ACP is the right integration

`oh-gemini-tool` drives `agy` through its headless print mode (`agy -p ...`). That works,
but it is a subprocess wrapper around another agent, and it gives up a lot:

| Capability | ACP integration | This tool (`agy -p`) |
|---|---|---|
| OpenHands as the primary agent | Yes — one agent loop | No — two loops, one opaque |
| Streaming of intermediate steps | Yes (`session/update`) | No — one final envelope |
| Tool calls visible to OpenHands | Yes (`session/update`, typed) | No — invisible |
| Mid-task questions / steering | Yes | No — one-shot per call |
| Permission gating | Yes — OpenHands auto-approves or prompts | No — `--dangerously-skip-permissions` |
| Session continuity | Yes — native session ids | Partial — resume by explicit id |
| Model / thinking-level switching | Yes — `session/set_model`, selectors | Limited — `--model` per call |

With ACP, Antigravity becomes a *tool provider* under OpenHands' own agent loop. With
`agy -p`, Antigravity *is* the agent and OpenHands just reads its output. The first is
what you want for a real workflow.

---

## 2. What OpenHands supports today

ACP support in the SDK is real and reasonably mature. As of `openhands-sdk` 1.49.6
(checked 2026-10-19), `openhands.sdk.settings.acp_providers` ships **six** built-in
providers:

| Provider key | Notes |
|---|---|
| `claude-code` | pinned via `CLAUDE_AGENT_ACP_VERSION = "0.63.0"` |
| `codex` | pinned via `CODEX_ACP_VERSION = "1.10.0"` |
| `gemini-cli` | pinned via `GEMINI_CLI_VERSION = "0.46.0"` |
| `kimi-code` | pinned via `KIMI_CODE_VERSION = "0.38.0"` |
| `pi` | two independent npm pins |
| `opencode` | |

Each entry is an `ACPProviderInfo` carrying its launch command, API-key env var, session
mode, and available models. Providers are installed by npm pin and launched through
`npx`.

There is also an **escape hatch**: `ACPAgent` accepts a free-form `acp_command` plus
`acp_server="custom"`, which lets you point at any ACP-speaking binary you supply
yourself. This is documented in
[the ACP agent guide](https://docs.openhands.dev/sdk/guides/agent-acp.md).

---

## 3. Limitations of that support

Three limitations matter for a personal Gemini/Antigravity subscription.

### 3.1 The `gemini-cli` provider requires a billed API key

The provider declares `api_key_env_var="GEMINI_API_KEY"`. Google retired consumer-tier
OAuth for the Gemini CLI on **2026-06-18**, so an individual account cannot use the
subscription login path — it needs an API key, which is billed separately from the
subscription. That is the "paying twice" problem.

### 3.2 A retired auth method outranks a working API key — bug #4629

`ACPAgent._select_auth_method()` in `openhands/sdk/agent/acp_agent.py` resolves
credentials in this order:

```
chat-gpt        (codex)          -> file-backed login
vertex-ai       (gemini-cli)     -> GOOGLE_APPLICATION_CREDENTIALS
oauth-personal  (gemini-cli)     -> ~/.gemini/oauth_creds.json    <-- line 373
api-key         (codex)
<env-var map>   (GEMINI_API_KEY) -> line 381-384, the fallback
```

The docstring is explicit that file-backed logins are checked first *by design*, with
API keys as the fallback. The problem: `oauth-personal` is the **retired** method, yet a
stale `~/.gemini/oauth_creds.json` on the host still wins over a perfectly good
`GEMINI_API_KEY`. The failure is silent and confusing — you have a valid key set and the
CLI still tries the dead login path.

Tracked as [OpenHands/software-agent-sdk#4629](https://github.com/OpenHands/software-agent-sdk/issues/4629)
— *"[Bug]: Retired gemini-cli OAuth outranks a working API key, and the ACP Gemini pin is
badly stale."* Filed **2026-08-25**, labelled `bug`, `acp`, `security`,
`priority:medium`, `release-note-required`, and `ready-for-dev`. **Still open as of
2026-10-19**, with an automation nudge on **2026-09-29** after 34 days of no activity.

A fix was written: [PR #4646](https://github.com/OpenHands/software-agent-sdk/pull/4646)
(*"fix(acp): prefer GEMINI_API_KEY over leftover oauth-personal"*, +86/-6 across 2 files)
by the original reporter. It was **closed unmerged on 2026-09-15** with the comment:

> "Closing to keep the review queue clean — this has been open a while without traction.
> Happy to reopen or resubmit a fresh version if it would still be useful."

So the fix exists, is small, and is sitting on the floor for want of review.

### 3.3 The `gemini-cli` pin is stale — same issue

`GEMINI_CLI_VERSION = "0.46.0"`. The pin has not tracked upstream. This is the second
half of #4629. A stale pin compounds the auth problem, because the auth-method
negotiation is exactly the surface that changed.

### 3.4 The provider mechanism assumes npm — issue #4823, closed

Adding a *new* provider is not just a registry entry. The npm assumption is load-bearing
in five places (`default_command`, `_prefer_pinned_binary()`, the Dockerfile install
arms, `_REGISTRY_ACP_PACKAGES` pin-parity, and the TypeScript
`clients/typescript/.../acp-providers.json` mirror). `ACPInstallSpec` documents itself as
*"Everything needed to install and launch one provider's ACP CLI **via npm**"*, with
`packages` *"One or more npm packages to pin and install. **Never empty**."*

[Issue #4823](https://github.com/OpenHands/software-agent-sdk/issues/4823) proposed
`install_method` to unblock non-npm providers. It was **closed as a watch item on
2026-09-04** — *"this mechanism now has no scheduled consumer."*

**Verified 2026-10-19: `install_method` is not present in `openhands-sdk` 1.49.6.** The
catalog is still npm-only. Any binary-distributed provider still needs bespoke work.

---

## 4. The proper solution: Antigravity's first-party ACP server

The blocker above is about the *Gemini CLI*. There is a better target.

Google ships a **first-party ACP server for Antigravity**, published to the official ACP
registry by Google LLC:

- Registry entry: [`agentclientprotocol/registry` → `antigravity-acp`](https://github.com/agentclientprotocol/registry/tree/main/antigravity-acp)
- Version verified: **1.4.1**
- License: proprietary (`https://antigravity.google/terms`)
- Distribution: prebuilt binaries for `darwin-aarch64`, `darwin-x86_64`, `linux-x86_64`,
  `linux-aarch64`, `windows-x86_64`, `windows-aarch64`

### 4.1 It supports the subscription login

This is the whole point, so I tested it directly rather than trusting the registry
metadata (which does not declare auth methods — they are negotiated at `initialize`).
The server advertises four:

| Auth method id | Name |
|---|---|
| `oauth-personal` | Log in with Google |
| `oauth-business` | Log in with Gemini Enterprise |
| `gemini-api-key` | Gemini API key |
| `agent-platform` | Gemini Enterprise Agent Platform (formerly Vertex AI) |

`oauth-personal` is the personal subscription path. It completes an interactive Google
OAuth challenge and then works. Raw response, 2026-10-19:

```json
{"jsonrpc":"2.0","id":1,"result":{
  "protocolVersion":1,
  "agentCapabilities":{"loadSession":true,
    "promptCapabilities":{"image":true,"audio":true,"embeddedContext":true},
    "mcpCapabilities":{"http":true,"sse":true},
    "sessionCapabilities":{"list":{},"resume":{}},
    "auth":{"logout":{}}},
  "authMethods":[
    {"id":"oauth-personal","name":"Log in with Google", ...},
    {"id":"oauth-business","name":"Log in with Gemini Enterprise", ...},
    {"id":"gemini-api-key","name":"Gemini API key", ...},
    {"id":"agent-platform","name":"Gemini Enterprise Agent Platform", ...}],
  "agentInfo":{"name":"antigravity-acp","title":"Google Antigravity","version":"1.4.1"}}}
```

The server also exposes more than the auth fix needs: `loadSession`, session `list` and
`resume`, MCP over http/sse, image/audio/embedded-context prompts, and a `tier` +
`systemPrompt.append` extension under `_meta.antigravity`.

### 4.2 OpenHands can drive it today

This is the most useful finding in this document: **no SDK change is required to use it
now.** The `acp_command` + `acp_server="custom"` escape hatch already accepts it.

Verified 2026-10-19 — this ran end-to-end on a personal subscription:

```python
from openhands.sdk import Conversation
from openhands.sdk.agent.acp_agent import ACPAgent

agent = ACPAgent(
    acp_command=["/path/to/agy_acp_server.par"],
    acp_server="custom",
)
conversation = Conversation(agent=agent, workspace="/path/to/workspace")
conversation.send_message("Create a file named oh_acp_proof.txt containing OH_ACP_WORKS.")
conversation.run()
```

Result: the file was created with the correct contents, tool calls streamed through
`session/update` (`kind=execute`, `kind=edit`), permissions were auto-approved by the SDK
(`ACP auto-approving permission: ... (option: allow_always)`), and the run finished with
`stopReason: end_turn` under model `gemini-3.8-flash-high`. No API key, no billing.

So the working answer *today* is the escape hatch; the issue is that it is undiscoverable
and unsupported rather than that it is impossible.

### 4.3 One rough edge observed

During verification, `run_command`-style tool calls executed correctly, but two
`create_file`-style (`kind=edit`) tool calls were reported by the server as
*"Permission prompt ... was allowed but no execution step arrived; closing as failed
(dropped step)"* and surfaced in OpenHands as *"Tool call was approved but never
executed."* The file was still written, so the run succeeded — but this suggests some
friction between the SDK's auto-approval path and this server's edit-tool step lifecycle.
Worth reproducing before relying on edit-heavy workloads. Not yet filed as an issue.

---

## 5. What is blocking the proper solution

Pulling it together, in rough order of tractability:

| # | Blocker | Status | Link |
|---|---|---|---|
| 1 | Auth precedence: retired `oauth-personal` outranks `GEMINI_API_KEY` | Fix written, **closed unmerged** 2026-09-15 | [#4629](https://github.com/OpenHands/software-agent-sdk/issues/4629), [PR #4646](https://github.com/OpenHands/software-agent-sdk/pull/4646) |
| 2 | `gemini-cli` pin stale at `0.46.0` | Open, part of #4629 | [#4629](https://github.com/OpenHands/software-agent-sdk/issues/4629) |
| 3 | Add Antigravity as a first-class ACP provider | Open, **reopened and rescoped**, `ready-for-dev`, unscheduled | [#4624](https://github.com/OpenHands/software-agent-sdk/issues/4624) |
| 4 | Registry cannot express non-npm (binary) providers | **Closed as watch item** 2026-09-04; not in SDK 1.49.6 | [#4823](https://github.com/OpenHands/software-agent-sdk/issues/4823) |
| 5 | Artifact size / image variant | Cited as a gating reason | see below |

### 5.1 Issue #4624 — the Antigravity provider

*"[Feature]: Add Antigravity CLI as a new, additive ACP provider (alongside gemini-cli)"*,
filed **2026-08-24**. It was closed once on the premise that no trustworthy ACP server
existed for `agy`, then **reopened and rescoped** after that premise was corrected — the
first-party server had been in the ACP registry five days before the close. It carries
`enhancement`, `acp`, `release-note-required`, `ready-for-dev`, and is **unscheduled**;
the 2026-09-04 notice reads *"Neither is justified without demand."*

That last clause is the actionable part: this is a demand problem, not a technical one.

### 5.2 The artifact-size argument

The 2026-09-04 rationale cites the artifact at **650.4 MiB** at registry v1.1.1,
unpacking to **~1.9 GiB**, and concludes it needs a dedicated image variant. That is a
real cost for a Docker-deployed agent-server.

**Measured 2026-10-19 at registry v1.4.1** (`darwin-arm64`), the numbers are materially
smaller:

| Measure | Value |
|---|---|
| Download (zip) | 107.5 MiB |
| Unpacked: `agy_acp_server.par` | 279 MiB |
| Unpacked: `localharness_external` | 115 MiB |
| Total unpacked | ~394 MiB |

So the download is ~6x smaller than the figure cited, and unpacked is roughly a fifth.
It is not free, but it is in the same order as other prebuilt toolchains, and the
download is comfortably smaller than a browser or a CUDA runtime.

**Caveat, stated plainly:** I measured one platform at one version and did not reproduce
the 650 MiB figure, which may have been a different platform, a different version, or a
measurement of the whole install directory rather than the artifact. The discrepancy is
worth confirming in #4624 rather than treating either number as settled. If ~394 MiB
holds across platforms, the size objection is much weaker than it reads.

### 5.3 The npm assumption

Even with size settled, #4823's closure means adding a binary-distributed provider needs
the npm assumption unpicked in five places, or the provider has to be special-cased. That
is the real engineering cost behind #4624 — not the download.

---

## 6. How to help

If you want the proper integration:

1. **Say so on [#4624](https://github.com/OpenHands/software-agent-sdk/issues/4624).**
   The close rationale was explicitly "without demand." A comment describing your
   subscription-backed use case is the single highest-leverage action.
2. **Ask for [#4646](https://github.com/OpenHands/software-agent-sdk/pull/4646) to be
   reopened or resubmitted.** It is +86/-6, already written, and fixes a real bug on the
   deployed path. It closed for lack of review traction, not for a technical objection.
3. **Correct or confirm the size figures in #4624** with a per-platform measurement.
   If ~394 MiB is representative, say so; if 650 MiB is, say that.
4. **Meanwhile, use the escape hatch** (§4.2) or this repository's
   [`oh-gemini-tool`](../README.md). Neither requires an SDK change.

---

## 7. Verification log

Everything version-sensitive in this document was checked on the date shown.

| Date | Check | Result |
|---|---|---|
| 2026-06-18 | Google retires consumer-tier OAuth for Gemini CLI | individual accounts need a billed API key |
| 2026-08-24 | #4624 filed (Antigravity as ACP provider) | later closed, then reopened and rescoped |
| 2026-08-25 | #4629 filed (auth precedence + stale pin) | open, `ready-for-dev` |
| 2026-08-26 | PR #4646 opened | fix for #4629 |
| 2026-09-02 | #4823 filed (`install_method`) | — |
| 2026-09-04 | #4823 closed as watch item; #4624 notice | "no scheduled consumer"; "without demand" |
| 2026-09-15 | PR #4646 closed unmerged | "open a while without traction" |
| 2026-09-29 | Automation nudge on #4629 | 34 days inactive |
| 2026-10-19 | SDK 1.49.6 provider list | 6 npm providers; `install_method` absent |
| 2026-10-19 | SDK 1.49.6 pins | `gemini-cli` = `0.46.0` |
| 2026-10-19 | ACP registry `antigravity-acp` | v1.4.1, Google LLC, 6 platforms |
| 2026-10-19 | Artifact sizes (darwin-arm64, v1.4.1) | 107.5 MiB zip, ~394 MiB unpacked |
| 2026-10-19 | Server `initialize` auth methods | includes `oauth-personal` |
| 2026-10-19 | End-to-end on personal subscription | file created, `gemini-3.8-flash-high` |
| 2026-10-19 | OpenHands driving it via `acp_command` | worked, no SDK change |
