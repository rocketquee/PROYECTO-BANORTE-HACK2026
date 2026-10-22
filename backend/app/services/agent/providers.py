"""Configurable AI providers. The backend never talks to a provider directly
from the UI layer — everything goes through this interface.

If no API key is configured, `get_provider()` returns None and the orchestrator
runs the explicit demo agent (rule-based, no network calls, real MCP tools).
"""
import json

import httpx
from pydantic import BaseModel, ConfigDict, Field, Field

from app.core import config


class ProviderError(RuntimeError):
    pass


class StrictProviderModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProviderToolCall(StrictProviderModel):
    id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=100)
    arguments: str = Field(max_length=10_000)


class ProviderTurn(StrictProviderModel):
    content: str | None = None
    tool_calls: list[ProviderToolCall] = Field(default_factory=list, max_length=8)
    raw_message: dict


class OpenAIProvider:
    name = "openai"

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
            "tools": payload_tools,
        }
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
            msg = resp.json()["choices"][0]["message"]
            out = {
                "content": msg.get("content"),
                "tool_calls": [
                    {"id": tc["id"], "name": tc["function"]["name"],
                     "arguments": tc["function"]["arguments"]}
                    for tc in msg.get("tool_calls") or []
                ],
                "raw_message": msg,
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


class AnthropicProvider:
    name = "anthropic"

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
            "tools": payload_tools,
        }
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
            out = {
                "content": text,
                "tool_calls": tool_calls,
                "raw_message": {"role": "assistant", "content": content},
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


def get_provider():
    provider = config.AI_PROVIDER.lower()
    if provider == "openai" and config.OPENAI_API_KEY:
        return OpenAIProvider()
    if provider == "anthropic" and config.ANTHROPIC_API_KEY:
        return AnthropicProvider()
    return None


def provider_mode() -> str:
    return "live" if get_provider() else "demo"
