#!/usr/bin/env python3
"""Snad MC Checker — Minecraft Java username availability server."""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

PORT = 3847
PUBLIC_DIR = Path(__file__).resolve().parent / "public"
NAME_RE = re.compile(r"^[A-Za-z0-9_]{2,16}$")
MOJANG_URL = "https://api.mojang.com/users/profiles/minecraft/"
USER_AGENT = "SnadMCChecker/1.0"


def format_uuid(raw: str | None) -> str | None:
    if not raw or len(raw) != 32:
        return raw
    return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"


def validate_name(raw) -> dict:
    name = str(raw or "").strip()
    if not name:
        return {"ok": False, "error": "empty", "message": "Enter a username."}
    if not NAME_RE.fullmatch(name):
        return {
            "ok": False,
            "error": "invalid",
            "message": "Java names must be 2-16 characters and only use letters, numbers, and underscores.",
        }
    return {"ok": True, "name": name}


def check_mojang(name: str) -> dict:
    req = urllib.request.Request(
        MOJANG_URL + urllib.request.quote(name),
        headers={"User-Agent": USER_AGENT},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as res:
            status = res.status
            body = res.read()
    except urllib.error.HTTPError as err:
        status = err.code
        body = err.read() if err.fp else b""
        if status in (204, 404):
            return {"name": name, "status": "available"}
        if status == 429:
            return {
                "name": name,
                "status": "rate_limited",
                "message": "Mojang rate limit hit. Wait a moment and try again.",
            }
        return {
            "name": name,
            "status": "error",
            "message": f"Mojang API error ({status}).",
        }
    except urllib.error.URLError:
        return {
            "name": name,
            "status": "error",
            "message": "Could not reach Mojang. Check your connection.",
        }

    if status in (204, 404) or not body:
        return {"name": name, "status": "available"}

    data = json.loads(body.decode("utf-8"))
    uuid_raw = data.get("id")
    return {
        "name": data.get("name") or name,
        "status": "taken",
        "uuid": format_uuid(uuid_raw),
        "uuidRaw": uuid_raw,
    }


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PUBLIC_DIR), **kwargs)

    def log_message(self, fmt: str, *args) -> None:
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def send_json(self, status: int, payload: dict | list) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/check":
            qs = parse_qs(parsed.query)
            name = (qs.get("name") or [""])[0]
            validated = validate_name(name)
            if not validated["ok"]:
                self.send_json(
                    400,
                    {
                        "name": str(name or "").strip(),
                        "status": "invalid",
                        "message": validated["message"],
                    },
                )
                return
            self.send_json(200, check_mojang(validated["name"]))
            return
        super().do_GET()

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/check":
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length", "0"))
        if length > 50_000:
            self.send_json(413, {"error": "Payload too large."})
            return

        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self.send_json(400, {"error": "Invalid JSON body."})
            return

        if isinstance(data.get("names"), list):
            names = data["names"]
        elif isinstance(data.get("name"), str):
            names = [data["name"]]
        else:
            names = []

        if not names:
            self.send_json(400, {"error": "Provide name or names[]."})
            return
        if len(names) > 40:
            self.send_json(400, {"error": "Max 40 names per request."})
            return

        results = []
        for item in names:
            validated = validate_name(item)
            if not validated["ok"]:
                results.append(
                    {
                        "name": str(item or "").strip(),
                        "status": "invalid",
                        "message": validated["message"],
                    }
                )
                continue
            result = check_mojang(validated["name"])
            results.append(result)
            if result.get("status") == "rate_limited":
                break
            time.sleep(0.12)

        self.send_json(200, {"results": results})


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Snad MC Checker -> http://localhost:{PORT}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.", flush=True)
        server.server_close()


if __name__ == "__main__":
    main()
