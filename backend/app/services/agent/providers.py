"""Configurable AI providers. The backend never talks to a provider directly
from the UI layer — everything goes through this interface.

If no API key is configured, `get_provider()` returns None and the orchestrator
runs the explicit demo agent (rule-based, no network calls, real MCP tools).
"""
import json

import httpx

from app.core import config


class ProviderError(RuntimeError):
    pass


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
            "messages": [{"role": "system", "content": system}, *messages],
            "tools": payload_tools,
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{config.OPENAI_BASE_URL}/chat/completions",
                json=body,
                headers={"Authorization": f"Bearer {config.OPENAI_API_KEY}"},
            )
        if resp.status_code != 200:
            raise ProviderError(f"OpenAI HTTP {resp.status_code}: {resp.text[:200]}")
        msg = resp.json()["choices"][0]["message"]
        return {
            "content": msg.get("content"),
            "tool_calls": [
                {"id": tc["id"], "name": tc["function"]["name"], "arguments": tc["function"]["arguments"]}
                for tc in msg.get("tool_calls") or []
            ],
            "raw_message": msg,
        }

    def assistant_message(self, out: dict) -> dict:
        return out["raw_message"]

    def tool_result_message(self, call: dict, result: dict) -> dict:
        return {"role": "tool", "tool_call_id": call["id"], "content": json.dumps(result, ensure_ascii=False)}


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
            "system": system,
            "messages": messages,
            "tools": payload_tools,
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.anthropic.com/v1/messages",
                json=body,
                headers={"x-api-key": config.ANTHROPIC_API_KEY,
                         "anthropic-version": "2023-06-01"},
            )
        if resp.status_code != 200:
            raise ProviderError(f"Anthropic HTTP {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        tool_calls = [
            {"id": b["id"], "name": b["name"], "arguments": json.dumps(b.get("input", {}), ensure_ascii=False)}
            for b in data.get("content", []) if b.get("type") == "tool_use"
        ]
        return {"content": text, "tool_calls": tool_calls, "raw_message": {"role": "assistant", "content": data.get("content", [])}}

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
