"""CLI: ``python -m projects.streaming_ws server`` or ``... client``.

Tyro expects flags first; we consume the ``server`` / ``client`` token so
``tyro.cli(ServerConfig|ClientConfig)`` sees only ``--port``-style arguments.
"""

from __future__ import annotations

import sys


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in ("server", "client"):
        print(
            "usage: python -m projects.streaming_ws {server|client} [options...]",
            file=sys.stderr,
        )
        sys.exit(2)
    cmd = sys.argv[1]
    del sys.argv[1]  # shift argv for tyro

    import tyro

    if cmd == "server":
        from projects.streaming_ws.server import ServerConfig, main_server

        main_server(tyro.cli(ServerConfig))
    else:
        from projects.streaming_ws.client import ClientConfig, main_client

        main_client(tyro.cli(ClientConfig))


if __name__ == "__main__":
    main()
