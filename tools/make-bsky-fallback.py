#!/usr/bin/env python3
"""Render the final frame of the Bluesky post-card animation as a static PNG.

Replicates js/bsky-cards.js exactly — the seeded mulberry32 PRNG fixes the
shuffle order and placement jitter, so the last four cards (the frame the
slide ends on) can be computed without a browser. Field geometry follows
reveal.js's base slide (960x700) and the theme's 36px root font:
    .bsky-field { inset: 3.5em 13.5% 1.5em 0 }  ->  830.4 x 520 px

Output: img/anti-ai-posts-fallback.png (2x scale, transparent background).
Usage: python3 tools/make-bsky-fallback.py [live-layout.log]
Requires: pip install pillow fonttools brotli, and a one-time woff2->ttf
conversion of css/fonts/NotoSans-400.woff2 (see FONT_PATH).
"""

from __future__ import annotations

import json
import pathlib
import re
import sys
import urllib.request
from datetime import datetime, timezone
from typing import Callable, TypedDict

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCALE = 2  # render at 2x for a crisp fallback

SLIDE_W, SLIDE_H = 960, 700
EM = 36  # --r-main-font-size
FIELD_TOP, FIELD_BOTTOM, FIELD_RIGHT = 3.5 * EM, 1.5 * EM, 0.135 * SLIDE_W
FW = SLIDE_W - FIELD_RIGHT
FH = SLIDE_H - FIELD_TOP - FIELD_BOTTOM

CARD_W, CARD_MIN_H = 250, 128
PAD_X, PAD_Y = 14, 10
AVATAR, AV_GAP, AV_MARGIN = 32, 8, 6
BODY_FONT, BODY_LH = 12.5, 1.45
NAME_FONT, META_FONT = 12.5, 11
TEXT_W = CARD_W - 2 - 2 * PAD_X  # 220: minus borders and padding
MAX_LINES = 10  # -webkit-line-clamp
GAP = 24
SEED = 0x9E3779B9
VISIBLE = 4

RGB = tuple[int, int, int]

INK: RGB = (61, 55, 84)  # #3d3754
META_INK: RGB = tuple(round(c * 0.7 + 255 * 0.3) for c in INK)  # type: ignore[assignment]
BORDER: RGB = tuple(  # type: ignore[assignment]
    round(c * 0.45 + 255 * 0.55) for c in (111, 91, 146)
)
PLUM: RGB = (111, 91, 146)
PAPER: RGB = (250, 249, 252)
CARD_ALPHA = 235  # .bsky-show opacity: .92
RADIUS = 8

FONT_PATH = "/tmp/NotoSans.ttf"  # woff2 -> ttf, converted once


class Author(TypedDict):
    handle: str
    displayName: str
    avatar: str


class Post(TypedDict):
    url: str
    author: Author
    date: str
    text: str


# Card heights as measured in the browser (offsetHeight, post-webfont) —
# from the "bsky layout:" console log bsky-cards.js emits. PIL's font
# metrics run ~10-15% short of the browser's, and heights drive both the
# grid's row count and the slack clamps, so the tool trusts these over its
# own estimates. Keyed by the deterministic shuffle index; if the post set
# changes, re-derive from a fresh layout log (or fall back to estimates).
MEASURED_H: dict[int, int] = {
    0: 128,
    1: 198,
    2: 230,
    3: 263,
    4: 149,
    5: 149,
    6: 246,
    7: 198,
    8: 128,
    9: 133,
    10: 246,
    11: 214,
    12: 246,
    13: 165,
}

POST_URL = re.compile(r"^https://bsky\.app/profile/([^/]+)/post/([^/?#]+)$")


def font(px: float, weight: int = 400) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(FONT_PATH, round(px * SCALE))
    f.set_variation_by_axes([weight])
    return f


def wrap(text: str, width: float, f: ImageFont.FreeTypeFont) -> list[str]:
    """Greedy wrap with anywhere-breaking for overlong words (pre-wrap +
    overflow-wrap:anywhere), returned as base-scale line strings."""
    out: list[str] = []
    for para in text.split("\n"):
        line = ""
        for word in para.split(" "):
            trial = word if not line else line + " " + word
            if f.getlength(trial) / SCALE <= width:
                line = trial
                continue
            if line:
                out.append(line)
                line = ""
            while f.getlength(word) / SCALE > width:  # break the long word
                k = next(
                    k
                    for k in range(len(word), 0, -1)
                    if f.getlength(word[:k]) / SCALE <= width
                )
                out.append(word[:k])
                word = word[k:]
            line = word
        out.append(line)
    return out


def ellipsize(text: str, f: ImageFont.FreeTypeFont, width: float) -> str:
    """text-overflow: ellipsis for the one-line .bsky-who name/meta."""
    if f.getlength(text) / SCALE <= width:
        return text
    ell = "…"
    while text and f.getlength(text + ell) / SCALE > width:
        text = text[:-1]
    return text + ell


