"""Serve only the public submission artifacts on IPv4 loopback (never .env or source)."""

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = {
    "SUBMISSION-EVIDENCE.html": "text/html; charset=utf-8",
    **{
        name + ".pdf": "application/pdf"
        for name in (
            "README",
            "REPORT",
            "ASSIGNMENT-CHECKLIST",
            "VIVA-NOTES",
            "VERIFICATION",
            "SCREENSHOT-CHECKLIST",
        )
    },
    "SCREENSHOT-CHECKLIST.txt": "text/plain; charset=utf-8",
}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        name = unquote(urlsplit(self.path).path).lstrip("/") or "SUBMISSION-EVIDENCE.html"
        if name.startswith("go/"):
            manifest = json.loads(
                (ROOT / "docs/submission/latest.json").read_text(encoding="utf-8")
            )
            match = next((s for s in manifest["screenshots"] if s["number"] == name[3:]), None)
            if match:
                self.send_response(302)
                self.send_header("Location", match["url"])
                self.end_headers()
                return
        if name not in PUBLIC or not (ROOT / name).is_file():
            self.send_error(404)
            return
        data = (ROOT / name).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", PUBLIC[name])
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *_args):
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8011)
    args = parser.parse_args()
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()
