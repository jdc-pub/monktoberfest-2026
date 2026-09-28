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
OUT = ROOT / "dist" / "presentation.html"
WATCH_DIRS = ("css", "data", "img", "js")
ADOC_FLAGS = ["-I", "tools", "-r", "og-macro.rb", "-r", "bsky-macro.rb"]

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
        files += [p for p in (ROOT / d).rglob("*") if p.is_file()]
    return files


class State:
    version: ClassVar[int] = 0
    lock: ClassVar[threading.Lock] = threading.Lock()

    @classmethod
    def bump(cls) -> None:
        with cls.lock:
            cls.version += 1


def rebuild_loop() -> None:
    last = [p.stat().st_mtime for p in watched_files()]
    while True:
        time.sleep(0.5)
        now = [p.stat().st_mtime for p in watched_files()]
        if now == last:
            continue
        last = now
        old = OUT.read_bytes() if OUT.is_file() else None
        r = subprocess.run(
            ["asciidoctor-revealjs", *ADOC_FLAGS, str(DOC), "-o", str(OUT)],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        if r.returncode == 0:
            if OUT.read_bytes() == old:
                log("no output change")
                continue
            State.bump()
            log(f"rebuilt -> {OUT.relative_to(ROOT)}")
        else:
            log(f"BUILD FAILED\n{r.stderr}")


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
    subprocess.run(
        ["asciidoctor-revealjs", *ADOC_FLAGS, str(DOC), "-o", str(OUT)],
        cwd=ROOT,
        check=True,
    )
    State.bump()
    threading.Thread(target=rebuild_loop, daemon=True).start()
    print(f"http://localhost:{PORT}/dist/presentation.html", flush=True)
    http.server.ThreadingHTTPServer(("", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
