#!/usr/bin/env python3
"""Inline all local assets into a single self-contained presentation.html.

Reads  dist/presentation.html (must be built first)
Writes dist/presentation-standalone.html

Transforms:
  1. <link rel="stylesheet" href=...>   -> <style>contents</style>
     (url() refs inside CSS — fonts, images — become base64 data: URIs,
      resolved against the stylesheet's own directory)
  2. <script src=...></script>          -> <script>contents</script>
  3. Reveal.initialize `dependencies:`  -> removed (see 4)
  4. zoom/notes plugins inlined as classic scripts that register themselves
"""

from __future__ import annotations

import base64
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"
SRC = DIST / "presentation.html"
DST = DIST / "presentation-standalone.html"
REVEAL = ROOT / "node_modules" / "reveal.js"

PLUGINS: list[tuple[str, Path]] = [
    ("RevealZoom", REVEAL / "plugin" / "zoom" / "zoom.js"),
    ("RevealNotes", REVEAL / "plugin" / "notes" / "notes.js"),
]

MIME: dict[str, str] = {
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".ttf": "font/ttf",
    ".otf": "font/otf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
    ".gif": "image/gif",
}

link_re = re.compile(r'<link rel="stylesheet" href="([^"]+)"[^>]*>')
script_re = re.compile(r'<script src="([^"]+)"></script>')
img_re = re.compile(r'<img\b[^>]*\bsrc="([^"]+)"[^>]*>')
url_re = re.compile(r"""url\(\s*['"]?([^'")]+)['"]?\s*\)""")

FONT_LICENSE = """<!--
Fonts embedded below are licensed under the SIL Open Font License 1.1:
Noto Sans (Copyright 2022 The Noto Project Authors) and JetBrainsMono
Nerd Font Mono (Copyright 2020 The JetBrains Mono Project Authors,
patched by github.com/ryanoasis/nerd-fonts). License text:
https://openfontlicense.org
-->
"""

THEME_LICENSE = """<!--
The syntax-highlighting theme embedded below is Catppuccin Latte for
Highlight.js (Copyright 2021 Catppuccin), MIT-licensed: vendored from
github.com/catppuccin/highlightjs.
-->
"""

STYLESHEET_LICENSES: dict[str, str] = {
    "catppuccin-latte.css": THEME_LICENSE,
}


def is_local(url: str) -> bool:
    """True unless the URL carries a scheme (http:, data:, mailto:, ...)."""
    return not re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", url)


def data_uri(path: Path) -> str:
    mime = MIME.get(path.suffix.lower())
    if mime is None:
        raise SystemExit(f"no known MIME type for {path}")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def inline_stylesheet(href: str) -> str:
    css_path = (DIST / href).resolve()
    css = css_path.read_text()
    license_note = STYLESHEET_LICENSES.get(css_path.name, "")

    def embed(m: re.Match[str]) -> str:
        url = m.group(1)
        if not is_local(url):
            return m.group(0)
        asset = (css_path.parent / url).resolve()
        if not asset.is_file():
            raise SystemExit(f"{css_path} references missing asset: {asset}")
        return f"url({data_uri(asset)})"

    return f"<style>\n{license_note}{url_re.sub(embed, css)}\n</style>"


def inline_link(m: re.Match[str]) -> str:
    if not is_local(m.group(1)):
        return m.group(0)
    return inline_stylesheet(m.group(1))


def inline_script(m: re.Match[str]) -> str:
    if not is_local(m.group(1)):
        return m.group(0)
    js = (DIST / m.group(1)).resolve().read_text()
    return f"<script>\n{js}\n</script>"


def inline_img(m: re.Match[str]) -> str:
    if not is_local(m.group(1)):
        return m.group(0)
    return m.group(0).replace(
        f'src="{m.group(1)}"', f'src="{data_uri((DIST / m.group(1)).resolve())}"'
    )


def main() -> None:
    html = SRC.read_text()

    refs = set(
        m.group(1)
        for tag_re in (link_re, script_re, img_re)
        for m in tag_re.finditer(html)
        if is_local(m.group(1))
    )
    html = link_re.sub(inline_link, html)
    html = script_re.sub(inline_script, html)
    html = img_re.sub(inline_img, html)

    plugin_tags = ""
    for global_name, path in PLUGINS:
        js = path.read_text()
        plugin_tags += (
            f"<script>\n{js}\nReveal.registerPlugin({global_name});\n</script>"
        )
    html, n = re.subn(r"  dependencies: \[[^\]]*\],\n", "", html)
    if n != 1:
        raise SystemExit("expected exactly one `dependencies:` block; rebuild first")
    marker = "<script>Array.prototype.slice"
    if marker not in html:
        raise SystemExit(
            "initialize script marker not found; converter output changed?"
        )
    html = html.replace(marker, plugin_tags + marker, 1)
    html = html.replace("</head>", FONT_LICENSE + "</head>", 1)
    leftover = [u for u in refs if f'href="{u}"' in html or f'src="{u}"' in html]
    if leftover:
        raise SystemExit(f"unresolved local references: {leftover}")

    DST.write_text(html)
    print(f"wrote {DST.relative_to(ROOT)} ({DST.stat().st_size / 1024:.0f} KiB)")


if __name__ == "__main__":
    main()
