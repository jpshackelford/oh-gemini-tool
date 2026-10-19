"""OpenHands SDK integration for delegating work to the Antigravity CLI.

The agent loop stays small and cheap; ``gemini_delegate`` hands a self-contained
task to ``agy``, which does the work in the conversation workspace on the user's
Antigravity subscription and returns a summary.

Importing this module registers the ``gemini_delegate`` tool as a side effect,
which is what a remote agent-server relies on when it loads the module via
``tool_module_qualnames``.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Literal

try:
    from openhands.sdk.llm import TextContent
    from openhands.sdk.tool import (
        Action,
        Observation,
        ToolAnnotations,
        ToolDefinition,
        ToolExecutor,
        register_tool,
    )
    from pydantic import Field
    from rich.text import Text
except ModuleNotFoundError as exc:  # pragma: no cover
    raise ModuleNotFoundError(
        "The OpenHands tool integration requires extra dependencies. "
        "Install them with: pip install 'oh-gemini-tool[openhands]'"
    ) from exc

from .agy import (
    DEFAULT_BINARY,
    DEFAULT_TIMEOUT_SECONDS,
    AgyNotFoundError,
    format_usage,
    run_agy,
)

if TYPE_CHECKING:
    from openhands.sdk.conversation.state import ConversationState


GEMINI_DELEGATE_DESCRIPTION = """
Delegate a self-contained chunk of work to the Google Antigravity CLI (`agy`).

This runs `agy` headlessly in the current workspace on the user's Antigravity
subscription. Use it to offload large, mechanical, or exploratory work — multi-file
refactors, "find and fix all X", bulk code generation or migration — so it runs on
the subscription instead of this model's context and credits.

IMPORTANT:
- `agy` runs autonomously and CANNOT ask clarifying questions mid-task, so `task`
  must be complete and specific: state the goal, the files involved, and what "done"
  looks like.
- It edits files in the workspace directly. Verify important outcomes yourself
  (re-read changed files, run tests) before reporting success.
- Delegations share one Antigravity session by default, so later calls see earlier
  context. Set `reuse_session=false` for unrelated work — starting fresh is also
  faster, since resuming replays the prior session.
