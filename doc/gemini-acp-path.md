# Using Gemini with OpenHands: the ACP path

`oh-gemini-tool` — the tool this repository ships — drives the Antigravity CLI (`agy`)
as a headless subprocess. It works, and it is a reasonable demonstration of delegating
work to another agent from inside OpenHands. But it is **not the best integration**, and
this document explains what is.

**ACP is the better approach**, and OpenHands already supports it well. For most Gemini
users the question is not *whether* ACP works — it does — but *which account type you
have*, because that determines whether you use a supported built-in provider or a
documented escape hatch.

This document covers, in order: what ACP is and how OpenHands supports other vendors'
harnesses today; subscription-based auth over ACP; how to use Gemini with an **Enterprise**
account; how to use it with a **personal** account; why first-class support for personal
Gemini subscriptions does not exist yet; and a factual account of what the OpenHands ACP
integration does and does not do.

**Last verified: 2026-10-19** against `openhands-sdk` 1.49.6 and Antigravity ACP server
1.4.1. Version-sensitive claims are dated inline. Re-check them before relying on them.

---

## 1. What ACP is, and how OpenHands supports other harnesses today

### 1.1 The protocol

The [Agent Client Protocol](https://agentclientprotocol.com/) (ACP) is a JSON-RPC
protocol between an **agent host** (OpenHands) and an **agent server** (a coding harness
such as Claude Code, Codex, or Gemini CLI). The host launches the server as a local
subprocess and they talk over stdio:

1. The host calls `initialize`; the server replies with its capabilities, the **auth
   methods** it supports, and its model list.
2. The host calls `authenticate` with the id of an auth method it can satisfy.
3. The host creates a session and sends prompts; the server streams back typed
   `session/update` notifications — tool calls, edits, messages — until the turn ends
   with a `stopReason`.

The important property is that **OpenHands remains the agent**. The server is a tool
provider under OpenHands' own loop, not a second opaque agent whose output you scrape.
That is the whole difference between an ACP integration and a subprocess wrapper:

| Capability | ACP integration | This tool (`agy -p`) |
|---|---|---|
| OpenHands as the primary agent | Yes — one agent loop | No — two loops, one opaque |
| Streaming of intermediate steps | Yes (`session/update`) | No — one final envelope |
| Tool calls visible to OpenHands | Yes (`session/update`, typed) | No — invisible |
| Mid-task questions / steering | Yes | No — one-shot per call |
| Permission gating | Yes — OpenHands decides, see §6.2 | No — `--dangerously-skip-permissions` |
| Session continuity | Yes — native session ids | Partial — resume by explicit id |
| Model / thinking-level switching | Yes — `session/set_model`, selectors | Limited — `--model` per call |

### 1.2 What ships today

As of `openhands-sdk` 1.49.6 (checked 2026-10-19),
`openhands.sdk.settings.acp_providers` ships **six** built-in providers:

| Provider key | Notes |
|---|---|
| `claude-code` | pinned via `CLAUDE_AGENT_ACP_VERSION = "0.63.0"` |
| `codex` | pinned via `CODEX_ACP_VERSION = "1.10.0"` |
| `gemini-cli` | pinned via `GEMINI_CLI_VERSION = "0.46.0"` |
| `kimi-code` | pinned via `KIMI_CODE_VERSION = "0.38.0"` |
| `pi` | two independent npm pins |
| `opencode` | |

Each entry is an `ACPProviderInfo` carrying its launch command, API-key env var, session
mode, and available models. Each is installed by an npm pin and launched through `npx`,
which is what makes them *first-class*: OpenHands supplies the binary, pins the version,
carries the branding, and covers it with tests.

There is also a documented **escape hatch**: `ACPAgent` accepts a free-form `acp_command`
plus `acp_server="custom"`, which points at any ACP-speaking binary you supply yourself.
See [the ACP agent guide](https://docs.openhands.dev/sdk/guides/agent-acp.md).

---

## 2. Subscriptions over ACP

A recurring reason people choose ACP over plain API access is **billing model**. Several
harnesses expose a *subscription* login — a consumer or team plan you already pay for —
and OpenHands can drive them through it:

| Provider | Subscription auth method | Where the credential lives |
|---|---|---|
| `codex` | `chat-gpt` | `$CODEX_HOME/auth.json` or `~/.codex/auth.json` |
| `claude-code` | file-backed login | the CLI's own config root |
| `gemini-cli` | `oauth-personal` | `~/.gemini/oauth_creds.json` |

Where this works, it means the OpenHands agent loop runs against your existing
subscription quota rather than a metered API key. Many people prefer that — it is one
bill instead of two, and it uses capacity they have already paid for. The SDK supports
the pattern directly: `_select_auth_method` deliberately prefers file-backed
subscription logins over API keys, so a subscription is used when one is available.

**This is the crux for Gemini.** The mechanism exists and is first-class in the SDK — but
Google **retired consumer-tier OAuth for the Gemini CLI on 2026-06-18**. The
`oauth-personal` method is still advertised by `gemini-cli`, but it no longer works for
individual accounts, so the only working path through that provider is a billed
`GEMINI_API_KEY`. That is why §3 (Enterprise) and §4 (personal) diverge.

---

## 3. Using Gemini with an Enterprise account

**Enterprise accounts work today through the supported, first-class path — no escape
hatch required.**

The `gemini-cli` provider supports service-account authentication via the `vertex-ai`
method, driven by `GOOGLE_APPLICATION_CREDENTIALS`:

```
vertex-ai       (gemini-cli)     -> GOOGLE_APPLICATION_CREDENTIALS
```

This is the deployable path, and the SDK prefers it over personal OAuth by design —
service-account credentials are not host-bound, so they work in a container or sandbox
where an interactive login cannot be performed. In a server image the interactive-login
files are absent anyway, so the service-account or API-key path is what runs.

Set the credential file, point `GOOGLE_APPLICATION_CREDENTIALS` at it, select the
`gemini-cli` provider, and the SDK completes the `vertex-ai` handshake automatically.

The Antigravity ACP server (§4) also advertises two enterprise methods, should you be
driving it directly:

| Auth method id | Name |
|---|---|
| `oauth-business` | Log in with Gemini Enterprise |
| `agent-platform` | Gemini Enterprise Agent Platform (formerly Vertex AI) |

---

## 4. Using Gemini with a personal account

There are two paths, and they are very different in effort and in billing.

### 4.1 The easy path: an API key

A personal account with a **billed `GEMINI_API_KEY`** works through the built-in
`gemini-cli` provider with no custom configuration. Set `GEMINI_API_KEY` in the
environment, select `gemini-cli`, and the SDK selects the `gemini-api-key` method.

This is straightforward. It is also **billed separately from any subscription you
already hold** — which is the reason people look for the second path.

### 4.2 The subscription path: custom ACP

Google ships a **first-party ACP server for Antigravity**, published to the official ACP
registry by Google LLC. It supports the personal subscription login, and OpenHands can
drive it today through the `acp_command` escape hatch. **No SDK change is required.**

This works — it was verified end-to-end on a personal subscription (§4.2, step 4) — but
it is manual: you obtain the binary, authenticate it, and point OpenHands at it yourself.

#### Step 1 — Get the server

Source the artifact from the official registry rather than a hardcoded URL, so you pick
up the current version:

- Registry metadata: <https://cdn.agentclientprotocol.com/registry/v1/latest/registry.json>
  (entry `antigravity-acp`)
- Registry repo: [`agentclientprotocol/registry` → `antigravity-acp`](https://github.com/agentclientprotocol/registry/tree/main/antigravity-acp)

Version verified here: **1.4.1**. Prebuilt binaries are published per platform:

| Platform | Archive |
|---|---|
| `darwin-aarch64` | `.../releases/macos/agy-acp-server-1.4.1-darwin-arm64.zip` |
| `darwin-x86_64` | `.../releases/macos/agy-acp-server-1.4.1-darwin-x86_64.zip` |
| `linux-x86_64` | `.../releases/linux/agy-acp-server-1.4.1-linux-x86_64.zip` |
| `linux-aarch64` | `.../releases/linux/agy-acp-server-1.4.1-linux-arm64.zip` |
| `windows-x86_64` | `.../releases/windows/agy-acp-server-1.4.1-windows-x86_64.zip` |
| `windows-aarch64` | `.../releases/windows/agy-acp-server-1.4.1-windows-arm64.zip` |

(prefix: `https://dl.google.com/agy-extensions/`). Unzip it and make the launcher
executable. On Linux the registry specifies an extra `--uid=` argument; on macOS and
Windows the launcher is run directly.

```bash
unzip agy-acp-server-1.4.1-darwin-arm64.zip -d agy-acp
chmod +x agy-acp/agy_acp_server.par
```

**The archive is self-contained — you do not need Antigravity installed.** It unpacks to
two files, and both are required: `agy_acp_server.par` (the server) and
`localharness_external` (the harness, which the server resolves as a sibling and will not
start without). Verified 2026-10-19: with `agy` absent from `PATH` and an empty `HOME`,
the server still completes `initialize` and advertises all four auth methods. The
harness binary contains the agent logic itself — the `agy-customizations` skills and the
model client — rather than shelling out to `agy`.

Note the size varies a lot by platform, and the figure that matters for a container is
linux-x86_64: see §5.3.

#### Step 2 — Authenticate

On first use with no credentials present, the server advertises `oauth-personal`
("Log in with Google") and completes an interactive Google OAuth challenge against your
personal account. Once done, the credential is reused on subsequent runs, and the SDK
selects `oauth-personal` automatically.

#### Step 3 — Point OpenHands at it

```python
from openhands.sdk import Conversation
from openhands.sdk.agent.acp_agent import ACPAgent

agent = ACPAgent(
    acp_command=["/path/to/agy-acp/agy_acp_server.par"],
    acp_server="custom",
)
conversation = Conversation(agent=agent, workspace="/path/to/workspace")
conversation.send_message("Create a file named oh_acp_proof.txt containing OH_ACP_WORKS.")
conversation.run()
```

`acp_server="custom"` is what tells the SDK to use your `acp_command` verbatim instead of
resolving a pinned built-in provider.

#### Step 4 — Verify it worked

A successful run shows tool calls streaming through `session/update` (`kind=execute`,
`kind=edit`), permissions auto-approved by the SDK
(`ACP auto-approving permission: ... (option: allow_always)`), and a `stopReason:
end_turn` under model `gemini-3.8-flash-high` — with no API key and no billing. The file
named in the prompt should exist in the workspace.

### 4.3 What the server advertises

The registry metadata does not declare auth methods — they are negotiated at
`initialize`. The server advertises four. Raw response, 2026-10-19:

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

Beyond the auth fix, the server exposes `loadSession`, session `list` and `resume`, MCP
over http/sse, image/audio/embedded-context prompts, and a `tier` + `systemPrompt.append`
extension under `_meta.antigravity`.

### 4.4 One rough edge observed

During verification, `run_command`-style tool calls executed correctly, but two
`create_file`-style (`kind=edit`) tool calls were reported by the server as
*"Permission prompt ... was allowed but no execution step arrived; closing as failed
(dropped step)"* and surfaced in OpenHands as *"Tool call was approved but never
executed."* The file was still written, so the run succeeded — but this suggests some
friction between the SDK's auto-approval path and this server's edit-tool step lifecycle.
Worth reproducing before relying on edit-heavy workloads. Not yet filed as an issue.

### 4.5 The escape hatch is not first-class support

This distinction matters and is easy to lose: **being able to run something does not make
it supported.**

| | `acp_command` + `acp_server="custom"` | First-class provider |
|---|---|---|
| Who supplies the binary | you, by hand | the agent-server image |
| Where it lives | wherever you put it | `/acp-node`, via the pinned install stage |
| Version management | yours | pinned in `ACP_INSTALL_CATALOG` |
| Secrets UI | none | provider entry in the frontend |
| Model list / branding | none | registry entry + chip icon |
| Usage analytics | unlabelled | grouped by provider |
| Cloud | not available | opt-in via a provider allowlist |
| Regression coverage | none | pin-parity + conformance tests |

§4.2 is how *you* can use Antigravity today, on your own machine, with your own
credentials, with no upstream change. §5 is how OpenHands would ship it to everyone,
including Cloud. Documenting the escape hatch is not a substitute for the second.

---

## 5. Why there is not yet first-class support for personal Gemini subscriptions

This section is deliberately technical. The blockers are engineering and packaging
constraints; the question of what any provider's terms permit is separate, and §6
addresses it.

Summary, in rough order of tractability:

| # | Blocker | Status | Link |
|---|---|---|---|
| 1 | Add Antigravity as a first-class ACP provider | Open, `ready-for-dev`, unscheduled | [#4624](https://github.com/OpenHands/software-agent-sdk/issues/4624) |
| 2 | Registry cannot express non-npm (binary) providers | **Closed as watch item** 2026-09-04; not in SDK 1.49.6 | [#4823](https://github.com/OpenHands/software-agent-sdk/issues/4823) |
| 3 | Artifact size / image variant | Measured all platforms; linux-x86_64 is 320.6 MiB down / 1012.8 MiB unpacked | see §5.3 |
| 4 | Proprietary binary — no source; distribution question for an image | **Not filed** — see §5.5 | — |
| 5 | Auth selection cannot tell `gemini-cli` and `antigravity-acp` apart | **Not filed** — see §5.4 | — |
| 6 | `gemini-cli` auth precedence + stale pin | Fix written, **closed unmerged** 2026-09-15; pin still undone | [#4629](https://github.com/OpenHands/software-agent-sdk/issues/4629), [PR #4646](https://github.com/OpenHands/software-agent-sdk/pull/4646) |

Items 1–5 gate the Antigravity path. Item 6 affects `gemini-cli` — and, as §5.4 explains,
fixing it the obvious way would work *against* item 1's goal.

### 5.1 The actual gate: a distribution OpenHands can consume

[OpenHands/enterprise#235](https://github.com/OpenHands/enterprise/issues/235) carries the
written criterion:

> an npm or otherwise thin install path, or an artifact small enough to fetch on demand

It is a disjunction, so the size measurement in §5.3 speaks directly to one of its arms
rather than being a side note. Two further points from that issue: Cloud needs a separate
provider allowlist even after upstream registration, and the "Gemini CLI was sunset"
premise is wrong — `@google/gemini-cli` is at 0.58.0 and not deprecated. Only the consumer
*login* stopped.

### 5.2 The provider mechanism assumes npm

`ACP_INSTALL_CATALOG` → `render_docker_install_plan()` → the `acp-providers` Dockerfile
stage installs by `npm install --global $PACKAGES` and wraps each `binary_name` under
`/opt/acp-wrappers`. There is no branch in that stage for "download a platform binary and
unpack it."

**Verified 2026-10-19: `install_method` is not present in `openhands-sdk` 1.49.6.** The
catalog is still npm-only. [#4823](https://github.com/OpenHands/software-agent-sdk/issues/4823)
proposed a general `install_method` and was closed as a watch item on 2026-09-04 —
*"this mechanism now has no scheduled consumer."*

Note the scope: this blocks *shipping* a provider, not *running* one. The `acp_command`
escape hatch bypasses all of it — see §4.5.

### 5.3 Artifact size

This section previously reported only the darwin-arm64 figure (107.5 MiB download,
~394 MiB unpacked) and concluded the cited numbers were stale. **That conclusion was
wrong, and the single-platform framing was misleading.** Measured across all six targets
at v1.4.1:

| Target | Download (zip) | Unpacked |
|---|---|---|
| `darwin-arm64` | 107.5 MiB | 382.7 MiB |
| `darwin-x86_64` | 112.9 MiB | — |
| **`linux-x86_64`** | **320.6 MiB** | **1012.8 MiB** |
| `linux-arm64` | 307.0 MiB | — |
| `windows-x86_64` | 123.6 MiB | — |
| `windows-arm64` | 126.4 MiB | — |

The platform that matters for a container image is **linux-x86_64**, and it is roughly
**3× the darwin-arm64 figure**. Each archive contains two files, and both are required:
the server resolves its harness as a sibling (`localharness_external`) and does not start
without it.

The figures cited in #4624 (650.4 MiB download, ~1.9 GiB unpacked, v1.1.1) are still
larger than anything measured here — but they are not the order-of-magnitude error the
darwin-only comparison suggested. For linux-x86_64 the real numbers are about half the
cited download and about half the cited unpacked size. The cited figures are also
unverifiable now: the v1.1.1 URL returns 404, so the older artifact is gone.

Whether ~320 MiB (or ~1013 MiB unpacked) is acceptable is the actual decision. It is
roughly the size of a browser or a CUDA runtime, and #4624's gate language contemplates
"an artifact small enough to fetch on demand" — so the measurement speaks to that arm of
the disjunction rather than settling it. A contributing factor: `localharness_external`
is 114.7 MiB stripped, but the equivalent installed `agy` binary is 177.9 MiB. If the
distributed harness is built without stripping, most of the unpacked size may be debug
symbols and symbol tables — which is consistent with #4624's own observation that a
`.par_data` section holds embedded Python alongside 283 MiB of debug symbols. Verifying
that, and whether a stripped build would shrink the artifact, is the cheapest next step.

### 5.4 Two servers, one auth-method id, opposite meanings

Both `gemini-cli` and `antigravity-acp` advertise `oauth-personal`, but for `gemini-cli`
it is retired and for `antigravity-acp` it works. `_select_auth_method` returns a method
id from a flat global ranking and never sees the provider, so it cannot tell them apart.

Measured against the method list the Antigravity server actually returns, with a
`GEMINI_API_KEY` present: [#4646](https://github.com/OpenHands/software-agent-sdk/pull/4646)'s
ranking picks `gemini-api-key` over `oauth-personal`, i.e. it would move a
subscription-backed session onto billed API usage. That is the outcome this document
exists to avoid.

This is not an argument that #4646 is wrong — in a server image there is no
`oauth_creds.json`, so the API-key path is correct there. The point is that the ranking
needs to be provider-aware once a second Google provider exists, and that this is worth
raising in #4624 before the provider lands.

Relatedly, `gemini-cli`'s pin is stale at `0.46.0`, and #4646 deliberately left the pin
bump undone, so even merged it would not fully close #4629.

### 5.5 The artifact is a closed binary

There is no source release. The registry declares `"license": "proprietary"`, and the
artifact confirms it — two stripped native executables and nothing else:

| File | Size | Type |
|---|---|---|
| `agy_acp_server.par` | 279 MiB | Mach-O 64-bit executable (arm64) |
| `localharness_external` | 115 MiB | Mach-O 64-bit executable (arm64) |

`.par` is a filename only — despite the extension it is not a Python archive or a PEX; it
is a raw Mach-O binary. There is no `LICENSE`, `NOTICE`, or source tree inside the zip,
and no public repository exists. (The Apache-2.0 and MIT strings visible in `strings`
output are from vendored third-party libraries, not from the server itself.)

This differs from the other ACP providers, which are npm packages with public source. A
proprietary binary can be *consumed*, but it cannot be read, patched, vendored, or
audited.

It also matters if `antigravity-acp` ever became a *first-class built-in provider*, and
the shape of that matters too — there are two, and they are not equivalent:

- **Baked at image build time.** This is what the mechanism does today. The
  `acp-providers` stage installs the npm payload into `/acp-node` and the result is
  `COPY`ed into the published base image, deliberately as a shared layer reused across
  builds. A binary provider added this way would **ship inside OpenHands' own image**.
- **Fetched on demand at runtime.** The artifact is downloaded when needed rather than
  baked in. This is the branch the gate language in §5.1 contemplates — *"an artifact
  small enough to fetch on demand"* — and it is a different shape: OpenHands would ship
  a URL and a fetch step, not the artifact.

For the escape hatch in §4.2, neither applies: you obtain the binary, and OpenHands
neither ships nor fetches it.

Which of these a given artifact's terms permit is a question this document does not
answer. The two branches put the artifact in different places, so it is worth naming
both rather than collapsing them.

Two related gaps, stated without interpretation:

- The registry's `website` field points at
  `https://antigravity.google/docs/ide/extensions`, which documents IDE extensions and
  authentication but not the ACP server, its intended clients, or its supported use.
- The governing terms are at `https://antigravity.google/terms` and are Google's to
  change. **They are not reproduced or interpreted here.**

---

## 6. Terms, and what the integration does

### 6.1 Read your own terms

Different providers express their terms differently — what is and is not permitted when
driving a harness programmatically, and how subscription capacity relates to API
consumption, varies by vendor and by plan tier. These terms have been changing rapidly,
and recently the direction has generally been toward **greater openness**: several
vendors now publish ACP servers explicitly for third-party clients to drive.

This document does not characterize any provider's terms, and it is not legal advice.
Terms are the vendor's to write and to change. **Read the terms that apply to your
account and your intended use**, at the version in force when you read them, and decide
whether your use is permitted. For Google specifically, see
<https://antigravity.google/terms>.

### 6.2 What the OpenHands ACP integration does and does not do

These are factual statements about the integration as implemented in `openhands-sdk`
1.49.6 (verified 2026-10-19). They are listed because they are technically unambiguous
and may help you interpret the agreement that applies to you.

**The OpenHands ACP integration described here DOES:**

- Launch the ACP server as a **local subprocess** on the machine running OpenHands, and
  communicate with it over stdio.
- Delegate the authentication handshake to the server: it sends `authenticate` with a
  method id and lets the server run its own login flow.
- Select an auth method by checking which credentials are **already present** — for
  example `~/.gemini/oauth_creds.json`, `GEMINI_API_KEY`, or
  `GOOGLE_APPLICATION_CREDENTIALS`.
- Use the credential the environment or disk provides; it does not create an account,
  purchase a plan, or provision a subscription.
- **Auto-approve** the server's tool permission requests (`request_permission` returns the
  first offered option) and decline elicitation requests, because a headless turn has no
  user to prompt.
- Stream the server's tool calls and updates into OpenHands events.

**The OpenHands ACP integration described here does NOT:**

- Call the model provider's API directly. In ACP mode all model traffic goes through the
  ACP server; OpenHands does not contact `googleapis.com` or equivalent itself.
- Perform the vendor's OAuth login itself. It asks the server to authenticate and the
  server runs that flow.
- Create, purchase, or manage subscriptions or billing of any kind.
- Multiplex one subscription across users or machines. It uses whatever credential is
  present in the environment it runs in.
- Act as the gatekeeper for what the delegated agent does on your machine. Because it
  auto-approves permission requests, the ACP server's own permission model governs the
  actions taken.
- Redistribute the ACP server binary. In the escape-hatch path you supply it. A packaged
  first-class provider would either bake it into the image or fetch it at runtime —
  see §5.5.

---

## 7. How to help

In rough order of tractability:

1. **Check whether a stripped harness shrinks the artifact.** §5.3 found the distributed
   harness is larger than the installed `agy` and the unpacked size is dominated by what
   looks like debug symbols. If a stripped build is materially smaller, that changes the
   size argument in #4624.
2. **Raise the auth-method collision (§5.4) in #4624** before a provider lands. It is not
   filed anywhere, and it is the kind of thing that is cheap now and expensive later.
3. **Comment on [#4624](https://github.com/OpenHands/software-agent-sdk/issues/4624)** if
   you want first-class support — it is `ready-for-dev` and unscheduled, so demand is the
   signal.
4. **Note the distribution question (§5.5)** if you are weighing whether the binary can
   ship inside an image.

---

## 8. Verification log

Everything version-sensitive in this document was checked on the date shown.

| Date | Check | Result |
|---|---|---|
| 2026-10-19 | `openhands-sdk` version | 1.49.6 |
| 2026-10-19 | Built-in ACP providers | six: `claude-code`, `codex`, `gemini-cli`, `kimi-code`, `pi`, `opencode` |
| 2026-10-19 | `gemini-cli` pin | `0.46.0` |
| 2026-10-19 | Google consumer OAuth retirement | 2026-06-18; `oauth-personal` advertised but non-functional for individuals |
| 2026-10-19 | Antigravity ACP server | registry v1.4.1; `oauth-personal` works on a personal subscription |
| 2026-10-19 | End-to-end via `acp_command` | file created, tool calls streamed, `end_turn`, model `gemini-3.8-flash-high` |
| 2026-10-19 | Main branch re-checked for #4629 | bug still live at `acp_agent.py:386`; fix branch deleted; no replacement PR |
| 2026-10-19 | Dockerfile `acp-providers` stage on main | installs via `npm install --global`; no branch for platform binaries |
| 2026-10-19 | `install_method` on main | absent — #4823's proposal never landed |
| 2026-10-19 | enterprise#235 gate notice | "npm or otherwise thin install path, or an artifact small enough to fetch on demand" |
| 2026-10-19 | Artifact contents | two Mach-O binaries; no source, `LICENSE`, or `NOTICE` |
| 2026-10-19 | Registry license field | `proprietary` |
| 2026-10-19 | Antigravity terms URL | `https://antigravity.google/terms` (not reproduced or interpreted here) |
| 2026-10-19 | All six platform archive sizes | darwin-arm64 107.5 MiB … linux-x86_64 320.6 MiB (largest); measured via `content-length` |
| 2026-10-19 | linux-x86_64 unpacked | 1012.8 MiB across two files |
| 2026-10-19 | v1.1.1 archive URL | 404 — the version #4624 cites is no longer downloadable |
| 2026-10-19 | Standalone operation | boots and answers `initialize` with `agy` absent from `PATH` and empty `HOME` |
| 2026-10-19 | Harness binary | `localharness_external`, 114.7 MiB stripped; installed `agy` is 177.9 MiB |
