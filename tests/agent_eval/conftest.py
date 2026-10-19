"""Fixtures for end-to-end agent evals.

These evals run a real LLM agent, equipped only with the ``gemini_delegate`` tool,
against natural-language instructions. They exist to catch a class of regression
the unit tests cannot: whether the model can translate plain instructions into
correct tool calls given the tool's description and schema.

They are non-deterministic, cost money, and require a working, authenticated
``agy`` (the delegation lands on the Antigravity account), so they are excluded
from the default ``pytest`` run (see the ``-m`` default in ``pyproject.toml``) and
are intended to be triggered manually.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

# The evals need the ``[openhands]`` extra. Skip cleanly if it is not installed.
pytest.importorskip("openhands.sdk", reason="agent evals require the [openhands] extra")

from openhands.sdk import LLM, Agent, Conversation, Tool  # noqa: E402
from pydantic import SecretStr  # noqa: E402

# Importing the module registers the ``gemini_delegate`` tool as a side effect.
import oh_gemini_tool.tool  # noqa: E402,F401
from oh_gemini_tool.tool import GeminiDelegateTool  # noqa: E402

# Pinned model — do NOT let this float. Matches the PR-review bot configuration so
# eval results are comparable across runs and only change when we change it here.
EVAL_MODEL = "litellm_proxy/claude-sonnet-4-5-20250929"
# Base URL is overridable (e.g. to run locally against a different proxy) but the
# model itself stays pinned.
EVAL_BASE_URL = os.environ.get("EVAL_LLM_BASE_URL", "https://llm-proxy.app.all-hands.dev")


@pytest.fixture(scope="session")
def llm_api_key() -> str:
    key = os.environ.get("LLM_API_KEY")
    if not key:
        pytest.skip("LLM_API_KEY not set; skipping agent evals")
    return key


@pytest.fixture(scope="session", autouse=True)
def require_agy() -> None:
    """These evals cannot pass without a real, authenticated agy."""
    if shutil.which("agy") is None:
        pytest.skip("agy not installed; skipping agent evals")


@pytest.fixture
def agent(llm_api_key: str) -> Agent:
    """An agent equipped ONLY with the delegation tool.

    No default file editor or terminal is included, so the agent must exercise
    ``gemini_delegate`` to satisfy an instruction — which is exactly what we want
    to evaluate.
    """
    llm = LLM(
        usage_id="agent-eval",
        model=EVAL_MODEL,
        base_url=EVAL_BASE_URL,
        api_key=SecretStr(llm_api_key),
        temperature=0.0,
    )
    return Agent(llm=llm, tools=[Tool(name=GeminiDelegateTool.name)])


@pytest.fixture
def run_instruction(agent: Agent):
    """Return a helper that sends ``instruction`` to the agent in a fresh workspace
    and returns that workspace directory for assertions.
    """

    def _run(tmp_path: Path, instruction: str) -> Path:
        conversation = Conversation(agent=agent, workspace=str(tmp_path))
        conversation.send_message(instruction)
        conversation.run()
        return tmp_path

    return _run
