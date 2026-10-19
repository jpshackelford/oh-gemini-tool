"""Tests for the dependency-free agy client."""

from __future__ import annotations

import json

import pytest

from oh_gemini_tool.agy import (
    MODEL_TIERS,
    AgyNotFoundError,
    argv_for_display,
    build_command,
    format_usage,
    parse_result,
    run_agy,
)


class TestBuildCommand:
    """The argv must be exactly what the CLI expects."""

    def test_minimal_command(self):
        cmd = build_command("do the thing")
        assert cmd == [
            "agy",
            "-p",
            "do the thing",
            "--output-format",
            "json",
            "--dangerously-skip-permissions",
        ]

    def test_includes_model_and_conversation(self):
        cmd = build_command("t", model="pro", conversation_id="abc-123")
        assert cmd[-4:] == ["--model", "pro", "--conversation", "abc-123"]

    def test_omits_conversation_when_none(self):
        assert "--conversation" not in build_command("t")

    def test_can_omit_skip_permissions(self):
        assert "--dangerously-skip-permissions" not in build_command("t", skip_permissions=False)

    def test_model_tiers_are_the_documented_ones(self):
        assert MODEL_TIERS == ("flash_lite", "flash", "pro")


class TestParseResult:
    """Parsing must never raise on bad CLI output."""

    def test_parses_a_successful_envelope(self, envelope, envelope_json):
        result = parse_result(envelope_json)
        assert result.ok is True
        assert result.response == "DONE\n"
        assert result.status == "SUCCESS"
        assert result.conversation_id == envelope["conversation_id"]
        assert result.num_turns == 1
        assert result.duration_seconds == pytest.approx(4.065896)
        assert result.usage["total_tokens"] == 11785

    def test_error_field_becomes_a_failed_result(self):
        result = parse_result(json.dumps({"error": "ANTIGRAVITY_LS_ADDRESS is not set"}))
        assert result.ok is False
        assert "ANTIGRAVITY_LS_ADDRESS" in result.error

    def test_non_json_becomes_a_failed_result(self):
        result = parse_result("not json at all")
        assert result.ok is False
        assert "Unparseable" in result.error

    def test_non_object_json_becomes_a_failed_result(self):
        result = parse_result("[1, 2, 3]")
        assert result.ok is False
        assert "Unexpected" in result.error

    def test_missing_optional_fields_default_cleanly(self):
        result = parse_result(json.dumps({"status": "SUCCESS"}))
        assert result.ok is True
        assert result.response == ""
        assert result.num_turns == 0
        assert result.usage == {}

    def test_null_fields_do_not_crash(self):
        result = parse_result(
            json.dumps({"status": "SUCCESS", "conversation_id": None, "num_turns": None})
        )
        assert result.ok is True
        assert result.conversation_id == ""
        assert result.num_turns == 0


class TestFormatUsage:
    def test_renders_total_tokens(self):
        assert format_usage({"total_tokens": 15}) == "15"

    def test_missing_usage_renders_placeholder(self):
        assert format_usage(None) == "?"
        assert format_usage({}) == "?"

    def test_usage_without_total_renders_placeholder(self):
        assert format_usage({"input_tokens": 10}) == "?"


class TestArgvForDisplay:
    def test_redacts_the_task_text(self):
        rendered = argv_for_display(["agy", "-p", "secret task text", "--output-format", "json"])
        assert "secret task text" not in rendered
        assert "<task>" in rendered


class TestRunAgy:
    """End-to-end through a real subprocess, using the fake agy on PATH."""

    def test_successful_run(self, fake_agy, tmp_path):
        result = run_agy("say hi", working_dir=str(tmp_path), binary=fake_agy)
        assert result.ok is True
        assert result.response == "fresh: say hi"
        assert result.num_turns == 1
        assert result.usage["total_tokens"] == 15

    def test_missing_binary_raises(self, tmp_path):
        with pytest.raises(AgyNotFoundError):
            run_agy("hi", working_dir=str(tmp_path), binary="definitely-not-installed-xyz")

    def test_nonzero_exit_is_reported(self, fake_agy, tmp_path, monkeypatch):
        monkeypatch.setenv("FAKE_AGY_MODE", "nonzero")
        result = run_agy("hi", working_dir=str(tmp_path), binary=fake_agy)
        assert result.ok is False
        assert "exited with code 3" in result.error

    def test_timeout_is_reported(self, fake_agy, tmp_path, monkeypatch):
        monkeypatch.setenv("FAKE_AGY_MODE", "sleep")
        result = run_agy("hi", working_dir=str(tmp_path), binary=fake_agy, timeout_seconds=1)
        assert result.ok is False
        assert "timeout" in result.error

    def test_error_envelope_is_reported(self, fake_agy, tmp_path, monkeypatch):
        monkeypatch.setenv("FAKE_AGY_MODE", "error_json")
        result = run_agy("hi", working_dir=str(tmp_path), binary=fake_agy)
        assert result.ok is False
        assert "ANTIGRAVITY_LS_ADDRESS" in result.error

    def test_resuming_passes_conversation_through(self, fake_agy, tmp_path):
        first = run_agy("remember this", working_dir=str(tmp_path), binary=fake_agy)
        assert first.conversation_id == "conv-new"

        second = run_agy(
            "what did I say?",
            working_dir=str(tmp_path),
            binary=fake_agy,
            conversation_id=first.conversation_id,
        )
        assert second.ok is True
        assert second.response == "resumed: what did I say?"
        assert second.num_turns == 2
        assert second.conversation_id == "conv-new"
