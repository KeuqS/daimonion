# References

External sources consulted during template design, kept to what actually
shaped the output. Consulted-but-rejected sources are not listed — their
verdicts live in `TODO.md` next to the decision.

## MCP scaffold

- [MCP Python SDK で MCP サーバーを作ってみる](https://zenn.dev/kiitosu/articles/31f55b99c33ce5)
  (Zenn, 2025/06) — v1-era intro, but its three-primitive layout (tool /
  resource / prompt) confirmed the scaffold was missing `prompt` and
  resource templates. Led to `review_code` + `greeting://{name}`.
- [mcp-cookie-cutter](https://github.com/codingthefuturewithai/mcp-cookie-cutter)
  — example-rich but pinned to SDK `<2.0` (`FastMCP`), so the foundation
  predates this template's v2 (`MCPServer`) port. Only the example breadth
  was referenced; its decorator layer, Streamlit UI, SQLite logging and
  JIRA DevFlow were judged out of scope.
- [MCP Deploy & scale](https://py.sdk.modelcontextprotocol.io/run/deploy/) —
  official SDK docs. Basis for the "no MCP-specific Docker recipe" position
  in the [MCP how-to](../how-to/mcp.md): process management and auth stay
  outside the scaffold.
- [modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers) —
  the official reference implementations (educational, not production-ready).
  Basis for the [distribution recipe](../how-to/mcp-distribute.md): the
  `everything` shape reference, the `filesystem` access-control pattern, and
  the `uvx mcp-server-<name>` + registry publication model.
- [Model Context Protocol](https://modelcontextprotocol.io) — the spec
  itself. Referenced for transport status (SSE deprecated → streamable-http)
  and `TransportSecuritySettings` semantics.
