"""Synchronous JSON-RPC 2.0 protocol implementation for MCP over stdin/stdout.

This module implements the MCP wire protocol using pure Python stdlib.
No async/asyncio - simple blocking read/write for stdio transport.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from typing import Any


def read_message() -> dict[str, Any] | None:
    """Read one JSON-RPC message from stdin.

    Returns
    -------
    dict[str, Any] | None
        Parsed JSON message, or None on EOF.

    Notes
    -----
    Blocks until a complete line is available. Each message is one line
    of JSON followed by newline (JSON-RPC over stdio convention).
    """
    try:
        line = sys.stdin.readline()
        if not line:
            return None
        return json.loads(line)
    except json.JSONDecodeError as e:
        # Invalid JSON - log and skip
        print(f"Warning: Invalid JSON: {e}", file=sys.stderr)
        return None
    except KeyboardInterrupt:
        return None


def write_message(msg: dict[str, Any]) -> None:
    """Write one JSON-RPC message to stdout.

    Parameters
    ----------
    msg : dict[str, Any]
        JSON-RPC message to send.

    Notes
    -----
    Writes one line of JSON followed by newline, then flushes stdout
    to ensure immediate delivery.
    """
    try:
        json.dump(msg, sys.stdout)
        sys.stdout.write("\n")
        sys.stdout.flush()
    except (OSError, BrokenPipeError):
        # Client disconnected - exit gracefully
        sys.exit(0)


def serve(handler: Callable[[dict[str, Any]], dict[str, Any] | None]) -> None:
    """Main serving loop for MCP over stdin/stdout.

    Parameters
    ----------
    handler : Callable[[dict[str, Any]], dict[str, Any] | None]
        Function that processes incoming requests and returns responses.
        Should return None for notifications (no response needed).

    Notes
    -----
    Runs forever until stdin is closed or handler raises an exception.
    This is synchronous - one request at a time.

    Examples
    --------
    >>> def my_handler(msg):
    ...     method = msg.get("method")
    ...     if method == "ping":
    ...         return {"jsonrpc": "2.0", "result": "pong", "id": msg["id"]}
    ...     return None
    >>> serve(my_handler)  # doctest: +SKIP
    """
    while True:
        msg = read_message()
        if msg is None:
            break

        try:
            response = handler(msg)
            if response is not None:
                write_message(response)
        except Exception as e:
            # Handler raised an exception - send error response if possible
            if "id" in msg:
                error_response = {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32603,  # Internal error
                        "message": str(e),
                    },
                    "id": msg["id"],
                }
                write_message(error_response)
