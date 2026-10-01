"""Bookshelf tools over MCP Streamable HTTP for agents outside the hub process (K5).

One endpoint per connector, e.g. Hermes profile `default` -> http://127.0.0.1:8787/mcp/hermes/default/.
The path fixes the agent id the tools act as; the hub stays on 127.0.0.1 and refuses foreign
Origins (app.py), and every write is only a proposal that waits for the user (I1).
"""
from __future__ import annotations

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations

from .tools import INSTRUCTIONS, LIST_DESC, PROPOSE_DESC, READ_DESC, SEARCH_DESC, BookshelfTools, as_text

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False)
PROPOSES = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False)


def mcp_path(agent_id: str) -> str:
    """hermes:default -> /mcp/hermes/default"""
    return "/mcp/" + "/".join(agent_id.split(":"))


def build_server(tools: BookshelfTools, agent: str, port: int):
    """-> (ASGI app to mount at mcp_path(agent), the server's session manager to run in the lifespan)."""
    server = MCPServer(name="sage-os-bookshelf", instructions=INSTRUCTIONS)

    @server.tool(name="search_notes", description=SEARCH_DESC, annotations=READ_ONLY)
    async def search_notes(query: str, limit: int = 10, include_archive: bool = False) -> str:
        return as_text(await tools.search(agent, query, limit, include_archive))

    @server.tool(name="read_note", description=READ_DESC, annotations=READ_ONLY)
    async def read_note(uid: str) -> str:
        return as_text(await tools.read(agent, uid))

    @server.tool(name="propose_note", description=PROPOSE_DESC, annotations=PROPOSES)
    async def propose_note(changes: list[dict], summary: str = "") -> str:
        return as_text(await tools.propose(agent, changes, summary))

    @server.tool(name="list_proposals", description=LIST_DESC, annotations=READ_ONLY)
    async def list_proposals(status: str | None = None) -> str:
        return as_text(await tools.proposals(agent, status))

    hosts = [f"127.0.0.1:{port}", "127.0.0.1", f"localhost:{port}", "localhost"]
    app = server.streamable_http_app(
        streamable_http_path="/", stateless_http=True, json_response=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True, allowed_hosts=hosts,
            allowed_origins=[f"http://{h}" for h in hosts]))
    return app, server.session_manager
