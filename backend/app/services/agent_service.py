"""services/agent_service.py — builds and runs the RAG agent."""
from __future__ import annotations
from langchain_groq import ChatGroq
from langchain_classic.agents import AgentType, initialize_agent
from langchain_classic.agents.agent import AgentExecutor
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
    """Build a LangChain-compatible chat model for any provider."""
    name = provider_name.strip().lower() if provider_name else "groq"

    if name == "groq":
        return ChatGroq(
            groq_api_key=api_key,
            model_name=model,
            streaming=False,
            temperature=temperature,
        )

    # For non-Groq providers, create a custom LangChain-compatible wrapper
    from langchain_core.language_models.llms import LLM
    from typing import Optional, List, Any

    provider_cls = get_provider_class(name)
    resolved_base_url = get_base_url(name, base_url)
    provider_impl = provider_cls(api_key=api_key, model=model, temperature=temperature, base_url=resolved_base_url)

    class ProviderChatModel(LLM):
        """Wraps any LLMProviderBase into a LangChain LLM compatible with initialize_agent."""

        provider: Any = provider_impl
        model_name: str = model

        def __init__(self, **kwargs):
            kwargs.setdefault('temperature', temperature)
            super().__init__(**kwargs)

        def _call(self, prompt: str, stop: Optional[List[str]] = None, **kwargs) -> str:
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(
                        lambda: asyncio.run(
                            self.provider.ainvoke([{"role": "user", "content": prompt}])
                        )
                    )
                    return future.result()
            except RuntimeError:
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


def _needs_tools(message: str, history_text: str, has_custom_tools: bool) -> bool:
    """Quick check if a question likely needs tool calls vs just model knowledge.
    
    Returns True if the question should go through the agent with tools,
    False if a simple direct answer would suffice.
    """
    msg_lower = message.lower().strip()
    
    # Always use tools if the user has added custom sources
    if has_custom_tools:
        return True
    
    # Greetings and simple chit-chat don't need tools
    simple_greetings = [
        "hi", "hello", "hey", "thanks", "thank you", "bye", "goodbye",
        "what's up", "how are you", "good morning", "good evening",
    ]
    if msg_lower in simple_greetings or msg_lower.startswith(tuple(f"{g} " for g in simple_greetings)):
        return False
    
    # Questions about the user's identity from context
    if msg_lower.startswith(("what is my", "what's my", "who am i", "do you know me", "what do you know about me")):
        return False
    
    return True


async def _direct_query(llm, message: str, history_text: str) -> str:
    """Ask the model directly without going through the ReAct agent."""
    prompt = (
        "You are a helpful AI assistant. Answer the user's question based on your knowledge.\n\n"
        "Previous conversation context:\n"
        + history_text +
        "\n\nUser's question: " + message +
        "\n\nAnswer the question directly and concisely. If you don't know the answer, say so."
    )

    if hasattr(llm, '_acall'):
        return await llm._acall(prompt)
    else:
        result = await llm.ainvoke([{"role": "user", "content": prompt}])
        if hasattr(result, 'content'):
            return result.content
        return str(result)


async def run_agent(req: ChatRequest, user_id: str | None = None) -> ChatResponse:
    # Tools are scoped to the authenticated user (derived from the JWT) so a
    # user can only ever retrieve from their own isolated vector collections.
    # Falls back to session_id for unauthenticated/legacy callers.
    scope_key = user_id or req.session_id
    history_text = build_history_text(req.history, max_turns=req.memory_turns)
    source_lines = get_source_lines(scope_key)
    custom_tools = get_all_tools(scope_key)
    all_tools = custom_tools + _base_tools()

    provider = req.provider or "groq"

    # Build the LLM
    llm = _build_chat_model(
        provider_name=provider,
        api_key=req.api_key,
        model=req.model_name,
        temperature=req.temperature,
        base_url=req.base_url,
    )

    # For simple questions that don't need tools, skip the agent entirely
    if not _needs_tools(req.message, history_text, bool(custom_tools)):
        log.info("Direct query (no tools needed) | session=%s | model=%s", 
                 req.session_id, req.model_name)
        try:
            answer = await _direct_query(llm, req.message, history_text)
            return ChatResponse(
                answer=answer,
                tool_steps=[],
                tools_used=[],
                answered_from_history=False,
            )
        except Exception as e:
            log.warning("Direct query failed, falling back to agent: %s", e)
            # Fall through to agent

    # Build prefix with improved instructions
    prefix = build_agent_prefix(history_text, source_lines)
    augmented = augment_prompt(req.message, history_text)

    # Use initialize_agent (langchain_classic-compatible) for all providers
    agent = initialize_agent(
        tools=all_tools,
        llm=llm,
        agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
        handle_parsing_errors=True,
        verbose=False,
        max_iterations=4,
        early_stopping_method="generate",
        return_intermediate_steps=True,
        agent_kwargs={"prefix": prefix},
    )

    log.info("Running agent | session=%s | model=%s | provider=%s | tools=%d | temp=%s",
             req.session_id, req.model_name, provider, len(all_tools), req.temperature)

    try:
        result = await agent.ainvoke({"input": augmented})
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)[:200]
        log.error("Agent execution failed [%s]: %s", error_type, error_msg)
        
        # Fallback: try a direct query without the ReAct agent wrapper
        try:
            log.info("Falling back to direct query for model=%s", req.model_name)
            fallback_answer = await _direct_query(llm, req.message, history_text)
            return ChatResponse(
                answer=fallback_answer,
                tool_steps=[],
                tools_used=[],
                answered_from_history=False,
            )
        except Exception as fallback_e:
            log.error("Fallback query also failed: %s", fallback_e)
            # Determine a helpful error message based on the error type
            if "OutputParserException" in error_type or "parse" in error_msg.lower():
                user_msg = "The model had trouble formatting its response. Try rephrasing your question or switching to a different model."
            elif "RateLimit" in error_type or "429" in error_msg or "rate_limit" in error_msg.lower():
                user_msg = "Rate limit exceeded by the provider. Please wait a moment and try again."
            elif "Timeout" in error_type or "timed out" in error_msg.lower():
                user_msg = "The model took too long to respond. Try a faster model or try again."
            else:
                user_msg = f"Something went wrong: {error_type}. Please try again or use a different model/provider."
            return ChatResponse(
                answer=user_msg,
                tool_steps=[],
                tools_used=[],
                answered_from_history=False,
            )

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
