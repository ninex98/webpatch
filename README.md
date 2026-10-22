<p align="center">
  <picture>
    <source media="(max-width: 600px) and (prefers-color-scheme: dark)" srcset="assets/readme/hero-mobile-dark.svg">
    <source media="(max-width: 600px)" srcset="assets/readme/hero-mobile-light.svg">
    <source media="(prefers-color-scheme: dark)" srcset="assets/readme/hero-dark.svg">
    <img src="assets/readme/hero-light.svg" alt="WebPatch — Evidence before action. Read-only PHP runtime security inventory." width="100%">
  </picture>
</p>

<p align="center">
  <a href="https://github.com/ninex98/webpatch/actions/workflows/ci.yml"><img src="https://github.com/ninex98/webpatch/actions/workflows/ci.yml/badge.svg?branch=main" alt="WebPatch safety checks on main"></a>
  <a href="#roadmap"><img src="assets/readme/preview-badge.svg" alt="0.1.0 · development"></a>
  <a href="LICENSE"><img src="assets/readme/license-badge.svg" alt="License: Apache-2.0"></a>
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> · <a href="#cli-preview">Preview</a> · <a href="docs/cli.md">Docs</a> · <a href="README.zh-CN.md">简体中文</a>
</p>

# WebPatch

**Evidence before action.** A conservative CLI for PHP runtime security: discover local installations, compare package versions with vendor advisories, and prepare reviewable repair plans.

**0.1.0 is a development preview.** Scans remain read-only; explicit service preparation can restart declared services after exact plan-hash confirmation. Package repair is still disabled. The bundled rules focus on PHP2Shell (`CVE-2026-109618` / `CVE-2026-109619`); a matching package version never means a safe running service.

## Why WebPatch

The PHP in your shell may not be the PHP serving your site. Distribution backports can fix an older version, while a running process can still hold an old image.

WebPatch connects **packages, processes, services and local evidence**. It keeps version assessments, file identity and runtime safety separate, and makes missing proof visible as `UNKNOWN`.

## Quick Start

On a target Linux system, use **Git and Python 3.10+ with `venv` and `pip` available**. Install from this repository into a virtual environment; the runtime has no third-party Python dependencies.

```sh
git clone https://github.com/ninex98/webpatch.git
cd webpatch
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/webpatch scan
```

No root is required to scan. Restricted reads become coverage gaps. Scan exits **1** for potentially affected packages or **2** for unknown/incomplete coverage; neither means a successful safety check.

Export evidence and prepare a plan:

```sh
.venv/bin/webpatch scan --format json > scan.json
.venv/bin/webpatch plan --dry-run --format json > reviewed-plan.json
.venv/bin/webpatch verify-plan reviewed-plan.json --format json
```

`plan` and `verify-plan` return **4** in this preview. Every plan is `BLOCKED` with `executable=false`; even a successful APT simulation does not authorize changes. See the [CLI reference](docs/cli.md) for exit codes, package-cache verification and local `.deb` builds. There is no published APT repository or GitHub Release installation path yet.

## CLI Preview

<p align="center">
  <picture>
    <source media="(max-width: 600px)" srcset="assets/readme/terminal-mobile.svg">
    <img src="assets/readme/terminal.svg" alt="Actual Ubuntu 24.04 container output: scope is container, runtime safety is UNKNOWN, the plan is BLOCKED, and apply refuses execution." width="100%">
  </picture>
</p>

Captured from the installed CLI in an isolated **Ubuntu 24.04 / arm64 container** on **2026-10-22**. Selected output is shown verbatim with visual line wrapping; this container reports `APT dry-run: NOT_RUN`. Styling is an illustration of the terminal, not a built-in TUI. [Full text and capture details](assets/readme/README.md).

The current workflow is **discover → assess → review a blocked repair plan**. Deployment reconciliation, explicit application probes and confirmed service preparation are documented in the [phase-three interfaces](docs/phase-3.md). Package execution and post-repair verification remain under development.

## Key Features

- **Local runtime discovery.** Correlates dpkg packages, process identities, namespaces, systemd units, FPM pools and static web handlers. Reports unresolved relationships.
- **Vendor-aware assessments.** Uses distribution-specific rules and `dpkg --compare-versions`, respecting backported fixes instead of comparing upstream version strings.
- **Ubuntu archive identity checks.** Verifies existing InRelease signatures, Packages digests, cached `.deb` archives and supported runtime files for supported official sources. Missing evidence stays unknown.
- **Real APT simulation.** Plans exact, authenticated Ubuntu candidates on the same PHP branch; reports dependency changes, possible service interruptions and blockers without installing packages.
- **Reviewable evidence.** JSON reports, input digests, expiring plans and `verify-plan` drift checks. Saved plan data is never executed as commands.

