from __future__ import annotations

import argparse
import json
import os
import sys
from http.server import ThreadingHTTPServer
from typing import Sequence

from urirun.host import host_dashboard

SERVICE_ID = "chat"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8194


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if not value:
        return default
    return int(value)


def default_host() -> str:
    return os.environ.get("URIRUN_CHAT_HOST", DEFAULT_HOST)


def default_port() -> int:
    return _env_int("URIRUN_CHAT_PORT", DEFAULT_PORT)


def service_manifest() -> dict:
    return {
        "id": SERVICE_ID,
        "kind": "service",
        "name": "urirun-service-chat",
        "label": "urirun chat/operator dashboard",
        "defaultHost": DEFAULT_HOST,
        "defaultPort": DEFAULT_PORT,
        "env": {
            "host": "URIRUN_CHAT_HOST",
            "port": "URIRUN_CHAT_PORT",
            "db": "URIRUN_HOST_DB",
            "token": "URIRUN_NODE_TOKEN",
        },
        "routes": [
            "dashboard://host/chat/command/ask",
            "dashboard://host/service/chat/command/restart",
            "service://host/chat/command/restart",
            "service://chat/command/restart",
            "dashboard://host/artifacts/query/list",
            "dashboard://host/services/query/live",
            "dashboard://host/uri/command/invoke",
        ],
        "http": {
            "index": "/",
            "api": [
                "/api/chat/ask",
                "/api/chat/history",
                "/api/chat/messages/delete",
                "/api/artifacts",
                "/api/artifacts/delete",
                "/api/artifacts/dedupe",
                "/api/artifacts/cleanup-orphans",
                "/api/services/live",
                "/api/uri/invoke",
            ],
        },
    }


def urirun_service() -> dict:
    return service_manifest()


def serve(
    *,
    project: str = ".",
    db: str | None = None,
    config: str | None = None,
    host: str | None = None,
    port: int | None = None,
    node_urls: list[str] | None = None,
    token: str | None = None,
    identity: str | None = None,
    tls_cert: str | None = None,
    tls_key: str | None = None,
    startup_qr: bool = False,
    qr_url: str | None = None,
    replace: bool = True,
    force_replace: bool = False,
) -> ThreadingHTTPServer:
    bind_port = int(port or default_port())
    replace_result = None
    if replace:
        replace_result = host_dashboard._free_port_from_old_chat(bind_port, force=force_replace, emit=True)
        if not replace_result.get("ok"):
            raise OSError(
                "port is already in use by a non-chat process; "
                f"port={bind_port} replace={json.dumps(replace_result, sort_keys=True)}"
            )
    server = host_dashboard.serve(
        project=project,
        db=db,
        config=config,
        host=host or default_host(),
        port=bind_port,
        node_urls=node_urls,
        token=token or os.environ.get("URIRUN_NODE_TOKEN"),
        identity=identity,
        tls_cert=tls_cert,
        tls_key=tls_key,
        startup_qr=startup_qr,
        qr_url=qr_url,
    )
    setattr(server, "urirun_replace", replace_result)
    return server


def dashboard_url(host: str | None = None, port: int | None = None, *, https: bool = False) -> str:
    scheme = "https" if https else "http"
    return f"{scheme}://{host or default_host()}:{int(port or default_port())}/"


def _add_common_args(parser: argparse.ArgumentParser, *, allow_no_replace: bool = True) -> None:
    parser.add_argument("--project", default=".", help="planfile/project directory")
    parser.add_argument("--db", default=None, help="host SQLite db path; default follows urirun")
    parser.add_argument("--config", default=None, help="host mesh config path")
    parser.add_argument("--host", default=None, help=f"bind host; default {DEFAULT_HOST} or URIRUN_CHAT_HOST")
    parser.add_argument("--port", type=int, default=None, help=f"bind port; default {DEFAULT_PORT} or URIRUN_CHAT_PORT")
    parser.add_argument("--node-url", action="append", default=None, help="temporarily add NAME=URL node; repeatable")
    parser.add_argument("--token", default=None, help="X-Urirun-Token for auth-gated nodes")
    parser.add_argument("--identity", default=None, help="SSH private key used to sign /run calls")
    parser.add_argument("--tls-cert", default=None, help="optional TLS certificate file")
    parser.add_argument("--tls-key", default=None, help="optional TLS private key file")
    if allow_no_replace:
        parser.add_argument("--no-replace", action="store_true", help="do not replace an older chat process holding the same port")
    parser.add_argument("--force-replace", action="store_true", help="allow replacing any process holding the chat port; use only in controlled dev environments")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="urirun-service-chat")
    sub = parser.add_subparsers(dest="command")

    serve_parser = sub.add_parser("serve", help="serve the chat dashboard")
    _add_common_args(serve_parser)
    serve_parser.add_argument("--startup-qr", action="store_true", help="add a scanner QR message on startup")
    serve_parser.add_argument("--qr-url", default=None, help="scanner URL encoded into startup QR")

    restart_parser = sub.add_parser("restart", help="replace any older chat service on the port, then serve")
    _add_common_args(restart_parser, allow_no_replace=False)
    restart_parser.add_argument("--startup-qr", action="store_true", help="add a scanner QR message on startup")
    restart_parser.add_argument("--qr-url", default=None, help="scanner URL encoded into startup QR")

    url_parser = sub.add_parser("url", help="print the dashboard URL")
    url_parser.add_argument("--host", default=None)
    url_parser.add_argument("--port", type=int, default=None)
    url_parser.add_argument("--https", action="store_true")

    sub.add_parser("manifest", help="print the service manifest")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command or "serve"

    if command == "manifest":
        print(json.dumps(service_manifest(), indent=2, sort_keys=True))
        return 0
    if command == "url":
        print(dashboard_url(args.host, args.port, https=bool(args.https)))
        return 0
    if command in {"serve", "restart"}:
        try:
            server = serve(
                project=args.project,
                db=args.db,
                config=args.config,
                host=args.host,
                port=args.port,
                node_urls=args.node_url,
                token=args.token,
                identity=args.identity,
                tls_cert=args.tls_cert,
                tls_key=args.tls_key,
                startup_qr=bool(getattr(args, "startup_qr", False)),
                qr_url=getattr(args, "qr_url", None),
                replace=command == "restart" or not bool(getattr(args, "no_replace", False)),
                force_replace=bool(getattr(args, "force_replace", False)),
            )
        except OSError as exc:
            print(json.dumps({
                "ok": False,
                "event": "urirun.service_chat.start_failed",
                "error": str(exc),
                "host": args.host or default_host(),
                "port": int(args.port or default_port()),
            }, sort_keys=True), file=sys.stderr)
            return 1
        print(json.dumps({
            "event": "urirun.service_chat.ready",
            "url": dashboard_url(args.host, args.port),
            "replace": getattr(server, "urirun_replace", None),
        }, sort_keys=True), flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            return 130
        return 0

    parser.error(f"unknown command: {command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
