"""Shared fixtures.

Rather than mocking ``subprocess``, the fixtures here drop a small executable
"fake agy" on ``PATH``. That keeps the tests exercising the real code path —
``shutil.which`` lookup, argv construction, process execution, and JSON parsing —
while staying deterministic and offline.
"""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

import pytest

# A stand-in for the real CLI. Behaviour is selected with FAKE_AGY_MODE:
#   ok (default)  print a well-formed envelope
#   error_json    print an envelope containing an "error" field
#   bad_json      print something that is not JSON
#   nonzero       exit non-zero with a message on stderr
#   sleep         sleep past any sane timeout, to exercise the timeout path
#
# When --conversation is present it reports num_turns=2 and echoes the id, which
# lets tests assert that session threading actually reached the CLI.
_FAKE_AGY = """\
#!{python}
import json, os, sys, time

mode = os.environ.get("FAKE_AGY_MODE", "ok")
argv = sys.argv[1:]

if mode == "sleep":
    time.sleep(60)

if mode == "nonzero":
    sys.stderr.write("fake agy: boom\\n")
    sys.exit(3)

if mode == "bad_json":
    print("not json at all")
    sys.exit(0)

if mode == "error_json":
    print(json.dumps({{"error": "ANTIGRAVITY_LS_ADDRESS is not set"}}))
    sys.exit(0)

resumed = "--conversation" in argv
cid = argv[argv.index("--conversation") + 1] if resumed else "conv-new"
model = argv[argv.index("--model") + 1] if "--model" in argv else None
task = argv[argv.index("-p") + 1] if "-p" in argv else ""

print(json.dumps({{
    "conversation_id": cid,
    "status": "SUCCESS",
    "response": ("resumed: " if resumed else "fresh: ") + task,
    "duration_seconds": 1.5,
    "num_turns": 2 if resumed else 1,
    "usage": {{"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}},
    "model": model,
}}))
"""


@pytest.fixture
def fake_agy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """Put a fake ``agy`` on PATH and return the binary name."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    script = bindir / "agy"
    script.write_text(_FAKE_AGY.format(python=sys.executable))
    script.chmod(script.stat().st_mode | stat.S_IEXEC)

    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.delenv("FAKE_AGY_MODE", raising=False)
    return "agy"


@pytest.fixture
def envelope() -> dict:
    """A representative successful ``agy`` JSON envelope."""
    return {
        "conversation_id": "0a03e81e-55d9-4cc5-ac59-dfac1a9371b4",
        "status": "SUCCESS",
        "response": "DONE\n",
        "duration_seconds": 4.065896,
        "num_turns": 1,
        "usage": {"input_tokens": 11768, "output_tokens": 17, "total_tokens": 11785},
    }


@pytest.fixture
def envelope_json(envelope: dict) -> str:
    return json.dumps(envelope)


@pytest.fixture
def fake_conv_state(tmp_path: Path):
    """Minimal stand-in for the SDK ConversationState used by ``Tool.create``."""

    class _Workspace:
        working_dir = str(tmp_path)

    class _ConvState:
        workspace = _Workspace()

    return _ConvState()
