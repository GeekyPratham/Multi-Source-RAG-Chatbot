"""services/agent_service.py — builds and runs the LangChain RAG agent."""
from __future__ import annotations
from langchain_groq import ChatGroq
from langchain_classic.agents import AgentType, initialize_agent
from langchain_community.tools import ArxivQueryRun, DuckDuckGoSearchRun, WikipediaQueryRun
from langchain_community.utilities import ArxivAPIWrapper, WikipediaAPIWrapper
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from app.core.models import ChatRequest, ChatResponse, ToolStep
from app.core.memory import build_history_text, build_agent_prefix, augment_prompt
from app.services.session_store import get_all_tools, get_source_lines
from app.services.providers import get_provider_class, get_base_url
from app.utils.logger import log


def _base_tools() -> list:
    return [
        DuckDuckGoSearchRun(name="DuckDuckGo_Search"),
        ArxivQueryRun(api_wrapper=ArxivAPIWrapper(top_k_results=1, doc_content_chars_max=400)),
        WikipediaQueryRun(api_wrapper=WikipediaAPIWrapper(top_k_results=1, doc_content_chars_max=400)),
    ]


def _build_chat_model(provider_name: str, api_key: str, model: str, temperature: float, base_url: str | None = None):
    """Build a LangChain-compatible chat model for any provider.

    For Groq: returns ChatGroq directly.
    For others: returns a custom wrapper that uses the provider abstraction.
    """
    name = provider_name.strip().lower() if provider_name else "groq"

    if name == "groq":
        return ChatGroq(
            groq_api_key=api_key,
            model_name=model,
            streaming=False,
            temperature=temperature,
        )

    # For non-Groq providers, create a LangChain-compatible wrapper
    from langchain_core.language_models.llms import LLM
    from typing import Optional, List, Any

    provider_cls = get_provider_class(name)
    resolved_base_url = get_base_url(name, base_url)
    provider_impl = provider_cls(api_key=api_key, model=model, temperature=temperature, base_url=resolved_base_url)

    # Special handling: Anthropic and other providers use our wrapper
    class ProviderChatModel(LLM):
        """Wraps any LLMProviderBase into a LangChain LLM compatible with initialize_agent."""

        provider: Any = provider_impl
        model_name: str = model
        temperature: float = temperature

        def _call(self, prompt: str, stop: Optional[List[str]] = None, **kwargs) -> str:
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            return loop.run_until_complete(
                self.provider.ainvoke([{"role": "user", "content": prompt}])
            )

        async def _acall(self, prompt: str, stop: Optional[List[str]] = None, **kwargs) -> str:
            result = await self.provider.ainvoke([{"role": "user", "content": prompt}])
            return result

        @property
        def _llm_type(self) -> str:
            return f"custom-{name}"

    return ProviderChatModel()


async def run_agent(req: ChatRequest) -> ChatResponse:
    history_text = build_history_text(req.history, max_turns=req.memory_turns)
    source_lines = get_source_lines(req.session_id)
    custom_tools = get_all_tools(req.session_id)
    all_tools = custom_tools + _base_tools()

    prefix = build_agent_prefix(history_text, source_lines)
    augmented = augment_prompt(req.message, history_text)

    provider = req.provider or "groq"

    # Build the LLM — Groq uses ChatGroq, others use the provider wrapper
    llm = _build_chat_model(
        provider_name=provider,
        api_key=req.api_key,
        model=req.model_name,
        temperature=req.temperature,
        base_url=req.base_url,
    )

    # Use initialize_agent (langchain_classic-compatible) for all providers
    agent = initialize_agent(
        tools=all_tools,
        llm=llm,
        agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        handle_parsing_errors=True,
        verbose=False,
        max_iterations=12,
        early_stopping_method="generate",
        return_intermediate_steps=True,
        agent_kwargs={"prefix": prefix},
    )

    log.info("Running agent | session=%s | model=%s | provider=%s | tools=%d | temp=%s",
             req.session_id, req.model_name, provider, len(all_tools), req.temperature)

    try:
        result = await agent.ainvoke({"input": augmented})
    except Exception as e:
        log.error("Agent execution failed: %s", e)
        raise

    answer = result.get("output", "")
    steps = result.get("intermediate_steps", [])

    tool_steps = []
    tools_used = []
    for i, (action, obs) in enumerate(steps, 1):
        tool_steps.append(ToolStep(
            step=i,
            tool=action.tool,
            tool_input=action.tool_input,
            observation=str(obs)[:500],
        ))
        if action.tool not in tools_used:
            tools_used.append(action.tool)

    return ChatResponse(
        answer=answer,
        tool_steps=tool_steps,
        tools_used=tools_used,
        answered_from_history=(len(steps) == 0),
    )