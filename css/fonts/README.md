# Vendored fonts

All fonts are SIL Open Font License 1.1; the full license text ships next to
the files (`OFL-*.txt`) and must accompany any redistribution, including
`dist/presentation-standalone.html`, which embeds them as base64.

| File                                                     | Upstream                                                                                                                              | Notes                                                                              |
| -------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| `NotoSans-400.woff2`, `NotoSans-Italic[wght].woff2`      | [notofonts/latin-greek-cyrillic](https://github.com/notofonts/latin-greek-cyrillic) via Google Fonts                                  | Variable fonts (wght 100–900), latin subset; one file per style covers all weights |
| `JetBrainsMonoNerdFontMono-Regular.woff2`, `-Bold.woff2` | [JetBrains Mono](https://github.com/JetBrains/JetBrainsMono), patched by [nerd-fonts v3.5.1](https://github.com/ryanoasis/nerd-fonts) | TTF from the release converted to woff2 with fonttools                             |