def card_height(post: Post, body_font: ImageFont.FreeTypeFont) -> int:
    lines = wrap(post["text"], TEXT_W, body_font)[:MAX_LINES]
    text_h = len(lines) * BODY_FONT * BODY_LH
    return max(CARD_MIN_H, round(2 + 2 * PAD_Y + AVATAR + AV_MARGIN + text_h))


def draw_avatar(post: Post, size_px: int) -> Image.Image:
    try:
        url = post["author"]["avatar"]
        dest = pathlib.Path("/tmp/avatars") / (post["author"]["handle"] + ".img")
        dest.parent.mkdir(exist_ok=True)
        if not dest.exists():
            urllib.request.urlretrieve(url, dest)  # noqa: S310
        im: Image.Image = Image.open(dest).convert("RGB").resize((size_px, size_px))
    except Exception:
        im = Image.new("RGB", (size_px, size_px), PLUM)
        ImageDraw.Draw(im).text(
            (size_px / 2, size_px / 2),
            post["author"]["displayName"][0],
            font=font(15, 700),
            fill=PAPER,
            anchor="mm",
        )
    mask = Image.new("L", (size_px, size_px), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size_px, size_px), fill=255)
    out = Image.new("RGBA", (size_px, size_px), (0, 0, 0, 0))
    out.paste(im, (0, 0), mask)
    return out


