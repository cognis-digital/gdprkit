"""GDPRKIT MCP server — exposes scan() as an MCP tool for Cognis.Studio."""
from __future__ import annotations
from gdprkit.core import scan, to_json

def serve() -> int:
    """Start an MCP stdio server. Requires the optional 'mcp' extra:
        pip install "cognis-gdprkit[mcp]"
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except Exception:
        print("Install the MCP extra: pip install 'cognis-gdprkit[mcp]'")
        return 1
    app = FastMCP("gdprkit")

    @app.tool()
    def gdprkit_scan(target: str) -> str:
        """GDPR/CCPA DSAR, RoPA, and cookie-consent toolkit. Returns JSON findings."""
        return to_json(scan(target))

    app.run()
    return 0
