# -*- coding: utf-8 -*-
"""Local static preview with GitHub Pages-style extensionless URLs."""
from __future__ import annotations

import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class CleanURLHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):  # noqa: N802
        path = self.path.split("?", 1)[0].split("#", 1)[0]
        if path.endswith(".html"):
            clean = path[: -len(".html")] or "/"
            if clean.endswith("/index"):
                clean = clean[: -len("index")] or "/"
            loc = clean + (f"?{self.path.split('?', 1)[1]}" if "?" in self.path else "")
            self.send_response(301)
            self.send_header("Location", loc)
            self.end_headers()
            return

        candidate = ROOT / path.lstrip("/")
        if path != "/" and not candidate.exists() and not path.endswith("/"):
            html = ROOT / f"{path.lstrip('/')}.html"
            if html.exists():
                self.path = f"/{html.name}"
        super().do_GET()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), CleanURLHandler)
    print(f"Serving {ROOT} at http://127.0.0.1:{args.port}/ (extensionless URLs enabled)")
    server.serve_forever()


if __name__ == "__main__":
    main()
