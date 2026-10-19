"""Delegate agent work to the Google Antigravity CLI (``agy``)."""

__version__ = "0.1.0"

from .agy import (
    AgyNotFoundError,
    AgyResult,
    build_command,
    parse_result,
    run_agy,
)

# The OpenHands tool integration lives in ``oh_gemini_tool.tool`` and is imported
# separately (see ``pip install "oh-gemini-tool[openhands]"``). It is intentionally
# NOT imported here so the core client has no dependency on ``openhands-sdk`` and
# importing this package triggers no tool-registration side effects.

__all__ = [
    "__version__",
    "AgyResult",
    "AgyNotFoundError",
    "build_command",
    "parse_result",
    "run_agy",
]
