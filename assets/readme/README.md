# README visual assets

Original, editable SVG artwork for WebPatch. No remote fonts, scripts, animation, raster embeds or design dependencies. The W trace and separate square suggest a patch without implying that a safety check has passed. The name, mark and palette remain replaceable; the repository's existing [Apache-2.0 license](../../LICENSE) is unchanged.

| Asset | Use |
| :--- | :--- |
| [logo.svg](logo.svg) | Standalone 96 × 96 geometric W mark |
| [hero-light.svg](hero-light.svg) · [hero-dark.svg](hero-dark.svg) | Desktop hero, 1120 × 350 |
| [hero-mobile-light.svg](hero-mobile-light.svg) · [hero-mobile-dark.svg](hero-mobile-dark.svg) | Compact hero, 480 × 290 |
| [terminal.svg](terminal.svg) · [terminal-mobile.svg](terminal-mobile.svg) | Desktop / mobile terminal illustration using actual output |
| [preview-badge.svg](preview-badge.svg) · [license-badge.svg](license-badge.svg) | Local badges for verified version / license facts |
| [cli-transcript.txt](cli-transcript.txt) | Accessible full text for the illustrated commands |

GitHub-native `<picture>` selects light / dark hero artwork and a readable narrow terminal layout. The fallback images remain usable without media-query selection. SVG text uses local font fallbacks; no font download is required. The only external image in the READMEs is the live GitHub Actions badge, linked to its actual workflow. There are no download-count, coverage or security-certification badges.

## Capture provenance

The terminal previews show the complete actual `webpatch scan` output from the installed 0.2.0 CLI in a disposable Ubuntu 24.04 / arm64 container on 2026-10-23, as UID/GID 65534. Separate 88-column and 44-column runs produce desktop/mobile layouts. The container has no PHP packages; the CLI clearly reports UNKNOWN and explains that an empty inventory cannot prove absence. No synthetic vulnerability or successful repair is pictured.

The capture JSON is [terminal-capture.json](../../evidence/phase-6b-guided/terminal-capture.json). Installation occurred only inside the disposable container; scanning used the real reader with networking disabled and no host mounts. SVG chrome/colors are presentation styling; all content lines and wrapping come from actual output, with no omissions. The installed CLI itself also supports TTY colors, NO_COLOR and Chinese output.

Earlier screenshots and their source-specific provenance remain in [the historical design evidence](../../evidence/readme-design/README.md); they do not describe the new CLI.

## Regeneration

```sh
python3 assets/readme/generate.py
```

The standard-library generator reads the committed real capture, verifies its commands and exit codes, and renders the SVG previews plus accessible transcript. It never scans or repairs the developer host. Re-capture actual output before changing version claims or example content.
