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

Captured on **2026-10-22** from the installed current WebPatch CLI in an isolated **Ubuntu 24.04 / arm64** container, as UID / GID **65534**. Source baseline: `7495d77c1835c519ca0f487a0372064e998e02de`; application code is identical to the preceding accepted `37dc9d9` implementation. The capture uses the real system reader, real package metadata and the actual wall clock, with no synthetic inventory or fake CLI output.

The standard Docker build could not fetch Docker Hub metadata during this run. A derived image used the existing local `webpatch-phase1:noble` base, copied current source, rebuilt the `.deb`, and installed it inside the container. Runtime flags were `--read-only --network none --cap-drop ALL --security-opt no-new-privileges`, with a small isolated `/tmp` tmpfs for the saved plan and no host mounts. Build details, image identity, full command results and exit codes are in [validation evidence](../../evidence/readme-design/README.md).

The illustration selects exact lines from `webpatch scan`, `webpatch plan --dry-run` and `webpatch apply`. Wrapping is visual only; omissions are labeled `··· output omitted ···`. Prompts, headings, dates and exit-code comments are presentation annotations. Colors and terminal chrome are illustration styling, not a shipped TUI.

This sample reports `MEETS_VENDOR_FIX` for a PHP package but keeps runtime safety `UNKNOWN`. Container planning reports `APT dry-run: NOT_RUN`; it is not an example of a successful host APT simulation. No active FPM service, healthy application, vulnerability exploitation or repair is demonstrated. The full capture also preserves `verify-plan` returning `PLAN_SIMULATION_DRIFT` because simulation is unavailable; that is not a successful plan verification.

## Regeneration

From the repository root, with Python 3.10+:

```sh
python3 assets/readme/generate.py
```

The standard-library generator reads the committed [capture JSON](../../evidence/readme-design/cli/capture.json), validates the illustrated commands / exit codes and produces the SVGs plus transcript. It never scans or writes system state. Re-capture real output before changing the example environment or command results. The generator's palette and geometry are the editable source; there is no separate build toolchain.

Design references: [Trivy](https://github.com/aquasecurity/trivy) for explicit capability scope, [Starship](https://github.com/starship/starship) for a clear identity and language navigation, and [uv](https://github.com/astral-sh/uv) for direct installation and theme-aware presentation. The artwork, wording and layout here are original.
