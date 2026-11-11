"""Configurable AI providers. The backend never talks to a provider directly
from the UI layer — everything goes through this interface.

If no API key is configured, `get_provider()` returns None and the orchestrator
runs the explicit demo agent (rule-based, no network calls, real MCP tools).
"""
import asyncio
import json
import logging
import time

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.core import config

logger = logging.getLogger("banorte")


class ProviderError(RuntimeError):
    pass


class StrictProviderModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProviderToolCall(StrictProviderModel):
    id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=100)
    arguments: str = Field(max_length=10_000)


class ProviderUsage(StrictProviderModel):
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)


class ProviderTurn(StrictProviderModel):
    content: str | None = None
    tool_calls: list[ProviderToolCall] = Field(default_factory=list, max_length=8)
    raw_message: dict
    usage: ProviderUsage | None = None


class CompleteMixin:
    """Segundo paso (planificador): una respuesta de texto, sin herramientas."""

    async def complete(self, system: str, messages: list[dict]) -> str:
        raw = await self.chat_with_tools(system, messages, [])
        turn = ProviderTurn.model_validate(raw)
        return turn.content or ""


class OpenAIProvider(CompleteMixin):
    name = "openai"

    @property
    def model(self) -> str:
        return config.OPENAI_MODEL

    async def chat_with_tools(self, system: str, messages: list[dict], tools: list[dict]) -> dict:
        payload_tools = [
            {"type": "function", "function": {"name": t["name"], "description": t["description"],
                                              "parameters": t["input_schema"]}}
            for t in tools
        ]
        body = {
            "model": config.OPENAI_MODEL,
            "temperature": config.AI_TEMPERATURE,
            "messages": [{"role": "system", "content": system}, *messages],
        }
        if payload_tools:
            body["tools"] = payload_tools
        async with httpx.AsyncClient(timeout=config.AI_TIMEOUT_SECONDS) as client:
            try:
                resp = await client.post(
                    f"{config.OPENAI_BASE_URL}/chat/completions",
                    json=body,
                    headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"},
                )
            except httpx.HTTPError as exc:
                raise ProviderError("No se pudo contactar el proveedor OpenAI.") from exc
        if resp.status_code != 200:
            raise ProviderError(f"OpenAI devolvió HTTP {resp.status_code}.")
        try:
            data = resp.json()
            msg = data["choices"][0]["message"]
            usage = data.get("usage") or {}
            out = {
                "content": msg.get("content"),
                "tool_calls": [
                    {"id": tc["id"], "name": tc["function"]["name"],
                     "arguments": tc["function"]["arguments"]}
                    for tc in msg.get("tool_calls") or []
                ],
                "raw_message": msg,
                "usage": (
                    {
                        "prompt_tokens": usage.get("prompt_tokens", 0),
                        "completion_tokens": usage.get("completion_tokens", 0),
                    }
                    if usage else None
                ),
            }
            ProviderTurn.model_validate(out)
            return out
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError("OpenAI devolvió una respuesta inválida.") from exc

    def assistant_message(self, out: dict) -> dict:
        return out["raw_message"]

    def tool_result_message(self, call: dict, result: dict) -> dict:
        return {"role": "tool", "tool_call_id": call["id"],
                "content": json.dumps(result, ensure_ascii=False)}


class AnthropicProvider(CompleteMixin):
    name = "anthropic"

    @property
    def model(self) -> str:
        return config.ANTHROPIC_MODEL

    async def chat_with_tools(self, system: str, messages: list[dict], tools: list[dict]) -> dict:
        payload_tools = [
            {"name": t["name"], "description": t["description"], "input_schema": t["input_schema"]}
            for t in tools
        ]
        body = {
            "model": config.ANTHROPIC_MODEL,
            "max_tokens": 1500,
            "temperature": config.AI_TEMPERATURE,
            "system": system,
            "messages": messages,
        }
        if payload_tools:
            body["tools"] = payload_tools
        async with httpx.AsyncClient(timeout=config.AI_TIMEOUT_SECONDS) as client:
            try:
                resp = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    json=body,
                    headers={"x-api-key": config.ANTHROPIC_API_KEY,
                             "anthropic-version": "2023-06-01"},
                )
            except httpx.HTTPError as exc:
                raise ProviderError("No se pudo contactar el proveedor Anthropic.") from exc
        if resp.status_code != 200:
            raise ProviderError(f"Anthropic devolvió HTTP {resp.status_code}.")
        try:
            data = resp.json()
            content = data.get("content", [])
            text = "".join(b.get("text", "") for b in content if b.get("type") == "text")
            tool_calls = [
                {"id": b["id"], "name": b["name"],
                 "arguments": json.dumps(b.get("input", {}), ensure_ascii=False)}
                for b in content if b.get("type") == "tool_use"
            ]
            usage = data.get("usage") or {}
            out = {
                "content": text,
                "tool_calls": tool_calls,
                "raw_message": {"role": "assistant", "content": content},
                "usage": (
                    {
                        "prompt_tokens": usage.get("input_tokens", 0),
                        "completion_tokens": usage.get("output_tokens", 0),
                    }
                    if usage else None
                ),
            }
            ProviderTurn.model_validate(out)
            return out
        except (ValueError, KeyError, TypeError) as exc:
            raise ProviderError("Anthropic devolvió una respuesta inválida.") from exc

    def assistant_message(self, out: dict) -> dict:
        return out["raw_message"]

    def tool_result_message(self, call: dict, result: dict) -> dict:
        return {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": call["id"],
                         "content": json.dumps(result, ensure_ascii=False)}],
        }


