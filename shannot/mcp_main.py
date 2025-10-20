"""Entry point for Shannot MCP server.

This module provides the main entry point for running the MCP server.
It can be invoked via:
  - python -m shannot.mcp_main
  - shannot-mcp (if installed as separate package)
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from shannot.mcp_server import ShannotMCPServer


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the MCP server."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr,  # MCP uses stderr for logs, stdout for protocol
    )


async def main() -> None:
    """Main entry point for MCP server."""
    # Parse simple command line args
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    setup_logging(verbose)

    logger = logging.getLogger(__name__)
    logger.info("Starting Shannot MCP server")

    # Discover profiles
    profile_paths: list[Path] = []

    # Check if specific profiles were requested
    if "--profile" in sys.argv:
        idx = sys.argv.index("--profile")
        if idx + 1 < len(sys.argv):
            profile_path = Path(sys.argv[idx + 1])
            if profile_path.exists():
                profile_paths.append(profile_path)
            else:
                logger.error(f"Profile not found: {profile_path}")
                sys.exit(1)

    # Create and run server
    try:
        server = ShannotMCPServer(profile_paths if profile_paths else None)
        logger.info(f"Loaded {len(server.deps_by_profile)} profiles")
        for name in server.deps_by_profile.keys():
            logger.info(f"  - {name}")

        await server.run()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
