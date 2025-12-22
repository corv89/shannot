"""Entry point for shannot-mcp MCP server command.

This module provides the main() function that serves as the console script
entry point for the `shannot-mcp` command.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .mcp import ShannotMCPServer, serve

logger = logging.getLogger(__name__)


def main() -> int:
    """Main entry point for shannot-mcp command.

    Returns
    -------
    int
        Exit code (0 for success, non-zero for failure).
    """
    parser = argparse.ArgumentParser(
        prog="shannot-mcp",
        description="MCP server for Shannot PyPy sandbox",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start MCP server with default profiles
  shannot-mcp

  # Start with custom profile
  shannot-mcp --profile ~/.config/shannot/custom.json

  # Start with verbose logging
  shannot-mcp --verbose

The server communicates via JSON-RPC over stdin/stdout and is designed
to be launched by MCP clients like Claude Desktop or Claude Code.
        """,
    )

    parser.add_argument(
        "--profile",
        action="append",
        type=Path,
        metavar="PATH",
        help="Path to approval profile JSON file (can be specified multiple times)",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose debug logging to stderr",
    )

    args = parser.parse_args()

    try:
        # Create Shannot MCP server
        server = ShannotMCPServer(
            profile_paths=args.profile,
            verbose=args.verbose,
        )

        logger.info("Shannot MCP server started")
        logger.info(f"Available profiles: {list(server.profiles.keys())}")
        logger.info(f"Runtime available: {server.runtime is not None}")

        # Run serving loop (blocks until stdin closes)
        serve(server.handle_request)

        logger.info("Shannot MCP server stopped")
        return 0

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 130

    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
