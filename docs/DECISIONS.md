# Architecture Decisions

## 1. Configurable LLM, deterministic local default

**Decision:** Support OpenAI and Anthropic through `AI_PROVIDER`, model,
temperature, and timeout environment variables. Default to `AI_PROVIDER=demo`
with no key or internet dependency.

**Trade-off:** Demo mode is less flexible with unusual language, but is
reproducible, private, and available offline. The LLM may interpret intent and
select allowlisted read tools; deterministic code remains responsible for
validating tool calls, composing UI, and authorizing writes. Sensitive-data
handling and refusals do not depend on the provider.

## 2. Versioned A2UI-equivalent contract

**Decision:** Use the existing Pydantic UI contract, mirrored by strict
TypeScript types, with `schema_version: "1.0"` and a closed component registry.

**Trade-off:** This is less expressive than model-generated HTML, but prevents
executable output and keeps frontend rendering predictable. Unknown components
are rejected or shown as a safe error card.

## 3. MCP over stdio

**Decision:** Launch the official FastMCP server as a local subprocess and
invoke its tools with the MCP Python SDK over stdio.

**Trade-off:** Process startup and lifecycle need supervision, but this keeps a
real interoperable MCP boundary without exposing another network service. MCP
tools reuse the backend finance service layer.

## 4. SQLite for synthetic data and idempotency

**Decision:** Keep demonstration financial data and durable goal idempotency
records in SQLite.

**Trade-off:** SQLite is appropriate for a single-user local prototype and
supports atomic goal-plus-idempotency writes. It is not a multi-user production
database and the in-memory plan/confirmation context expires or is lost on
restart.

## 5. Deterministic offline fallback

**Decision:** Use local intent rules and the same MCP tools and UI contract when
no provider is configured or an LLM call fails.

**Trade-off:** Unsupported phrasings receive a clarification rather than
best-effort model interpretation. Local calculations and the UI remain
available, and the response mode visibly identifies the deterministic
demonstration.

## 6. Explicit UI confirmation and idempotent goal creation

**Decision:** The purchase-plan flow requires a request event followed by a
separate confirmation event. The server verifies the trace, selected savings
option, one-time confirmation capability, and UUID idempotency key before MCP
write execution.

**Trade-off:** The user takes one extra confirmation step. This makes the write
intent visible and lets retries/double clicks replay one result without
duplicating a goal. No transfer or real-money operation is available.
