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

> **This fix is not the answer to the Antigravity problem (§5.1).** It is a *different*
> issue in the same area, and it points the opposite way: it makes a working API key
> outrank `oauth-personal`, which is right for `gemini-cli` (whose consumer login is
> dead) but would move a subscription-backed Antigravity session onto **billed** API
> usage. See §5.4.

### 3.3 The `gemini-cli` pin is stale — same issue

`GEMINI_CLI_VERSION = "0.46.0"`. The pin has not tracked upstream. This is the second
half of #4629. A stale pin compounds the auth problem, because the auth-method
negotiation is exactly the surface that changed.

Note that PR #4646 deliberately left this half undone — its own description says the
bump "is a separate change and was left as a follow-up." So even if that PR were revived
and merged, #4629 would not be fully closed.

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

Note the scope: this blocks *shipping* a provider, not *running* one. The `acp_command`
escape hatch bypasses all five sites — see §4.4.

---

## 4. The proper solution: Antigravity's first-party ACP server

The blocker above is about the *Gemini CLI*. There is a better target.

Google ships a **first-party ACP server for Antigravity**, published to the official ACP
registry by Google LLC:

- Registry entry: [`agentclientprotocol/registry` → `antigravity-acp`](https://github.com/agentclientprotocol/registry/tree/main/antigravity-acp)
- Version verified: **1.4.1**
- License: **proprietary, no source available** — see §4.0
- Distribution: prebuilt binaries for `darwin-aarch64`, `darwin-x86_64`, `linux-x86_64`,
  `linux-aarch64`, `windows-x86_64`, `windows-aarch64`

### 4.0 No source, and a proprietary license

**There is no source release.** The registry entry declares `"license": "proprietary"`
and points at `https://antigravity.google/terms`. The artifact itself confirms it — it
ships as two stripped native executables and nothing else:

| File | Size | Type |
|---|---|---|
| `agy_acp_server.par` | 279 MiB | Mach-O 64-bit executable (arm64) |
| `localharness_external` | 115 MiB | Mach-O 64-bit executable (arm64) |

`.par` is a filename only — despite the extension it is not a Python archive or a PEX;
it is a raw Mach-O binary. There is no `LICENSE`, `NOTICE`, or source tree inside the
zip, and no public repository exists. (The Apache-2.0 and MIT strings visible in `strings`
output are from vendored third-party libraries, not from the server itself.)

This is a practical difference from the other ACP providers: `gemini-cli`,
`claude-code`, `codex` and the rest are npm packages whose source is on GitHub. A
proprietary binary can be *consumed*, but it cannot be read, patched, vendored, or
audited.

It is also a difference that matters if `antigravity-acp` ever became a *first-class
built-in provider*: the agent-server image would download Google's proprietary binary
and ship it inside an OpenHands image. That is redistribution of a proprietary artifact
rather than an npm install, which raises a licensing question this document does not
answer. It is a further reason the provider is not simply a registry entry, and it
belongs in the discussion on #4624.

Two related gaps, stated without interpretation:

- The registry's `website` field points at
  `https://antigravity.google/docs/ide/extensions`, which documents IDE extensions and
  authentication but not the ACP server, its intended clients, or its supported use.
- The governing terms are at `https://antigravity.google/terms` and are Google's to
  change. **They are not reproduced or interpreted here.** Read them yourself, at the
  version in force when you read them, and decide whether your intended use is permitted.

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

### 4.4 The escape hatch is not first-class support

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

Concretely, first-class means the provider key resolves through
`ACP_INSTALL_CATALOG` → `render_docker_install_plan()` → the `acp-providers` Dockerfile
stage, which currently installs by `npm install --global $PACKAGES` and wraps each
`binary_name` under `/opt/acp-wrappers`. There is no branch in that stage for "download a
platform binary and unpack it." That is the gap.

So the two things this document describes are genuinely different:

- **§4.2 (the escape hatch)** — how *you* can use Antigravity today, on your own machine,
  with your own credentials, with no upstream change.
- **§5 (first-class support)** — how OpenHands would ship Antigravity to everyone,
  including Cloud. This is what #4624 tracks, and it is gated.

Documenting the escape hatch is not a substitute for the second. It is a workaround that
happens to work, and it carries none of the guarantees above.

---

## 5. What is blocking first-class support

### 5.0 The actual gate: a distribution OpenHands can consume

The blocker is not "the code assumes npm" in the abstract. It is a specific, written
gating criterion. [OpenHands/enterprise#235](https://github.com/OpenHands/enterprise/issues/235)
(*"Support Antigravity CLI (agy) ACP Provider and Update Gemini Branding"*) carries this
notice, added **2026-09-04**:

> **On hold — not planned.**
>
> **Gate: a distribution we can consume — an npm or otherwise thin install path, or an
> artifact small enough to fetch on demand.** Today it is a 650.4 MiB download unpacking
> to ~1.9 GiB, shipped as a platform binary rather than npm.

That is the cleanest statement of the blocker anywhere, and it is a disjunction — **any
one** of three things unblocks it:

1. an npm (or otherwise thin) install path,
2. an artifact small enough to fetch on demand, or
3. the npm assumption being lifted so a platform binary can be installed deliberately.

So "npm" is shorthand. The real requirement is *a distribution the agent-server image can
consume*, and size is an equally load-bearing half of it. §5.2 is therefore not a side
note — it speaks directly to criterion 2.

The same issue records two things worth knowing:

- **Antigravity would not appear in Cloud even once registered upstream.**
  OpenHands/enterprise#315 gives Cloud an explicit provider allowlist, so enabling a
  harness there is a separate, deliberate decision. Registering the provider in the SDK is
  necessary but not sufficient for Cloud availability.
- **The "Gemini CLI was sunset" premise is wrong.** `@google/gemini-cli` is at 0.58.0
  (published 2026-09-01), not deprecated on npm, and still supports `--acp`. Only the
  *consumer* auth tiers stopped. No deployed OpenHands path was affected, because Cloud
  authenticates via `vertex-ai`. The "Update Gemini Branding" half of that issue is marked
  for dropping rather than implementing.

That last point is a useful corrective to a lot of the surrounding discussion: the
Gemini CLI was not sunset, and the provider is not going away. The consumer *login* is what
died — which is precisely the case §5.4 is about.

**Upstream scope is additive.** #4624 adds Antigravity *alongside* `gemini-cli`; the
`gemini-cli` key is never removed or renamed.

Pulling the rest together, in rough order of tractability:

| # | Blocker | Status | Link |
|---|---|---|---|
| 1 | Add Antigravity as a first-class ACP provider | Open, **reopened and rescoped**, `ready-for-dev`, unscheduled | [#4624](https://github.com/OpenHands/software-agent-sdk/issues/4624) |
| 2 | Registry cannot express non-npm (binary) providers | **Closed as watch item** 2026-09-04; not in SDK 1.49.6 | [#4823](https://github.com/OpenHands/software-agent-sdk/issues/4823) |
| 3 | Artifact size / image variant | Cited as a gating reason; figures appear stale | see §5.2 |
| 4 | Proprietary binary — no source; redistribution question for an image | **Not filed** — see §4.0 | — |
| 5 | Auth selection cannot tell `gemini-cli` and `antigravity-acp` apart | **Not filed** — see §5.4 | — |
| 6 | `gemini-cli` auth precedence + stale pin | Fix written, **closed unmerged** 2026-09-15; pin still undone | [#4629](https://github.com/OpenHands/software-agent-sdk/issues/4629), [PR #4646](https://github.com/OpenHands/software-agent-sdk/pull/4646) |

Items 1–5 gate the Antigravity path. Item 6 affects `gemini-cli` — and, as §5.4 explains,
fixing it the obvious way would work *against* item 1's goal.

### 5.1 Issue #4624 — the Antigravity provider

*"[Feature]: Add Antigravity CLI as a new, additive ACP provider (alongside gemini-cli)"*,
filed **2026-08-24**. It was closed once on the premise that no trustworthy ACP server
existed for `agy`, then **reopened and rescoped** after that premise was corrected — the
first-party server had been in the ACP registry five days before the close. It carries
`enhancement`, `acp`, `release-note-required`, `ready-for-dev`, and is **unscheduled**;
the 2026-09-04 notice reads *"Neither is justified without demand."*

That last clause is the actionable part: this is a demand problem, not a technical one.

One thing #4624 does not yet cover: adding the provider surfaces an auth-selection
collision, because `antigravity-acp` and `gemini-cli` advertise the same `oauth-personal`
method id with opposite meanings. See §5.4.

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

### 5.4 Two servers, one auth-method id, opposite meanings

This is a design gap that #4624 will run into, and it is not yet filed anywhere.

Both servers advertise an auth method with the **same id, `oauth-personal`** — but with
opposite status:

| Server | `oauth-personal` | Correct precedence |
|---|---|---|
| `gemini-cli` | **retired** for consumers on 2026-06-18 | `GEMINI_API_KEY` should win |
| `antigravity-acp` | **works**, and is the point of #4624 | `oauth-personal` should win |

`_select_auth_method()` cannot distinguish them. It takes only the advertised method list
and the environment, and returns a method id from a flat global ranking — it never sees
which provider it is selecting for. The caller does have the provider available
(`detect_acp_provider_by_agent_name(agent_name)` is called a few lines later at the
`gemini-api-key` branch), so the information exists; it just is not threaded into the
ranking.

**Measured 2026-10-19** against the method list the Antigravity server actually returns:

```
~/.gemini/oauth_creds.json exists: True

=== ANTIGRAVITY ACP server ===
  no key   main=oauth-personal   if-#4646=oauth-personal
  key set  main=oauth-personal   if-#4646=gemini-api-key     <-- CHANGES
```

So on a host where `GEMINI_API_KEY` is set, merging #4646 as written would flip an
Antigravity session from the subscription (`oauth-personal`) to **billed** API usage. For
a personal subscriber, that is the exact outcome this document exists to avoid.

This is not an argument that #4646 is wrong. In a server image there is no
`oauth_creds.json`, so the API-key path is the only one available and the fix is correct
there. The point is narrower and worth making in #4624: **a blanket global ranking is the
wrong shape once a second Google provider exists.** The ranking should be provider-aware
— prefer the API key for `gemini-cli`, prefer `oauth-personal` for `antigravity-acp`.

If Antigravity is added as a built-in provider without addressing this, subscription users
with a `GEMINI_API_KEY` in their environment will silently land on billed usage, and the
symptom will look like a mystery charge rather than an auth-precedence bug.

---

## 6. How to help

If you want the proper integration:

1. **Say so on [#4624](https://github.com/OpenHands/software-agent-sdk/issues/4624).**
   The close rationale was explicitly "without demand." A comment describing your
   subscription-backed use case is the single highest-leverage action.
2. **Attack the distribution gate directly (enterprise#235, §5.0).** The gate is a
   disjunction, so the cheapest win is the one you can actually evidence: a per-platform
   size measurement. If ~394 MiB unpacked holds, criterion 2 ("small enough to fetch on
   demand") is much closer to satisfied than the 650 MiB / ~1.9 GiB figures suggest. This
   is concrete, checkable, and does not require anyone to design anything.
3. **Raise the auth-precedence collision (§5.4).** Ask that the ranking be made
   provider-aware rather than globally ordered, so a subscription-backed Antigravity
   session does not get silently moved onto billed API usage once `GEMINI_API_KEY` is in
   the environment. This is unfiled, and it directly affects the personal-account case.
4. **Meanwhile, use the escape hatch** (§4.2) or this repository's
   [`oh-gemini-tool`](../README.md). Neither requires an SDK change — but note §4.4: this
   is a workaround, not first-class support, and it is not a substitute for items 1–3.

> **On PR [#4646](https://github.com/OpenHands/software-agent-sdk/pull/4646):** it is a
> legitimate fix for `gemini-cli` on the deployed path, and it closed for lack of review
> rather than on a technical objection. But it is **not** the answer to #4624, and for a
> personal subscriber it currently points the wrong way — it would prefer a billed API
> key over a working subscription login. Support it only together with the provider-aware
> ranking in item 2 above, not on its own.

---

## 7. Verification log

Everything version-sensitive in this document was checked on the date shown.

| Date | Check | Result |
|---|---|---|
| 2026-06-18 | Google retires consumer-tier OAuth for Gemini CLI | individual accounts need a billed API key |
| 2026-08-24 | #4624 filed (Antigravity as ACP provider) | later closed, then reopened and rescoped |
| 2026-08-25 | #4629 filed (auth precedence + stale pin) | open, `ready-for-dev` |
| 2026-08-26 | PR #4646 opened | fix for the `gemini-cli` half of #4629 |
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
| 2026-10-19 | `_select_auth_method` against Antigravity's method list | with `GEMINI_API_KEY` set, #4646's ranking picks `gemini-api-key` over `oauth-personal` (§5.4) |
| 2026-10-19 | Main branch re-checked for #4629 | bug still live at `acp_agent.py:386`; fix branch deleted; no replacement PR |
| 2026-10-19 | Dockerfile `acp-providers` stage on main | installs via `npm install --global`; no branch for platform binaries |
| 2026-10-19 | `install_method` on main | absent — #4823's proposal never landed |
| 2026-10-19 | enterprise#235 gate notice | "npm or otherwise thin install path, or an artifact small enough to fetch on demand" |
| 2026-10-19 | Artifact contents | two Mach-O binaries; no source, `LICENSE`, or `NOTICE` |
| 2026-10-19 | Registry license field | `proprietary` |
| 2026-10-19 | Antigravity terms URL | `https://antigravity.google/terms` (not reproduced or interpreted here) |
