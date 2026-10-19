"""End-to-end agent evals.

Starting deliberately small: two simple, single-delegation instructions. Each runs
once against a tiny task to bound token spend. Assertions check the end state of
the workspace, not the exact tool-call transcript, since the agent's path is
non-deterministic.
"""

import pytest

pytestmark = pytest.mark.agent_eval


def test_agent_delegates_file_creation(run_instruction, tmp_path):
    """The agent should delegate and the file should exist afterwards."""
    workspace = run_instruction(
        tmp_path,
        "Create a file named hello.txt in the workspace containing exactly the "
        "text BANANA. Use the Antigravity delegation tool to do it.",
    )
    assert (workspace / "hello.txt").read_text().strip() == "BANANA"


def test_agent_delegates_a_small_refactor(run_instruction, tmp_path):
    """The agent should delegate a mechanical edit and the edit should land."""
    (tmp_path / "calc.py").write_text("def add(a, b):\n    return a - b\n")
    workspace = run_instruction(
        tmp_path,
        "calc.py has a bug: add() subtracts instead of adding. Fix it using the "
        "Antigravity delegation tool.",
    )
    assert "a + b" in (workspace / "calc.py").read_text()