HEALTH_TOOL = {
    "name": "health_check",
    "description": "Responde si el proveedor puede invocar herramientas.",
    "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
}


class OpenAICompatibleProvider(CompleteMixin):
    """OpenAI chat-completions client with explicit endpoint settings.

    Used by the unified `LLM_*` configuration for OpenAI and local
    OpenAI-compatible servers such as Ollama. The legacy `OpenAIProvider`
    remains untouched for `AI_PROVIDER=openai`.
    """

    def __init__(self, name: str, model: str, base_url: str, api_key: str) -> None:
        self.name = name
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key

    @property
    def model(self) -> str:
        return self._model

    async def chat_with_tools(self, system: str, messages: list[dict], tools: list[dict]) -> dict:
        payload_tools = [
            {"type": "function", "function": {"name": t["name"], "description": t["description"],
                                              "parameters": t["input_schema"]}}
            for t in tools
        ]
        body = {
            "model": self._model,
            "temperature": config.AI_TEMPERATURE,
            "messages": [{"role": "system", "content": system}, *messages],
        }
        if payload_tools:
            body["tools"] = payload_tools
        async with httpx.AsyncClient(timeout=config.AI_TIMEOUT_SECONDS) as client:
            try:
                resp = await client.post(
                    f"{self._base_url}/chat/completions",
                    json=body,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
            except httpx.HTTPError as exc:
                raise ProviderError("No se pudo contactar el proveedor de IA.") from exc
        if resp.status_code != 200:
            raise ProviderError(f"El proveedor de IA devolvió HTTP {resp.status_code}.")
        try:
            data = resp.json()
            msg = data["choices"][0]["message"]
            usage = data.get("usage") or {}
            out = {
                "content": msg.get("content"),
                "tool_calls": [
                    {"id": tc["id"], "name": tc["function"]["name"],
                     "arguments": tc["function"]["arguments"]}
                    for tc in msg.get("tool_calls") or []
                ],
                "raw_message": msg,
                "usage": (
                    {
                        "prompt_tokens": usage.get("prompt_tokens", 0),
                        "completion_tokens": usage.get("completion_tokens", 0),
                    }
                    if usage else None
                ),
            }
            ProviderTurn.model_validate(out)
            return out
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError("El proveedor de IA devolvió una respuesta inválida.") from exc

    async def healthcheck(self, timeout: float = 5.0) -> dict:
        body = {
            "model": self._model,
            "temperature": 0,
            "max_tokens": 5,
            "messages": [
                {"role": "system", "content": "Invoca la herramienta health_check."},
                {"role": "user", "content": "ping"},
            ],
            "tools": [{"type": "function", "function": {
                "name": HEALTH_TOOL["name"],
                "description": HEALTH_TOOL["description"],
                "parameters": HEALTH_TOOL["input_schema"],
            }}],
            "tool_choice": {"type": "function", "function": {"name": HEALTH_TOOL["name"]}},
        }
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                resp = await client.post(
                    f"{self._base_url}/chat/completions",
                    json=body,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
            except httpx.HTTPError as exc:
                raise ProviderError("No se pudo contactar el proveedor de IA.") from exc
        if resp.status_code != 200:
            raise ProviderError(f"El proveedor de IA devolvió HTTP {resp.status_code}.")
        try:
            msg = resp.json()["choices"][0]["message"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError("El proveedor de IA devolvió una respuesta inválida.") from exc
        calls = msg.get("tool_calls") or []
        tools_supported = any(
            call.get("function", {}).get("name") == HEALTH_TOOL["name"]
            for call in calls if isinstance(call, dict)
        )
        return {"reachable": True, "tools_supported": tools_supported}

    def assistant_message(self, out: dict) -> dict:
        return out["raw_message"]

    def tool_result_message(self, call: dict, result: dict) -> dict:
        return {"role": "tool", "tool_call_id": call["id"],
                "content": json.dumps(result, ensure_ascii=False)}


class AnthropicCompatibleProvider(CompleteMixin):
    """Anthropic Messages client with explicit endpoint settings."""

    name = "anthropic"

    def __init__(self, model: str, base_url: str, api_key: str) -> None:
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key

    @property
    def model(self) -> str:
        return self._model

    async def chat_with_tools(self, system: str, messages: list[dict], tools: list[dict]) -> dict:
        payload_tools = [
            {"name": t["name"], "description": t["description"], "input_schema": t["input_schema"]}
            for t in tools
        ]
        body = {
            "model": self._model,
            "max_tokens": 1500,
            "temperature": config.AI_TEMPERATURE,
            "system": system,
            "messages": messages,
        }
        if payload_tools:
            body["tools"] = payload_tools
        async with httpx.AsyncClient(timeout=config.AI_TIMEOUT_SECONDS) as client:
            try:
                resp = await client.post(
                    f"{self._base_url}/messages",
                    json=body,
                    headers={"x-api-key": self._api_key,
                             "anthropic-version": "2023-06-01"},
                )
            except httpx.HTTPError as exc:
                raise ProviderError("No se pudo contactar el proveedor Anthropic.") from exc
        if resp.status_code != 200:
            raise ProviderError(f"Anthropic devolvió HTTP {resp.status_code}.")
        try:
            data = resp.json()
            content = data.get("content", [])
            if not isinstance(content, list):
                raise TypeError("content inválido")
            text = "".join(b.get("text", "") for b in content if b.get("type") == "text")
            tool_calls = [
                {"id": b["id"], "name": b["name"],
                 "arguments": json.dumps(b.get("input", {}), ensure_ascii=False)}
                for b in content if b.get("type") == "tool_use"
            ]
            usage = data.get("usage") or {}
            out = {
                "content": text,
                "tool_calls": tool_calls,
                "raw_message": {"role": "assistant", "content": content},
                "usage": (
                    {
                        "prompt_tokens": usage.get("input_tokens", 0),
                        "completion_tokens": usage.get("output_tokens", 0),
                    }
                    if usage else None
                ),
            }
            ProviderTurn.model_validate(out)
            return out
        except (ValueError, KeyError, TypeError) as exc:
            raise ProviderError("Anthropic devolvió una respuesta inválida.") from exc

    async def healthcheck(self, timeout: float = 5.0) -> dict:
        body = {
            "model": self._model,
            "max_tokens": 5,
            "system": "Invoca la herramienta health_check.",
            "messages": [{"role": "user", "content": "ping"}],
            "tools": [{
                "name": HEALTH_TOOL["name"],
                "description": HEALTH_TOOL["description"],
                "input_schema": HEALTH_TOOL["input_schema"],
            }],
            "tool_choice": {"type": "tool", "name": HEALTH_TOOL["name"]},
        }
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                resp = await client.post(
                    f"{self._base_url}/messages",
                    json=body,
                    headers={"x-api-key": self._api_key,
                             "anthropic-version": "2023-06-01"},
                )
            except httpx.HTTPError as exc:
                raise ProviderError("No se pudo contactar el proveedor Anthropic.") from exc
        if resp.status_code != 200:
            raise ProviderError(f"Anthropic devolvió HTTP {resp.status_code}.")
        try:
            content = resp.json()["content"]
            if not isinstance(content, list):
                raise TypeError("content inválido")
        except (ValueError, KeyError, TypeError) as exc:
            raise ProviderError("Anthropic devolvió una respuesta inválida.") from exc
        tools_supported = any(
            block.get("type") == "tool_use" and block.get("name") == HEALTH_TOOL["name"]
            for block in content if isinstance(block, dict)
        )
        return {"reachable": True, "tools_supported": tools_supported}

    def assistant_message(self, out: dict) -> dict:
        return out["raw_message"]

    def tool_result_message(self, call: dict, result: dict) -> dict:
        return {
            "role": "user",
            "content": [{"type": "tool_result", "tool_use_id": call["id"],
                         "content": json.dumps(result, ensure_ascii=False)}],
        }


_health_status: dict | None = None


def _configured_provider() -> object | None:
    provider = config.LLM_PROVIDER.strip().lower()
    if not provider:
        legacy = config.AI_PROVIDER.strip().lower()
        if legacy == "openai" and config.OPENAI_API_KEY:
            return OpenAICompatibleProvider(
                name="openai",
                model=config.OPENAI_MODEL,
                base_url=config.OPENAI_BASE_URL,
                api_key=config.OPENAI_API_KEY,
            )
        if legacy == "anthropic" and config.ANTHROPIC_API_KEY:
            return AnthropicCompatibleProvider(
                model=config.ANTHROPIC_MODEL,
                base_url="https://api.anthropic.com/v1",
                api_key=config.ANTHROPIC_API_KEY,
            )
        return None
    if provider in ("demo", "none"):
        return None
    if provider in ("openai", "ollama", "local", "openai-compatible", "openai_compatible"):
        local = provider in ("ollama", "local")
        api_key = config.LLM_API_KEY or ("" if local else config.OPENAI_API_KEY)
        if not local and not api_key:
            return None
        base_url = (config.LLM_BASE_URL
                    or ("http://localhost:11434/v1" if local else config.OPENAI_BASE_URL))
        model = config.LLM_MODEL or ("llama3.2" if local else config.OPENAI_MODEL)
        return OpenAICompatibleProvider(
            name="ollama" if local else "openai",
            model=model,
            base_url=base_url,
            api_key=api_key or "ollama",
        )
    if provider == "anthropic":
        api_key = config.LLM_API_KEY or config.ANTHROPIC_API_KEY
        if not api_key:
            return None
        return AnthropicCompatibleProvider(
            model=config.LLM_MODEL or config.ANTHROPIC_MODEL,
            base_url=config.LLM_BASE_URL or "https://api.anthropic.com/v1",
            api_key=api_key,
        )
    return None


def configured_provider_name() -> str:
    explicit = config.LLM_PROVIDER.strip().lower()
    if explicit:
        if explicit in ("demo", "none"):
            return "none"
        if explicit in ("local", "ollama"):
            return "ollama"
        return explicit
    legacy = config.AI_PROVIDER.strip().lower()
    return legacy if legacy in ("openai", "anthropic") else "none"


def configured_model() -> str | None:
    if not config.LLM_PROVIDER.strip():
        legacy = config.AI_PROVIDER.strip().lower()
        if legacy == "openai":
            return config.OPENAI_MODEL
        if legacy == "anthropic":
            return config.ANTHROPIC_MODEL
        return None
    name = configured_provider_name()
    if name == "none":
        return None
    if name == "anthropic":
        return config.LLM_MODEL or config.ANTHROPIC_MODEL
    if name == "ollama":
        return config.LLM_MODEL or "llama3.2"
    return config.LLM_MODEL or config.OPENAI_MODEL


def get_provider():
    explicit = config.LLM_PROVIDER.strip().lower()
    if explicit:
        if explicit in ("demo", "none"):
            return None
        if _health_status is not None and _health_status.get("mode") != "live":
            return None
        return _configured_provider()
    provider = config.AI_PROVIDER.lower()
    healthy = _health_status is None or _health_status.get("mode") == "live"
    if provider == "openai" and config.OPENAI_API_KEY:
        return OpenAIProvider() if healthy else None
    if provider == "anthropic" and config.ANTHROPIC_API_KEY:
        return AnthropicProvider() if healthy else None
    return None


def provider_mode() -> str:
    return "live" if get_provider() else "demo"


async def check_provider_health(provider=None, timeout: float | None = None) -> dict:
    """Ping the configured provider once and cache the operational status.

    A failure never raises: the orchestrator simply falls back to the
    deterministic local agent.
    """
    global _health_status
    name = getattr(provider, "name", None) if provider is not None else configured_provider_name()
    model = getattr(provider, "model", None) if provider is not None else configured_model()
    if provider is None:
        provider = _configured_provider()
    if provider is None:
        _health_status = {
            "name": name or "none",
            "model": model,
            "reachable": False,
            "tools_supported": False,
            "mode": "demo",
            "reason": "not_configured" if (name or "none") == "none" else "missing_credentials",
            "latency_ms": None,
        }
        return dict(_health_status)

    limit = float(timeout if timeout is not None else config.LLM_HEALTHCHECK_TIMEOUT_SECONDS)
    started = time.monotonic()
    reachable = False
    tools_supported = False
    reason: str | None = None
    try:
        result = await asyncio.wait_for(provider.healthcheck(timeout=limit), timeout=limit + 0.5)
        reachable = bool(result.get("reachable"))
        tools_supported = bool(result.get("tools_supported"))
        reason = result.get("reason")
    except asyncio.TimeoutError:
        reason = "timeout"
    except Exception as exc:  # noqa: BLE001 - degrade to demo, never crash startup
        reason = f"error:{type(exc).__name__}"
    if not reachable:
        reason = reason or "unreachable"
    elif not tools_supported:
        reason = reason or "tools_unsupported"
    _health_status = {
        "name": name or "none",
        "model": model,
        "reachable": reachable,
        "tools_supported": tools_supported,
        "mode": "live" if reachable and tools_supported else "demo",
        "reason": reason,
        "latency_ms": int((time.monotonic() - started) * 1000),
    }
    return dict(_health_status)


def provider_health_report() -> dict:
    if _health_status is not None:
        return dict(_health_status)
    name = configured_provider_name()
    return {
        "name": name,
        "model": configured_model(),
        "reachable": False,
        "tools_supported": False,
        "mode": "demo",
        "reason": "not_checked",
        "latency_ms": None,
    }


def reset_provider_health() -> None:
    global _health_status
    _health_status = None
