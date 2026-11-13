"""Command line: `nichescope serve | mcp | map | refresh | read-uploads | meanings`."""
from __future__ import annotations

import argparse
import json
import logging
import sys
import webbrowser

from .config import settings


def _report(text: str) -> None:
    print(f"  {text}", file=sys.stderr)


def _serve(args: argparse.Namespace) -> None:
    import uvicorn

    from .api.app import create_app

    cfg = settings()
    host, port = args.host or cfg.host, args.port or cfg.port
    if not args.no_browser:
        webbrowser.open(f"http://{host}:{port}/")
    uvicorn.run(create_app(auto_refresh=not args.no_auto_refresh), host=host, port=port, log_level="info")


def _mcp(_: argparse.Namespace) -> None:
    from .mcp_server import main

    main()


def _map(args: argparse.Namespace) -> None:
    from .research import mapping

    m = mapping.map_channel(args.channel, args.steps, _report)
    print(json.dumps({"id": m["channel_id"], "title": m["title"], "channels": len(m["channels"])}))


def _refresh(args: argparse.Namespace) -> None:
    from .research import mapping

    m = mapping.refresh(args.map, _report) if args.map else mapping.refresh_due(_report)
    print(m["title"] if m else "no map is due for a refresh")


def _read_uploads(args: argparse.Namespace) -> None:
    from .research import mapping, storage

    m = storage.find(args.map)
    print(json.dumps(mapping.read_uploads(m["channel_id"], limit=args.limit, quota_floor=args.quota_floor,
                                          report=_report), indent=2))


def _demo(args: argparse.Namespace) -> None:
    import os
    from pathlib import Path

    from . import config, demo

    folder = Path(args.folder).resolve()
    got = demo.build(folder)
    os.environ["NICHESCOPE_DATA_DIR"] = str(folder)
    config.settings.cache_clear()
    from .research import database

    database.import_maps()
    print(f"Demo niche written to {folder}: {got['maps']} maps, {got['channels']} channels.")
    print("Start it with NICHESCOPE_DATA_DIR set to that folder, then run: nichescope serve")


def _meanings(args: argparse.Namespace) -> None:
    from .research import database

    print(json.dumps(database.fill_meanings(_report, args.limit)))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="nichescope", description="YouTube niche research.")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("serve", help="run the web app")
    p.add_argument("--host")
    p.add_argument("--port", type=int)
    p.add_argument("--no-browser", action="store_true")
    p.add_argument("--no-auto-refresh", action="store_true", help="do not refresh overdue maps in the background")
    p.set_defaults(func=_serve)

    sub.add_parser("mcp", help="run the MCP server over stdio").set_defaults(func=_mcp)

    p = sub.add_parser("map", help="map a channel")
    p.add_argument("channel")
    p.add_argument("--steps", type=int, default=1)
    p.set_defaults(func=_map)

    p = sub.add_parser("refresh", help="refresh one map, or the most overdue one")
    p.add_argument("map", nargs="?")
    p.set_defaults(func=_refresh)

    p = sub.add_parser("read-uploads", help="read the full uploads of a map's channels into the store")
    p.add_argument("map")
    p.add_argument("--limit", type=int)
    p.add_argument("--quota-floor", type=int, default=2000)
    p.set_defaults(func=_read_uploads)

    p = sub.add_parser("demo", help="write a fictional demo niche into an empty folder")
    p.add_argument("folder")
    p.set_defaults(func=_demo)

    p = sub.add_parser("meanings", help="compute meanings for stored videos")
    p.add_argument("--limit", type=int)
    p.set_defaults(func=_meanings)

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        stream=sys.stderr)
    args.func(args)
