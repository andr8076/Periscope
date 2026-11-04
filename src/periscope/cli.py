"""Periscope command-line interface. Does not change Jan Desktop data."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from urllib import error, parse, request

from .core import (
    PeriscopeError, jan_data_dir, thread_dirs, read_thread, locate_thread,
    state_directory, load_state, save_state, linked_imports, import_record,
)


def _base_url() -> str:
    url = os.getenv("PERISCOPE_WEBUI_URL", "http://127.0.0.1:3000").rstrip("/")
    parsed = parse.urlsplit(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.path not in ("", "/"):
        raise PeriscopeError("Invalid PERISCOPE_WEBUI_URL")
    if parsed.scheme == "http" and parsed.hostname not in ("localhost", "127.0.0.1", "::1"):
        raise PeriscopeError("An API token may only be sent over HTTPS to a nonlocal Open WebUI host")
    return url


def _api_post(path: str, payload: dict) -> object:
    token = os.getenv("PERISCOPE_WEBUI_TOKEN")
    if not token:
        raise PeriscopeError("Set PERISCOPE_WEBUI_TOKEN for authenticated Open WebUI chat importing")
    blob = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    endpoint = _base_url() + path
    req = request.Request(
        endpoint,
        data=blob,
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except (error.HTTPError, error.URLError, TimeoutError) as exc:
        detail = f"HTTP {exc.code}" if isinstance(exc, error.HTTPError) else str(exc.reason if hasattr(exc, "reason") else exc)
        raise PeriscopeError(f"Open WebUI import failed: {detail}") from exc


def _probe(url: str) -> str:
    try:
        with request.urlopen(url, timeout=3) as resp:
            return f"HTTP {resp.status}"
    except (error.HTTPError, error.URLError, TimeoutError) as exc:
        if isinstance(exc, error.HTTPError):
            return f"HTTP {exc.code}"
        return "not reachable"


def run(args: argparse.Namespace) -> int:
    data_dir = jan_data_dir()
    registry_dir = state_directory()
    if args.command == "doctor":
        print(f"Jan Desktop data: {data_dir}")
        print(f"Jan thread count: {len(thread_dirs(data_dir))}")
        print(f"Jan model API: {_probe(os.getenv('PERISCOPE_JAN_API', 'http://127.0.0.1:1337/v1').rstrip('/')+'/models')}")
        print(f"Open WebUI: {_probe(_base_url()+'/health')}")
        print(f"Registry: {registry_dir / 'links.json'}")
        return 0

    if args.command == "list":
        folders = thread_dirs(data_dir)
        if not folders:
            print(f"No Jan Desktop conversation files found under {data_dir / 'threads'}.")
            return 0
        for folder in folders:
            thread = read_thread(folder)
            print(f"{thread.id}  {thread.title}  ({len(thread.messages)} text messages)")
        return 0

    state = load_state(registry_dir)
    links = state["links"]

    if args.command == "link":
        thread = locate_thread(data_dir, args.thread_id)
        if args.thread_id in links:
            print(f"Already linked: {thread.title}")
            return 0
        links[args.thread_id] = {"openwebui_id": None}
        save_state(registry_dir, state)
        print(f"Selected for import: {thread.title} ({thread.id})")
        return 0

    if args.command == "unlink":
        if args.thread_id not in links:
            raise PeriscopeError("That Jan thread is not linked")
        del links[args.thread_id]
        save_state(registry_dir, state)
        print("Unlinked locally. Existing Open WebUI conversations were not deleted.")
        return 0

    if args.command == "status":
        if not links:
            print("No selected Jan threads. Use 'periscope link <THREAD_ID>'.")
        for key, value in links.items():
            print(f"{key}: Open WebUI chat {value.get('openwebui_id') or '(not imported through API)'}")
        return 0

    if args.command == "export":
        records = linked_imports(data_dir, state)
        destination = Path(args.output).expanduser()
        if destination.exists() and not args.overwrite:
            raise PeriscopeError(f"{destination} exists; add --overwrite to replace")
        if not records:
            print("No selected threads containing text; nothing exported.")
            return 0
        destination.write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Wrote {len(records)} selected Jan chat(s) to {destination}.")
        print("Import the JSON in Open WebUI -> Settings -> Data Controls -> Import Chats.")
        return 0

    if args.command == "push":
        unimported = [key for key, value in links.items() if not value.get("openwebui_id")]
        if not unimported:
            print("No new selected threads to import. Existing chats are not resynchronized.")
            return 0
        for key in unimported:
            thread = locate_thread(data_dir, key)
            if not thread.messages:
                print(f"Skipping empty text conversation: {key}")
                continue
            result = _api_post("/api/v1/chats/import", {"chats": [import_record(thread)]})
            if not isinstance(result, list) or len(result) != 1 or not isinstance(result[0], dict) or not result[0].get("id"):
                raise PeriscopeError("Open WebUI returned an unexpected response; check for a created chat before retrying")
            links[key]["openwebui_id"] = str(result[0]["id"])
            save_state(registry_dir, state)
            print(f"Imported {thread.title} -> Open WebUI chat {links[key]['openwebui_id']}")
        return 0

    raise PeriscopeError("Unsupported command")


def main() -> None:
    parser = argparse.ArgumentParser(prog="periscope", description="Selectively import Jan Desktop chats into Open WebUI (read-only Jan)")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="Check local Jan and Open WebUI access")
    commands.add_parser("list", help="List available Jan Desktop conversation files")
    link = commands.add_parser("link", help="Select a Jan chat for export")
    link.add_argument("thread_id")
    unlink = commands.add_parser("unlink", help="Stop tracking a Jan chat (does not delete)")
    unlink.add_argument("thread_id")
    commands.add_parser("status", help="Show selected Jan chat IDs and imported chat IDs")
    export = commands.add_parser("export", help="Write selected chats to an Open WebUI import JSON file")
    export.add_argument("output")
    export.add_argument("--overwrite", action="store_true")
    commands.add_parser("push", help="Import not-yet-imported selected chats over Open WebUI API")
    try:
        result = run(parser.parse_args())
    except (PeriscopeError, OSError) as exc:
        print(f"Periscope: {exc}", file=sys.stderr)
        result = 1
    raise SystemExit(result)