def appview_get(path: str, params: str) -> str:
    req = urllib.request.Request(  # noqa: S310
        f"https://public.api.bsky.app/xrpc/{path}?{params}",
        headers={"User-Agent": "monktoberfest-build/1.0"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310
        return str(resp.read().decode("utf-8"))


def fetch_posts(urls: set[str]) -> list[Post]:
    """Fetch post data for the bsky-cards:: targets straight from the
    Bluesky AppView — the same source the bsky-macro.rb extension uses,
    so the static fallback always matches what the live cards render.
    Deleted posts are dropped (staleness is a feature)."""
    dids = {
        h: str(
            json.loads(
                appview_get("com.atproto.identity.resolveHandle", f"handle={h}")
            )["did"]
        )
        for h in {POST_URL.match(u).group(1) for u in urls}  # type: ignore[union-attr]
    }
    url_of: dict[str, str] = {}
    for u in urls:
        h, rkey = POST_URL.match(u).groups()  # type: ignore[union-attr]
        url_of[f"at://{dids[h]}/app.bsky.feed.post/{rkey}"] = u
    posts_raw = list(
        json.loads(
            appview_get("app.bsky.feed.getPosts", "uris=" + "&uris=".join(url_of))
        )["posts"]
    )
    posts: list[Post] = []
    for p in posts_raw:
        created = datetime.fromisoformat(
            p["record"]["createdAt"].replace("Z", "+00:00")
        )
        posts.append(
            {
                "url": url_of[p["uri"]],
                "author": {
                    "handle": p["author"]["handle"],
                    "displayName": p["author"]["displayName"],
                    "avatar": p["author"]["avatar"],
                },
                "date": created.astimezone(timezone.utc).strftime("%b %-d, %Y"),
                "text": p["record"]["text"],
            }
        )
    return posts


def card_urls() -> set[str]:
    """bsky-cards:: targets in the .adoc sources — the source of truth."""
    urls: set[str] = set()
    for src in (ROOT / "presentation.adoc", ROOT / "essay.adoc"):
        if src.exists():
            urls |= {
                u
                for target in re.findall(r"bsky-cards::(\S+?)\[\]", src.read_text())
                for u in target.split(",")
            }
    return urls


def shuffle_like_js(posts: list[Post], rng: Callable[[], float]) -> None:
    """Fisher–Yates shuffle, then the same-author pass — both verbatim
    ports of bsky-cards.js."""
    for i in range(len(posts) - 1, 0, -1):
        j = int(rng() * (i + 1))
        posts[i], posts[j] = posts[j], posts[i]
    for i in range(1, len(posts)):
        if posts[i]["author"]["handle"] == posts[i - 1]["author"]["handle"]:
            j = next(
                (
                    k
                    for k in range(i + 1, len(posts))
                    if posts[k]["author"]["handle"] != posts[i - 1]["author"]["handle"]
                    and (
                        k + 1 == len(posts)
                        or posts[k + 1]["author"]["handle"]
                        != posts[i]["author"]["handle"]
                    )
                ),
                -1,
            )
            if j > 0:
                posts[i], posts[j] = posts[j], posts[i]


def check_against_live(
    log_path: str,
    posts: list[Post],
    x_of: dict[int, float],
    y_of: dict[int, float],
    heights: list[int],
) -> None:
    """Cross-check against a live "bsky layout:" console log (the
    deterministic trace bsky-cards.js emits): the fallback must agree
    with the real deck to ~1px."""
    log = pathlib.Path(log_path).read_text()
    live = {
        int(m[0]): (float(m[2]), float(m[3]), int(m[4]))
        for m in re.findall(
            r"(\d+) (\S+) ([\d.]+)px,([\d.]+)px 250x(\d+)",
            log.split("bsky layout:")[-1],
        )
    }
    for i in range(len(posts) - VISIBLE, len(posts)):
        lx, ly, lh = live[i]
        ok = abs(lx - x_of[i]) <= 1 and abs(ly - y_of[i]) <= 1 and lh == heights[i]
        print(
            f"card {i}: live=({lx:.1f},{ly:.1f}) h={lh}  "
            f"render=({x_of[i]:.1f},{y_of[i]:.1f}) h={heights[i]}  "
            f"{'OK' if ok else 'MISMATCH'}"
        )


def draw_card(post: Post, hi: int, body_font: ImageFont.FreeTypeFont) -> Image.Image:
    card = Image.new("RGBA", (CARD_W * SCALE, round(hi * SCALE)), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle(
        (0, 0, CARD_W * SCALE - 1, round(hi * SCALE) - 1),
        radius=RADIUS * SCALE,
        fill=(255, 255, 255, CARD_ALPHA),
        outline=(*BORDER, CARD_ALPHA),
        width=SCALE,
    )
    av = draw_avatar(post, AVATAR * SCALE)
    card.paste(av, (PAD_X * SCALE, PAD_Y * SCALE), av)
    tx = (PAD_X + AVATAR + AV_GAP) * SCALE
    who_w = TEXT_W - AVATAR - AV_GAP  # the .bsky-who column width
    d.text(
        (tx, (PAD_Y + 1) * SCALE),
        ellipsize(post["author"]["displayName"], font(NAME_FONT, 700), who_w),
        font=font(NAME_FONT, 700),
        fill=(*INK, CARD_ALPHA),
    )
    d.text(
        (tx, (PAD_Y + 17) * SCALE),
        ellipsize(
            f"@{post['author']['handle']} · {post['date']}",
            font(META_FONT),
            who_w,
        ),
        font=font(META_FONT),
        fill=(*META_INK, CARD_ALPHA),
    )
    lines = wrap(post["text"], TEXT_W, body_font)
    if len(lines) > MAX_LINES:
        lines = lines[:MAX_LINES]
        lines[-1] = lines[-1][:-1] + "…"
    ty = (PAD_Y + AVATAR + AV_MARGIN) * SCALE
    for n, line in enumerate(lines):
        d.text(
            (PAD_X * SCALE, ty + n * BODY_FONT * BODY_LH * SCALE),
            line,
            font=body_font,
            fill=(*INK, CARD_ALPHA),
        )
    return card


def main() -> None:
    posts = fetch_posts(card_urls())

    # Seeded mulberry32 — exact port of the JS closure in bsky-cards.js.
    state = SEED & 0xFFFFFFFF

    def rng() -> float:
        nonlocal state
        state = (state + 0x6D2B79F5) & 0xFFFFFFFF
        t = ((state ^ (state >> 15)) * (1 | state)) & 0xFFFFFFFF
        u = (t + (((t ^ (t >> 7)) * (61 | t)) & 0xFFFFFFFF)) & 0xFFFFFFFF
        t = u ^ t
        return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 2**32

    shuffle_like_js(posts, rng)

    jitter: list[list[float]] = [[rng(), rng()] for _ in posts]

    # place(): grid sizing from measured card sizes.
    body_font = font(BODY_FONT)
    heights = [
        MEASURED_H[i] if i in MEASURED_H else card_height(p, body_font)
        for i, p in enumerate(posts)
    ]
    h = max(heights)
    cols = max(1, int((FW + GAP) // (CARD_W + GAP)))
    rows = max(2, int((FH + GAP) // (h + GAP)))
    slots = cols * rows
    cell_w, cell_h = FW / cols, FH / rows

    img = Image.new("RGBA", (round(FW * SCALE), round(FH * SCALE)), (0, 0, 0, 0))
    x_of: dict[int, float] = {}
    y_of: dict[int, float] = {}

    for i in range(len(posts) - VISIBLE, len(posts)):
        post, hi = posts[i], heights[i]
        col, row = (i % slots) % cols, (i % slots) // cols
        jx, jy = jitter[i]
        slack_x, slack_y = cell_w - CARD_W, cell_h - hi
        x = max(0, min(col * cell_w + slack_x * (0.1 + 0.8 * jx), FW - CARD_W))
        y = max(0, min(row * cell_h + slack_y * (0.1 + 0.8 * jy), FH - hi))

        card = draw_card(post, hi, body_font)
        img.alpha_composite(card, (round(x * SCALE), round(y * SCALE)))
        x_of[i], y_of[i] = x, y
        print(
            f"card {i}: {post['author']['handle'][:20]:22} "
            f"cell=({col},{row}) pos=({x:.0f},{y:.0f}) h={hi:.0f}"
        )

    if len(sys.argv) > 1:
        check_against_live(sys.argv[1], posts, x_of, y_of, heights)

    out = ROOT / "img/anti-ai-posts-fallback.png"
    img.save(out)
    print(f"grid: cols={cols} rows={rows} slots={slots} max_h={h:.0f}")
    print(f"wrote {out} ({img.size[0]}x{img.size[1]})")


if __name__ == "__main__":
    main()
