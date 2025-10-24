"""Entry point for Shannot MCP server.

This module provides the main entry point for running the MCP server.
It can be invoked via:
  - python -m shannot.mcp_main
  - shannot-mcp (if installed as separate package)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from shannot.config import create_executor, load_config
from shannot.mcp_server import ShannotMCPServer


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the MCP server."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr,  # MCP uses stderr for logs, stdout for protocol
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="shannot-mcp",
        add_help=True,
        description="Run the Shannot MCP server.",
    )
    _ = parser.add_argument(
        "--profile",
        action="append",
        dest="profiles",
        help="Path or name of sandbox profile to expose (can be specified multiple times).",
    )
    _ = parser.add_argument(
        "--target",
        "-t",
        help="Target executor name from shannot/config.toml (enables remote execution).",
    )
    _ = parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging.",
    )
    return parser


def _coerce_profile_spec(value: str) -> Path | str:
    """Convert profile CLI value into path or name."""
    expanded = Path(value).expanduser()
    if expanded.exists():
        return expanded

    if any(sep in value for sep in ("/", "\\")) or value.endswith(".json") or value.startswith("."):
        return expanded

    return value


def _resolve_profiles(
    cli_profiles: Sequence[str] | None,
    executor_profile: str | None,
) -> list[Path | str] | None:
    """Determine profile specs to load."""
    if cli_profiles:
        return [_coerce_profile_spec(item) for item in cli_profiles]

    if executor_profile:
        return [_coerce_profile_spec(executor_profile)]

    return None


async def main(argv: Sequence[str] | None = None) -> None:
    """Main entry point for MCP server."""
    if argv is None:
        argv = sys.argv[1:]

    parser = _build_parser()
    args = parser.parse_args(list(argv))

    verbose: bool = bool(args.verbose)
    setup_logging(verbose)

    logger = logging.getLogger(__name__)
    logger.info("Starting Shannot MCP server")

    executor = None
    executor_profile: str | None = None

    target: str | None = args.target if args.target else None
    if target:
        logger.info("Using executor target: %s", target)
        try:
            config = load_config()
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Failed to load configuration: %s", exc)
            raise SystemExit(1) from exc

        if target not in config.executor:
            logger.error("Target '%s' not found in configuration", target)
            logger.info("List targets with: shannot remote list")
            raise SystemExit(1)

        executor_config = config.executor[target]
        executor_profile = executor_config.profile

        try:
            executor = create_executor(config, target)
        except Exception as exc:
            logger.error("Failed to create executor '%s': %s", target, exc)
            if "pip install shannot[remote]" in str(exc):
                logger.info("Install remote support with: pip install shannot[remote]")
            raise SystemExit(1) from exc

    profiles: list[str] | None = args.profiles if args.profiles else None
    profile_specs = _resolve_profiles(profiles, executor_profile)

    # Create and run server
    server = None
    try:
        server = ShannotMCPServer(profile_specs, executor, executor_label=target)
        logger.info("Loaded %s profiles", len(server.deps_by_profile))
        for name in server.deps_by_profile.keys():
            logger.info("  - %s", name)

        await server.run()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except SystemExit:
        raise
    except Exception as e:
        logger.error("Server error: %s", e, exc_info=True)
        raise SystemExit(1) from e
    finally:
        if server is not None:
            try:
                await server.cleanup()
            except Exception as exc:  # pragma: no cover - best effort cleanup
                logger.debug("Failed to cleanup server resources: %s", exc)


def entrypoint() -> None:
    """Synchronous entrypoint for console_scripts."""

    asyncio.run(main())


if __name__ == "__main__":
    entrypoint()
