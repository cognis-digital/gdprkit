"""GDPRKIT MCP server -- exposes audit functions as MCP tools for Cognis.Studio."""
from __future__ import annotations

import json
from gdprkit.core import DSARTracker, validate_ropa, audit_cookies


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
    def gdprkit_dsar(records_json: str) -> str:
        """Evaluate DSAR records for GDPR deadline compliance. Returns JSON report."""
        records = json.loads(records_json)
        return json.dumps(DSARTracker.from_records(records).report(), indent=2)

    @app.tool()
    def gdprkit_ropa(records_json: str) -> str:
        """Validate RoPA entries against Art. 30 requirements. Returns JSON report."""
        records = json.loads(records_json)
        return json.dumps(validate_ropa(records), indent=2)

    @app.tool()
    def gdprkit_cookies(records_json: str) -> str:
        """Audit cookie-consent compliance (ePrivacy Art. 5(3)). Returns JSON report."""
        records = json.loads(records_json)
        return json.dumps(audit_cookies(records), indent=2)

    app.run()
    return 0