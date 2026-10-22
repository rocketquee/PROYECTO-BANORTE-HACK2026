"""Real MCP client (official `mcp` Python SDK, stdio transport).

The backend spawns `mcp-server/server.py` as a subprocess and talks to it over
the Model Context Protocol — tool discovery (list_tools) and execution
(call_tool) go through the protocol, not HTTP wrappers.
"""
import json
import os
import sys
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.core import database
from app.core.config import MCP_SERVER_PATH


class MCPClientError(RuntimeError):
    pass


class MCPFinanceClient:
    def __init__(self) -> None:
        self._stack: AsyncExitStack | None = None
        self.session: ClientSession | None = None
        self.tools: list = []

    @property
    def available(self) -> bool:
        return self.session is not None

    async def start(self) -> None:
        self._stack = AsyncExitStack()
        params = StdioServerParameters(
            command=sys.executable,
            args=[str(MCP_SERVER_PATH)],
            env={**os.environ, "BANORTE_DB_PATH": str(database.DB_PATH)},
        )
        try:
            read, write = await self._stack.enter_async_context(stdio_client(params))
            self.session = await self._stack.enter_async_context(ClientSession(read, write))
            await self.session.initialize()
            result = await self.session.list_tools()
            self.tools = result.tools
        except Exception:
            await self.stop()
            raise

    async def call(self, name: str, arguments: dict) -> dict:
        if not self.available:
            raise MCPClientError("El servidor MCP no está disponible.")
        result = await self.session.call_tool(name, arguments)
        if result.isError:
            text = "".join(getattr(b, "text", "") for b in result.content)
            raise MCPClientError(text or f"La herramienta MCP '{name}' devolvió un error.")
        structured = getattr(result, "structuredContent", None)
        if isinstance(structured, dict):
            return structured
        for block in result.content:
            if getattr(block, "type", "") == "text":
                try:
                    return json.loads(block.text)
                except json.JSONDecodeError:
                    return {"text": block.text}
        return {}

    def tool_specs(self) -> list[dict]:
        """Tool descriptions exposed by the MCP server, for LLM providers."""
        return [
            {"name": t.name, "description": t.description or "", "input_schema": t.inputSchema}
            for t in self.tools
        ]

    async def stop(self) -> None:
        if self._stack:
            try:
                await self._stack.aclose()
            except Exception:
                pass
        self._stack = None
        self.session = None
        self.tools = []


mcp_client = MCPFinanceClient()
