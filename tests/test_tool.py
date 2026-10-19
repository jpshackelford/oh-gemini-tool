"""Tests for the OpenHands SDK tool integration."""

from __future__ import annotations

from pathlib import Path

import pytest

from oh_gemini_tool.tool import (
    GeminiDelegateAction,
    GeminiDelegateExecutor,
    GeminiDelegateObservation,
    GeminiDelegateTool,
)


class TestGeminiDelegateAction:
    def test_defaults(self):
        action = GeminiDelegateAction(task="do it")
        assert action.reuse_session is True
        assert action.model is None
        assert action.timeout_seconds == 900

    def test_rejects_unknown_model_tier(self):
        with pytest.raises(ValueError):
            GeminiDelegateAction(task="do it", model="gpt-9")

    def test_rejects_too_small_timeout(self):
        with pytest.raises(ValueError):
            GeminiDelegateAction(task="do it", timeout_seconds=5)


class TestObservationContent:
    """A successful observation must never hand the agent empty content."""

    def test_to_llm_content_summarizes_when_content_is_empty(self):
        obs = GeminiDelegateObservation(
            response="created demo.txt",
            status="SUCCESS",
            num_turns=1,
            duration_seconds=4.1,
            usage={"total_tokens": 42},
        )
        content = obs.to_llm_content
        assert len(content) == 1
        text = content[0].text
        assert "Antigravity finished" in text
        assert "created demo.txt" in text
        assert "tokens=42" in text
        assert "turns=1" in text
        assert "4.1s" in text

    def test_to_llm_content_defers_to_base_for_errors(self):
        obs = GeminiDelegateObservation.from_text("boom", is_error=True)
        assert obs.is_error is True
        # The base implementation returns the error header plus the message.
        joined = "".join(c.text for c in obs.to_llm_content)
        assert obs.ERROR_MESSAGE_HEADER in joined
        assert "boom" in joined

    def test_visualize_renders_error_marker(self):
        obs = GeminiDelegateObservation.from_text("boom", is_error=True)
        assert "❌" in obs.visualize.plain

    def test_long_responses_are_truncated_in_the_summary(self):
        obs = GeminiDelegateObservation(response="x" * 1000, status="SUCCESS")
        assert "…" in obs.visualize.plain


class TestExecutor:
    """Exercises the real subprocess path via the fake agy on PATH."""

    def _executor(self, tmp_path, fake_agy):
        return GeminiDelegateExecutor(tmp_path, binary=fake_agy)

    def test_successful_delegation(self, tmp_path, fake_agy):
        executor = self._executor(tmp_path, fake_agy)
        obs = executor.execute(GeminiDelegateAction(task="build the thing"))
        assert obs.is_error is False
        assert obs.status == "SUCCESS"
        assert obs.response == "fresh: build the thing"
        assert obs.conversation_id == "conv-new"
        assert obs.num_turns == 1

    def test_session_is_reused_by_default(self, tmp_path, fake_agy):
        executor = self._executor(tmp_path, fake_agy)

        first = executor.execute(GeminiDelegateAction(task="remember MANGO-42"))
        assert first.num_turns == 1

        second = executor.execute(GeminiDelegateAction(task="what token?"))
        assert second.num_turns == 2
        assert second.conversation_id == first.conversation_id
        assert second.response == "resumed: what token?"

    def test_reuse_session_false_starts_fresh(self, tmp_path, fake_agy):
        executor = self._executor(tmp_path, fake_agy)

        executor.execute(GeminiDelegateAction(task="remember MANGO-42"))
        fresh = executor.execute(GeminiDelegateAction(task="what token?", reuse_session=False))
        assert fresh.num_turns == 1
        assert fresh.response == "fresh: what token?"

    def test_model_tier_is_forwarded(self, tmp_path, fake_agy):
        executor = self._executor(tmp_path, fake_agy)
        obs = executor.execute(GeminiDelegateAction(task="t", model="pro"))
        # The fake CLI echoes back the model it was given.
        assert obs.is_error is False

    def test_missing_binary_becomes_an_error_observation(self, tmp_path):
        executor = GeminiDelegateExecutor(tmp_path, binary="definitely-not-installed-xyz")
        obs = executor.execute(GeminiDelegateAction(task="t"))
        assert obs.is_error is True
        assert "not found on PATH" in obs.content[0].text

    def test_cli_failure_becomes_an_error_observation(self, tmp_path, fake_agy, monkeypatch):
        monkeypatch.setenv("FAKE_AGY_MODE", "nonzero")
        executor = self._executor(tmp_path, fake_agy)
        obs = executor.execute(GeminiDelegateAction(task="t"))
        assert obs.is_error is True
        assert "exited with code 3" in obs.content[0].text

    def test_error_envelope_becomes_an_error_observation(self, tmp_path, fake_agy, monkeypatch):
        monkeypatch.setenv("FAKE_AGY_MODE", "error_json")
        executor = self._executor(tmp_path, fake_agy)
        obs = executor.execute(GeminiDelegateAction(task="t"))
        assert obs.is_error is True
        assert "ANTIGRAVITY_LS_ADDRESS" in obs.content[0].text

    def test_call_delegates_to_execute(self, tmp_path, fake_agy):
        executor = self._executor(tmp_path, fake_agy)
        obs = executor(GeminiDelegateAction(task="hi"))
        assert obs.is_error is False


class TestToolDefinition:
    def test_registered_under_its_name(self):
        from openhands.sdk.tool import list_registered_tools

        assert GeminiDelegateTool.name in list_registered_tools()

    def test_name_is_derived_from_the_class(self):
        assert GeminiDelegateTool.name == "gemini_delegate"

    def test_create_uses_the_workspace_dir(self, fake_conv_state):
        tools = GeminiDelegateTool.create(fake_conv_state)
        assert len(tools) == 1
        tool = tools[0]
        assert tool.executor.workspace_dir == Path(fake_conv_state.workspace.working_dir)
        assert tool.action_type is GeminiDelegateAction
        assert tool.observation_type is GeminiDelegateObservation


@pytest.mark.agy_integration
class TestRealAgyBinary:
    """Opt-in suite that drives a real, authenticated ``agy``.

    Run with ``make test-agy``. Skipped automatically when ``agy`` is absent so it
    never breaks a machine that has not installed Antigravity.
    """

    def test_real_delegation_writes_a_file(self, tmp_path):
        import shutil

        if shutil.which("agy") is None:
            pytest.skip("agy not installed")

        executor = GeminiDelegateExecutor(tmp_path)
        obs = executor.execute(
            GeminiDelegateAction(
                task=(
                    "Create a file named demo.txt containing exactly the text "
                    "HELLO_FROM_AGY. Then reply DONE."
                ),
                timeout_seconds=300,
            )
        )
        assert obs.is_error is False, obs.content
        assert (tmp_path / "demo.txt").read_text().strip() == "HELLO_FROM_AGY"
