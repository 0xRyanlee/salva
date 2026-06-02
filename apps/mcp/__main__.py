"""
Entry point: python3 -m apps.mcp

Defaults to stdio transport (Claude Code / Claude Desktop compatible).
Pass --http <port> for HTTP transport (testing / other clients).
"""
import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description="Salva MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport mode (default: stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8001,
        help="Port for HTTP transport (default: 8001)",
    )
    args = parser.parse_args()

    from apps.mcp.server import mcp
    from apps.mcp.server import validate_auth_environment

    if not getattr(mcp, "available", True):
        print(
            "ERROR: mcp package not installed.\n"
            "Install with: pip install 'salva-runtime[mcp]'\n"
            "or: pip install mcp",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.transport == "http":
        validate_auth_environment("http")
        import uvicorn
        uvicorn.run(
            mcp.streamable_http_app(),
            host="0.0.0.0",
            port=args.port,
        )
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
