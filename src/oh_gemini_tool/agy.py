"""Thin, dependency-free client for the Antigravity CLI (``agy``).

This module knows how to drive ``agy`` in non-interactive ("print") mode and
parse its JSON envelope. It deliberately imports nothing outside the standard
library so the parsing and command-building logic can be tested without the
OpenHands SDK, and so it can be reused outside an agent context.

The CLI surface this targets::

    agy -p "<task>" --output-format json --dangerously-skip-permissions \
        [--model <flash_lite|flash|pro>] [--conversation <id>]

which prints a single JSON object::

    {"conversation_id": "...", "status": "SUCCESS", "response": "...",
     "duration_seconds": 4.0, "num_turns": 1, "usage": {...}}
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

DEFAULT_BINARY = "agy"
DEFAULT_TIMEOUT_SECONDS = 900

# Antigravity model tiers accepted by ``--model``.
MODEL_TIERS: tuple[str, ...] = ("flash_lite", "flash", "pro")


@dataclass(frozen=True)
class AgyResult:
    """Outcome of one ``agy`` invocation.

    ``ok`` is False for every failure mode (missing binary, non-zero exit,
    timeout, unparseable output, or an error field in the envelope) so callers
    can branch once. ``error`` carries a human-readable reason when ``ok`` is
    False.
    """

    ok: bool
    response: str = ""
    status: str = ""
    conversation_id: str = ""
    num_turns: int = 0
    duration_seconds: float = 0.0
    usage: dict[str, Any] = field(default_factory=dict)
    error: str = ""


class AgyNotFoundError(RuntimeError):
    """Raised when the ``agy`` binary cannot be located on PATH."""


def build_command(
    task: str,
    *,
    binary: str = DEFAULT_BINARY,
    model: str | None = None,
    conversation_id: str | None = None,
    skip_permissions: bool = True,
) -> list[str]:
    """Build the argv for one headless ``agy`` run.

    ``conversation_id`` resumes an existing conversation. It is always passed
    explicitly: the CLI's ``-c``/``--continue`` flag resumes whichever
    conversation was most recently touched by *any* ``agy`` process, which would
    leak context between unrelated delegations.
    """
    cmd = [binary, "-p", task, "--output-format", "json"]
    if skip_permissions:
        cmd.append("--dangerously-skip-permissions")
    if model:
        cmd += ["--model", model]
    if conversation_id:
        cmd += ["--conversation", conversation_id]
    return cmd


def parse_result(stdout: str) -> AgyResult:
    """Parse the JSON envelope printed by ``agy``.

    Returns an ``ok=False`` result rather than raising, so a malformed envelope
    from the CLI surfaces as a tool error instead of a crash.
    """
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return AgyResult(ok=False, error=f"Unparseable agy output: {stdout.strip()[:2000]}")

    if not isinstance(payload, dict):
        return AgyResult(ok=False, error=f"Unexpected agy output: {stdout.strip()[:2000]}")

    if payload.get("error"):
        return AgyResult(ok=False, error=str(payload["error"]))

    return AgyResult(
        ok=True,
        response=payload.get("response", ""),
        status=payload.get("status", ""),
        conversation_id=payload.get("conversation_id", "") or "",
        num_turns=int(payload.get("num_turns", 0) or 0),
        duration_seconds=float(payload.get("duration_seconds", 0.0) or 0.0),
        usage=payload.get("usage", {}) or {},
    )


def run_agy(
    task: str,
    *,
    working_dir: str,
    binary: str = DEFAULT_BINARY,
    model: str | None = None,
    conversation_id: str | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    skip_permissions: bool = True,
) -> AgyResult:
    """Run one headless ``agy`` task and return its result.

    Raises:
        AgyNotFoundError: if ``binary`` is not on PATH.
    """
    resolved = shutil.which(binary)
    if resolved is None:
        raise AgyNotFoundError(
            f"'{binary}' not found on PATH. Install Google Antigravity, or pass "
            f"the full path to the binary."
        )

    cmd = build_command(
        task,
        binary=resolved,
        model=model,
        conversation_id=conversation_id,
        skip_permissions=skip_permissions,
    )

    try:
        proc = subprocess.run(
            cmd,
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return AgyResult(ok=False, error=f"agy exceeded the {timeout_seconds}s timeout.")
    except OSError as exc:  # pragma: no cover - environment dependent
        return AgyResult(ok=False, error=f"Failed to run agy: {exc}")

    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "non-zero exit").strip()
        return AgyResult(
            ok=False,
            error=f"agy exited with code {proc.returncode}: {detail[:2000]}",
        )

    return parse_result(proc.stdout)


def format_usage(usage: dict[str, Any] | None) -> str:
    """Render token usage compactly for an observation summary."""
    if not usage:
        return "?"
    total = usage.get("total_tokens")
    return str(total) if total is not None else "?"


def argv_for_display(cmd: Sequence[str]) -> str:
    """Render an argv for error messages without leaking the full task text."""
    parts = list(cmd)
    if "-p" in parts:
        parts[parts.index("-p") + 1] = "<task>"
    return " ".join(parts)
