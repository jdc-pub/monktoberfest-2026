#!/usr/bin/env python3
"""Live server for presentation.adoc: rebuild on change, reload browser.

Serves the project root on localhost. Watches the build inputs; when any
change, re-runs asciidoctor-revealjs and bumps a version counter. Served
HTML gets a small script injected that polls the counter and reloads.
"""

from __future__ import annotations

import http.server
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, ClassVar

PORT = 8080
ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "presentation.adoc"
RAW = ROOT / "dist" / ".presentation.html"
OUT = ROOT / "dist" / "presentation.html"
WATCH_DIRS = ("css", "data", "img", "js")
# Derived data: rewritten by every conversion (og-macro.rb's at_exit hook),
# so watching it would trigger an endless rebuild loop.
WATCH_EXCLUDE = {ROOT / "data" / "og-cache.json"}
ADOC_FLAGS = [
    "-I",
    "tools",
    "-r",
    "og-macro.rb",
    "-r",
    "bsky-macro.rb",
    "-a",
    "data-uri",
    "-a",
    "imagesdir=img",
]

RELOAD_POLL = b"""
<script>
(() => {
  const v = () => fetch('/__reload').then(r => r.text());
  v().then(initial => setInterval(async () => {
    if (await v() !== initial) {
      const i = Reveal.getIndices();
      location.hash = `#/${i.h}/${i.v}`;
      location.reload();
    }
  }, 700));
})();
</script>
"""


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def watched_files() -> list[Path]:
    files = [DOC]
    for d in WATCH_DIRS:
        files += [
            p for p in (ROOT / d).rglob("*") if p.is_file() and p not in WATCH_EXCLUDE
        ]
    return files


class State:
    version: ClassVar[int] = 0
    lock: ClassVar[threading.Lock] = threading.Lock()

    @classmethod
    def bump(cls) -> None:
        with cls.lock:
            cls.version += 1


def build() -> tuple[bytes | None, str]:
    """Convert to an intermediate, inline it, publish atomically to OUT.

    The converter never writes OUT directly, so a kill (or crash) mid-build
    can only leave the intermediate stale, never a raw file at OUT.
    """
    r = subprocess.run(
        ["asciidoctor-revealjs", *ADOC_FLAGS, str(DOC), "-o", str(RAW)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        return None, r.stderr
    raw = RAW.read_bytes()
    ir = subprocess.run(
        ["python3", str(ROOT / "tools" / "inline.py"), str(RAW), str(OUT)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    if ir.returncode != 0:
        return None, ir.stderr
    return raw, ""


def rebuild_loop(last_raw: bytes) -> None:
    last = [p.stat().st_mtime for p in watched_files()]
    while True:
        time.sleep(0.5)
        now = [p.stat().st_mtime for p in watched_files()]
        if now == last:
            continue
        last = now
        try:
            raw, stderr = build()
        except Exception as e:  # never let the rebuild thread die silently
            log(f"REBUILD ERROR: {e}")
            continue
        if raw is None:
            log(f"BUILD FAILED\n{stderr}")
            continue
        if raw == last_raw:
            log("no output change")
            continue
        last_raw = raw
        State.bump()
        log(f"rebuilt -> {OUT.relative_to(ROOT)}")


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self) -> None:
        if self.path == "/__reload":
            body = str(State.version).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        path = Path(self.translate_path(self.path))
        if path.suffix == ".html" and path.is_file():
            html = path.read_bytes().replace(b"</body>", RELOAD_POLL + b"</body>", 1)
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)
            return
        super().do_GET()

    def log_message(self, format: str, *args: Any) -> None:
        log(format % args)


def main() -> None:
    raw, stderr = build()
    if raw is None:
        raise SystemExit(f"initial build failed:\n{stderr}")
    State.bump()
    threading.Thread(target=rebuild_loop, args=(raw,), daemon=True).start()
    print(f"http://localhost:{PORT}/dist/presentation.html", flush=True)
    http.server.ThreadingHTTPServer(("", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
