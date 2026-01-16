"""
Entry point for running OSlash Local server as a module.

Usage:
    python -m oslash
    python -m oslash --port 8080
    python -m oslash --reload
"""

import argparse
import uvicorn

from oslash.config import get_settings


def main():
    """Run the OSlash Local server."""
    parser = argparse.ArgumentParser(
        description="OSlash Local - Search your files locally"
    )
    parser.add_argument(
        "--host",
        default=None,
        help="Host to bind to (default: from config or 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port to bind to (default: from config or 8000)",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development",
    )
    parser.add_argument(
        "--log-level",
        default=None,
        choices=["debug", "info", "warning", "error", "critical"],
        help="Log level (default: from config or info)",
    )

    args = parser.parse_args()
    settings = get_settings()

    # Use args or fall back to settings
    host = args.host or settings.host
    port = args.port or settings.port
    log_level = args.log_level or settings.log_level.lower()

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                     OSlash Local Server                       ║
╠══════════════════════════════════════════════════════════════╣
║  Starting server at http://{host}:{port:<5}                       ║
║  API docs at http://{host}:{port}/docs                        ║
║  Press Ctrl+C to stop                                         ║
╚══════════════════════════════════════════════════════════════╝
""")

    uvicorn.run(
        "oslash.main:app",
        host=host,
        port=port,
        reload=args.reload,
        log_level=log_level,
    )


if __name__ == "__main__":
    main()