""".strip()


class GeminiDelegateAction(Action):
    """Action for the Antigravity delegation tool."""

    task: str = Field(
        description=(
            "A self-contained instruction for the Antigravity agent. Include the goal, "
            "the files involved, and the definition of done. It runs autonomously and "
            "cannot ask you questions mid-task."
        )
    )
    model: Literal["flash_lite", "flash", "pro"] | None = Field(
        default=None,
        description=(
            "Antigravity model tier: 'flash_lite' (fastest/cheapest), 'flash' "
            "(balanced), or 'pro' (most capable). Omit to use the account default."
        ),
    )
    reuse_session: bool = Field(
        default=True,
        description=(
            "Continue the previous Antigravity conversation so it keeps context from "
            "earlier delegations. Set false for unrelated work that should start clean."
        ),
    )
    timeout_seconds: int = Field(
        default=DEFAULT_TIMEOUT_SECONDS,
        ge=30,
        description="Hard wall-clock limit for the delegated run, in seconds.",
    )


class GeminiDelegateObservation(Observation):
    """Observation for the Antigravity delegation tool."""

    response: str = Field(default="", description="Antigravity's final response text.")
    status: str = Field(default="", description="Antigravity run status, e.g. SUCCESS.")
    conversation_id: str = Field(
        default="", description="Antigravity conversation id, for resuming."
    )
    num_turns: int = Field(
        default=0, description="Number of turns in the Antigravity conversation."
    )
    duration_seconds: float = Field(
        default=0.0, description="Wall-clock duration of the run, in seconds."
    )
    usage: dict[str, int | float | str] = Field(
        default_factory=dict, description="Token usage reported by Antigravity."
    )

    @property
    def to_llm_content(self) -> list[TextContent]:
        """Agent-facing content for this observation.

        A successful run populates structured fields but may leave ``content``
        empty (a run that only edited files can return a terse response). Returning
        empty content leaves the agent with no feedback and trips an empty-message
        edge case in the prompt-caching path of some LLM clients, so always surface
        the concise summary. Errors already carry a message via ``from_text``.
        """
        if self.is_error or self.content:
            return super().to_llm_content
        return [TextContent(text=self.visualize.plain.strip())]

    @property
    def visualize(self) -> Text:
        """Return a Rich Text representation of this observation."""
        text = Text()

        if self.is_error:
            text.append("❌ ", style="red bold")
            text.append(self.ERROR_MESSAGE_HEADER, style="bold red")
            return text

        text.append("✅ ", style="green bold")
        text.append("Antigravity finished", style="green")
        if self.status:
            text.append(f" ({self.status})", style="dim")
        if self.num_turns:
            text.append(f" turns={self.num_turns}", style="dim")
        if self.duration_seconds:
            text.append(f" {self.duration_seconds:.1f}s", style="dim")
        text.append(f" tokens={format_usage(self.usage)}", style="dim")

        response = (self.response or "").strip()
        if response:
            snippet = response if len(response) <= 500 else response[:500] + "…"
            text.append("\n\n")
            text.append(snippet)

        return text


class GeminiDelegateExecutor(ToolExecutor[GeminiDelegateAction, GeminiDelegateObservation]):
    """Executor that shells out to ``agy`` and threads session state."""

    def __init__(self, workspace_dir: Path, binary: str = DEFAULT_BINARY):
        """Initialize the executor.

        Args:
            workspace_dir: Directory to run ``agy`` in.
            binary: Name or path of the Antigravity CLI binary.
        """
        self.workspace_dir = workspace_dir
        self.binary = binary
        # Conversation id of the last delegation, so successive calls share one
        # Antigravity session. Antigravity persists conversations on disk, but this
        # pointer is in-memory: a restarted agent-server starts a fresh session.
        self._conversation_id: str | None = None

    def __call__(
        self,
        action: GeminiDelegateAction,
        conversation=None,  # noqa: ARG002 - SDK executor protocol
    ) -> GeminiDelegateObservation:
        """Execute a delegation.

        Args:
            action: The delegation request.
            conversation: The conversation context (unused).

        Returns:
            Observation with the result.
        """
        return self.execute(action)

    def execute(self, action: GeminiDelegateAction) -> GeminiDelegateObservation:
        """Execute a delegation.

        Args:
            action: The delegation request.

        Returns:
            Observation with the result.
        """
        session = self._conversation_id if action.reuse_session else None
        try:
            result = run_agy(
                action.task,
                working_dir=str(self.workspace_dir),
                binary=self.binary,
                model=action.model,
                conversation_id=session,
                timeout_seconds=action.timeout_seconds,
            )
        except AgyNotFoundError as exc:
            return GeminiDelegateObservation.from_text(str(exc), is_error=True)

        if not result.ok:
            return GeminiDelegateObservation.from_text(result.error, is_error=True)

        self._conversation_id = result.conversation_id or self._conversation_id
        return GeminiDelegateObservation(
            response=result.response,
            status=result.status,
            conversation_id=self._conversation_id or "",
            num_turns=result.num_turns,
            duration_seconds=result.duration_seconds,
            usage=result.usage,
        )


class GeminiDelegateTool(ToolDefinition[GeminiDelegateAction, GeminiDelegateObservation]):
    """Tool that delegates work to the Antigravity CLI."""

    @classmethod
    def create(cls, conv_state: ConversationState) -> Sequence[GeminiDelegateTool]:
        """Create the delegation tool.

        Args:
            conv_state: Conversation state with workspace info.
        """
        workspace_dir = Path(conv_state.workspace.working_dir)
        executor = GeminiDelegateExecutor(workspace_dir)

        return [
            cls(
                description=GEMINI_DELEGATE_DESCRIPTION,
                action_type=GeminiDelegateAction,
                observation_type=GeminiDelegateObservation,
                annotations=ToolAnnotations(
                    title="Antigravity Delegate",
                ),
                executor=executor,
            )
        ]


# Registering on import is the side effect the agent-server relies on when it loads
# this module via ``tool_module_qualnames`` (qualname: ``oh_gemini_tool.tool``).
# Registered under the tool's own name so ``agent.tools`` and the registry key match.
register_tool(GeminiDelegateTool.name, GeminiDelegateTool)
