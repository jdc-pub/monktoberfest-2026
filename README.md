# monktoberfest-2026

Deck source: `presentation.adoc` (AsciiDoc → reveal.js via the Ruby
`asciidoctor-revealjs` gem, styled by `css/theme-override.css`).

```sh
make build      # dist/presentation.html (loads tools/og-macro.rb + tools/bsky-macro.rb)
make serve      # live rebuild + browser reload at :8080
make release    # single self-contained dist/presentation-standalone.html
make typecheck  # mypy --strict tools
make fallback   # re-render img/anti-ai-posts-fallback.png from the current posts
```

Both card macros fetch live at conversion time — every `make build` hits
the network, and the deck's source (the `.adoc`) is the only data source.

## OpenGraph link cards (`og::URL[]`)

Slides can embed link-preview cards (Slack/iMessage-style: image, site,
headline, description, `host · date`) with a native block macro:

```adoc
og::https://example.com/article[]
```

**`tools/og-macro.rb`** registers the macro (loaded by the `-I tools -r
og-macro.rb` flag in Makefile `build`/`release` and `tools/serve.py`
`ADOC_FLAGS`; note plain `-r` resolves against Ruby's load path, not the
project directory — always pair it with `-I tools`). At conversion time it
fetches the page, reads its `og:*`/`twitter:`/`<title>` values, downloads
the preview image as a data URI, and emits the card HTML inline — the
built slide needs no runtime JavaScript and has no fallback stand-in.

**Blocked sites cannot be fetched by any tool** — WSJ (and other paywalled
publishers) answer 403/401 to every user agent including
`facebookexternalhit`/`Twitterbot`, and link-preview services (microlink et
al.) report antibot protection. For those, hand-curate an entry in
`data/og-links.json`: open the page in a browser, copy its `og:` values,
and encode a preview image (screenshot, or the image URL recovered from a
syndicated copy of the article) as a data URI:

```sh
python3 -c 'import base64,pathlib; print("data:image/webp;base64,"+base64.b64encode(pathlib.Path("img.webp").read_bytes()).decode())'
```

The macro uses a curated `og-links.json` entry only when the live fetch
fails; a URL that is both unfetchable and uncurated fails the build with a
message naming the fix.

## Bluesky post cards (`bsky-cards::URL,...[]`)

The "Many Creatives Hate AI" slide embeds a live grid of Bluesky posts via
one macro whose comma-separated targets are the deck's only post data:

```adoc
bsky-cards::https://bsky.app/profile/maris.bsky.social/post/3k45dh7dnhx23[],https://bsky.app/profile/404media.co/post/3mm2ivguvq22x[]
```

**`tools/bsky-macro.rb`** fetches each post live from the public Bluesky
AppView (one batched `app.bsky.feed.getPosts` call) and emits the field
markup, a posts JSON `<script>`, and the driver reference — exactly the
markup the earlier static `include::data/anti-ai-posts.json[]` produced.
**A post deleted from Bluesky silently drops out of the deck** — staleness
is a feature. To add a post, paste its URL into the macro target list; to
remove one, delete it.

The slide also carries a pre-rendered static frame
(`img/anti-ai-posts-fallback.png`) shown when the runtime driver
(`js/bsky-cards.js`) can't run. Regenerate it after changing the post set:

```sh
make fallback   # requires pillow; fetches the same posts the macro does
```

Optionally cross-check the render against a live `"bsky layout:"` console
log (the deterministic trace `js/bsky-cards.js` emits; `check.js` captures
it) to confirm pixel agreement.

## Notes

- `data/substituting-artists.md` is research scratch (the advertising
  claims table); not consumed by the build.
- `css/fonts/` holds the Noto Sans variable font used by the theme and by
  `make fallback` (see its docstring for the one-time woff2→ttf step).
