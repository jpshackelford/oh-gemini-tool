"""Standalone usage of the agy client and the OpenHands tool.

Run the client-only part (no SDK needed):

    python examples/basic_usage.py

Run the agent part (needs the [openhands] extra and LLM credentials):

    python examples/basic_usage.py --agent
"""

from __future__ import annotations

import sys
from pathlib import Path


def run_client_only() -> None:
    """Drive the Antigravity CLI directly, with no agent involved."""
    from oh_gemini_tool.agy import run_agy

    workspace = Path("agy_demo")
    workspace.mkdir(exist_ok=True)

    print("Delegating a task to Antigravity...")
    result = run_agy(
        "Create a file named demo.txt containing exactly the text HELLO_FROM_AGY. Then reply DONE.",
        working_dir=str(workspace),
    )

    if not result.ok:
        print(f"Delegation failed: {result.error}")
        return

    print(f"status={result.status} turns={result.num_turns} usage={result.usage}")
    print(f"response: {result.response!r}")
    print(f"workspace now contains: {sorted(p.name for p in workspace.iterdir())}")

    # A second call resumes the same Antigravity conversation by default.
    follow_up = run_agy(
        "What file did you just create? Reply with only the filename.",
        working_dir=str(workspace),
        conversation_id=result.conversation_id,
    )
    print(f"follow-up (resumed session): {follow_up.response!r}")


def run_agent() -> None:
    """Give an OpenHands agent the delegation tool."""
    import os

    from openhands.sdk import LLM, Agent, Conversation, Tool
    from pydantic import SecretStr

    from oh_gemini_tool.tool import GeminiDelegateTool

    llm = LLM(
        model=os.environ.get("LLM_MODEL", "litellm_proxy/claude-sonnet-4-5-20250929"),
        base_url=os.environ.get("LLM_BASE_URL", "https://llm-proxy.app.all-hands.dev"),
        api_key=SecretStr(os.environ["LLM_API_KEY"]),
    )
    agent = Agent(llm=llm, tools=[Tool(name=GeminiDelegateTool.name)])

    workspace = Path("agent_demo")
    workspace.mkdir(exist_ok=True)
    conversation = Conversation(agent=agent, workspace=str(workspace))
    conversation.send_message(
        "Use the Antigravity delegation tool to create a file named notes.md "
        "containing a three-item checklist for shipping a Python package."
    )
    conversation.run()
    print(f"workspace now contains: {sorted(p.name for p in workspace.iterdir())}")


if __name__ == "__main__":
    if "--agent" in sys.argv:
        run_agent()
    else:
        run_client_only()