## Compatibility

Capabilities describe the current code, not a guarantee of complete discovery. **Automatic repair is unavailable in every environment.**

| Environment | Available now | Boundary / validation |
| :--- | :--- | :--- |
| Ubuntu 22.04 / 24.04, official APT PHP | Discovery, vendor comparison, archive identity, host APT simulation | Direct official sources only; FPM and mod_php in hosted VM CI |
| Debian 12 / 13, official PHP packages | Read-only discovery and vendor comparison | No archive authentication or repair planning; Debian 12 Docker + fixtures, Debian 13 fixtures only |
| Inside Ubuntu / Debian Docker containers | Inventory of the current container; rebuild recommendations | No in-place repair or APT simulation; Docker CI: Ubuntu 22.04 / 24.04, Debian 12 |
| Docker / containerd observed from a host | Process, namespace and common socket hints | No daemon access, image scanning or fleet enumeration |
| PPA / Sury, mixed sources, ESM, unsupported mirrors | Source audit, readable inventory and blockers | Unsupported trust paths; no automatic repair |
| Custom builds, `/usr/local`, `/opt/php`, BaoTa | Common path and process hints | Patch status unknown; arbitrary install paths are not exhaustively discovered |
| CGI, FrankenPHP, LiteSpeed, PHP built-in server | Package or process hints where observable | Runtime safety unknown; no dedicated repair support |
| Other OSes, hidden PIDs, restricted permissions | Readable observations and coverage gaps | No supported repair path; macOS / Windows are not validated scan targets |

## Security by Design

**Observe without changing the target.** Scans do not execute PHP, send HTTP requests, contact container daemons, refresh APT indexes, install packages or restart services. APT simulation uses isolated temporary configuration; system hooks are not executed and remain blockers.

**Use dated, attributable rules.** The [bundled rules](src/webpatch/data/php2shell.json) record official PHP, Ubuntu and Debian sources, a revision, review time and expiry. Reviewed **2026-10-22**, valid until **2026-10-29 00:00 UTC**. Expired rules or a clock before review yield `UNKNOWN`. There is no automatic online rule refresh; extending the date requires a new source review.

**Keep uncertainty actionable.** `MEETS_VENDOR_FIX` is a package-version comparison. `VERIFIED_LOCAL_ASSOCIATION` is a local relationship check. Neither proves loaded configuration, application routing or health. All reports retain `safe=false`; unknown evidence blocks automatic repair. Digests are not remote attestation or proof against a compromised root account.

**Require review before future execution.** Plans bind rules, scope and observed state, expire within 30 minutes, and can be checked for drift. Removal, downgrade, new dependencies, cross-branch changes and unapproved dependency changes block the automatic path. `apply` always refuses; there is no `--yes` bypass. Plan-hash confirmation, execution, post-repair checks and failure auditing are future gates; automatic rollback is not promised.

## Documentation

| Resource | What you will find |
| :--- | :--- |
| [CLI reference](docs/cli.md) | Commands, exit codes, report semantics and local packaging |
| [Architecture and staged design](docs/design.md) (中文) | Component boundaries, threat assumptions and acceptance gates |
| [Engineering evidence](evidence/phase-2c/README.md) (中文 / English) | Recorded APT simulation results, failures and accepted CI artifacts |
| [CI workflow](.github/workflows/ci.yml) · [Live runs](https://github.com/ninex98/webpatch/actions) | Python fixtures, three container environments and four Ubuntu VM combinations |
| [Visual assets and transcript](assets/readme/README.md) | Editable SVG sources, capture provenance and accessible text |

Historical evidence applies to its recorded source revision. The CI badge tracks `main`; it is not a runtime safety or coverage claim.

## Roadmap

- **Available:** read-only inventory, local runtime associations, Ubuntu source and archive checks, APT simulation, immutable plans and drift verification.
- **Next gates:** complete runtime / loaded-configuration / application-route evidence, explicit plan-hash authorization, limited Ubuntu execution and post-repair verification in disposable VMs.
- **Later, separately validated:** Debian repair and additional runtime adapters such as Node.js. Container rebuild advice exists today; automated image rebuilding does not.

The [staged design](docs/design.md) defines the acceptance criteria. These are engineering directions, not release dates or current support promises.

## Contributing

Start with [CONTRIBUTING.md](CONTRIBUTING.md). New adapters need explicit capability boundaries, failure-path fixtures and real environment evidence. Development and installation tests use project virtual environments, disposable containers and GitHub-hosted VMs.

## License

[Apache License 2.0](LICENSE). The name and local SVG assets can be revised independently of the CLI; this presentation does not change the existing license or release policy.
