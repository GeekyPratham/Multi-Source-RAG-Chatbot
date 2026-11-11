"""services/providers.py — Pluggable LLM provider abstraction.

Each provider implements the same interface, allowing the RAG agent
to use whatever LLM the user has configured in their settings.
Supports any OpenAI-compatible API (Groq, DeepSeek, Together, etc.)
and Anthropic natively.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Optional
from app.utils.logger import log

# No provider-specific base URL defaults — users must always supply a base URL.
# Kept as an empty placeholder for future use; get_base_url() returns only the
# user-provided value and never falls back to a hardcoded URL.
PROVIDER_BASE_URLS: dict[str, str | None] = {}

# Providers that use the Anthropic API format
ANTHROPIC_PROVIDERS = {"anthropic", "claude"}


class LLMProviderBase(ABC):
    """Abstract base for LLM providers."""

    def __init__(self, api_key: str, model: str, temperature: float, base_url: Optional[str] = None):
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.base_url = base_url

    @abstractmethod
    async def ainvoke(self, messages: list[dict]) -> str:
        """Send messages and return the response text.

        messages: list of {"role": "user"|"assistant"|"system", "content": str}
        """
        ...

    async def validate(self) -> str:
        """Test connection by sending a minimal message. Returns provider name on success."""
        result = await self.ainvoke([{"role": "user", "content": "Respond with just the word OK"}])
        return result[:100]


class GroqProvider(LLMProviderBase):
    """Groq via LangChain's ChatGroq."""

    async def ainvoke(self, messages: list[dict]) -> str:
        from langchain_groq import ChatGroq
        from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

        llm = ChatGroq(
            groq_api_key=self.api_key,
            model_name=self.model,
            temperature=self.temperature,
            streaming=False,
        )

        lc_messages = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "system":
                lc_messages.append(SystemMessage(content=content))
            elif role == "assistant":
                lc_messages.append(AIMessage(content=content))
            else:
                lc_messages.append(HumanMessage(content=content))

        response = await llm.ainvoke(lc_messages)
        return response.content


class OpenAIProvider(LLMProviderBase):
    """OpenAI-compatible API via httpx."""

    async def ainvoke(self, messages: list[dict]) -> str:
        import httpx

        base_url = self.base_url or "https://api.openai.com/v1"
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": self.temperature,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]


class GenericOpenAIProvider(LLMProviderBase):
    """Generic OpenAI-compatible provider — works with any API that follows the OpenAI format."""

    async def ainvoke(self, messages: list[dict]) -> str:
        import httpx

        base_url = self.base_url or "https://api.openai.com/v1"
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": self.temperature,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        # Handle different response formats (OpenAI-compatible, OpenRouter, etc.)
        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0]["message"]["content"]
        elif "error" in data:
            raise ValueError(f"Provider error: {data['error'].get('message', str(data['error']))}")
        else:
            raise ValueError(f"Unexpected response format from provider: {str(data)[:300]}")


class AnthropicProvider(LLMProviderBase):
    """Anthropic Claude API via httpx."""

    async def ainvoke(self, messages: list[dict]) -> str:
        import httpx

        # Convert OpenAI-style messages to Anthropic format
        system_prompt = None
        cleaned = []
        for m in messages:
            if m["role"] == "system":
                system_prompt = m["content"]
            else:
                cleaned.append({"role": m["role"], "content": m["content"]})

        body = {
            "model": self.model,
            "max_tokens": 4096,
            "temperature": self.temperature,
            "messages": cleaned,
        }
        if system_prompt:
            body["system"] = system_prompt

        base_url = self.base_url or "https://api.anthropic.com/v1"
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{base_url}/messages",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["content"][0]["text"]


# ── Factory ────────────────────────────────────────────────────────────────────
def _normalize_provider(name: str) -> str:
    """Normalize provider name to lowercase."""
    return name.strip().lower() if name else ""


def get_provider_class(provider_name: str) -> type[LLMProviderBase]:
    """Return the provider class for the given name.

    All providers are treated as OpenAI-compatible except Anthropic.
    Users must always supply a base_url — there are no provider-specific defaults.
    """
    name = _normalize_provider(provider_name)

    if name == "openai":
        return OpenAIProvider
    elif name in ANTHROPIC_PROVIDERS:
        return AnthropicProvider
    else:
        return GenericOpenAIProvider


def get_base_url(provider_name: str, user_base_url: Optional[str] = None) -> Optional[str]:
    """Get the base URL for a provider.

    Users must always supply a base_url; there are no provider-specific defaults.
    """
    if user_base_url:
        return user_base_url.rstrip("/")
    return None


async def validate_provider_connection(provider_name: str, api_key: str, model: str, base_url: Optional[str] = None) -> str:
    """Test a provider connection. Returns success message or raises.

    A base_url is required for every provider.
    """
    name = _normalize_provider(provider_name)
    provider_cls = get_provider_class(name)
    resolved_base_url = get_base_url(name, base_url)

    if not resolved_base_url:
        raise ValueError(
            f"A base URL is required for provider '{provider_name}'. "
            f"Please provide a base URL (e.g., https://api.{provider_name}.com/v1)."
        )

    provider = provider_cls(api_key=api_key, model=model, temperature=0.1, base_url=resolved_base_url)
    await provider.validate()
    return f"✓ {provider_name.title()} connection successful!"


def get_available_models(provider_name: str) -> list[str]:
    """Return available model names for a given provider. (Deprecated — models are user-specified now.)"""
    return []


def get_default_models() -> dict[str, str]:
    """Return {provider: default_model} mapping. (Deprecated — models are user-specified now.)"""
    return {}


# ── API Key encryption helpers ────────────────────────────────────────────────
import os as _os
from cryptography.fernet import Fernet as _Fernet, InvalidToken as _InvalidToken
import base64 as _base64


def _get_fernet():
    """Get a Fernet instance from ENCRYPTION_KEY or auto-generate one."""
    raw_key = _os.getenv("ENCRYPTION_KEY", "")
    if raw_key:
        try:
            return _Fernet(raw_key.encode() if isinstance(raw_key, str) else raw_key)
        except (ValueError, TypeError):
            import hashlib
            key = _base64.urlsafe_b64encode(hashlib.sha256(raw_key.encode()).digest())
            log.warning("ENCRYPTION_KEY is not a valid Fernet key — derived a key from it")
            return _Fernet(key)
    else:
        return _Fernet(_Fernet.generate_key())


_fernet = _get_fernet()


def encrypt_api_key(plaintext: str) -> str:
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt_api_key(ciphertext: str) -> str:
    return _fernet.decrypt(ciphertext.encode()).decode()