"""core/memory.py — conversation history helpers."""
from __future__ import annotations
from app.core.models import ChatMessage


def build_history_text(messages: list[ChatMessage], max_turns: int = 6) -> str:
    recent = [m for m in messages if m.content.strip() and not m.content.startswith("⚠️")]
    recent = recent[-max_turns:]
    if not recent:
        return ""
    lines = []
    for m in recent:
        label = "Human" if m.role == "user" else "Assistant"
        content = m.content[:600] + "…" if m.role == "assistant" and len(m.content) > 600 else m.content
        lines.append(f"{label}: {content}")
    return "\n".join(lines)


def build_agent_prefix(history_text: str, source_lines: list[str]) -> str:
    history_block = ""
    if history_text:
        history_block = (
            "CONVERSATION HISTORY (most recent exchanges):\n"
            + history_text + "\n\n"
            "Use this history to resolve references like 'them', 'it', 'those'. "
            "If the question can be answered from history alone, do so WITHOUT calling tools.\n\n"
        )
    sources_block = ""
    if source_lines:
        sources_block = (
            "Custom knowledge sources loaded:\n" + "\n".join(source_lines) +
            "\n\nCall the matching tool FIRST for questions about these sources.\n\n"
        )
    return (
        "You are InsightAgent, a helpful research assistant with multiple tools "
        "and conversation memory.\n\n"
        + history_block + sources_block +
        "INSTRUCTIONS:\n"
        "1. Read conversation history first to understand context.\n"
        "2. Resolve all pronouns/references before acting.\n"
        "3. Select the most relevant tool(s).\n"
        "4. Cross-reference multiple tools when needed.\n"
        "5. State which tools you used in your Final Answer.\n\n"
        "You have access to the following tools:"
    )


def augment_prompt(prompt: str, history_text: str) -> str:
    if not history_text:
        return prompt
    return (
        "[CONVERSATION HISTORY]\n" + history_text + "\n\n"
        "[CURRENT QUESTION]\n" + prompt + "\n\n"
        "Resolve any references using the history above before choosing a tool."
    )
